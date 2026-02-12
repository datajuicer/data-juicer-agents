# -*- coding: utf-8 -*-
import prompts

import os
import json
import importlib.util
import time
from typing import Optional, Tuple, Any, Callable, Awaitable

from session_logger import SessionLogger, ENABLE_SESSION_LOGGING

from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.agent import ReActAgent
from agentscope.message import Msg
from agentscope.tool import Toolkit
from agentscope.pipeline import stream_printing_messages
from agentscope.token import CharTokenCounter

from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from agent_helper import (
    TTLJSONSessionHistoryService,
    RedisSessionHistoryService,
    add_qa_tools,
    FeedbackRequest,
    JuicerAgentRequest,
    SessionLockManager,
)


# Session logging configuration - set DJ_COPILOT_ENABLE_LOGGING=false to disable
if not ENABLE_SESSION_LOGGING:
    print("ℹ️ Session logging disabled (DJ_COPILOT_ENABLE_LOGGING=false)")
else:
    print("✅ Session logging enabled")

# Session-level locks to ensure requests for the same session are processed sequentially
# This prevents state corruption and message history issues in concurrent scenarios
session_lock_manager = SessionLockManager()

session_history_service = None

# Allow configuring FastAPI config file.
FASTAPI_CONFIG_PATH = os.getenv("FASTAPI_CONFIG_PATH", "")

fastapi_kwargs = {}
try:
    if FASTAPI_CONFIG_PATH and os.path.exists(FASTAPI_CONFIG_PATH):
        with open(FASTAPI_CONFIG_PATH, "r", encoding="utf-8") as f:
            fastapi_kwargs = json.load(f) or {}
        print(f"✅ Loaded FastAPI config from {FASTAPI_CONFIG_PATH}: {fastapi_kwargs}")
    elif FASTAPI_CONFIG_PATH:
        print(f"ℹ️  Config file not found at {FASTAPI_CONFIG_PATH}, using defaults.")
    else:
        print("ℹ️  FASTAPI_CONFIG_PATH not set, using defaults.")
except (json.JSONDecodeError, IOError) as e:
    print(f"⚠️  Failed to load or parse FastAPI config from {FASTAPI_CONFIG_PATH}: {e}")
    fastapi_kwargs = {}


app = AgentApp(
    agent_name="Juicer",
    **fastapi_kwargs,
)

# Initialize services conditionally based on session store type
SESSION_STORE_TYPE = os.getenv("SESSION_STORE_TYPE", "json")
print(f"✅ SESSION_STORE_TYPE: {SESSION_STORE_TYPE}")

if SESSION_STORE_TYPE not in ["json", "redis"]:
    raise ValueError(f"❌ Invalid SESSION_STORE_TYPE: {SESSION_STORE_TYPE}")

model_params = {
    "model_name": "qwen3-max-2026-01-23",
    "api_key": os.getenv("DASHSCOPE_API_KEY"),
    "stream": True,
    "enable_thinking": False,
}
# formatter is used to format the messages for the model
# MAX_TOKENS specifies the maximum token count (default: 200000)
# CharTokenCounter counts characters, and for mixed CHN & ENG text,
# approximately 3 characters ≈ 1 token, so we multiply by 3 when passing to formatter
max_tokens_config = int(os.getenv("MAX_TOKENS", "200000"))
formatter = DashScopeChatFormatter(
    token_counter=CharTokenCounter(),
    max_tokens=max_tokens_config * 3,  # Convert token count to character count (×3)
)
toolkit = Toolkit()


# Safe Check Dynamic Import
async def _dummy_check_user_input_safety(
    user_input: Any, user_id: str
) -> Tuple[bool, Optional[Msg]]:
    """
    Dummy function used when safe check module is not available.
    Defaults to allowing all inputs through.
    """
    return True, None


