# Architecture

`data_juicer_agents` is organized around one core idea: keep data-processing logic in reusable Python modules, then expose the same core through different user-facing surfaces.

The package is not designed as a single monolithic "agent product". Its main architectural unit is the reusable data-processing primitive, not the chat shell.

## Package Scope

Current user-facing surfaces:

| Surface | Role | Primary entry |
| --- | --- | --- |
| `djx` | Deterministic CLI for planning, retrieval, execution, and scaffold generation | `data_juicer_agents/cli.py` |
| `dj-agents` | Conversational ReAct session over the same capability base | `data_juicer_agents/session_cli.py` |
| `skills` (future) | Prompt-packaged compositions for external general-purpose agents | not implemented yet |

The design target is:

- `djx` for explicit, file-oriented, reproducible workflows
- `dj-agents` for interactive orchestration over the same primitives
- future `skills` as lightweight packaging of those primitives for other agent runtimes

## Layer Model

The package is best understood as four main layers:

| Layer | Directory | Responsibility | Typical dependencies |
| --- | --- | --- | --- |
| Surface adapters | `commands/`, `cli.py`, `session_cli.py`, `tui/` | Parse user input, select UI mode, print output, translate between shell/session and structured payloads | capabilities, tools, utils |
| Use-case orchestration | `capabilities/` | Define one end-to-end user story such as planning or session orchestration | tools, utils |
| Reusable domain primitives | `tools/` | Contain planner core, retrieval, execution, scaffold generation, session tool adapters, and model gateway | external runtimes, utils |
| Shared infrastructure | `utils/` | Logging, terminal I/O, small helpers | standard library and external libs |

In dependency terms:

```text
djx CLI / dj-agents session / future skills
        -> commands or session entrypoints
        -> capabilities
        -> tools
        -> external runtimes (Data-Juicer CLI, LLM APIs, AgentScope)
```

The important rule is directional:

- `commands` may depend on `capabilities` and selected `tools`
- `capabilities` may depend on `tools`
- `tools` must not depend on `commands`, `cli.py`, or `tui/`
- future `skills` should depend on `capabilities` or `tools`, not shell out to `djx`

## Surface Adapters

### `djx` CLI

`data_juicer_agents/cli.py` defines the deterministic command-line contract:

- `djx plan`
- `djx apply`
- `djx retrieve`
- `djx dev`

`commands/` is intentionally thin. Each command does argument validation, output formatting, exit-code handling, and then hands off to a capability or tool-level API.

Current command mapping:

| Command | Main module | Downstream dependency |
| --- | --- | --- |
| `plan` | `commands/plan_cmd.py` | `capabilities.plan.PlanOrchestrator` |
| `apply` | `commands/apply_cmd.py` | `capabilities.apply.ApplyUseCase` + `tools.planner.PlanValidator` |
| `retrieve` | `commands/retrieve_cmd.py` | `tools.op_manager.retrieval_service` |
| `dev` | `commands/dev_cmd.py` | `capabilities.dev.DevUseCase` |

This is an important boundary: the CLI is not where domain logic should grow. It is an adapter layer.

### `dj-agents` session

`data_juicer_agents/session_cli.py` is the conversational surface adapter. It is responsible for:

- argument parsing for session startup
- plain-text versus TUI session selection
- Ctrl+C / Ctrl+D terminal behavior
- handing each turn to `DJSessionAgent`

The TUI in `tui/` is also a surface adapter, not a domain layer. It renders the event stream emitted by the session capability and should not own planning or execution logic.

### `skills` (future)

The future skills outlet should package reusable orchestration for external agents. The intended integration boundary is:

- structured `tools/*`
- selected `capabilities/*`

It should not depend on:

- CLI argument parsing
- shell-oriented output text
- TUI rendering
- parsing `djx` stdout back into machine-readable state

## Capabilities

`capabilities/` is the use-case layer. It answers: "what end-to-end workflow do we want to expose?"

### `capabilities.plan`

This is the most substantial capability today.

`PlanOrchestrator` in `capabilities/plan/service.py` wires together:

1. `tools.op_manager.retrieval_service.retrieve_operator_candidates`
2. `PlanDraftGenerator`
3. `tools.llm_gateway.call_model_json`
4. `tools.planner.PlannerCore`
5. `tools.planner.PlanValidator`

Its role is not to own planning semantics itself; its role is to compose a fixed planning pipeline:

`retrieve evidence -> generate draft spec -> build deterministic plan -> validate`

### `capabilities.session`

`DJSessionAgent` in `capabilities/session/orchestrator.py` is the orchestration boundary for conversational use.

It owns:

- session state bootstrapping
- AgentScope `ReActAgent` construction
- tool registration through `build_session_toolkit`
- interrupt handling
- event emission for plain/TUI rendering
- session-level system prompt and turn protocol

This capability does not call CLI commands. It calls reusable session tools and tool runtimes directly.

### `capabilities.apply` and `capabilities.dev`

These are currently thin CLI-facing wrappers over tool-level use cases:

