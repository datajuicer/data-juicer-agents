# -*- coding: utf-8 -*-
import asyncio
from typing import Optional
from pydantic import BaseModel
import os
import subprocess
import shutil
import prompts
from copy import deepcopy

from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.agent import ReActAgent

from agent_helper import (
    toolkit,
    mcp_clients,
    file_tracking_pre_print_hook,
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
from agentscope_runtime.engine.services.memory.redis_memory_service import (
    RedisMemoryService,
)
from agentscope_runtime.engine.services.session_history import (
    RedisSessionHistoryService,
)

DEFAULT_DATA_JUICER_PATH = os.path.join(os.getcwd(), "data-juicer")
DATA_JUICER_PATH = os.getenv("DATA_JUICER_PATH") or DEFAULT_DATA_JUICER_PATH

app = AgentApp(
    agent_name="Juicer",
)


# Initialize services
long_memory_service = RedisMemoryService()
session_history_service = RedisSessionHistoryService()
state_service = InMemoryStateService()
model = DashScopeChatModel(
    "qwen-max",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    stream=True,
)
formatter = DashScopeChatFormatter()


class FeedbackRequest(BaseModel):
    message_id: str
    feedback: str  # 'like' or 'dislike'
    session_id: str
    user_id: str = ""  # Default to empty string for compatibility
    timestamp: Optional[int] = None


@app.init
async def init_resources(self):
    print("🚀 Starting resources...")
    await state_service.start()
    print("🚀 Connecting to Redis...")
    await session_history_service.start()
    await long_memory_service.start()

    if not os.path.exists(DATA_JUICER_PATH):
        print("Cloning data-juicer repository...")
        try:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "https://github.com/datajuicer/data-juicer.git",
                    f"{DATA_JUICER_PATH}",
                ],
                check=True,
            )
            print("✅ Successfully cloned data-juicer repository")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to clone data-juicer repository: {e}")
        print("Cloning data-juicer-hub repository...")
        try:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "https://github.com/datajuicer/data-juicer-hub.git",
                    f"{DATA_JUICER_PATH}/data-juicer-hub",
                ],
                check=True,
            )
            print("✅ Successfully cloned data-juicer-hub repository")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to clone data-juicer-hub repository: {e}")
    else:
        print("📁 data-juicer directory already exists")

    serena_config_dir = os.path.join(DATA_JUICER_PATH, ".serena")
    os.makedirs(serena_config_dir, exist_ok=True)
    source_serena_config = os.path.join(
        os.path.dirname(__file__), "config", "project.yml"
    )
    if os.path.exists(source_serena_config):
        try:
            shutil.copy(source_serena_config, os.path.join(serena_config_dir, "project.yml"))
            print("✅ Successfully copied .serena configuration to data-juicer")
        except Exception as e:
            print(f"⚠️ Failed to copy .serena configuration: {e}")
    else:
        print(f"⚠️ {source_serena_config} not found")

    if mcp_clients:
        for mcp_client in mcp_clients:
            print("🚀 Connecting to MCP server...")
            await mcp_client.connect()
            await toolkit.register_mcp_client(
                mcp_client,
                disable_funcs=[
                    "activate_project",
                    "create_text_file",
                    "delete_lines",
                    "delete_memory",
                    "execute_shell_command",
                    "insert_after_symbol",
                    "insert_at_line",
                    "insert_before_symbol",
                    "onboarding",
                    "remove_project",
                    "replace_lines",
                    "replace_symbol_body",
                    "restart_language_server",
                    "switch_modes",
                    "write_memory",
                    "get_current_config",
                    "check_onboarding_performed",
                    "edit_memory",
                    "record_to_memory",
                    "retrieve_from_memory",
                    "rename_symbol",
                    "replace_content",
                    "initial_instructions"
                ],
            )


@app.shutdown
async def cleanup_resources(self):
    await state_service.stop()

    print("🛑 Shutting down Redis...")
    await session_history_service.stop()
    await long_memory_service.stop()

    if mcp_clients:
        for mcp_client in mcp_clients:
            print("🛑 Disconnecting from MCP server...")
            await mcp_client.close()


@app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    session_id = request.session_id
    user_id = request.user_id

    state = await state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    _toolkit = deepcopy(toolkit)

    agent = ReActAgent(
        name="Juicer",
        formatter=formatter,
        model=model,
        sys_prompt=prompts.QA,
        toolkit=_toolkit,
        parallel_tool_calls=True,
        memory=AgentScopeSessionHistoryMemory(
            service=session_history_service,
            session_id=session_id,
            user_id=user_id,
        ),
        long_term_memory=AgentScopeLongTermMemory(
            service=long_memory_service,
            session_id=session_id,
            user_id=user_id,
        ),
    )
    agent.set_console_output_enabled(enabled=False)
    agent.register_instance_hook(
        hook_type="pre_print",
        hook_name="test_pre_print",
        hook=file_tracking_pre_print_hook,
    )

    if state:
        agent.load_state_dict(state)

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs[-1]),
    ):
        yield msg, last

    state = agent.state_dict()

    await state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )


@app.endpoint("/memory")
async def get_memory(request: AgentRequest):
    """Retrieve conversation history for a session."""
    session_id = request.session_id
    user_id = request.user_id
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
            messages.append({"role": msg.role, "content": content_text.strip()})

    response = {"messages": messages}
    print(f"[{user_id}] 📤 Returning {len(messages)} messages")
    return response


@app.endpoint("/clear")
async def clear_memory(request: AgentRequest):
    """Clear conversation history for a session."""
    session_id = request.session_id
    user_id = request.user_id
    print(f"[{user_id}] 🧹 Clearing memory for session: {session_id}")
    await session_history_service.delete_session(user_id, session_id)
    return {"status": "ok"}


@app.endpoint("/feedback")
async def handle_feedback(request: FeedbackRequest):
    """Record user feedback (like/dislike) for a message."""
    message_id = request.message_id
    session_id = request.session_id
    user_id = request.user_id
    feedback_data = {"type": request.feedback, "timestamp": request.timestamp}

    try:
        # Update feedback in Redis memory
        success = await session_history_service.update_message_feedback(
            user_id=user_id,
            msg_id=message_id,
            feedback=feedback_data,
            session_id=session_id,
        )

        if success:
            return {
                "status": "ok",
                "message": "Feedback recorded successfully",
                "message_id": message_id,
            }
        else:
            return {
                "status": "error",
                "message": "Message not found",
                "message_id": message_id,
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to save feedback: {str(e)}",
            "message_id": message_id,
        }


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
