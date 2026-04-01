# DJX CLI Reference

## Command Map

| Command | Purpose | Source |
|---|---|---|
| `djx plan` | Generate a plan YAML from intent, retrieval evidence, staged specs, and an LLM-generated operator list | `data_juicer_agents/commands/plan_cmd.py` |
| `djx apply` | Load a saved plan, materialize a recipe, and execute or dry-run `dj-process` | `data_juicer_agents/commands/apply_cmd.py` |
| `djx retrieve` | Retrieve candidate operators by intent | `data_juicer_agents/commands/retrieve_cmd.py` |
| `djx dev` | Generate a non-invasive custom operator scaffold | `data_juicer_agents/commands/dev_cmd.py` |
| `djx tool` | Inspect or execute any registered atomic tool through a generic JSON-first wrapper | `data_juicer_agents/commands/tool_cmd.py` |

Additional entry:
- `dj-agents`: `data_juicer_agents/session_cli.py`
- `djx --version`: print the installed package version

The CLI does not include `trace`, `templates`, or `evaluate`.

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
1. internally retrieves operator candidates from the intent and optional dataset-derived modality signals
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
- the CLI does not run a separate `plan_validate` step automatically
- the CLI does not persist or expose a separate trace query command
- `--dry-run` also writes the recipe file

## `djx retrieve`

```bash
djx retrieve "<intent>" [--dataset <path>] [--type <op_type>] [--tags <tag> ...] [--top-k 10] [--mode auto|llm|vector|bm25|regex] [--json]
```

Key options:
- `--dataset`: optional dataset path; when provided, the CLI probes the dataset through the retrieval layer's dataset inspection logic to infer modality (text / image / multimodal / audio / video) and converts it into operator tags for filtering
- `--type`: filter by operator type (e.g. `filter`, `mapper`, `deduplicator`)
- `--tags`: filter by operator tags (e.g. `text`, `image`, `multimodal`); can be combined with `--dataset` (tags are merged)
- `--top-k`: maximum number of candidates (default: 10)
- `--mode`: retrieval backend selection
- `--json`: output the full payload as JSON instead of human-readable summary

Returns:
- ranked operator candidates
- retrieval source, trace, and notes
- when `--dataset` is provided and modality is detected, the payload includes `inferred_tags`
- `auto` uses `llm -> vector -> bm25 -> lexical` (without API key: `bm25 -> lexical`)
- `regex` uses Python regex pattern matching against operator name, description, and parameter fields (standalone mode, not part of auto fallback)

Dataset-aware filtering:
- when `--dataset` is provided, the CLI runs dataset inspection logic inside the retrieval layer to detect the dataset modality
- the detected modality is mapped to operator tags (e.g. `image` → `["image"]`, `multimodal` → `["multimodal"]`)
- these tags are passed to the retrieval backends, which filter the operator catalog so that only operators tagged with matching modalities are returned
- if modality detection fails, retrieval proceeds without tag filtering

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

## `djx tool`

```bash
djx tool list [--tag <tag>]
djx tool schema <tool-name>
djx tool run <tool-name> (--input-json '<json>' | --input-file <input.json>) [--working-dir <path>] [--yes]
```

Purpose:
- expose the atomic `ToolSpec` layer directly for agents, skills, and automation
- keep workflow commands such as `plan`, `apply`, `retrieve`, and `dev` unchanged
- avoid hand-maintaining one bespoke CLI adapter per tool

Default behavior:
- output is JSON for `list`, `schema`, and `run`
- write / execute tools are non-interactive; if a tool declares `confirmation=recommended|required`, you must pass `--yes`

Subcommands:
- `list`: returns registered tool metadata (`name`, `tags`, `effects`, `confirmation`, input/output model names)
- `schema`: returns tool metadata plus the input model JSON Schema
- `run`: loads JSON input, builds a minimal `ToolContext`, executes the tool, and returns the normalized tool payload

Exit codes:
- `0`: success
- `2`: CLI misuse, unknown tool, invalid JSON input, or input-model validation failure
- `3`: explicit confirmation required but not granted
- `4`: tool executed and returned a failure payload

Examples:

```bash
djx tool list --tag plan
djx tool schema inspect_dataset
djx tool run list_system_config --input-json '{}'
djx tool run inspect_dataset --input-json '{"dataset_path":"./data/demo-dataset.jsonl","sample_size":5}'
djx tool run write_text_file --yes --input-json '{"file_path":"./tmp.txt","content":"hello"}'
djx tool run plan_validate --input-file ./examples/plan_payload.json
```

Notes:
- the tool interface is JSON-only; it does not expand tool input fields into per-tool CLI flags
- the exposed context surface is limited to `--working-dir`
- `ToolContext.env` and `runtime_values` are not exposed through the CLI
- `tool run` is suitable for machine-to-machine use; stable JSON output is the primary contract
- `--quiet`, `--verbose`, and `--debug` are accepted for CLI-shape consistency with other `djx` subcommands, but they do not change `djx tool` output
- set `DJX_TOOL_PROFILE=harness` after installing `data-juicer-agents[harness]` to restrict `djx tool` to the harness groups (`apply`, `context`, `retrieve`, `plan`)
- tools outside the active profile return a structured JSON error instead of being exposed by `list`

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
- For operator discovery and schema lookup, prefer `retrieve_operators` / `retrieve_operators_api`, then `get_operator_info`.

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
- `DJX_TOOL_PROFILE`: optional tool-catalog profile; set to `harness` to expose only the harness tool set in `djx tool`
