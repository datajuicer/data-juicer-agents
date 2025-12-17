# -*- coding: utf-8 -*-
import os
import copy
import json
import asyncio
import time
from typing import Optional, Dict, Any, List, Union

from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService
from agentscope_runtime.engine.schemas.session import Session
from agentscope_runtime.engine.schemas.agent_schemas import Message

from op_manager.dj_op_retriever import DJOperatorRetriever

from agentscope.tool import Toolkit
from agentscope.agent import ReActAgent
from agentscope.mcp import StdIOStatefulClient

data_juicer_repo_url = "https://github.com/datajuicer/data-juicer/blob/main/"
data_juicer_doc_url = "https://datajuicer.github.io/data-juicer/"

DATA_JUICER_PATH = os.getenv("DATA_JUICER_PATH", "/data-juicer")

class TTLInMemorySessionHistoryService(InMemorySessionHistoryService):
    def __init__(self, ttl_seconds: int = 3600, cleanup_interval: int = 60, *args, **kwargs):
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
                print(f"Failed to delete expired session {session_id} for user {user_id}: {e}")

    async def create_session(self, user_id: str, session_id: Optional[str] = None) -> Session:
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



async def file_tracking_pre_print_hook(
    self: "ReActAgent",
    kwargs: dict[str, Any],
) -> dict[str, Any] | None:
    """
    The statistics file is accessed and appended to the last message.
    """
    try:
        # 1. Logic is executed only on the last reply (last=True)
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

        # Define focused tool keywords
        target_tools = {
            "view_text_file",
            "read_file",
            "get_symbols_overview",
            "get_operator_details",
            # "find_symbol",
            # "find_referencing_symbols",
            # "search_for_pattern",
        }

        history = await self.memory.get_memory()

        # 3. Traverse all messages looking for tool_use
        for message in reversed(history):
            if getattr(message, "role", None) == "user":
                break

            content = getattr(message, "content", None)

            # Only deal with structures where content is a list
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = block.get("name", "")

                        # Hit File Reading Class Tool
                        if any(t in tool_name.lower() for t in target_tools):
                            inputs = block.get("input", {})

                            # Handling cases where inputs may be JSON strings
                            if isinstance(inputs, str):
                                try:
                                    inputs = json.loads(inputs)
                                except json.JSONDecodeError:
                                    continue

                            # Extract file path (try common parameter name)
                            if isinstance(inputs, dict):
                                for key in [
                                    "file_path",
                                    "filepath",
                                    "path",
                                    "filename",
                                    "relative_path",
                                    "operator_name",
                                ]:
                                    val = inputs.get(key)
                                    if val and isinstance(val, str):
                                        accessed_files.add(val)
                                        break

        # 4. If the file is found, splice it into msg's text block
        if accessed_files:
            file_list = []
            for f in accessed_files:
                if f.endswith("_ZH.md"):
                    file_list.append(
                        (
                            data_juicer_doc_url
                            + "zh_CN/main/"
                            + f.replace(".md", ".html"),
                            f,
                        )
                    )
                elif f.endswith(".md"):
                    file_list.append(
                        (
                            data_juicer_doc_url
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
                            data_juicer_doc_url
                            + "en/main/docs/operators/"
                            + f.split("_")[-1]
                            + "/"
                            + f
                            + ".html",
                            f,
                        )
                    )
                else:
                    file_list.append((data_juicer_repo_url + f, f))

            summary_text = "\n\n---\nReference: \n" + "\n".join(
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
    DATA_JUICER_PATH,
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
