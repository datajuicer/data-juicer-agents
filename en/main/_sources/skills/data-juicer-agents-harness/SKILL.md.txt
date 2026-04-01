---
name: data-juicer-agents-harness
description: Use the Data-Juicer Agents harness for dataset inspection, cleaning, filtering, deduplication, transformation, and recipe-oriented data processing through the `djx tool` interface. Trigger when the user explicitly mentions Data-Juicer, data-juicer-agents, data_juicer_agents, dj-agents, or djx, or when the user asks for data processing work that should be handled through the Data-Juicer Agents tool-based CLI harness.
---

# Data Juicer Agents Harness

Use `data-juicer-agents` only through the documented `djx tool` surface in harness mode.

## Install

Requirements:
- Python `>=3.10,<3.13`
- `uv`

Recommended setup:

```bash
uv venv --python python3.11 .venv
source .venv/bin/activate
uv pip install -U 'data-juicer-agents[harness]'
export DJX_TOOL_PROFILE=harness
```

For unreleased local testing, if the user explicitly provides a local `data-juicer-agents` checkout, prefer a local editable install instead of PyPI:

```bash
uv venv --python python3.11 .venv
source .venv/bin/activate
uv pip install -U -e '/path/to/data-juicer-agents[harness]'
export DJX_TOOL_PROFILE=harness
```

If `uv venv` fails in the current environment, fall back to:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U 'data-juicer-agents[harness]'
export DJX_TOOL_PROFILE=harness
```

For the same unreleased-local-testing case, the fallback install is:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U -e '/path/to/data-juicer-agents[harness]'
export DJX_TOOL_PROFILE=harness
```

Do not use the system default `python3` when it resolves to Python 3.9 or any interpreter outside `>=3.10,<3.13`.

## Supported CLI Surface

Use only these commands:

```bash
djx --version
djx tool list
djx tool schema <tool-name>
djx tool run <tool-name> (--input-json '<json>' | --input-file <input.json>) [--working-dir <path>] [--yes]
```

Rules:
- output is always JSON
- `--quiet`, `--verbose`, and `--debug` are accepted for CLI consistency but do not change `djx tool` output
- tools that declare confirmation requirements must be run with `--yes`

## How the Harness Works

The harness is organized around building and executing a Data-Juicer processing plan.

The usual flow is:
1. inspect the dataset and collect context
2. build a dataset spec, process spec, and system spec
3. assemble those specs into one plan payload
4. validate and save the plan if needed
5. apply the saved plan to produce processed output

The tool groups map to that flow:
- `context`: inspect the input dataset and discover available system settings before planning
- `retrieve`: retrieve built-in operators locally and inspect their parameter schema
- `plan`: build, validate, assemble, and save the plan components that define the pipeline
- `apply`: execute a saved plan against the dataset

Stay within these groups in harness mode.

## Supported Tools

### `apply`
- `apply_recipe`: run a saved plan against an input dataset and write the processed output.
  - Example: `djx tool run apply_recipe --yes --input-json '{"plan_path":"./plan.yaml","dry_run":false,"confirm":true}'`

### `context`
- `inspect_dataset`: inspect a dataset path and return schema, sampling, and profile information for planning.
  - Example: `djx tool run inspect_dataset --input-json '{"dataset_path":"./data/demo.jsonl","sample_size":20}'`
- `list_dataset_fields`: list supported dataset-spec fields and their defaults.
  - Example: `djx tool run list_dataset_fields --input-json '{}'`
- `list_dataset_formatters`: list available dataset formatter names.
  - Example: `djx tool run list_dataset_formatters --input-json '{}'`
- `list_dataset_load_strategies`: list available dataset loading strategies.
  - Example: `djx tool run list_dataset_load_strategies --input-json '{}'`
- `list_system_config`: list supported system configuration fields and available runtime options.
  - Example: `djx tool run list_system_config --input-json '{}'`

### `retrieve`
- `retrieve_operators`: retrieve candidate operators with local retrieval (`auto`, `bm25`, `regex`).
  - Example: `djx tool run retrieve_operators --input-json '{"intent":"filter long text","mode":"bm25"}'`
- `list_operator_catalog`: list the local built-in operator catalog with descriptions, types, tags, and optional parameter schemas.
  - Example: `djx tool run list_operator_catalog --input-json '{"include_parameters":false}'`
  - Use this as a fallback only when targeted retrieval is insufficient. It can load a large amount of operator context, especially with `include_parameters=true`, so use it cautiously.
