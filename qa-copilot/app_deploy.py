# -*- coding: utf-8 -*-
import prompts
from typing import Optional

import os
import importlib.util
import time
import asyncio
from typing import Optional, Tuple, Any, Callable, Awaitable

from session_logger import SessionLogger, ENABLE_SESSION_LOGGING

from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.agent import ReActAgent
from agentscope.message import Msg
from agentscope.tool import Toolkit

from agent_helper import (
    TTLInMemorySessionHistoryService,
    add_qa_tools,
    FeedbackRequest
)
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.adapters.agentscope.long_term_memory import (
    AgentScopeLongTermMemory,
)
from agentscope.pipeline import stream_printing_messages
from agentscope_runtime.adapters.agentscope.memory import (
    AgentScopeSessionHistoryMemory,
)
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)
from agentscope_runtime.engine.services.session_history import (
    RedisSessionHistoryService,
)

from agentscope_runtime.engine.services.memory.redis_memory_service import (
    RedisMemoryService,
)

# Database configuration - set DISABLE_DATABASE=1 to disable all backend databases
DISABLE_DATABASE = os.getenv("DISABLE_DATABASE", "false") == "1"

# Session logging configuration - set DJ_COPILOT_ENABLE_LOGGING=false to disable
if not ENABLE_SESSION_LOGGING:
    print("ℹ️  Session logging disabled (DJ_COPILOT_ENABLE_LOGGING=false)")
else:
    print("✅ Session logging enabled")

# ========== Session Lock Manager ==========
# Session-level locks to ensure requests for the same session are processed sequentially
# This prevents state corruption and message history issues in concurrent scenarios
_session_locks: dict[str, asyncio.Lock] = {}
_lock_manager_lock = asyncio.Lock()

async def get_session_lock(session_id: str) -> asyncio.Lock:
    """Get or create a lock for the given session ID"""
    async with _lock_manager_lock:
        if session_id not in _session_locks:
            _session_locks[session_id] = asyncio.Lock()
        return _session_locks[session_id]


async def cleanup_session_lock(session_id: str) -> None:
    """
    Remove the lock for a given session ID.
    This should be called when a session is deleted to prevent memory leaks.
    """
    async with _lock_manager_lock:
        if session_id in _session_locks:
            del _session_locks[session_id]

# ========== End Session Lock Manager ==========

app = AgentApp(
    agent_name="Juicer",
)

# Initialize services conditionally based on database configuration
if DISABLE_DATABASE:
    print("⚠️  Database disabled - running in memory-only mode")
    long_memory_service = None
    session_history_service = TTLInMemorySessionHistoryService(
        ttl_seconds=60 * 60 * 12, 
        cleanup_interval=60 * 60 * 6,
        session_cleanup_callback=cleanup_session_lock
    )
else:
    long_memory_service = RedisMemoryService()
    session_history_service = RedisSessionHistoryService()

state_service = InMemoryStateService()
model = DashScopeChatModel(
    # "qwen-max",
    "qwen3-max-preview",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    stream=True,
    enable_thinking=False,
)
formatter = DashScopeChatFormatter()
toolkit = Toolkit()


# ========== Safe Check Dynamic Import ==========
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

# ========== End Safe Check Dynamic Import ==========


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
    global _check_user_input_safety_func
    print("🚀 Starting resources...")

    # Initialize safe check handler
    _check_user_input_safety_func = await _load_safe_check_handler()

    await state_service.start()
    await session_history_service.start()
    if not DISABLE_DATABASE:
        print("🚀 Connecting to Redis...")
        await long_memory_service.start()
    else:
        print("ℹ️  Skipping database connections (DISABLE_DATABASE=1)")
    
    await add_qa_tools(toolkit)



@app.shutdown
async def cleanup_resources(self):
    await state_service.stop()
    await session_history_service.stop()

    if not DISABLE_DATABASE:
        print("🛑 Shutting down Redis...")
        await long_memory_service.stop()

