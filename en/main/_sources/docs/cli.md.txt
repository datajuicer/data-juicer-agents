# DJX CLI Reference

## Command Map

| Command | Purpose | Source |
|---|---|---|
| `djx plan` | Generate a plan YAML from intent, retrieval evidence, and an LLM draft spec | `data_juicer_agents/commands/plan_cmd.py` |
| `djx apply` | Validate a saved plan and execute or dry-run `dj-process` | `data_juicer_agents/commands/apply_cmd.py` |
| `djx retrieve` | Retrieve candidate operators by intent | `data_juicer_agents/commands/retrieve_cmd.py` |
| `djx dev` | Generate a non-invasive custom operator scaffold | `data_juicer_agents/commands/dev_cmd.py` |

Additional entry:
- `dj-agents`: `data_juicer_agents/session_cli.py`

Current CLI does not include `trace`, `templates`, or `evaluate`.

## Global Output Levels (`djx`)

All `djx` subcommands support:
- `--quiet` (default): summary output
- `--verbose`: expanded execution output
- `--debug`: raw structured payloads useful for debugging

Examples:

```bash
djx plan "deduplicate text" --dataset ./data.jsonl --export ./out.jsonl --quiet
djx plan "deduplicate text" --dataset ./data.jsonl --export ./out.jsonl --verbose
djx --debug retrieve "deduplicate text" --dataset ./data.jsonl
```

## `djx plan`

```bash
djx plan "<intent>" --dataset <input.jsonl> --export <output.jsonl> [options]
```

Key options:
- `--output`: output plan path (default: `plans/<plan_id>.yaml`)
- `--custom-operator-paths`: custom operator dirs/files used for validation and later execution

Behavior:
1. internally retrieves operator candidates from the intent and optional dataset profile
2. calls the model once to generate a draft spec
3. reconciles the draft with the deterministic planner core
4. validates schema, filesystem paths, custom operator paths, and installed operator names
5. writes the final plan YAML

CLI output:
- summary: `Plan generated`, `Modality`, `Operators`
- `--verbose`: planning meta (`planner_model`, `retrieval_source`, `retrieval_candidate_count`)
- `--debug`: retrieval payload, draft spec payload, and planning meta payload

Failure behavior:
- exits non-zero and prints a user-facing error message

## `djx apply`

```bash
djx apply --plan <plan.yaml> [--yes] [--dry-run] [--timeout 300]
```

Behavior:
- validates the plan before execution
- writes a recipe to `.djx/recipes/<plan_id>.yaml`
- executes `dj-process` unless `--dry-run` is set
- prints `Execution ID`, `Status`, and generated recipe path

Notes:
- current CLI does not persist or expose a separate trace query command
- `--dry-run` still writes the recipe file

## `djx retrieve`

```bash
djx retrieve "<intent>" [--dataset <path>] [--top-k 10] [--mode auto|llm|vector] [--json]
```

Returns:
- ranked operator candidates
- optional dataset profile when dataset path is provided
- retrieval source and notes

## `djx dev`

```bash
djx dev "<intent>" \
  --operator-name <snake_case_name> \
  --output-dir <dir> \
  [--type mapper|filter] \
  [--from-retrieve <json>] \
  [--smoke-check]
```

Outputs:
- operator scaffold
- test scaffold
- summary markdown
- optional smoke-check result

Default behavior is non-invasive: generate code and guidance, but do not auto-install the operator.

## `dj-agents`

```bash
dj-agents [--dataset <path>] [--export <path>] [--verbose] [--ui plain|tui]
```

Behavior:
- natural-language conversation over the same planning, retrieval, apply, and dev primitives
- ReAct agent with a registered session toolkit
- LLM required at startup

Typical internal planning chain:
- `inspect_dataset -> retrieve_operators -> plan_build -> plan_validate -> plan_save`

Interrupt:
- plain mode: `Ctrl+C` interrupts the current turn, `Ctrl+D` exits
- tui mode: `Ctrl+C` interrupts the current turn, `Ctrl+D` exits

## Environment Variables

- `DASHSCOPE_API_KEY` or `MODELSCOPE_API_TOKEN`: API credential
- `DJA_OPENAI_BASE_URL`: OpenAI-compatible endpoint base URL
- `DJA_SESSION_MODEL`: model used by `dj-agents`
- `DJA_PLANNER_MODEL`: model used by `djx plan`
- `DJA_MODEL_FALLBACKS`: comma-separated fallback models for `llm_gateway.py`
- `DJA_LLM_THINKING`: toggles `enable_thinking` in model requests
