# Architecture

`data_juicer_agents` is organized around reusable data-processing capabilities, not around a single agent shell.

The current package has four important internal layers:

- surface adapters
- capability orchestration
- tools
- runtime adapters

## User-Facing Surfaces

Current surfaces:

| Surface | Role | Entry |
| --- | --- | --- |
| `djx` | engineer-facing CLI | `data_juicer_agents/cli.py` |
| `dj-agents` | conversational session interface | `data_juicer_agents/session_cli.py` |
| skills | packaged orchestration for other agents | available |

The current architectural intent is:

- `djx` remains the explicit engineer workflow surface
- `dj-agents` orchestrates lower-level tools through AgentScope
- skills should build on stable atomic tools, not on shell-text parsing

## Current Layer Model

| Layer | Main directories | Responsibility |
| --- | --- | --- |
| Surface adapters | `commands/`, `cli.py`, `session_cli.py`, `tui/` | parse user input, present output, select interaction mode |
| Capabilities | `capabilities/` | define end-to-end use cases such as plan, apply, dev, session |
| Tools | `core/tool/`, `tools/` | define atomic tool contracts and grouped tool sets |
| Runtime adapters and infra | `adapters/`, `utils/` | connect tools to AgentScope/session and provide shared helpers |

Dependency direction:

```text
CLI / session / skills
    -> capabilities
    -> tools
    -> runtime adapters / backend implementations
```

The key rule is:

- core tool contracts are runtime-agnostic
- runtime-specific behavior belongs in adapters/bindings, not in tool specs

## Module Boundaries

The package is easiest to reason about when each layer keeps a narrow role.

- `commands/`, `cli.py`, `session_cli.py`, and `tui/` own user-facing entrypoints, argument parsing, and presentation
- `capabilities/` owns end-to-end use-case orchestration such as planning, applying, development, and session flow
- `core/tool/` and `tools/` own reusable atomic capabilities, shared tool contracts, and grouped tool definitions
- `adapters/` and `utils/` own runtime integration, framework binding, and shared non-domain helpers

Boundary rule:

- if behavior should be reusable across `djx`, `dj-agents`, and skills, it belongs in the tool layer
- if behavior defines a user-facing workflow or multi-step orchestration, it belongs in capabilities or surface adapters
- if behavior only exists to bind the core system to a specific runtime, it belongs in adapters

## Exposure Strategy

The same package is exposed through different surfaces on purpose.

- `djx` exposes explicit engineer-facing operations with stable command boundaries
- `dj-agents` exposes natural-language orchestration over the same capability and tool layers
- skills should reuse the same atomic contracts instead of introducing shell-oriented wrappers

That means the architectural goal is not to make every surface look the same. The goal is to let different surfaces share one internal capability stack without duplicating domain logic.

## Reading Guide

- for command behavior, flags, and output contracts, see [CLI reference](cli.md)
- for tool contracts, grouped tool packages, and runtime bindings, see [Tools architecture](tools.md)
- for end-to-end usage examples, see [Quick Start](quick_start.md)