async def _load_safe_check_handler():
    """
    Dynamically load safe check handler.
    Load module based on environment variable SAFE_CHECK_HANDLER_PATH,
    return dummy function if not set or loading fails.
    """
    safe_check_path = os.getenv("SAFE_CHECK_HANDLER_PATH")

    if not safe_check_path:
        print(
            "ℹ️  SAFE_CHECK_HANDLER_PATH not set, using dummy safe check (all inputs allowed)"
        )
        return _dummy_check_user_input_safety

    try:
        # If path is a file path (ends with .py)
        if safe_check_path.endswith(".py") and os.path.exists(safe_check_path):
            spec = importlib.util.spec_from_file_location(
                "safe_check_handler", safe_check_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load spec from {safe_check_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            # Import as module name
            module = importlib.import_module(safe_check_path)

        if hasattr(module, "check_user_input_safety"):
            check_func = module.check_user_input_safety
            print(f"✅ Loaded safe check handler from: {safe_check_path}")
            return check_func
        else:
            raise AttributeError(
                f"Module {safe_check_path} does not have 'check_user_input_safety'"
            )

    except Exception as e:
        print(f"⚠️  Failed to load safe check handler from {safe_check_path}: {e}")
        print("ℹ️  Falling back to dummy safe check (all inputs allowed)")
        return _dummy_check_user_input_safety


# Global variable to store check function
_check_user_input_safety_func: Optional[
    Callable[[Any, str], Awaitable[Tuple[bool, Optional[Msg]]]]
] = None


def _extract_user_text(user_input: Any) -> str:
    """Extract plain text from user message for logging."""
    user_text = ""

    if hasattr(user_input, "content"):
        content = user_input.content
        if isinstance(content, list):
            for item in content:
                if getattr(item, "type", None) == "text":
                    user_text += getattr(item, "text", "")
                elif isinstance(item, dict) and item.get("type") == "text":
                    user_text += item.get("text", "")
        elif isinstance(content, str):
            user_text = content
    elif isinstance(user_input, str):
        user_text = user_input
    elif isinstance(user_input, dict):
        user_text = user_input.get("content", "")

    return user_text


@app.init
async def init_resources(self):
    global _check_user_input_safety_func, session_history_service
    print("🚀 Starting resources...")

    # Initialize safe check handler
    print("🚀 Initializing safe check handler...")
    _check_user_input_safety_func = await _load_safe_check_handler()

    # Initialize session
    print(f"🚀 Initializing SessionHistoryService type={SESSION_STORE_TYPE}...")
    if SESSION_STORE_TYPE == "json":
        session_history_service = TTLJSONSessionHistoryService(
            session_store_type=SESSION_STORE_TYPE,
            ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "21600")),
            cleanup_interval=int(os.getenv("SESSION_CLEANUP_INTERVAL", "1800")),
            session_cleanup_callback=session_lock_manager.cleanup_session_lock,
        )
        await session_history_service.start()
        print(
            f"✅ Initialized JSONSessionHistoryService with TTL: {int(os.getenv('SESSION_TTL_SECONDS', '21600'))} seconds"
        )
    elif SESSION_STORE_TYPE == "redis":
        session_history_service = RedisSessionHistoryService(
            session_store_type=SESSION_STORE_TYPE,
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            redis_password=os.getenv("REDIS_PASSWORD", None),
            redis_max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
        )
        await session_history_service.start()
        print(
            f"✅ Initialized RedisSessionHistoryService (TTL handled by Redis server)"
        )
    else:
        raise ValueError(f"❌ Invalid SESSION_STORE_TYPE: {SESSION_STORE_TYPE}")

    await add_qa_tools(toolkit)


@app.shutdown
async def cleanup_resources(self):
    global session_history_service
    if session_history_service:
        await session_history_service.stop()


@app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: JuicerAgentRequest = None,
    **kwargs,
):
    """
    Process query with session-level locking to prevent concurrent state corruption.
    Ensures requests for the same session are processed sequentially.
    """
    global _check_user_input_safety_func, session_history_service
    session_id = request.session_id
    _model_params = request.model_params or {}
    user_id = request.user_id or session_id

    # Get session lock to ensure sequential processing for the same session
    session_lock = await session_lock_manager.get_session_lock(session_id)

    # Acquire lock for the entire processing flow
    async with session_lock:
        # Timing metrics
        start_time = time.perf_counter()
        first_token_time: Optional[float] = None

        # Initialize session logger (per query)
        logger = SessionLogger(session_id=session_id, user_id=user_id)

        # Log metadata and user input
        user_input = msgs[-1] if msgs else None
        user_text = _extract_user_text(user_input) if user_input is not None else ""
        await logger.log_event(
            {
                "type": "user_input",
                "content": user_text,
            }
        )

        # Safe Check
        is_safe, error_msg = await _check_user_input_safety_func(msgs[-1], user_id)
        if not is_safe:
            yield error_msg, True
            return

        # Set memory using unified interface
        # For JSON mode, create an InMemoryMemory instance
        memory = session_history_service.create_memory(
            user_id=user_id, session_id=session_id
        )

        model_params.update(_model_params)

        # Model Configuration
        model = DashScopeChatModel(**model_params)

        # Build agent configuration
        agent_config = {
            "name": "Juicer",
            "formatter": formatter,
            "model": model,
            "sys_prompt": prompts.QA,
            "toolkit": toolkit,
            "parallel_tool_calls": True,
            "memory": memory,
        }

        try:
            agent = ReActAgent(**agent_config)
        except Exception as e:
            print(f"[{session_id}] ❌ Error creating agent: {str(e)}")
            raise

        # Attach session logger to agent so hooks can log tool usage
        agent.session_logger = logger
        agent.set_console_output_enabled(enabled=False)

        # Load session state (for JSON mode only; Redis mode doesn't need this check as load_session_state is a no-op)
        try:
            await session_history_service.load_session_state(
                session_id=session_id, agent=agent, user_id=user_id
            )
        except Exception as e:
            print(f"[{session_id}] ❌ Error loading session state: {str(e)}")
            raise

        final_response = ""
        processing_completed = False

        try:
            async for msg, last in stream_printing_messages(
                agents=[agent],
                coroutine_task=agent(msgs[-1]),
            ):
                if (
                    first_token_time is None
                    and hasattr(msg, "content")
                    and isinstance(msg.content, list)
                ):
                    for item in msg.content:
                        if (
                            item.get("type", None) == "text"
                            and item.get("text", "").strip()
                        ):
                            first_token_time = time.perf_counter()
                            break

                # Log every chunk where last=True for trace
                if last:
                    if hasattr(msg, "content") and isinstance(msg.content, list):
                        for item in msg.content:
                            if (
                                item.get("type", None) == "text"
                                and item.get("text", "").strip()
                            ):
                                final_response = item["text"]
                    await logger.log_event(
                        {
                            "type": "last_chunk",
                            "msg": str(msg),
                        }
                    )

                yield msg, last

            # Mark processing as completed if we reached here
            processing_completed = True

        except GeneratorExit:
            # Client disconnected during streaming - still save state
            print(f"[{session_id}] ⚠️  Client disconnected during streaming")
            processing_completed = False
            raise  # Re-raise GeneratorExit
        except Exception as e:
            # Log error but continue to save state
            print(f"[{session_id}] ❌ Error during query processing: {str(e)}")
            processing_completed = False
            raise
        finally:
            # Save session state
            # Always save state, even if there was an error or client disconnect
            # This ensures state consistency and prevents tool_calls without responses
            try:
                await session_history_service.save_session_state(
                    session_id=session_id, agent=agent, user_id=user_id
                )
            except Exception as e:
                print(f"[{session_id}] ❌ Error saving state: {str(e)}")

            # Cleanup memory resources (e.g., close Redis connections)
            try:
                await session_history_service.cleanup_memory(memory)
            except Exception as e:
                print(f"[{session_id}] ❌ Error cleaning up memory: {str(e)}")

        # Only log final response if processing completed successfully
        if processing_completed:
            # Compute timing metrics and log final response
            complete_time = time.perf_counter()
            first_token_duration = (
                first_token_time - start_time if first_token_time is not None else None
            )
            total_duration = complete_time - start_time

            await logger.log_event(
                {
                    "type": "final_response",
                    "content": final_response,
                    "first_token_duration": first_token_duration,
                    "total_duration": total_duration,
                }
            )


