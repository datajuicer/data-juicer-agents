# Tools and Service Primitives

This document describes the current atomic primitives behind DJX and how CLI/session compose them.

## 1) Primitive Tool Layer (`data_juicer_agents/tools`)

### `dataset_probe.py`

- Entry: `inspect_dataset_schema(dataset_path, sample_size=20)`
- Purpose:
  - lightweight dataset sampling
  - modality inference (`text` / `image` / `multimodal` / `unknown`)
  - candidate text/image key discovery

### `llm_gateway.py`

- Entry: `call_model_json(...)`
- Purpose:
  - call an OpenAI-compatible chat completion endpoint
  - enforce JSON-oriented responses
  - support fallback models via `DJA_MODEL_FALLBACKS`

### `op_manager/retrieval_service.py`

- Entry: `retrieve_operator_candidates(intent, top_k, mode, dataset_path)`
- Purpose:
  - retrieve candidate Data-Juicer operators from intent
  - combine backend retrieval with lexical fallback
  - optionally attach dataset profile hints

### `op_manager/operator_registry.py`

- Entries:
  - `get_available_operator_names()`
  - `resolve_operator_name(raw_name, available_ops)`
- Purpose:
  - load installed operator names
  - canonicalize model-produced operator names

### `planner/schema.py`

- Main models:
  - `PlanDraftSpec`
  - `PlanModel`
  - `OperatorStep`
- Purpose:
  - define the current draft-spec and final plan schema
  - represent executable plans without workflow/template metadata

### `planner/core.py`

- Entry: `PlannerCore.build_plan(...)`
- Purpose:
  - normalize planner context
  - reconcile draft specs into deterministic final plans
  - canonicalize operator names before validation

### `planner/validation.py`

- Entries:
  - `validate_plan_schema(plan)`
  - `PlanValidator.validate(plan)`
- Purpose:
  - validate schema and modality constraints
  - validate dataset/export/custom operator paths
  - validate operator availability against installed Data-Juicer metadata

### `planner/tool_api.py`

- Entries:
  - `plan_build(...)`
  - `plan_build_from_json(...)`
  - `plan_validate(...)`
- Purpose:
  - expose planner-core APIs to session tools
  - bridge JSON draft specs into final plans

### `apply_tool_api.py`

- Main types:
  - `ApplyUseCase`
  - `ApplyResult`
- Purpose:
  - materialize recipe YAML under `.djx/recipes/`
  - execute or dry-run `dj-process`
  - return structured execution summaries

### `dev_scaffold.py`

- Entries:
  - `generate_operator_scaffold(...)`
  - `run_smoke_check(scaffold)`
- Purpose:
  - generate custom operator scaffolds
  - optionally run a local smoke check

### `session/*`

- Main modules:
  - `context_tools.py`
  - `operator_tools.py`
  - `planner_tools.py`
  - `apply_tools.py`
  - `dev_tools.py`
  - `file_tools.py`
  - `process_tools.py`
  - `runtime.py`
  - `registry.py`
- Purpose:
  - adapt primitive APIs into the ReAct session toolkit
  - maintain session state, event emission, and file/process boundaries

## 2) Capability Composition Layer (`data_juicer_agents/capabilities`)

### Plan capability

- Files:
  - `capabilities/plan/generator.py`
  - `capabilities/plan/service.py`
- Composes:
  - operator retrieval
  - plan draft generation via LLM
  - deterministic planner core and validation

### Apply capability

- File: `capabilities/apply/service.py`
- Composes:
  - CLI-facing wrapper over `tools/apply_tool_api.py`

### Dev capability

- File: `capabilities/dev/service.py`
- Composes:
  - scaffold generator
  - optional smoke-check runner

### Session capability

- File: `capabilities/session/orchestrator.py`
- Composes:
  - ReAct agent
  - session toolkit registration
  - reasoning/tool event emission and interruption handling

## 3) Session-Exposed Tool Set

Registered for ReAct calls:
- `get_session_context`
- `set_session_context`
- `inspect_dataset`
- `retrieve_operators`
- `plan_build`
- `plan_validate`
- `plan_save`
- `apply_recipe`
- `develop_operator`
- `view_text_file`
- `write_text_file`
- `insert_text_file`
- `execute_shell_command`
- `execute_python_code`

Notes:
- there is no registered `plan_generate`, `plan_retrieve_candidates`, or `trace_run`
- `plan_build` expects the session agent to synthesize `draft_spec_json` from user goal + dataset inspection + retrieval evidence
- `apply_recipe` requires explicit confirmation

## 4) Command-to-Capability Mapping

- `djx plan` -> `PlanOrchestrator` -> `PlanDraftGenerator` + `PlannerCore` + `PlanValidator`
- `djx apply` -> `ApplyUseCase`
- `djx retrieve` -> retrieval service
- `djx dev` -> `DevUseCase`
- `dj-agents` -> `DJSessionAgent` + `tools/session/*`

## 5) Observability and Artifacts

Session/tool events:
- `tool_start`
- `tool_end`
- `reasoning_step`

Command-side output control:
- `--quiet` summary
- `--verbose` expanded execution output
- `--debug` structured debug payloads

Persistent artifacts:
- `.djx/recipes/`
- `.djx/session_plans/`
- user-specified plan YAML and export paths

## 6) Design Boundary

- tools are atomic primitives
- capabilities compose tools into CLI or session workflows
- plans are deterministic artifacts built from an LLM-produced draft spec
- `dev` remains non-invasive by default
