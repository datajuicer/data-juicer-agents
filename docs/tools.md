# DJX Tools and Service Primitives

This document describes the atomic primitives behind DJX, and how they are composed by capabilities/commands/session.

## 1) Primitive Tool Layer (`data_juicer_agents/tools`)

### `dataset_probe.py`

- Entry: `inspect_dataset_schema(dataset_path, sample_size=20)`
- Purpose:
  - sample-level schema summary
  - modality guess (`text` / `image` / `multimodal` / `unknown`)
  - candidate text/image keys and stats

### `llm_gateway.py`

- Entry: `call_model_json(...)`
- Purpose:
  - call OpenAI-compatible chat completion endpoint
  - enforce JSON-oriented LLM responses
  - optional model fallback chain via `DJA_MODEL_FALLBACKS`

### `op_manager/retrieval_service.py`

- Entry: `retrieve_operator_candidates(intent, top_k, mode, dataset_path)`
- Purpose:
  - intent-to-operator candidate retrieval
  - backend selection (`auto|llm|vector`) with lexical fallback
  - optional dataset-aware retrieval hints

### `op_manager/operator_registry.py`

- Entries:
  - `get_available_operator_names()`
  - `resolve_operator_name(raw_name, available_ops)`
- Purpose:
  - canonical operator name resolution
  - operator availability checks

### `router_helpers.py`

- Entries:
  - `retrieve_workflow(user_intent)`
  - `select_workflow(user_intent)`
  - `explain_routing(user_intent)`
- Purpose:
  - workflow template routing decisions in template-based planning paths

### `dev_scaffold.py`

- Entries:
  - `generate_operator_scaffold(...)`
  - `run_smoke_check(scaffold)`
- Purpose:
  - generate custom Data-Juicer operator scaffold
  - optional non-invasive smoke verification

### Retrieval internals (index/metadata)

- `op_manager/op_retrieval.py`
- `op_manager/create_dj_func_info.py`

Purpose:
- retrieval index/cache and operator metadata preparation

## 2) Capability Composition Layer (`data_juicer_agents/capabilities`)

### Plan capability

- File: `capabilities/plan/service.py`
- Composes:
  - workflow router helpers
  - retrieval candidates
  - operator canonicalization
  - LLM patch/full generation

### Apply capability

- File: `capabilities/apply/service.py`
- Composes:
  - recipe materialization
  - `dj-process` execution
  - timeout/cancel behavior

### Dev capability

- File: `capabilities/dev/service.py`
- Composes:
  - scaffold generator
  - optional smoke-check runner

### Trace capability

- File: `capabilities/trace/repository.py`
- Composes:
  - run trace persistence/query/stats

### Session capability

- File: `capabilities/session/orchestrator.py`
- Composes:
  - ReAct agent
  - tool exposure
  - event emission and interruption handling

## 3) Session-Exposed Tool Set

Registered for ReAct calls:
- `get_session_context`
- `set_session_context`
- `inspect_dataset`
- `retrieve_operators`
- `plan_retrieve_candidates`
- `plan_generate`
- `plan_validate`
- `plan_save`
- `apply_recipe`
- `trace_run`
- `develop_operator`
- `view_text_file`
- `write_text_file`
- `insert_text_file`
- `execute_shell_command`
- `execute_python_code`

Notes:
- `tool_plan(...)` exists as an internal compatibility helper in code, but it is not currently registered in the ReAct toolkit.
- Session planning prompt constrains the agent to use inspect/retrieve signals before `plan_generate`.

## 4) Command-to-Capability Mapping

- `djx plan` -> `PlanUseCase` + `PlanValidator`
- `djx apply` -> `ApplyUseCase`
- `djx trace` -> `TraceStore`
- `djx retrieve` -> retrieval service
- `djx dev` -> `DevUseCase`
- `djx evaluate` -> `PlanUseCase` + `ApplyUseCase` batch orchestration

## 5) Observability and Error Surface

Session/tool events:
- `tool_start`
- `tool_end`
- `reasoning_step`
- `interrupt_requested` / `interrupt_ack` / `interrupt_ignored` (runtime events)

Command-side output control:
- `--quiet` summary
- `--verbose` expanded execution logs
- `--debug` raw structured payload

Persistent traces:
- `.djx/runs.jsonl` queried by `djx trace`

## 6) Design Boundary

- Tools are atomic primitives.
- Capabilities compose tools into scenario workflows.
- Commands and session are two interaction surfaces over the same capability/tool base.
- `dev` remains non-invasive by default (generate scaffold + instructions, no auto installation).