@app.endpoint("/memory")
async def get_memory(request: AgentRequest):
    """Retrieve conversation history for a session."""
    global session_history_service
    session_id = request.session_id
    user_id = request.user_id or session_id
    print(f"[{user_id}] 📥 Fetching memory for session: {session_id}")

    try:
        memory_content = await session_history_service.get_memory(session_id, user_id)

        messages = []
        for msg in memory_content:
            content_text = ""
            if hasattr(msg, "content"):
                if isinstance(msg.content, list):
                    for item in msg.content:
                        if item.get("type", None) == "text":
                            content_text += item.get("text", "")
                elif isinstance(msg.content, str):
                    content_text = msg.content

            if content_text.strip() and hasattr(msg, "role"):
                messages.append(
                    {
                        "role": msg.role,
                        "content": content_text.strip(),
                        "id": msg.id,
                        "metadata": msg,
                    }
                )

        response = {"messages": messages}
        print(f"[{user_id}] 📤 Returning {len(messages)} messages")
        return response
    except Exception as e:
        print(f"[{user_id}] ❌ Error fetching memory: {str(e)}")
        return {"messages": []}


@app.endpoint("/clear")
async def clear_memory(request: AgentRequest):
    """Clear conversation history for a session."""
    global session_history_service
    session_id = request.session_id
    user_id = request.user_id or session_id
    print(f"[{user_id}] 🧹 Clearing memory for session: {session_id}")

    try:
        await session_history_service.delete_session(
            session_id=session_id, user_id=user_id
        )

        # Clean up session lock regardless of store type
        await session_lock_manager.cleanup_session_lock(session_id=session_id)
        return {"status": "ok"}
    except Exception as e:
        print(f"[{user_id}] ❌ Error clearing memory: {str(e)}")
        return {"status": "error", "message": str(e)}


@app.endpoint("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit user feedback (like/dislike) for a message."""
    session_id = request.session_id
    user_id = request.user_id or session_id

    # Extract feedback data from request
    feedback_type = request.data.feedback_type  # "like" or "dislike"
    message_id = request.data.message_id
    comment = request.data.comment  # Optional user comment

    print(f"[{user_id}] Received feedback: {feedback_type} for message {message_id}")

    if not message_id:
        print(f"[{user_id}] Missing message_id")
        return {"status": "error", "message": "message_id is required"}

    # Initialize session logger to record feedback
    logger = SessionLogger(session_id=session_id, user_id=user_id)

    # Log the feedback event
    await logger.log_event(
        {
            "type": "user_feedback",
            "feedback_type": feedback_type,
            "message_id": message_id,
            "comment": comment,
        }
    )

    print(f"[{user_id}] Feedback logged successfully")
    return {"status": "ok", "message": "Feedback recorded successfully"}


if __name__ == "__main__":
    host = os.getenv("DJ_COPILOT_SERVICE_HOST", "127.0.0.1")
    app.run(host=host, port=8080)
