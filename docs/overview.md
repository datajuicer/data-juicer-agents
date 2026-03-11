# DJX Overview

`data-juicer-agents` exposes DJX as a small set of composable capabilities for Data-Juicer workflows.

Primary entries:
- `djx`: deterministic CLI for `plan`, `apply`, `retrieve`, and `dev`
- `dj-agents`: natural-language ReAct session over the same capability base

## Positioning

DJX is a capability layer, not an all-in-one monolithic agent.

Design goals:
- stable command and tool boundaries
- structured inputs and outputs
- deterministic plan reconciliation before execution
- reusable primitives for upper-layer agents and skills

## Core Flows

### 1) CLI planning and execution

1. `djx retrieve` optionally inspects dataset modality and ranks operator candidates.
2. `djx plan` internally retrieves operators, asks the model for a draft spec, then reconciles it with the deterministic planner core.
3. `PlanValidator` checks schema, filesystem preconditions, custom operator paths, and installed operator availability.
4. Plan YAML is written to disk.
5. `djx apply` validates the saved plan again, writes a recipe under `.djx/recipes/`, and executes `dj-process` or a dry run.

### 2) Session orchestration

`dj-agents` runs one ReAct agent over registered session tools.

Typical planning chain:

`inspect_dataset -> retrieve_operators -> plan_build -> plan_validate -> plan_save`

`apply_recipe` requires explicit confirmation before execution.

### 3) Runtime artifacts

- `.djx/recipes/`: generated execution recipes
- `.djx/session_plans/`: plans saved from session tools
- user-specified `--output` plan YAML paths
- user-specified exported dataset paths

## Scope Notes

- Current user-facing surfaces documented here are `djx` and `dj-agents`.
- Older `trace`, `templates`, and `evaluate` command flows are not part of the current CLI.
- `interactive_recipe/` and `qa-copilot/` remain separate subsystems.