- `get_operator_info`: inspect one operator and return structured parameter/schema information.
  - Example: `djx tool run get_operator_info --input-json '{"operator_name":"text_length_filter"}'`

### `plan`
- `build_dataset_spec`: build a normalized dataset spec from dataset context and target input/output paths.
  - Example: `djx tool run build_dataset_spec --input-file ./build_dataset_spec.json`
- `build_process_spec`: build a normalized process spec from an ordered operator list.
  - Example: `djx tool run build_process_spec --input-json '{"operators":[{"name":"remove_duplicate","params":{"text_key":"text"}}]}'`
- `build_system_spec`: build a normalized system spec from runtime and configuration settings.
  - Example: `djx tool run build_system_spec --input-json '{"np":4,"executor_type":"default"}'`
- `validate_dataset_spec`: validate a dataset spec before assembling a full plan.
  - Example: `djx tool run validate_dataset_spec --input-file ./validate_dataset_spec.json`
- `validate_process_spec`: validate a process spec before assembling a full plan.
  - Example: `djx tool run validate_process_spec --input-file ./validate_process_spec.json`
- `validate_system_spec`: validate a system spec before assembling a full plan.
  - Example: `djx tool run validate_system_spec --input-file ./validate_system_spec.json`
- `assemble_plan`: combine dataset, process, and system specs into one executable plan payload.
  - Example: `djx tool run assemble_plan --input-file ./assemble_plan.json`
- `plan_validate`: validate a complete plan payload and surface schema or consistency issues.
  - Example: `djx tool run plan_validate --input-file ./plan_payload.json`
- `plan_save`: persist a complete plan payload to disk for later review or execution.
  - Example: `djx tool run plan_save --input-file ./plan_save.json`

## Operator Discovery and Authoring

In harness mode, operator discovery is local-first. When the user request implies a concrete data-processing operator, use:

- `retrieve_operators` for local retrieval without extra API calls
- `list_operator_catalog` when targeted retrieval is insufficient and broader local operator context is needed
- `get_operator_info` to inspect the canonical operator and its parameter schema

Recommended pattern:
1. Use `retrieve_operators` with `mode="auto"` for ordinary natural-language operator discovery.
2. Use `mode="bm25"` when you want deterministic keyword retrieval.
3. Use `mode="regex"` when the request or current context already suggests an operator naming pattern. This mode is often useful for agentic exploration when the likely operator family is known.
4. If `retrieve_operators` does not return valid candidates, call `list_operator_catalog` as a fallback and let the agent reason over the broader local operator catalog to identify likely operators.
5. Use `list_operator_catalog` cautiously: it may load a large amount of context, and `include_parameters=true` is especially heavy. Prefer filtered calls (`op_type`, `tags`, `limit`) whenever possible.
6. After selecting a candidate, call `get_operator_info` before filling `build_process_spec`.

Use these tools to map the user goal to canonical built-in operators before filling `build_process_spec`. Do not guess parameter names from operator names alone when `get_operator_info` can provide the schema directly.

Only if the tool output is insufficient or the existing operator catalog does not cover the requested behavior, refer to:

- [Operators.md](https://github.com/datajuicer/data-juicer/blob/main/docs/Operators.md)

- [DeveloperGuide.md](https://github.com/datajuicer/data-juicer/blob/main/docs/DeveloperGuide.md)

Use that guide to design or scaffold a custom operator implementation outside the harness flow when built-in operators are not sufficient.

## Agent Discipline

- Prefer `djx tool list` when you need to confirm what is available in the current environment.
- Use `djx tool schema` before first use of an unfamiliar tool.
- Do not assume non-harness tools are available. In `DJX_TOOL_PROFILE=harness`, rely on `djx tool list` and stay within the surfaced tool set.
- Prefer `--input-file` for large payloads instead of long inline JSON strings.
- Treat JSON output as the contract; do not parse human-oriented text.
- Summarize the user goal, the chosen `djx tool` sequence, and the concrete commands used.
- Call out any required credentials, missing files, or unresolved assumptions before execution when they block progress.
- If the task requires capabilities outside this harness surface, stop and say that the harness is not sufficient.
