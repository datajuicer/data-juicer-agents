# -*- coding: utf-8 -*-
import os
import copy
import json
import asyncio
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

from agentscope_runtime.engine.services.session_history import (
    InMemorySessionHistoryService,
)
from agentscope_runtime.engine.schemas.session import Session
from agentscope_runtime.engine.schemas.agent_schemas import Message

from op_manager.dj_op_retriever import DJOperatorRetriever
from session_logger import SessionLogger

from agentscope.tool import Toolkit
from agentscope.agent import ReActAgent
from agentscope.mcp import StdIOStatefulClient

data_juicer_repo_url = "https://github.com/datajuicer/{repo_name}/blob/main/"
data_juicer_doc_url = "https://datajuicer.github.io/{repo_name}/"

DEFAULT_DJ_HOME_PATH = Path.cwd() / "data-juicer-home"
DJ_HOME_PATH = Path(os.getenv("DJ_HOME_PATH") or DEFAULT_DJ_HOME_PATH)


class TTLInMemorySessionHistoryService(InMemorySessionHistoryService):
    def __init__(
        self, ttl_seconds: int = 3600, cleanup_interval: int = 60, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._ttl_seconds = ttl_seconds
        self._cleanup_interval = cleanup_interval

        self._last_access: Dict[str, Dict[str, float]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._ttl_lock = asyncio.Lock()

    def _touch(self, user_id: str, session_id: str) -> None:
        self._last_access.setdefault(user_id, {})[session_id] = time.time()

    async def start(self) -> None:
        await super().start()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        async with self._ttl_lock:
            self._last_access.clear()

        await super().stop()

    async def _cleanup_loop(self) -> None:
        try:
            while await self.health():
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_once()
        except asyncio.CancelledError:
            return

    async def _cleanup_once(self) -> None:
        now = time.time()
        expired: List[tuple[str, str]] = []

        async with self._ttl_lock:
            for user_id, m in list(self._last_access.items()):
                for session_id, ts in list(m.items()):
                    if now - ts > self._ttl_seconds:
                        expired.append((user_id, session_id))
                        del m[session_id]
                if not m:
                    del self._last_access[user_id]

        for user_id, session_id in expired:
            try:
                await super().delete_session(user_id, session_id)
            except Exception as e:
                print(
                    f"Failed to delete expired session {session_id} for user {user_id}: {e}"
                )

    async def create_session(
        self, user_id: str, session_id: Optional[str] = None
    ) -> Session:
        s = await super().create_session(user_id, session_id=session_id)
        async with self._ttl_lock:
            self._touch(user_id, s.id)
        return s

    async def get_session(self, user_id: str, session_id: str) -> Optional[Session]:
        s = await super().get_session(user_id, session_id)
        if s is not None:
            async with self._ttl_lock:
                self._touch(user_id, session_id)
        return s

    async def append_message(
        self,
        session: Session,
        message: Union[Message, List[Message], Dict[str, Any], List[Dict[str, Any]]],
    ) -> None:
        await super().append_message(session, message)
        async with self._ttl_lock:
            self._touch(session.user_id, session.id)

    async def delete_session(self, user_id: str, session_id: str) -> None:
        async with self._ttl_lock:
            if user_id in self._last_access:
                self._last_access[user_id].pop(session_id, None)
                if not self._last_access[user_id]:
                    self._last_access.pop(user_id, None)
        await super().delete_session(user_id, session_id)


def split_first_dir(path):
    try:
        p = Path(path)
        parts = list(p.parts)
        if len(parts) > 1:
            return parts[0], str(Path(*parts[1:]))
        else:
            return None, path
    except Exception:
        return None, path


async def file_tracking_pre_print_hook(
    self: "ReActAgent",
    kwargs: dict[str, Any],
) -> dict[str, Any] | None:
    """
    The statistics file is accessed and appended to the last message.
    Only tracks files from successful tool executions.
    Also logs a summary of accessed files into session logger if available.
    """
    try:
        if not kwargs.get("last", False):
            return None

        msg = kwargs["msg"]

        if isinstance(msg.content, str):
            return None
        if isinstance(msg.content, list):
            for block in msg.content:
                if block.get("type") != "text":
                    return None

        accessed_files = set()

        target_tools = {
            "view_text_file",
            "read_file",
            "get_symbols_overview",
            "get_operator_details",
        }

        history = await self.memory.get_memory()

        tool_id_to_file = {}
        tool_id_to_success = {}

        for message in reversed(history):
            if getattr(message, "role", None) == "user":
                break

            content = getattr(message, "content", None)

            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue

                    # 1. Record information of all tool_use blocks
                    if block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        tool_id = block.get("id", "")

                        if any(t in tool_name.lower() for t in target_tools):
                            inputs = block.get("input", {})

                            if isinstance(inputs, str):
                                try:
                                    inputs = json.loads(inputs)
                                except json.JSONDecodeError:
                                    continue

                            if isinstance(inputs, dict):
                                for key in [
                                    "relative_path",
                                    "operator_name",
                                ]:
                                    val = inputs.get(key)
                                    if val and isinstance(val, str):
                                        tool_id_to_file[tool_id] = val

                    # 2. Check the tool_result block to determine if execution is successful
                    elif block.get("type") == "tool_result":
                        tool_use_id = block.get("id", "")
                        output = block.get("output", [])

                        # Determine whether it is successful: check whether there is an error message in output
                        is_success = True
                        if isinstance(output, list):
                            for item in output:
                                if isinstance(item, dict):
                                    text = item.get("text", "")
                                    if "Error executing tool" in text:
                                        is_success = False
                                        break

                        tool_id_to_success[tool_use_id] = is_success

        # 3. Add only successful files
        for tool_id, file_path in tool_id_to_file.items():
            if tool_id_to_success.get(tool_id, False):
                accessed_files.add(file_path)

        if accessed_files:
            file_list = []
            for f in accessed_files:
                repo_name, f = split_first_dir(f)
                if f.endswith("_ZH.md"):
                    file_list.append(
                        (
                            data_juicer_doc_url.format(repo_name=repo_name)
                            + "zh_CN/main/"
                            + f.replace(".md", ".html"),
                            f,
                        )
                    )
                elif f.endswith(".md"):
                    file_list.append(
                        (
                            data_juicer_doc_url.format(repo_name=repo_name)
                            + "en/main/"
                            + f.replace(".md", ".html"),
                            f,
                        )
                    )
                elif "." not in f and f.split("_")[-1] in [
                    "aggregator",
                    "deduplicator",
                    "filter",
                    "mapper",
                    "formatter",
                    "grouper",
                    "selector",
                    "op",
                ]:
                    file_list.append(
                        (
                            data_juicer_doc_url.format(repo_name="data-juicer")
                            + "en/main/docs/operators/"
                            + f.split("_")[-1]
                            + "/"
                            + f
                            + ".html",
                            f,
                        )
                    )
                else:
                    file_list.append(
                        (data_juicer_repo_url.format(repo_name=repo_name) + f, f)
                    )

            summary_text = "\n\n# Reference: \n" + "\n".join(
                f"- [{n}]({f})." for f, n in file_list
            )

            # Modify current message content
            if isinstance(msg.content, list):
                for block in msg.content:
                    if block.get("type") == "text":
                        # Prevent duplicate additions (if retry mechanism is available)
                        if "Reference: " not in block["text"]:
                            block["text"] += summary_text
                            print(
                                f"📋 [Agent {self.name}] Append file summary: {len(file_list)} files."
                            )
                        break

            # Log summary to session logger if attached to agent
            if hasattr(self, "session_logger") and isinstance(
                self.session_logger, SessionLogger
            ):
                try:
                    await self.session_logger.log_event(
                        {
                            "type": "tool_summary",
                            "items": [
                                {"name": name, "url": url}
                                for url, name in file_list
                            ],
                            "file_count": len(file_list),
                        }
                    )
                except Exception as e:
                    print(f"⚠️ Warning: Error logging tool summary: {e}")

        return kwargs

    except Exception as e:
        print(f"⚠️ Warning: Error in file tracking hook: {e}")
        return None


class DeepCopyableToolkit(Toolkit):
    def __deepcopy__(self, memo):
        new_toolkit = DeepCopyableToolkit()

        for key, value in self.__dict__.items():
            try:
                new_toolkit.__dict__[key] = copy.deepcopy(value, memo)
            except (TypeError, AttributeError):
                # Fallback to shallow copy for non-deepcopyable objects
                if isinstance(value, (dict, list, set)):
                    new_toolkit.__dict__[key] = value.copy()
                else:
                    new_toolkit.__dict__[key] = value

        memo[id(self)] = new_toolkit
        return new_toolkit


toolkit = DeepCopyableToolkit()

# Initialize and register DJ Operator Retriever tools
dj_retriever = DJOperatorRetriever()
toolkit.register_tool_function(dj_retriever.search_operators)
toolkit.register_tool_function(dj_retriever.get_operator_details)

serena_command = [
    "uvx",
    "--with",
    "pyright[nodejs]",
    "--from",
    "git+https://github.com/oraios/serena",
    "serena",
    "start-mcp-server",
    "--project",
    str(DJ_HOME_PATH),
    "--mode",
    "planning",
]

mcp_clients = []

mcp_clients.append(
    StdIOStatefulClient(
        name="Serena",
        command=serena_command[0],
        args=serena_command[1:],
    )
)
