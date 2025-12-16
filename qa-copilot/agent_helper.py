# -*- coding: utf-8 -*-
import os
import copy
import json
from typing import Any

from op_manager.dj_op_retriever import DJOperatorRetriever

from agentscope.tool import Toolkit
from agentscope.agent import ReActAgent
from agentscope.mcp import StdIOStatefulClient

data_juicer_repo_url = "https://github.com/datajuicer/data-juicer/blob/main/"
data_juicer_doc_url = "https://datajuicer.github.io/data-juicer/"

DATA_JUICER_PATH = os.getenv("DATA_JUICER_PATH", "/data-juicer")


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