- `capabilities.apply` re-exports `tools.apply_tool_api.ApplyUseCase`
- `capabilities.dev` re-exports `tools.dev_tool_api.DevUseCase`

That means the architectural center for apply/dev currently lives in `tools/`, not in extra orchestration code inside `capabilities/`.

## Tools

`tools/` is the main reusable kernel of the package. This is where most stable integration boundaries live.

### `tools.planner`

This module is the deterministic planning core shared by CLI and session tools.

It contains:

- `schema.py`: `PlanDraftSpec`, `PlanContext`, `PlanModel`, `OperatorStep`
- `core.py`: `PlannerCore`
- `validation.py`: `PlanValidator`
- `tool_api.py`: JSON-friendly functions used by session tools

Architecturally, this is the center of plan semantics. Everything else feeds data into it or consumes its outputs.

### `tools.op_manager`

This module provides operator discovery and normalization:

- `retrieval_service.py`: structured operator retrieval payloads for CLI and session
- `operator_registry.py`: installed-operator lookup and canonical name resolution
- `op_retrieval.py`: backend retrieval implementation and vector/LLM fallback machinery

Its contract is "given intent plus optional dataset hints, return grounded operator candidates". It should not know about CLI formatting or session rendering.

### `tools.llm_gateway`

This is the narrow LLM boundary:

- OpenAI-compatible client invocation
- API-key and base-URL resolution
- JSON extraction
- candidate-model fallback

The planning layer uses it through `PlanDraftGenerator`, instead of scattering model calls across commands and session code.

### `tools.apply_tool_api`

This module owns deterministic execution:

- convert `PlanModel` into a Data-Juicer recipe YAML
- invoke `dj-process`
- classify execution failures
- return a structured `ApplyResult`

It is intentionally closer to the runtime than to presentation.

### `tools.dev_tool_api`

This module owns custom-operator scaffold generation and optional smoke checking. It packages:

- argument completeness checks
- scaffold generation
- optional smoke-test serialization

### `tools.session`

This module is the bridge between the conversational outlet and the reusable core.

It contains:

- `runtime.py`: mutable `SessionState`, event emission, saved-plan helpers
- `registry.py`: session tool registration
- `context_tools.py`: session context and dataset inspection
- `operator_tools.py`: operator retrieval tools
- `planner_tools.py`: draft-plan build/validate/save tools
- `apply_tools.py`: apply from session
- `dev_tools.py`: operator development from session
- file/process tools for session-side diagnostics and editing

This layer is important because `dj-agents` does not wrap `djx`; it re-exposes the same lower-level primitives through an agent-tool interface.

## Boundary and Dependency Notes

The key architectural boundaries are:

### 1. Commands are presentation adapters

They should own:

- argparse contracts
- terminal output
- exit codes
- human/debug formatting

They should not become the primary home of planning, execution, or retrieval semantics.

### 2. Capabilities define use cases

They answer:

- what fixed pipeline should be run
- what state must be carried across a session
- what confirmation policy exists before execution

They should not absorb UI-specific concerns.

### 3. Tools define reusable contracts

They should return structured payloads that can be reused by:

- CLI commands
- session tools
- future skills
- tests

This is why `PlanModel`, retrieval payloads, and `ApplyResult` matter more than terminal text.

### 4. Session is not a wrapper around shell commands

`dj-agents` is architected to call Python tools directly:

`session_cli -> DJSessionAgent -> SessionToolRuntime + session toolkit -> tools/*`

That keeps session orchestration machine-readable, interruptible, and observable through events.

## Key Call Chains

### `djx plan`

```text
cli.py
-> commands/plan_cmd.py
-> capabilities.plan.PlanOrchestrator
-> op_manager.retrieval_service
-> capabilities.plan.PlanDraftGenerator
-> tools.llm_gateway
-> tools.planner.PlannerCore
-> tools.planner.PlanValidator
-> write plan YAML
```

### `djx apply`

```text
cli.py
-> commands/apply_cmd.py
-> tools.planner.PlanValidator
-> ApplyUseCase
-> write recipe under .djx/recipes/
-> invoke dj-process
```

### `dj-agents`

```text
session_cli.py
-> DJSessionAgent
-> build_session_toolkit
-> AgentScope ReActAgent
-> session tool functions
-> tools.planner / tools.op_manager / ApplyUseCase / DevUseCase / file/process helpers
```

## Runtime State and Artifacts

Important on-disk artifacts:

- `.djx/recipes/`: recipes generated before execution
- `.djx/session_plans/`: plans saved from session tools
- user-specified plan YAML outputs from `djx plan`
- user-specified dataset exports from plan/apply flows

Important in-memory session state in `SessionState`:

- current dataset/export paths
- current saved plan path
- current draft plan
- last retrieval payload
- last dataset inspection result

This state is what allows the same session to move from inspection to retrieval to planning to confirmation and execution.

## Design Intent

The package is evolving toward this split:

- `tools`: stable machine-facing primitives
- `capabilities`: reusable orchestration patterns over those primitives
- `djx`: deterministic operator-facing shell
- `dj-agents`: conversational orchestration surface
- future `skills`: agent-facing packaging of the same structured building blocks
