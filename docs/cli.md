# DJX CLI Reference

## Command Map

| Command | Purpose | Source |
|---|---|---|
| `djx plan` | Generate/revise a plan YAML (LLM-driven) | `data_juicer_agents/commands/plan_cmd.py` |
| `djx apply` | Validate and execute a plan via `dj-process` | `data_juicer_agents/commands/apply_cmd.py` |
| `djx trace` | Query run detail/list/stats | `data_juicer_agents/commands/trace_cmd.py` |
| `djx templates` | List/show built-in workflow templates | `data_juicer_agents/commands/templates_cmd.py` |
| `djx retrieve` | Retrieve candidate operators by intent | `data_juicer_agents/commands/retrieve_cmd.py` |
| `djx dev` | Generate non-invasive custom operator scaffold | `data_juicer_agents/commands/dev_cmd.py` |
| `djx evaluate` | Run batch evaluation cases | `data_juicer_agents/commands/evaluate_cmd.py` |

Additional entries:
- `dj-agents`: `data_juicer_agents/session_cli.py`

## Global Output Levels (`djx`)

All `djx` subcommands support output levels:
- `--quiet` (default): summary output
- `--verbose`: expanded execution output
- `--debug`: raw structured call details

Examples:

```bash
djx apply --plan ./plan.yaml --yes --quiet
djx apply --plan ./plan.yaml --yes --verbose
djx --debug plan "deduplicate" --dataset ./data.jsonl --export ./out.jsonl
```

## `djx plan`

```bash
djx plan "<intent>" --dataset <input.jsonl> --export <output.jsonl> [options]
```

Key options:
- `--output`: output plan path (default: `plans/<plan_id>.yaml`)
- `--base-plan`: revise from existing plan
- `--from-run-id`: revision context from run trace (requires `--base-plan`)
- `--custom-operator-paths`: custom operator dirs/files for validation/execution
- `--from-template`: force template (`rag_cleaning` / `multimodal_dedup`)
- `--template-retrieve`: intent->template retrieval before full-LLM fallback
- `--llm-review` / `--no-llm-review`: toggle semantic LLM review after generation

Conflict rules:
- `--base-plan` conflicts with `--from-template` and `--template-retrieve`.
- if both `--from-template` and `--template-retrieve` are set, template-retrieve is ignored.

Planning stage order:
1. base-plan revision (if `--base-plan`)
2. explicit template (if `--from-template`)
3. template retrieve (if `--template-retrieve`)
4. full-LLM generation fallback

Notes:
- planning is always LLM-involved (template+LLM patch or full-LLM).
- final failure returns structured error metadata (`error_type/error_code/stage/next_actions`).

## `djx apply`

```bash
djx apply --plan <plan.yaml> [--yes] [--dry-run] [--timeout 300]
```

Behavior:
- validates plan before execution
- executes `dj-process`
- stores successful runs in `.djx/runs.jsonl`
- prints `Run ID` and trace command hint

## `djx trace`

```bash
djx trace <run_id>
djx trace --plan-id <plan_id> [--limit 20]
djx trace --stats [--plan-id <plan_id>]
```

Use cases:
- inspect one run
- list recent runs by `plan_id`
- aggregate success/error statistics

## `djx templates`

```bash
djx templates
djx templates rag_cleaning
```

## `djx retrieve`

```bash
djx retrieve "<intent>" [--dataset <path>] [--top-k 10] [--mode auto|llm|vector] [--json]
```

Returns:
- ranked operator candidates
- optional dataset profile (when dataset path is provided)
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

Default behavior is non-invasive (generate code + guidance, no auto install).

## `djx evaluate`

```bash
djx evaluate --cases <cases.jsonl> [options]
```

Important options:
- `--execute none|dry-run|run`
- `--planning-mode template-llm|full-llm`
- `--retries`, `--jobs`, `--timeout`
- `--output`, `--errors-output`, `--history-file`, `--no-history`

Compatibility:
- `--llm-full-plan` is a deprecated alias of `--planning-mode full-llm`.

## `dj-agents`

```bash
dj-agents [--dataset <path>] [--export <path>] [--verbose] [--ui plain|tui]
```

Behavior:
- natural-language conversation over atomic tools
- internal ReAct tool orchestration
- LLM required (missing key/model config causes startup failure)

Interrupt:
- plain mode: press `ESC` to interrupt current turn
- tui mode: press `ESC` to interrupt current turn

## Future Scope

- `DJX Studio` (API + Web UI) is deferred to a future release.