@app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    """
    Process query with session-level locking to prevent concurrent state corruption.
    Ensures requests for the same session are processed sequentially.
    """
    global _check_user_input_safety_func
    session_id = request.session_id
    user_id = request.user_id or session_id

    # Get session lock to ensure sequential processing for the same session
    session_lock = await get_session_lock(session_id)
    
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

        # ========== Safe Check ==========
        is_safe, error_msg = await _check_user_input_safety_func(msgs[-1], user_id)
        if not is_safe:
            yield error_msg, True
            return
        # ========== End Safe Check ==========

        # Export state - protected by lock to prevent concurrent reads
        state = await state_service.export_state(
            session_id=session_id,
            user_id=user_id,
        )

        # Build agent configuration
        agent_config = {
            "name": "Juicer",
            "formatter": formatter,
            "model": model,
            "sys_prompt": prompts.QA,
            "toolkit": toolkit,
            "parallel_tool_calls": True,
            "memory": AgentScopeSessionHistoryMemory(
                service=session_history_service,
                session_id=session_id,
                user_id=user_id,
            ),}

        # Add memory services only if database is enabled
        if not DISABLE_DATABASE:
            agent_config["long_term_memory"] = AgentScopeLongTermMemory(
                service=long_memory_service,
                session_id=session_id,
                user_id=user_id,
            )

        agent = ReActAgent(**agent_config
            )
        # Attach session logger to agent so hooks can log tool usage
        agent.session_logger = logger
        agent.set_console_output_enabled(enabled=False)

        if state:
            agent.load_state_dict(state)

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
                        if item.get("type", None) == "text" and item.get("text", "").strip():
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
            # Always save state, even if there was an error or client disconnect
            # This ensures state consistency and prevents tool_calls without responses
            try:
                state = agent.state_dict()
                await state_service.save_state(
                    user_id=user_id,
                    session_id=session_id,
                    state=state,
                )
            except Exception as e:
                print(f"[{session_id}] ❌ Error saving state: {str(e)}")
            
            # Cleanup agent resources if available
            if hasattr(agent, 'cleanup'):
                try:
                    await agent.cleanup()
                except Exception as e:
                    print(f"[{session_id}] ❌ Error cleaning up agent: {str(e)}")

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
    session_id = request.session_id
    user_id = request.user_id or session_id
    print(f"[{user_id}] 📥 Fetching memory for session: {session_id}")

    memories = await session_history_service.get_session(user_id, session_id)
    messages = []

    for msg in memories.messages:
        content_text = ""
        if hasattr(msg, "content"):
            if isinstance(msg.content, list):
                for item in msg.content:
                    if getattr(item, "type", None) == "text":
                        content_text += getattr(item, "text", "")
            elif isinstance(msg.content, str):
                content_text = msg.content

        if content_text.strip() and hasattr(msg, "role"):
            messages.append(
                {
                    "role": msg.role,
                    "content": content_text.strip(),
                    "id": msg.metadata.get("original_id", msg.id),
                    "metadata": msg,
                }
            )

    response = {"messages": messages}
    print(f"[{user_id}] 📤 Returning {len(messages)} messages")
    return response


@app.endpoint("/clear")
async def clear_memory(request: AgentRequest):
    """Clear conversation history for a session."""
    session_id = request.session_id
    user_id = request.user_id or session_id
    print(f"[{user_id}] 🧹 Clearing memory for session: {session_id}")
    await session_history_service.delete_session(user_id, session_id)
    return {"status": "ok"}


@app.endpoint("/sessions")
async def get_sessions(request: AgentRequest):
    """Get all sessions for a user."""
    user_id = request.user_id
    print(f"[{user_id}] 📋 Fetching all sessions")

    try:
        sessions = await session_history_service.list_sessions(user_id)

        session_list = []
        for session in sessions:
            preview = "New Chat"
            if session and session.messages:
                first_msg = session.messages[0]
                if hasattr(first_msg, "content"):
                    if isinstance(first_msg.content, list):
                        for item in first_msg.content:
                            if getattr(item, "type", None) == "text":
                                preview = getattr(item, "text", "")[:50]
                                break
                    elif isinstance(first_msg.content, str):
                        preview = first_msg.content[:50]

            session_list.append(
                {
                    "session_id": session.id,
                    "preview": preview,
                    "created_at": (
                        session.created_at if hasattr(session, "created_at") else None
                    ),
                    "updated_at": (
                        session.updated_at if hasattr(session, "updated_at") else None
                    ),
                }
            )

        print(f"[{user_id}] 📤 Returning {len(session_list)} sessions")
        return {"sessions": session_list}

    except Exception as e:
        print(f"[{user_id}] ❌ Error fetching sessions: {str(e)}")
        return {"sessions": []}


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
