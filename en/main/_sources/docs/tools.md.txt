# Tools Architecture

This document describes the current tool-layer architecture inside `data_juicer_agents`.

## 1. Design Goal

The tool layer is the stable atomic capability surface inside `data_juicer_agents`.

It serves three consumers:

- CLI and command surfaces
- the AgentScope-backed `dj-agents` session
- skills

The key rule is:

- tool definitions are runtime-agnostic and explicit-input/output
- higher layers must not rely on hidden session defaults or tool-internal state fallback
- runtime adapters may change transport/schema presentation, but not tool semantics

## 2. Core Tool Contracts

Core contracts live in:

- `data_juicer_agents/core/tool/contracts.py`
- `data_juicer_agents/core/tool/registry.py`
- `data_juicer_agents/core/tool/catalog.py`

They define:

- `ToolSpec`
- `ToolContext`
- `ToolResult`
- `ToolRegistry`

Responsibilities:

- describe what a tool is
- define explicit input and output schemas
- register built-in tool specs
- avoid direct dependency on AgentScope, TUI, session state, or CLI rendering

## 3. Tool Groups

`data_juicer_agents/tools/` is organized by tool group.

Each group publishes `TOOL_SPECS` through `registry.py`.

Concrete tools usually live under per-tool subdirectories with:

- `input.py`: input model
- `logic.py`: reusable implementation
- `tool.py`: `ToolSpec` binding

Package-level `__init__.py` files re-export stable helpers, and some groups keep shared models or validators in sibling modules such as `_shared/`.

### `tools/context`

- Files:
  - `context/registry.py`
  - `context/inspect_dataset/{input.py,logic.py,tool.py}`
  - `context/list_system_config/{input.py,logic.py,tool.py}`
  - `context/list_dataset_fields/{input.py,logic.py,tool.py}`
  - `context/list_dataset_formatters/{input.py,logic.py,tool.py}`
  - `context/list_dataset_load_strategies/{input.py,logic.py,tool.py}`
- Main responsibilities:
  - dataset inspection
  - system and dataset configuration discovery
  - dataset field / formatter / load-strategy enumeration

### `tools/retrieve`

- Files:
  - `retrieve/registry.py`
  - `retrieve/_shared/logic.py`
  - `retrieve/_shared/operator_registry.py`
  - `retrieve/_shared/backend/` (sub-package):
    - `backend.py`: shared retrieval entrypoints (`retrieve_ops_with_meta`, `retrieve_ops`, `get_op_catalog`, etc.)
    - `cache.py`: `RetrievalCacheManager` for vector store, tool info, and catalog caching
    - `catalog.py`: operator catalog builder (collects `class_name`, `class_desc`, `class_type`, `class_tags`)
    - `result_builder.py`: shared retrieval result shaping helpers and `trace_step`
    - `retriever.py`: `RetrieverBackend` ABC and concrete backends (`LLMRetriever`, `VectorRetriever`, `BM25Retriever`, `RegexRetriever`)
  - `retrieve/retrieve_operators/{input.py,logic.py,tool.py}`
  - `retrieve/retrieve_operators_api/{input.py,logic.py,tool.py}`
  - `retrieve/get_operator_info/{input.py,logic.py,tool.py}`
  - `retrieve/list_operator_catalog/{input.py,logic.py,tool.py}`
- Main responsibilities:
  - operator retrieval entrypoints for the main package
  - split local vs API-backed retrieval surfaces
  - shared multi-backend retrieval logic and catalog caching
  - operator type and tag filtering
  - canonical operator-name resolution
  - installed-operator lookup
  - operator detail lookup and full catalog listing

Tool split:

- `retrieve_operators`: local retrieval surface (`auto|bm25|regex`)
- `retrieve_operators_api`: API-backed retrieval surface (`auto|llm|vector`)
- `get_operator_info`: resolve one operator and return its schema/details
- `list_operator_catalog`: list the current operator catalog with optional filtering

### `tools/plan`

- Files:
  - `plan/registry.py`
  - `plan/<tool_name>/{input.py,logic.py,tool.py}`
  - `plan/_shared/*.py`
- Main responsibilities:
  - staged dataset/process/system specs and the final plan model
  - deterministic planner core
  - plan validation
  - explicit plan assembly and persistence helpers

### `tools/apply`

- Files:
  - `apply/registry.py`
  - `apply/apply_recipe/{input.py,logic.py,tool.py}`
- Main responsibilities:
  - recipe materialization
  - plan execution
  - structured execution results

### `tools/dev`

- Files:
  - `dev/registry.py`
  - `dev/develop_operator/{input.py,logic.py,tool.py,scaffold.py}`
- Main responsibilities:
  - custom operator scaffold generation
  - optional smoke-check

### `tools/files`

- Files:
  - `files/registry.py`
  - `files/{view_text_file,write_text_file,insert_text_file}/...`
- Main responsibilities:
  - read / write / insert text file helpers

### `tools/process`

- Files:
  - `process/registry.py`
  - `process/{execute_shell_command,execute_python_code}/...`
- Main responsibilities:
  - shell execution
  - python snippet execution

## 4. Runtime Adapters

Runtime-specific adaptation is not placed in the tool groups.

### AgentScope adapter

- `data_juicer_agents/adapters/agentscope/tools.py`
- `data_juicer_agents/adapters/agentscope/schema_utils.py`

Responsibilities:

- convert `ToolSpec` into AgentScope-compatible callable/schema
- normalize JSON schema so agent-facing tool calls stay shallow and explicit
- map `ToolResult` into AgentScope responses
- apply generic argument preview truncation

### Session runtime / toolkit

- `data_juicer_agents/capabilities/session/toolkit.py`
- `data_juicer_agents/capabilities/session/runtime.py`

Responsibilities:

- create the session runtime
- emit tool lifecycle events for TUI/CLI observation
- choose which registered tools are exposed to `DJSessionAgent`
- keep session memory observational only; tool semantics remain explicit

## 5. Default Registry and Session Toolkit

Built-in tool registration is assembled through:

- `data_juicer_agents/core/tool/catalog.py`

That catalog discovers tool groups under `data_juicer_agents/tools/` and loads each group's `TOOL_SPECS` (currently via `registry.py` in every built-in group). It feeds them into:

- `build_default_tool_registry()`

The session toolkit currently uses the default registry directly and orders tools by functional group priority. It does not depend on `session` tags embedded in tool definitions.

## 6. Current Session Tool Set

The default registry currently exposes these tools to the session runtime:

- `list_dataset_fields`
- `list_dataset_formatters`
- `list_dataset_load_strategies`
- `list_system_config`
- `inspect_dataset`
- `get_operator_info`
- `list_operator_catalog`
- `retrieve_operators`
- `retrieve_operators_api`
- `build_dataset_spec`
- `build_process_spec`
- `build_system_spec`
- `validate_dataset_spec`
- `validate_process_spec`
- `validate_system_spec`
- `assemble_plan`
- `plan_validate`
- `plan_save`
- `apply_recipe`
- `develop_operator`
- `view_text_file`
- `write_text_file`
- `insert_text_file`
- `execute_shell_command`
- `execute_python_code`

These tools stay generic. Session orchestration must call them with explicit arguments based on prior tool outputs.

## 7. Boundary Summary

- `core/tool/*` defines tool contracts, discovery, and registry
- `tools/<group>/*` defines atomic tools only
- `adapters/agentscope/*` adapts tools to AgentScope transport/schema
- `capabilities/session/*` orchestrates tools conversationally without changing tool semantics

This is the internal shape that future atomic CLI and skills should build on.
