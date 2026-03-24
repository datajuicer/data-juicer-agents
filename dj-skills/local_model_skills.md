---
name: local-model
description: "Install and configure Ollama as a local LLM backend for Data-Juicer Agents, enabling private data processing without exposing sensitive information to public APIs. Covers Ollama setup, model management, API switching between cloud and local endpoints, and integration with the existing DJA LLM gateway."
auto_load: false
---

# Local Model Skills — Private Data Processing with Ollama

When users need to process **sensitive or private data** with Data-Juicer Agents, they should switch to a local LLM to keep all data off the public internet. This skill sets up [Ollama](https://github.com/ollama/ollama) as a local OpenAI-compatible backend and manages the seamless switching between cloud and local models.

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│              Data-Juicer Agents                      │
│                                                      │
│  llm_gateway.py  ──→  DJA_OPENAI_BASE_URL           │
│       │                                              │
│       ├── Cloud Mode (default)                       │
│       │    → https://dashscope.aliyuncs.com/...      │
│       │    → DASHSCOPE_API_KEY required              │
│       │    → Models: qwen3-max, qwen-plus, etc.      │
│       │                                              │
│       └── Local Mode (private)                       │
│            → http://localhost:11434/v1                │
│            → No API key sent to external servers     │
│            → Models: qwen3.5:0.8b (runs on device)     │
└─────────────────────────────────────────────────────┘
```

**Key principle**: The existing `llm_gateway.py` already speaks the OpenAI-compatible protocol. Ollama exposes the same protocol at `http://localhost:11434/v1`. Switching is just a matter of changing environment variables — zero code changes required.

---

## 1. Install Ollama

### macOS

```bash
# Recommended: use Homebrew
brew install ollama

# Alternative: download from official site
curl -fsSL https://ollama.com/install.sh | sh
```

### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows

Download the installer from [https://ollama.com/download](https://ollama.com/download).

### Verify Installation

```bash
ollama --version
# Expected output: ollama version x.x.x
```

---

## 2. Start Ollama Server

```bash
# Start the Ollama daemon (runs on http://localhost:11434)
ollama serve
```

> **Note**: On macOS, if you installed via Homebrew or the desktop app, Ollama may already be running as a background service. Check with:
> ```bash
> curl -s http://localhost:11434/api/tags | python3 -m json.tool
> ```

---

## 3. Pull the Default Small Model

Use **Qwen3.5 0.8B** as the default lightweight model — it's the smallest Qwen3.5 variant, suitable for recipe generation and operator selection tasks while running efficiently on most hardware (including laptops without GPU).

```bash
# Pull Qwen3.5 0.8B (~1GB download)
ollama pull qwen3.5:0.8b
```

### Verify the Model

```bash
# List installed models
ollama list

# Quick test
ollama run qwen3.5:0.8b "Hello, respond in one sentence."
```

### Alternative Models (by resource budget)

| Model | Size | RAM Needed | Best For |
|-------|------|-----------|----------|
| `qwen3.5:0.8b` | ~1GB | ~2GB | Default — fast, lightweight, good for recipe generation |
| `qwen3.5:3b` | ~2GB | ~4GB | Better quality, still fast on most machines |
| `qwen3.5:7b` | ~5GB | ~8GB | High quality, needs decent hardware |
| `qwen3.5:14b` | ~9GB | ~16GB | Near cloud-level quality, needs GPU or Apple Silicon |

Pull any alternative with:
```bash
ollama pull qwen3.5:3b   # or whichever you prefer
```

---

## 4. API & Interface Management

### 4.1 How It Works

The DJA LLM gateway (`data_juicer_agents/utils/llm_gateway.py`) uses these environment variables:

| Variable | Cloud Default | Local Override | Purpose |
|----------|--------------|----------------|---------|
| `DJA_OPENAI_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `http://localhost:11434/v1` | API endpoint |
| `DASHSCOPE_API_KEY` | Your DashScope key | `ollama` (any non-empty string) | Auth token |
| `DJA_SESSION_MODEL` | `qwen3-max-2026-01-23` | `qwen3.5:0.8b` | Session model |
| `DJA_PLANNER_MODEL` | `qwen3-max-2026-01-23` | `qwen3.5:0.8b` | Planner model |
| `DJA_LLM_THINKING` | `true` | `false` | Disable thinking mode (local models don't support it) |
| `DJA_MODEL_FALLBACKS` | (cloud models) | `qwen3.5:3b,qwen3.5:7b` | Local fallback chain |

### 4.2 Switching: Environment Variable Profiles

Create shell profile files to toggle between modes quickly.

#### Cloud Mode (default) — `~/.dja_cloud_env`

```bash
# Cloud mode — data is sent to DashScope API
export DJA_OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export DASHSCOPE_API_KEY="your-actual-dashscope-key"
export DJA_SESSION_MODEL="qwen3-max-2026-01-23"
export DJA_PLANNER_MODEL="qwen3-max-2026-01-23"
export DJA_LLM_THINKING="true"
export DJA_MODEL_FALLBACKS=""
```

#### Local Mode (private) — `~/.dja_local_env`

```bash
# Local mode — ALL data stays on this machine
export DJA_OPENAI_BASE_URL="http://localhost:11434/v1"
export DASHSCOPE_API_KEY="ollama"
export DJA_SESSION_MODEL="qwen3.5:0.8b"
export DJA_PLANNER_MODEL="qwen3.5:0.8b"
export DJA_LLM_THINKING="false"
export DJA_MODEL_FALLBACKS="qwen3.5:3b,qwen3.5:7b"
```

#### Quick Switch Commands

```bash
# Switch to local (private) mode
source ~/.dja_local_env
echo "✓ Switched to LOCAL mode — data stays on device"

# Switch back to cloud mode
source ~/.dja_cloud_env
echo "✓ Switched to CLOUD mode — using DashScope API"

# Check current mode
echo "Current endpoint: $DJA_OPENAI_BASE_URL"
echo "Current model:    $DJA_SESSION_MODEL"
```

> **Tip**: Add shell aliases for convenience:
> ```bash
> # Add to ~/.zshrc or ~/.bashrc
> alias dja-local='source ~/.dja_local_env && echo "✓ LOCAL mode"'
> alias dja-cloud='source ~/.dja_cloud_env && echo "✓ CLOUD mode"'
> ```

### 4.3 Programmatic Switching (Python)

For scripts or agents that need to switch at runtime:

```python
import os


def switch_to_local_model(model: str = "qwen3.5:0.8b"):
    """Switch DJA to use a local Ollama model. No data leaves this machine."""
    os.environ["DJA_OPENAI_BASE_URL"] = "http://localhost:11434/v1"
    os.environ["DASHSCOPE_API_KEY"] = "ollama"
    os.environ["DJA_SESSION_MODEL"] = model
    os.environ["DJA_PLANNER_MODEL"] = model
    os.environ["DJA_LLM_THINKING"] = "false"
    print(f"✓ Switched to local model: {model}")


def switch_to_cloud_model(
    api_key: str | None = None,
    model: str = "qwen3-max-2026-01-23",
):
    """Switch DJA back to cloud API."""
    os.environ["DJA_OPENAI_BASE_URL"] = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    if api_key:
        os.environ["DASHSCOPE_API_KEY"] = api_key
    os.environ["DJA_SESSION_MODEL"] = model
    os.environ["DJA_PLANNER_MODEL"] = model
    os.environ["DJA_LLM_THINKING"] = "true"
    print(f"✓ Switched to cloud model: {model}")


def is_local_mode() -> bool:
    """Check if currently using local model."""
    base_url = os.environ.get("DJA_OPENAI_BASE_URL", "")
    return "localhost" in base_url or "127.0.0.1" in base_url
```

### 4.4 Health Check Before Use

Always verify the local model is ready before switching:

```python
import urllib.request
import json


def check_ollama_ready(model: str = "qwen3.5:0.8b") -> bool:
    """Check if Ollama is running and the model is available."""
    try:
        # Check Ollama server is up
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            available = [m["name"] for m in data.get("models", [])]

        if model in available or any(model in m for m in available):
            print(f"✓ Ollama running, model '{model}' available")
            return True
        else:
            print(f"✗ Model '{model}' not found. Available: {available}")
            print(f"  Run: ollama pull {model}")
            return False
    except Exception as e:
        print(f"✗ Ollama not reachable: {e}")
        print("  Run: ollama serve")
        return False
```

---

## 5. Private Data Probing with Local Model

The most critical use of the local model is **data probing** — inspecting dataset content to understand its structure, language, domain, and quality before building a processing pipeline. This is the step where actual data content is analyzed by an LLM, and it **must** happen locally for sensitive data.

### Why Data Probing Matters

Before building a Data-Juicer recipe, the agent needs to understand:
- What language is the data in?
- What domain does it belong to (medical, financial, legal, etc.)?
- What quality issues exist (duplicates, HTML artifacts, encoding errors)?
- What fields contain the main content?
- What is the typical text length distribution?

In the normal workflow, this probing may use a cloud LLM (fast, high quality). But for private data, **every byte of content must stay on the machine**, so the local model handles all probing.

### 5.1 Structure Probe (No LLM Needed)

First, extract pure metadata without touching content. This is safe even without a local model:

```python
import json

def probe_structure(dataset_path: str) -> dict:
    """Probe dataset structure without reading content. Safe for any data."""
    with open(dataset_path) as f:
        samples = [json.loads(line) for line in f][:5]

    total = sum(1 for _ in open(dataset_path))
    fields = list(samples[0].keys())
    field_types = {k: type(v).__name__ for k, v in samples[0].items()}

    # Detect modality from field names only
    field_set = set(fields)
    modality = {
        "text": bool(field_set & {"text", "content", "instruction", "input", "output"}),
        "image": bool(field_set & {"image", "images", "image_url", "img", "img_path"}),
        "audio": bool(field_set & {"audio", "audio_url", "audio_path"}),
    }

    # Basic stats without exposing content
    text_field = next((f for f in ["text", "content", "instruction"] if f in field_set), None)
    length_stats = None
    if text_field:
        lengths = [len(str(s.get(text_field, ""))) for s in samples]
        length_stats = {
            "min": min(lengths),
            "max": max(lengths),
            "avg": sum(lengths) // len(lengths),
        }

    return {
        "total_records": total,
        "fields": fields,
        "field_types": field_types,
        "modality": modality,
        "text_field_candidate": text_field,
        "sample_length_stats": length_stats,
    }

info = probe_structure("./sensitive_data.jsonl")
print(json.dumps(info, indent=2))
```

### 5.2 Content Probe via Local LLM

When you need deeper understanding (language detection, domain classification, quality assessment), use the local model:

```python
import json
from data_juicer_agents.utils.llm_gateway import call_model_json


def probe_content_locally(dataset_path: str, model: str = "qwen3.5:0.8b") -> dict:
    """
    Probe dataset content using a LOCAL model only.
    Prerequisite: Ollama is running and local mode env vars are set.
    """
    with open(dataset_path) as f:
        samples = [json.loads(line) for line in f][:3]

    # Send samples to LOCAL model only (localhost:11434)
    result = call_model_json(
        model_name=model,
        prompt=f"""You are a data analyst. Analyze these dataset samples and return a JSON object with:
{{
  "language": "detected primary language (e.g., en, zh, ja, mixed)",
  "domain": "content domain (e.g., medical, financial, legal, general, technical)",
  "text_field": "which field contains the main text content",
  "content_type": "what kind of content (articles, QA pairs, logs, records, etc.)",
  "quality_issues": ["list of observed quality issues"],
  "recommended_cleaning": ["list of suggested cleaning operations"],
  "avg_text_length": approximate average character count of main text
}}

Dataset samples:
{json.dumps(samples, ensure_ascii=False, indent=2)}""",
        thinking=False,
    )
    return result


# Ensure we're in local mode before probing
assert is_local_mode(), "Switch to local mode first! Call switch_to_local_model()"

probe = probe_content_locally("./sensitive_data.jsonl")
print(f"Language: {probe.get('language')}")
print(f"Domain: {probe.get('domain')}")
print(f"Recommended cleaning: {probe.get('recommended_cleaning')}")
```

### 5.3 Probe-Then-Build Pattern

The full private data workflow follows this pattern:

```
1. Structure Probe (no LLM)     → understand fields, modality, record count
2. Content Probe (local LLM)    → understand language, domain, quality
3. Operator Selection            → choose operators based on probe results
4. Recipe Generation (local LLM) → generate YAML recipe
5. Recipe Execution (dj-process) → runs locally, no LLM involved
6. Result Verification           → check output quality
```

Example combining probes into recipe generation:

```python
import json

# Step 1: Structure probe
structure = probe_structure("./sensitive_data.jsonl")
print(f"Dataset: {structure['total_records']} records, fields: {structure['fields']}")

# Step 2: Content probe (local LLM)
content = probe_content_locally("./sensitive_data.jsonl")

# Step 3-4: Use probe results to generate recipe (local LLM)
recipe_result = call_model_json(
    model_name="qwen3.5:0.8b",
    prompt=f"""Based on this dataset analysis, generate a Data-Juicer YAML recipe as JSON.

Dataset info:
- Records: {structure['total_records']}
- Fields: {structure['fields']}
- Text field: {content.get('text_field', 'text')}
- Language: {content.get('language', 'unknown')}
- Domain: {content.get('domain', 'general')}
- Quality issues: {content.get('quality_issues', [])}

Return JSON with:
{{
  "project_name": "a short project name",
  "text_keys": ["the text field name"],
  "np": 4,
  "process": [list of operator dicts like {{"operator_name": {{params}}}}]
}}

Choose operators from: fix_unicode_mapper, whitespace_normalization_mapper,
clean_html_mapper, text_length_filter, words_num_filter, document_deduplicator,
document_minhash_deduplicator, special_characters_filter, language_id_score_filter""",
    thinking=False,
)
print(f"Generated recipe: {json.dumps(recipe_result, indent=2)}")
```

---

## 6. Integration with DJA Workflow

### Typical Usage: Processing Sensitive Data

```python
# 1. Verify local model is ready
assert check_ollama_ready("qwen3.5:0.8b"), "Start Ollama first!"

# 2. Switch to local mode
switch_to_local_model("qwen3.5:0.8b")

# 3. Probe the dataset locally (see Section 5 for details)
structure = probe_structure("./sensitive_data.jsonl")
content = probe_content_locally("./sensitive_data.jsonl")
print(f"Probed: {structure['total_records']} records, domain={content.get('domain')}")

# 4. Retrieve operators — auto mode falls back to lexical search locally
from data_juicer_agents.tools.retrieve import RETRIEVE_OPERATORS
from data_juicer_agents.core.tool import ToolContext

ctx = ToolContext(working_dir="./.djx")
result = RETRIEVE_OPERATORS.execute(
    ctx=ctx,
    raw_input={
        "intent": "clean and deduplicate text data",  # describe TASK, not DATA content
        "top_k": 5,
        "mode": "auto",
        "dataset_path": "./sensitive_data.jsonl",
    },
)

# 5. Generate recipe and process data — everything stays local
# ...

# 6. Switch back to cloud when done with private data (optional)
switch_to_cloud_model()
```

### Using CLI with Local Mode

```bash
# Activate local mode
source ~/.dja_local_env

# Now all djx / dj-agents commands use the local model
# The agent will probe your data locally before generating a recipe
djx plan --intent "clean and deduplicate text data" --dataset ./private.jsonl --export ./cleaned.jsonl
dj-process --config recipe.yaml

# Verify no external API calls were made (optional)
# Ollama logs are at: ~/.ollama/logs/server.log
```

> **Reminder**: When using CLI in local mode, describe your processing **intent** in generic terms (e.g., "clean and deduplicate text data") rather than revealing data content (e.g., "clean patient medical records with SSN"). The intent string may be logged.

---

## 7. Security Notes

| Concern | Mitigation |
|---------|-----------|
| Data leakage via LLM API | Local mode sends all requests to `localhost:11434` — nothing leaves the machine |
| API key exposure | In local mode, `DASHSCOPE_API_KEY=ollama` is a dummy value — no real key is sent |
| Ollama listens on network | By default, Ollama binds to `127.0.0.1` only. To restrict explicitly: `OLLAMA_HOST=127.0.0.1:11434 ollama serve` |
| Model quality vs cloud | Local 0.6B model is less capable than cloud models. For critical tasks, review generated recipes before execution |
| Embedding retrieval | The operator vector retrieval (`retrieve_operators` with `mode: vector`) uses DashScope embeddings. In strict private mode, use `mode: auto` which falls back to lexical search when no API key is available |

### Strict Isolation Mode

For maximum privacy, unset all cloud API keys so no accidental cloud calls can happen:

```bash
# Strict local-only mode
source ~/.dja_local_env
unset DASHSCOPE_API_KEY_BACKUP 2>/dev/null
export DASHSCOPE_API_KEY="ollama"
export MODELSCOPE_API_TOKEN=""

# Now the only reachable LLM endpoint is localhost
```

---

## 8. Troubleshooting

| Issue | Fix |
|-------|-----|
| `ollama: command not found` | Install Ollama: `brew install ollama` (macOS) or `curl -fsSL https://ollama.com/install.sh \| sh` (Linux) |
| `Connection refused` on port 11434 | Start Ollama: `ollama serve` |
| Model not found | Pull it: `ollama pull qwen3.5:0.8b` |
| Very slow inference | Try a smaller model or check `ollama ps` for resource usage |
| JSON parse error from local model | Small models may produce malformed JSON. Try `qwen3.5:3b` or `qwen3.5:7b` for better structured output |
| `enable_thinking` error | Set `DJA_LLM_THINKING=false` — local models don't support extended thinking |
| Ollama using too much RAM | Stop unused models: `ollama stop qwen3.5:0.8b`; or set `OLLAMA_NUM_PARALLEL=1` |
| Want GPU acceleration | Ollama auto-detects CUDA/Metal. Check: `ollama ps` shows `gpu` column |
