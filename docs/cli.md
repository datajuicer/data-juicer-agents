# DJX CLI Reference

## Command Map

| Command | Purpose | Source |
|---|---|---|
| `djx plan` | Generate a plan YAML from intent, retrieval evidence, staged specs, and an LLM-generated operator list | `data_juicer_agents/commands/plan_cmd.py` |
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
2. builds a deterministic dataset spec from dataset IO and profile signals
3. calls the model once to generate only the operator list for the process spec
4. builds the process spec, builds the system spec, and assembles the final plan
5. validates the final plan and writes the plan YAML

CLI output:
- summary: `Plan generated`, `Modality`, `Operators`
- `--verbose`: planning meta (`planner_model`, `retrieval_source`, `retrieval_candidate_count`)
- `--debug`: retrieval payload, dataset spec, process spec, system spec, validation payload, and planning meta payload

Failure behavior:
- exits non-zero and prints a user-facing error message

## `djx apply`

```bash
djx apply --plan <plan.yaml> [--yes] [--dry-run] [--timeout 300]
```

Behavior:
- loads the saved plan YAML and requires a mapping payload
- writes a recipe to `.djx/recipes/<plan_id>.yaml`
- executes `dj-process` unless `--dry-run` is set
- prints `Execution ID`, `Status`, and generated recipe path

Notes:
- current CLI does not run a separate `plan_validate` step automatically
- current CLI does not persist or expose a separate trace query command
- `--dry-run` still writes the recipe file

## `djx retrieve`

```bash
djx retrieve "<intent>" [--dataset <path>] [--top-k 10] [--mode auto|llm|vector] [--json]
```

Returns:
- ranked operator candidates
- retrieval source, trace, and notes
- current output payload does not include dataset profile

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
dj-agents [--dataset <path>] [--export <path>] [--verbose] [--ui plain|tui|as_studio] [--studio-url <url>]
```

Behavior:
- natural-language conversation over the same planning, retrieval, apply, and dev primitives
- ReAct agent with a registered session toolkit
- LLM required at startup

Typical internal planning chain:
- `inspect_dataset -> retrieve_operators -> build_dataset_spec -> build_process_spec -> build_system_spec -> assemble_plan -> plan_validate -> plan_save`

Interrupt:
- plain mode: `Ctrl+C` interrupts the current turn, `Ctrl+D` exits
- tui mode: `Ctrl+C` interrupts the current turn, `Ctrl+D` exits
- as_studio mode: interaction is driven by AgentScope Studio

## Environment Variables

- `DASHSCOPE_API_KEY` or `MODELSCOPE_API_TOKEN`: API credential
- `DJA_OPENAI_BASE_URL`: OpenAI-compatible endpoint base URL
- `DJA_SESSION_MODEL`: model used by `dj-agents`
- `DJA_STUDIO_URL`: AgentScope Studio URL used by `dj-agents --ui as_studio`
- `DJA_PLANNER_MODEL`: model used by `djx plan`
- `DJA_MODEL_FALLBACKS`: comma-separated fallback models for `data_juicer_agents/utils/llm_gateway.py`
- `DJA_LLM_THINKING`: toggles `enable_thinking` in model requests
