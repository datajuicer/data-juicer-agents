# -*- coding: utf-8 -*-
"""Session toolkit registration."""

from __future__ import annotations

from typing import Any

from .apply_tools import apply_recipe as run_apply_recipe
from .context_tools import (
    get_session_context as run_get_session_context,
    inspect_dataset as run_inspect_dataset,
    set_session_context as run_set_session_context,
)
from .dev_tools import develop_operator as run_develop_operator
from .file_tools import (
    insert_text_file as run_insert_text_file,
    view_text_file as run_view_text_file,
    write_text_file as run_write_text_file,
)
from .operator_tools import (
    retrieve_operators as run_retrieve_operators,
)
from .planner_tools import (
    plan_build as run_plan_build,
    plan_save as run_plan_save,
    plan_validate as run_plan_validate,
)
from .process_tools import (
    execute_python_code as run_execute_python_code,
    execute_shell_command as run_execute_shell_command,
)
from .runtime import SessionToolRuntime, truncate_text


def build_session_toolkit(runtime: SessionToolRuntime):
    from agentscope.tool import Toolkit

    toolkit = Toolkit()

    def get_session_context() -> Any:
        return runtime.invoke_text_tool(
            "get_session_context",
            {},
            lambda: run_get_session_context(runtime),
        )

    def set_session_context(
        dataset_path: str = "",
        export_path: str = "",
        plan_path: str = "",
        custom_operator_paths: str = "",
    ) -> Any:
        return runtime.invoke_text_tool(
            "set_session_context",
            {
                "dataset_path": dataset_path,
                "export_path": export_path,
                "plan_path": plan_path,
            },
            lambda: run_set_session_context(
                runtime,
                dataset_path=dataset_path,
                export_path=export_path,
                plan_path=plan_path,
                custom_operator_paths=custom_operator_paths,
            ),
        )

    def inspect_dataset(
        dataset_path: str = "",
        sample_size: int = 20,
    ) -> Any:
        return runtime.invoke_text_tool(
            "inspect_dataset",
            {
                "dataset_path": dataset_path,
                "sample_size": sample_size,
            },
            lambda: run_inspect_dataset(
                runtime,
                dataset_path=dataset_path,
                sample_size=sample_size,
            ),
        )

    def retrieve_operators(
        intent: str,
        top_k: int = 10,
        mode: str = "auto",
        dataset_path: str = "",
    ) -> Any:
        return runtime.invoke_text_tool(
            "retrieve_operators",
            {
                "intent": intent,
                "top_k": top_k,
                "mode": mode,
                "dataset_path": dataset_path,
            },
            lambda: run_retrieve_operators(
                runtime,
                intent=intent,
                top_k=top_k,
                mode=mode,
                dataset_path=dataset_path,
            ),
        )

    def plan_build(
        intent: str,
        dataset_path: str = "",
        export_path: str = "",
        custom_operator_paths: str = "",
        draft_spec_json: str = "",
    ) -> Any:
        return runtime.invoke_text_tool(
            "plan_build",
            {
                "intent": intent,
                "dataset_path": dataset_path,
                "export_path": export_path,
                "draft_spec_json": truncate_text(draft_spec_json, limit=800),
            },
            lambda: run_plan_build(
                runtime,
                intent=intent,
                dataset_path=dataset_path,
                export_path=export_path,
                custom_operator_paths=custom_operator_paths,
                draft_spec_json=draft_spec_json,
            ),
        )

    def plan_validate(
        plan_path: str = "",
        use_draft: bool = True,
    ) -> Any:
        return runtime.invoke_text_tool(
            "plan_validate",
            {
                "plan_path": plan_path,
                "use_draft": use_draft,
            },
            lambda: run_plan_validate(
                runtime,
                plan_path=plan_path,
                use_draft=use_draft,
            ),
        )

    def plan_save(
        output_path: str = "",
        overwrite: bool = False,
        source_plan_path: str = "",
    ) -> Any:
        return runtime.invoke_text_tool(
            "plan_save",
            {
                "output_path": output_path,
                "overwrite": overwrite,
                "source_plan_path": source_plan_path,
            },
            lambda: run_plan_save(
                runtime,
                output_path=output_path,
                overwrite=overwrite,
                source_plan_path=source_plan_path,
            ),
        )

    def apply_recipe(
        plan_path: str = "",
        dry_run: bool = False,
        timeout: int = 300,
        confirm: bool = False,
    ) -> Any:
        return runtime.invoke_text_tool(
            "apply_recipe",
            {
                "plan_path": plan_path,
                "dry_run": dry_run,
                "timeout": timeout,
                "confirm": confirm,
            },
            lambda: run_apply_recipe(
                runtime,
                plan_path=plan_path,
                dry_run=dry_run,
                timeout=timeout,
                confirm=confirm,
            ),
        )

    def develop_operator(
        intent: str,
        operator_name: str = "",
        output_dir: str = "",
        operator_type: str = "",
        from_retrieve: str = "",
        smoke_check: bool = False,
    ) -> Any:
        return runtime.invoke_text_tool(
            "develop_operator",
            {
                "intent": intent,
                "operator_name": operator_name,
                "output_dir": output_dir,
                "operator_type": operator_type,
                "from_retrieve": from_retrieve,
                "smoke_check": smoke_check,
            },
            lambda: run_develop_operator(
                runtime,
                intent=intent,
                operator_name=operator_name,
                output_dir=output_dir,
                operator_type=operator_type,
                from_retrieve=from_retrieve,
                smoke_check=smoke_check,
            ),
        )

    def view_text_file(
        file_path: str,
        ranges: Any = None,
    ) -> Any:
        return runtime.invoke_text_tool(
            "view_text_file",
            {
                "file_path": file_path,
                "ranges": ranges,
            },
            lambda: run_view_text_file(
                file_path=file_path,
                ranges=ranges,
            ),
        )

    def write_text_file(
        file_path: str,
        content: str,
        ranges: Any = None,
    ) -> Any:
        return runtime.invoke_text_tool(
            "write_text_file",
            {
                "file_path": file_path,
                "ranges": ranges,
            },
            lambda: run_write_text_file(
                file_path=file_path,
                content=content,
                ranges=ranges,
            ),
        )

    def insert_text_file(
        file_path: str,
        content: str,
        line_number: int,
    ) -> Any:
        return runtime.invoke_text_tool(
            "insert_text_file",
            {
                "file_path": file_path,
                "line_number": line_number,
            },
            lambda: run_insert_text_file(
                file_path=file_path,
                content=content,
                line_number=line_number,
            ),
        )

    def execute_shell_command(
        command: str,
        timeout: int = 120,
    ) -> Any:
        command_text = str(command or "")
        return runtime.invoke_text_tool(
            "execute_shell_command",
            {
                "command": truncate_text(command_text, limit=500),
                "timeout": timeout,
            },
            lambda: run_execute_shell_command(
                runtime,
                command=command_text,
                timeout=timeout,
            ),
        )

    def execute_python_code(
        code: str,
        timeout: int = 120,
    ) -> Any:
        code_text = str(code or "")
        return runtime.invoke_text_tool(
            "execute_python_code",
            {
                "code": truncate_text(code_text, limit=800),
                "timeout": timeout,
            },
            lambda: run_execute_python_code(
                runtime,
                code=code_text,
                timeout=timeout,
            ),
        )

    toolkit.register_tool_function(get_session_context)
    toolkit.register_tool_function(set_session_context)
    toolkit.register_tool_function(inspect_dataset)
    toolkit.register_tool_function(retrieve_operators)
    toolkit.register_tool_function(plan_build)
    toolkit.register_tool_function(plan_validate)
    toolkit.register_tool_function(plan_save)
    toolkit.register_tool_function(apply_recipe)
    toolkit.register_tool_function(develop_operator)
    toolkit.register_tool_function(view_text_file)
    toolkit.register_tool_function(write_text_file)
    toolkit.register_tool_function(insert_text_file)
    toolkit.register_tool_function(execute_shell_command)
    toolkit.register_tool_function(execute_python_code)
    return toolkit


__all__ = ["build_session_toolkit"]
