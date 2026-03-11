# Quick Start

## 1. Prerequisites

- Python `>=3.10,<3.13`
- Data-Juicer runtime (`py-data-juicer`)
- A DashScope or OpenAI-compatible API key

## 2. Install

```bash
cd ./data-juicer-agents
uv venv .venv
source .venv/bin/activate
uv pip install -e .
```

## 3. Configure model access

```bash
export DASHSCOPE_API_KEY="<your_key>"
# or:
# export MODELSCOPE_API_TOKEN="<your_key>"

# Optional overrides
export DJA_OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export DJA_SESSION_MODEL="qwen3-max-2026-01-23"
export DJA_PLANNER_MODEL="qwen3-max-2026-01-23"
export DJA_MODEL_FALLBACKS="qwen-max,qwen-plus"
export DJA_LLM_THINKING="true"
```

## 4. Minimal CLI path

Optional inspection step:

```bash
djx retrieve "remove duplicate text records" \
  --dataset ./data/demo-dataset.jsonl \
  --top-k 8
```

Generate a plan:

```bash
djx plan "deduplicate and clean text for RAG" \
  --dataset ./data/demo-dataset.jsonl \
  --export ./data/demo-dataset-processed.jsonl \
  --output ./data/demo-plan.yaml
```

Apply the saved plan:

```bash
djx apply --plan ./data/demo-plan.yaml --yes
```

Dry-run without executing `dj-process`:

```bash
djx apply --plan ./data/demo-plan.yaml --yes --dry-run
```

Notes:
- `djx plan` already performs internal operator retrieval before building the final plan.
- `djx retrieve` is still useful for inspection and debugging.

## 5. Session mode (`dj-agents`)

Default TUI:

```bash
dj-agents --dataset ./data/demo-dataset.jsonl --export ./data/demo-dataset-processed.jsonl
```

Plain terminal mode:

```bash
dj-agents --ui plain --dataset ./data/demo-dataset.jsonl --export ./data/demo-dataset-processed.jsonl
```

Notes:
- `dj-agents` requires LLM access.
- In session mode, press `Ctrl+C` to interrupt the current turn and `Ctrl+D` to exit.
- The session agent usually plans with `inspect_dataset -> retrieve_operators -> plan_build -> plan_validate -> plan_save`.

## 6. Basic sanity checks

```bash
djx --help
djx retrieve "filter long text" --dataset ./data/demo-dataset.jsonl --json
djx plan "filter long text" --dataset ./data/demo-dataset.jsonl --export ./data/out.jsonl --verbose
djx apply --plan ./data/demo-plan.yaml --yes --dry-run
dj-agents --help
```

## 7. Troubleshooting

If planning or session startup fails with API/model errors, verify:
- `DASHSCOPE_API_KEY` or `MODELSCOPE_API_TOKEN`
- `DJA_OPENAI_BASE_URL`
- `DJA_SESSION_MODEL` and `DJA_PLANNER_MODEL`
- `DJA_MODEL_FALLBACKS` when you expect model fallback
- `DJA_LLM_THINKING` if your provider rejects the thinking flag
