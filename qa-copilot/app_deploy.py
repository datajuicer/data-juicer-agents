# -*- coding: utf-8 -*-
import shutil
import prompts
from copy import deepcopy
from pathlib import Path

from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.agent import ReActAgent

from agent_helper import (
    toolkit,
    mcp_clients,
    file_tracking_pre_print_hook,
    TTLInMemorySessionHistoryService,
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
import oyaml as yaml
import os

DEFAULT_DJ_HOME_PATH = Path.cwd() / "data-juicer-home"
DJ_HOME_PATH = Path(os.getenv("DJ_HOME_PATH") or DEFAULT_DJ_HOME_PATH)
FILE_PATH = Path(__file__).parent
SOURCE_SERENA_PROJECT_YML = FILE_PATH / "config" / "project.yml"
SOURCE_SERENA_CONFIG = FILE_PATH / "config" / "serena_config.yml"

# Database configuration - set DISABLE_DATABASE=1 to disable all backend databases
DISABLE_DATABASE = os.getenv("DISABLE_DATABASE", "false") == "1"

app = AgentApp(
    agent_name="Juicer",
)

# Initialize services conditionally based on database configuration
if DISABLE_DATABASE:
    print("⚠️  Database disabled - running in memory-only mode")
    long_memory_service = None
    session_history_service = TTLInMemorySessionHistoryService(
        ttl_seconds=60 * 60 * 12, cleanup_interval=60 * 60 * 6
    )
else:
    long_memory_service = RedisMemoryService()
    session_history_service = RedisSessionHistoryService()

state_service = InMemoryStateService()
model = DashScopeChatModel(
    # "qwen-plus-2025-07-14",
    "qwen-max",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    stream=True,
    enable_thinking=False,
)
formatter = DashScopeChatFormatter()


def append_project_to_serena(new_project_path, serena_cfg_path):
    with open(SOURCE_SERENA_CONFIG, "r") as file:
        data = yaml.safe_load(file)

    if "projects" not in data:
        data["projects"] = []

    if str(new_project_path) not in data["projects"]:
        data["projects"].append(str(new_project_path))
    else:
        return

    with open(serena_cfg_path, "w") as file:
        yaml.dump(data, file, default_flow_style=False, sort_keys=False)

    print(f"Successfully added project path: {new_project_path}")


@app.init
async def init_resources(self):
    print("🚀 Starting resources...")
    await state_service.start()
    await session_history_service.start()
    if not DISABLE_DATABASE:
        print("🚀 Connecting to Redis...")
        await long_memory_service.start()
    else:
        print("ℹ️  Skipping database connections (DISABLE_DATABASE=1)")

    if not DJ_HOME_PATH.exists():
        raise RuntimeError(f"data-juicer not found at {DJ_HOME_PATH}")

    project_serena_dir = DJ_HOME_PATH / ".serena"
    project_serena_dir.mkdir(parents=True, exist_ok=True)

    if SOURCE_SERENA_PROJECT_YML.exists():
        try:
            shutil.copy(
                SOURCE_SERENA_PROJECT_YML,
                project_serena_dir / "project.yml",
            )
            print("✅ Successfully copied .serena configuration to data-juicer")
        except Exception as e:
            print(f"⚠️ Failed to copy .serena configuration: {e}")
    else:
        print(f"⚠️ {SOURCE_SERENA_PROJECT_YML} not found")

    home_serena_config = Path.home() / ".serena" / "serena_config.yml"

    if SOURCE_SERENA_CONFIG.exists():
        append_project_to_serena(DJ_HOME_PATH, home_serena_config)

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
                    "initial_instructions",
                ],
            )


@app.shutdown
async def cleanup_resources(self):
    await state_service.stop()
    await session_history_service.stop()

    if not DISABLE_DATABASE:
        print("🛑 Shutting down Redis...")
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

    # Build agent configuration
    agent_config = {
        "name": "Juicer",
        "formatter": formatter,
        "model": model,
        "sys_prompt": prompts.QA,
        "toolkit": _toolkit,
        "parallel_tool_calls": True,
        "memory": AgentScopeSessionHistoryMemory(
            service=session_history_service,
            session_id=session_id,
            user_id=user_id,
        ),
    }

    # Add memory services only if database is enabled
    if not DISABLE_DATABASE:
        agent_config["long_term_memory"] = AgentScopeLongTermMemory(
            service=long_memory_service,
            session_id=session_id,
            user_id=user_id,
        )

    agent = ReActAgent(**agent_config)
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

    # Save final state
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
