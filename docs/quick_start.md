# DJX Quick Start

## 1. Prerequisites

- Python `>=3.10,<3.13`
- Data-Juicer runtime (`py-data-juicer`)
- DashScope/OpenAI-compatible API key

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
# Optional overrides
export DJA_OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export DJA_SESSION_MODEL="qwen3-max-2026-01-23"
export DJA_PLANNER_MODEL="qwen3-max-2026-01-23"
export DJA_VALIDATOR_MODEL="qwen3-max-2026-01-23"
```

## 4. Fast CLI path: retrieve -> plan -> apply -> trace

```bash
# 1) Retrieve candidate operators
djx retrieve "remove duplicate text records" \
  --dataset ./data/demo-dataset.jsonl \
  --top-k 8

# 2) Generate plan
djx plan "deduplicate and clean text for RAG" \
  --dataset ./data/demo-dataset.jsonl \
  --export ./data/demo-dataset-processed.jsonl \
  --output ./data/demo-plan.yaml

# Optional: force template route
djx plan "rag cleaning" \
  --dataset ./data/demo-dataset.jsonl \
  --export ./data/demo-dataset-processed.jsonl \
  --from-template rag_cleaning \
  --output ./data/demo-rag-plan.yaml

# 3) Execute
djx apply --plan ./data/demo-plan.yaml --yes

# 4) Trace
djx trace <run_id>
djx trace --stats
```

## 5. Revision mode example (base plan)

```bash
djx plan "tighten length threshold to <= 1000 chars" \
  --base-plan ./data/demo-plan.yaml \
  --output ./data/demo-plan-v2.yaml
```

## 6. Session mode (`dj-agents`)

Default TUI:

```bash
dj-agents --dataset ./data/demo-dataset.jsonl --export ./data/demo-dataset-processed.jsonl
```

Plain terminal mode:

```bash
dj-agents --ui plain --dataset ./data/demo-dataset.jsonl --export ./data/demo-dataset-processed.jsonl
```

Notes:
- `dj-agents` requires LLM access (API key/model config).
- In session mode, press `Ctrl+C` to interrupt the current turn and `Ctrl+D` to exit.

## 7. DJX Studio (future)

- Studio API + Web frontend is deferred to a future release.
- Current quick start only covers `djx` and `dj-agents`.

## 8. Basic sanity checks

```bash
djx templates
djx trace --stats
djx --debug plan "filter long text" --dataset ./data/demo-dataset.jsonl --export ./data/out.jsonl
```

If planning/session fails with API/model errors, verify:
- `DASHSCOPE_API_KEY`
- endpoint/model settings
- local profile in `.djx/config.json`
