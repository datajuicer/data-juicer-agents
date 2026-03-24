---
name: data-juicer
description: "End-to-end data processing skill powered by Data-Juicer. Guides the agent through environment setup, dataset inspection, operator selection, YAML recipe generation, and dj-process execution to clean, filter, deduplicate, and transform datasets autonomously."
auto_load: true
---

# Data-Juicer Agent Skills

Data-Juicer is a data-centric processing toolkit for building high-quality datasets. These skills guide you to clean, filter, deduplicate, and transform datasets end-to-end.

## Core Workflow

```
User Request
  ↓
Parse Intent (what to do with data)
  ↓
Privacy Check ← Does the user indicate data is sensitive/private?
  │
  ├── YES (private data) ──→ Switch to Local Model (Ollama)
  │   │                      • Set DJA_OPENAI_BASE_URL=http://localhost:11434/v1
  │   │                      • No data leaves the machine
  │   ↓
  │   Local Data Probe (inspect with local LLM only)
  │   ↓
  │   Select Operators (lexical retrieval, no cloud embeddings)
  │   ↓
  │   Generate YAML Recipe (via local model)
  │
  ├── NO (normal data) ──→ Inspect Dataset (cloud LLM ok)
  │   ↓
  │   Select Operators (LLM/vector retrieval)
  │   ↓
  │   Generate YAML Recipe
  │
  └──→ (both paths converge)
       ↓
       Run dj-process --config recipe.yaml
       ↓
       Verify & Return Results
```

> **IMPORTANT**: If the user mentions any privacy-related keywords (sensitive, private, confidential, PII, medical, financial, internal, proprietary, etc.), you **MUST** take the left (local) path. Never send private data samples to a cloud API for probing or analysis. See the [Local Model Skills](./local_model_skills.md) for setup instructions.

---

## 1. Environment Setup

### Prerequisites

- **Python**: 3.10 – 3.12 (3.11 recommended)
- **Package Manager**: [uv](https://github.com/astral-sh/uv) — if not installed, run: `curl -LsSf https://astral.sh/uv/install.sh | sh`

### Step 1: Create Virtual Environment

```bash
uv venv --python 3.11 .venv
source .venv/bin/activate    # macOS / Linux
# .venv\Scripts\activate     # Windows
```

### Step 2: Install Data-Juicer

The PyPI package is `py-data-juicer` (latest: v1.5.1).

**Basic installation:**
```bash
uv pip install py-data-juicer
```

> **Note:** This might take a while as it compiles some dependencies. Please be patient and wait for the installation to complete.

**With optional extras** (install what you need):
```bash
# Single extra
uv pip install "py-data-juicer[vision]"

# Multiple extras
uv pip install "py-data-juicer[vision,nlp]"

# Full installation (all features)
uv pip install "py-data-juicer[all]"
```

**Available Extras:**

| Extra | Purpose | Required For |
|-------|---------|-------------|
| `generic` | ML/DL frameworks (torch, transformers, vllm) | General ML operations |
| `vision` | Computer Vision (opencv, ultralytics, diffusers) | Image processing operators |
| `nlp` | NLP/Text (nltk, fasttext, kenlm, spacy-pkuseg) | `perplexity_filter`, `language_id_score_filter` |
| `audio` | Audio processing (torchaudio, soundfile) | Audio operators |
| `distributed` | Distributed computing (ray, pyspark) | `executor_type: ray` |
| `ai_services` | AI integrations (dashscope, openai) | API-based operators |
| `dev` | Development tools (pytest, black, sphinx) | Contributing |
| `all` | All of the above | Full feature set |

### Step 3: Install Data-Juicer-Agents (MANDATORY)

Required for programmatic access to operator retrieval and recipe tools:

```bash
uv pip install data-juicer-agents
```

> **Note:** This might take a while as it downloads models and dependencies. Please be patient and wait for the installation to complete.

### Verify Installation

```bash
# Check CLI tools are available
dj-process --help
dj-analyze --help

# Check Data-Juicer version
python -c "import data_juicer; print(data_juicer.__version__)"

# Check data-juicer-agents
python -c "import data_juicer_agents; print('data-juicer-agents OK')"
```

### Available CLI Tools

Installing `py-data-juicer` provides these command-line tools:

| Command | Purpose |
|---------|--------|
| `dj-process` | Execute YAML recipe pipelines |
| `dj-analyze` | Analyze datasets |
| `dj-install` | Install operator-specific dependencies |
| `dj-mcp` | MCP server for tool integrations |

### Setup Troubleshooting

| Issue | Fix |
|---|---|
| `command not found: dj-process` | Ensure venv is activated; re-run `uv pip install py-data-juicer` |
| `command not found: uv` | Install uv: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python version mismatch | Use `python3.11` explicitly |
| `ModuleNotFoundError: kenlm` | Install nlp extra: `uv pip install "py-data-juicer[nlp]"` |
| `ModuleNotFoundError: cv2` | Install vision extra: `uv pip install "py-data-juicer[vision]"` |
| `perplexity_filter` fails | Requires nlp extra: `uv pip install "py-data-juicer[nlp]"` |
| `language_id_score_filter` fails | Requires nlp extra: `uv pip install "py-data-juicer[nlp]"` |
| Ray executor not available | Install distributed extra: `uv pip install "py-data-juicer[distributed]"` |

---

## 2. Generate YAML Recipe

This section guides you to create a dj-process compatible YAML recipe from a user's data processing intent.

### Core Flow

```
User Intent → Privacy Check → [if private: activate local model] → Inspect Dataset → Retrieve Operators → Choose Operators → Write YAML → Validate → Save
```

### Step 1: Parse User Intent

Identify from the user's request:
- **Input dataset path** (JSONL file)
- **Output path** (where to save processed data)
- **Processing goals** (clean text? remove duplicates? filter quality? etc.)
- **Data sensitivity** (is the data private, sensitive, or confidential?)

#### Privacy Detection

Scan the user's request for any of these signals:
- **Explicit keywords**: "sensitive", "private", "confidential", "secret", "internal", "proprietary"
- **Data types**: "PII", "medical records", "patient data", "financial data", "personal information", "salary", "SSN", "ID card"
- **Compliance**: "GDPR", "HIPAA", "SOC2", "compliance", "regulated"
- **Intent signals**: "don't want data to leave", "keep local", "no cloud", "air-gapped", "offline processing"

**If ANY privacy signal is detected** → set `private_mode = True` and proceed to Step 1.5 below.
**Otherwise** → skip Step 1.5 and proceed directly to Step 2.

### Step 1.5: Activate Local Model (Private Data Only)

> **This step is MANDATORY when the user's data is sensitive.** You must complete it BEFORE inspecting the dataset or sending any data content to an LLM.

1. **Check Ollama is running** and the local model is available:

```python
import urllib.request
import json

def check_ollama_ready(model: str = "qwen3.5:0.8b") -> bool:
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            available = [m["name"] for m in data.get("models", [])]
        return model in available or any(model in m for m in available)
    except Exception:
        return False

assert check_ollama_ready("qwen3.5:0.8b"), (
    "Ollama is not running or qwen3.5:0.8b is not installed. "
    "See local_model_skills.md for setup instructions."
)
```

2. **Switch to local mode** — redirect ALL LLM calls to localhost:

```python
import os

os.environ["DJA_OPENAI_BASE_URL"] = "http://localhost:11434/v1"
os.environ["DASHSCOPE_API_KEY"] = "ollama"
os.environ["DJA_SESSION_MODEL"] = "qwen3.5:0.8b"
os.environ["DJA_PLANNER_MODEL"] = "qwen3.5:0.8b"
os.environ["DJA_LLM_THINKING"] = "false"
print("✓ Local mode active — all data stays on this machine")
```

Or via shell:
```bash
source ~/.dja_local_env   # see local_model_skills.md for setup
```

3. **Confirm** to the user that private mode is active and no data will be sent to external APIs.

> **From this point forward**, all steps (Inspect Dataset, Retrieve Operators, Generate Recipe) will use the local model. Data samples, field values, and content are never sent to the cloud.

### Step 2: Inspect Dataset

Examine the dataset to understand its structure.

> **⚠️ PRIVATE DATA**: If `private_mode = True` (from Step 1), you MUST have completed Step 1.5 first. All dataset inspection below should use ONLY local tools. **Never** print, log, or send data samples to any cloud API. The local LLM at `localhost:11434` is the only model you may use for content understanding.

#### 2a. Structure Probe (safe for all data — no LLM needed)

This step reads only metadata (field names, record count, field types). No actual content is sent anywhere:

```python
import json

with open("input.jsonl") as f:
    samples = [json.loads(line) for line in f][:5]

total_records = sum(1 for _ in open("input.jsonl"))

# Structure only — field names and types, NOT content values
print(f"Total records: {total_records}")
print(f"Fields: {list(samples[0].keys())}")
print(f"Field types: {  {k: type(v).__name__ for k, v in samples[0].items()}  }")

# Detect modality from field names (no content inspection)
field_names = set(samples[0].keys())
has_text = bool(field_names & {"text", "content", "instruction", "input", "output"})
has_image = bool(field_names & {"image", "images", "image_url", "img", "img_path"})
has_audio = bool(field_names & {"audio", "audio_url", "audio_path"})
print(f"Detected modality: text={has_text}, image={has_image}, audio={has_audio}")
```

#### 2b. Content Probe (cloud LLM ok for normal data; local LLM ONLY for private data)

If you need to understand content patterns (e.g., language, domain, quality):

```python
import json

with open("input.jsonl") as f:
    samples = [json.loads(line) for line in f][:3]

# For PRIVATE data: only show to local model, never cloud
# The environment was already switched in Step 1.5
print("Sample (first record):")
print(json.dumps(samples[0], indent=2, ensure_ascii=False))
```

For private data, use the local model to analyze content patterns:

```python
# This call goes to localhost:11434 (Ollama) when in private mode
from data_juicer_agents.utils.llm_gateway import call_model_json

# The local model analyzes the data — nothing leaves this machine
probe_result = call_model_json(
    model_name="qwen3.5:0.8b",
    prompt=f"""Analyze this dataset sample and return JSON with:
- "language": detected language
- "domain": content domain (e.g., medical, financial, general)
- "text_field": which field contains the main text
- "avg_length": approximate average text length
- "quality_notes": any quality issues noticed

Sample:
{json.dumps(samples[:2], ensure_ascii=False)}""",
    thinking=False,
)
print(f"Local probe result: {probe_result}")
```

Key things to determine:
- **text_keys**: Which fields contain the main text (e.g., `["text"]`)
- **image_key**: Field for image paths/URLs (if multimodal)
- **Modality**: text-only, image, multimodal

### Step 3: Retrieve Operator Candidates

Use the `retrieve_operators` tool to find suitable operators based on the user's intent.

> **⚠️ PRIVATE DATA**: When `private_mode = True`, operator retrieval must NOT use cloud-based embeddings or LLMs. Use `mode: "auto"` which automatically falls back to lexical search when no cloud API key is available, or explicitly pass the intent without including actual data content in the retrieval query.

```python
from data_juicer_agents.tools.retrieve import RETRIEVE_OPERATORS
from data_juicer_agents.core.tool import ToolContext

ctx = ToolContext(working_dir="./.djx")

# For private data: describe the TASK, not the DATA CONTENT
# Good: "remove duplicate documents and filter short texts"
# Bad:  "remove duplicates from medical patient records containing SSN..."
result = RETRIEVE_OPERATORS.execute(
    ctx=ctx,
    raw_input={
        "intent": "remove duplicate documents and filter short texts",
        "top_k": 5,
        "mode": "auto",       # auto falls back to lexical search in local mode
        "dataset_path": "./input.jsonl"
    }
)

if result.ok:
    for candidate in result.data.get("payload", {}).get("candidates", []):
        print(f"  {candidate['operator_name']}: {candidate['description']}")
        print(f"    Type: {candidate['operator_type']}, Score: {candidate.get('relevance_score', 'N/A')}")
        if candidate.get('arguments_preview'):
            print(f"    Params: {', '.join(candidate['arguments_preview'][:3])}")
```

**Retrieval Modes:**
- `auto`: Automatically chooses the best retrieval method (LLM or vector-based)
- `llm`: Uses LLM-based semantic retrieval
- `vector`: Uses vector similarity search

**Response Structure:**
```python
{
    "ok": True,
    "intent": "...",
    "candidate_count": 5,
    "candidate_names": ["document_deduplicator", "text_length_filter", ...],
    "payload": {
        "candidates": [
            {
                "rank": 1,
                "operator_name": "document_deduplicator",
                "operator_type": "deduplicator",
                "description": "Exact document deduplication",
                "relevance_score": 0.95,
                "arguments_preview": ["lowercase: bool", "ignore_non_character: bool"]
            }
        ]
    }
}
```

### Step 4: Choose Operators

Based on the retrieval results and user's goals, select operators. Common patterns:

**Text Cleaning Pipeline:**
- `fix_unicode_mapper` → `whitespace_normalization_mapper` → `clean_html_mapper` → `text_length_filter` → `words_num_filter`

**Deduplication Pipeline:**
- `document_deduplicator` (exact) or `document_minhash_deduplicator` (fuzzy)

**Quality Filtering Pipeline:**
- `language_id_score_filter` → `perplexity_filter` → `alphanumeric_filter` → `text_length_filter`

**Full Pipeline (clean + filter + dedup):**
- `fix_unicode_mapper` → `clean_html_mapper` → `whitespace_normalization_mapper` → `text_length_filter` → `words_num_filter` → `special_characters_filter` → `document_minhash_deduplicator`

**Semantic / LLM Pipeline (QA generation, tagging, scoring):**
- `fix_unicode_mapper` → `text_length_filter` → `llm_quality_score_filter` → `generate_qa_from_text_mapper` → `document_deduplicator`

> **⚠️ Semantic Ops + Private Data**: If the pipeline includes **any** semantic/LLM operator (see Operator Catalog → Semantic / LLM Operators), and the data is sensitive, you **MUST** configure each semantic operator to use the local Ollama endpoint (`api_model: "qwen3.5:0.8b"` + `model_params.base_url: "http://localhost:11434/v1"`), or set `OPENAI_BASE_URL=http://localhost:11434/v1` globally. These operators send actual data content to the LLM — without local routing, the content goes to a cloud API.

### Step 5: Write YAML Recipe

**Recipe Format** (this is what `dj-process --config` expects):

```yaml
project_name: my_project
dataset_path: ./input.jsonl
export_path: ./output.jsonl

# Dataset fields
text_keys:
  - text
# image_key: image       # uncomment for multimodal
# audio_key: audio       # uncomment for audio

# System settings
np: 4                     # parallel processes
executor_type: default    # or "ray" for distributed
open_tracer: false
skip_op_error: false

# Operator pipeline — each entry is {operator_name: {params}}
process:
  - fix_unicode_mapper: {}
  - whitespace_normalization_mapper: {}
  - text_length_filter:
      min_len: 50
      max_len: 100000
```

### Key Format Rules

1. **`process`** is a list of single-key dicts: `- operator_name: {params}`
2. Use `{}` for operators with no parameters
3. **`text_keys`** must be a YAML list, not a string
4. **`np`** ≥ 1 (number of parallel workers)

### Step 6: Validate Recipe

```python
import yaml

with open("recipe.yaml") as f:
    config = yaml.safe_load(f)

# Check required fields
assert "dataset_path" in config, "Missing dataset_path"
assert "export_path" in config, "Missing export_path"
assert "process" in config and len(config["process"]) > 0, "Empty process pipeline"

# Check dataset exists
import os
assert os.path.exists(config["dataset_path"]), f"Dataset not found: {config['dataset_path']}"

print("✓ Recipe is valid")
```

### Step 7: Save Recipe

```python
import yaml

recipe = {
    "project_name": "my_project",
    "dataset_path": "./input.jsonl",
    "export_path": "./output.jsonl",
    "text_keys": ["text"],
    "np": 4,
    "process": [
        {"fix_unicode_mapper": {}},
        {"whitespace_normalization_mapper": {}},
        {"text_length_filter": {"min_len": 50, "max_len": 100000}},
    ]
}

with open("recipe.yaml", "w") as f:
    yaml.dump(recipe, f, default_flow_style=False, allow_unicode=True)
```

### Complete Examples

#### Example 1: RAG Corpus Cleaning
```yaml
project_name: rag_cleaning
dataset_path: ./data/rag_corpus.jsonl
export_path: ./data/rag_cleaned.jsonl
text_keys: [text]
np: 4
process:
  - fix_unicode_mapper: {}
  - clean_html_mapper: {}
  - whitespace_normalization_mapper: {}
  - punctuation_normalization_mapper: {}
  - text_length_filter:
      min_len: 100
      max_len: 100000
  - words_num_filter:
      min_num: 20
      max_num: 100000
      lang: en
  - special_characters_filter:
      min_ratio: 0.0
      max_ratio: 0.25
  - document_deduplicator:
      lowercase: true
      ignore_non_character: true
```

#### Example 2: Chinese Text Processing
```yaml
project_name: chinese_clean
dataset_path: ./data/zh_corpus.jsonl
export_path: ./data/zh_cleaned.jsonl
text_keys: [text]
np: 4
process:
  - fix_unicode_mapper: {}
  - chinese_convert_mapper:
      mode: s2t
  - whitespace_normalization_mapper: {}
  - text_length_filter:
      min_len: 50
  - language_id_score_filter:
      lang: zh
      min_score: 0.5
  - document_minhash_deduplicator:
      tokenization: character
      window_size: 5
      num_permutations: 256
      jaccard_threshold: 0.7
```

#### Example 3: Multimodal Data Filtering
```yaml
project_name: mm_filter
dataset_path: ./data/multimodal.jsonl
export_path: ./data/mm_filtered.jsonl
text_keys: [text]
image_key: image
np: 2
process:
  - image_aspect_ratio_filter:
      min_ratio: 0.333
      max_ratio: 3.0
  - image_size_filter:
      min_size: 100
      max_size: 20000
  - text_length_filter:
      min_len: 10
      max_len: 50000
```

### Advanced: Using data-juicer-agents API for Operator Retrieval

```python
from data_juicer_agents.tools.retrieve import RETRIEVE_OPERATORS
from data_juicer_agents.core.tool import ToolContext

ctx = ToolContext(working_dir="./.djx")
result = RETRIEVE_OPERATORS.execute(
    ctx=ctx,
    raw_input={"intent": "remove duplicate documents", "top_k": 5}
)
if result.ok:
    for op in result.data.get("candidates", []):
        print(f"  {op['name']}: {op.get('description', '')}")
```

---

## 3. Execute Recipe

Run `dj-process` on a generated YAML recipe.

### Quick Run

```bash
dj-process --config recipe.yaml
```

### Recommended Flow

#### 1. Pre-flight Check

```python
import yaml, os

with open("recipe.yaml") as f:
    config = yaml.safe_load(f)

# Verify inputs exist
assert os.path.exists(config["dataset_path"]), f"Missing: {config['dataset_path']}"

# Verify output directory is writable
out_dir = os.path.dirname(config["export_path"]) or "."
os.makedirs(out_dir, exist_ok=True)

# Verify dj-process is available
import shutil
assert shutil.which("dj-process"), "dj-process not in PATH — run: pip install py-data-juicer"

print("✓ Pre-flight passed")
```

#### 2. Execute

```bash
dj-process --config recipe.yaml
```

Monitor stdout for progress. The command exits with code 0 on success.

#### 3. Verify Results

```python
input_count = sum(1 for _ in open("input.jsonl"))
output_count = sum(1 for _ in open("output.jsonl"))
print(f"Input:  {input_count} records")
print(f"Output: {output_count} records")
print(f"Removed: {input_count - output_count} ({(input_count - output_count) / input_count * 100:.1f}%)")

# Spot-check output quality
import json
with open("output.jsonl") as f:
    sample = json.loads(f.readline())
print(json.dumps(sample, indent=2, ensure_ascii=False))
```

### Exit Code Reference

| Exit Code | Meaning | Action |
|---|---|---|
| 0 | Success | Verify output |
| 1 | General error | Check stderr, see Troubleshooting section |
| 124 | Timeout | Reduce data size or increase resources |
| 130 | Interrupted | Re-run if needed |

### Advanced: Using data-juicer-agents API for Execution

```python
from data_juicer_agents.tools.apply import APPLY_RECIPE
from data_juicer_agents.core.tool import ToolContext

ctx = ToolContext(working_dir="./.djx")
result = APPLY_RECIPE.execute(
    ctx=ctx,
    raw_input={"plan_path": "recipe.yaml", "confirm": True, "timeout": 300}
)
print(f"Status: {'Success' if result.ok else 'Failed'}")
print(result.summary)
```

---

## 4. Operator Catalog

Data-Juicer provides 190+ operators in 8 categories. Below are the most commonly used.

### Mappers (Transform/Edit)

| Operator | Description | Key Params |
|---|---|---|
| `fix_unicode_mapper` | Fix broken unicode | — |
| `whitespace_normalization_mapper` | Normalize whitespace | — |
| `punctuation_normalization_mapper` | Normalize punctuation | — |
| `clean_html_mapper` | Strip HTML tags | — |
| `clean_email_mapper` | Remove email addresses | — |
| `clean_links_mapper` | Remove URLs | — |
| `clean_ip_mapper` | Remove IP addresses | — |
| `remove_header_mapper` | Remove document headers | — |
| `remove_long_words_mapper` | Remove overly long words | `min_len`, `max_len` |
| `remove_specific_chars_mapper` | Remove specified characters | `chars_to_remove` |
| `sentence_split_mapper` | Split into sentences | `lang` |
| `chinese_convert_mapper` | Simplified ↔ Traditional Chinese | `mode` (s2t/t2s) |
| `remove_repeat_sentences_mapper` | Remove repeated sentences | `min_repeat_sentence_length` |
| `replace_content_mapper` | Regex-based text replacement | `pattern`, `repl` |

### Filters (Quality Gate)

| Operator | Description | Key Params |
|---|---|---|
| `text_length_filter` | Filter by character length | `min_len`, `max_len` |
| `words_num_filter` | Filter by word count | `min_num`, `max_num`, `lang` |
| `alphanumeric_filter` | Filter by alphanumeric ratio | `min_ratio`, `max_ratio` |
| `special_characters_filter` | Filter by special char ratio | `min_ratio`, `max_ratio` |
| `average_line_length_filter` | Filter by avg line length | `min_len`, `max_len` |
| `maximum_line_length_filter` | Filter by max line length | `min_len`, `max_len` |
| `language_id_score_filter` | Filter by language score | `lang`, `min_score` |
| `perplexity_filter` | Filter by LM perplexity | `lang`, `max_ppl` |
| `flagged_words_filter` | Filter by toxic/flagged words | `lang`, `max_ratio` |
| `text_action_filter` | Filter by action keywords | `min_ratio` |
| `image_aspect_ratio_filter` | Filter image aspect ratio | `min_ratio`, `max_ratio` |
| `image_size_filter` | Filter image file size | `min_size`, `max_size` |
| `audio_duration_filter` | Filter audio duration | `min_duration`, `max_duration` |
| `video_duration_filter` | Filter video duration | `min_duration`, `max_duration` |
| `token_num_filter` | Filter by token count | `min_num`, `max_num`, `hf_tokenizer` |
| `suffix_filter` | Filter by file suffix | `suffixes` |
| `image_text_similarity_filter` | Filter by CLIP similarity | `min_score`, `max_score` |

### Deduplicators

| Operator | Description | Key Params |
|---|---|---|
| `document_deduplicator` | Exact document dedup | `lowercase`, `ignore_non_character` |
| `document_minhash_deduplicator` | MinHash LSH fuzzy dedup | `tokenization`, `window_size`, `num_permutations`, `jaccard_threshold` |
| `document_simhash_deduplicator` | SimHash fuzzy dedup | `tokenization`, `window_size`, `num_blocks`, `hamming_distance` |
| `image_deduplicator` | Image exact-match dedup | `method` |
| `ray_document_deduplicator` | Distributed exact dedup | (same as document_deduplicator) |
| `ray_image_deduplicator` | Distributed image dedup | (same as image_deduplicator) |

### Selectors (Ranking)

| Operator | Description |
|---|---|
| `topk_specified_field_selector` | Select top-K by field value |
| `frequency_specified_field_selector` | Select by field frequency |
| `range_specified_field_selector` | Select by field value range |
| `random_selector` | Random subsample |

### Aggregators

| Operator | Description |
|---|---|
| `entity_attribute_aggregator` | Aggregate entity attributes |
| `most_relevant_entities_aggregator` | Find most relevant entities |
| `nested_aggregator` | Hierarchical aggregation |
| `meta_tags_aggregator` | Aggregate metadata tags |

### Semantic / LLM Operators

These operators call an LLM API to process each sample. They send **actual data content** to the model endpoint. By default they use a cloud API (`OPENAI_BASE_URL`), but they can — and **should**, for private data — be pointed to a local Ollama model.

> **⚠️ PRIVATE DATA**: If the user's data is sensitive, **every** semantic operator in the recipe MUST use the local Ollama endpoint. Otherwise the data content will be sent to a cloud API. Configure each operator with `model_params` pointing to `http://localhost:11434/v1`, or set `OPENAI_BASE_URL` globally.

#### LLM Filters (semantic quality gates)

| Operator | Description | Key Params |
|---|---|---|
| `llm_quality_score_filter` | LLM-based quality scoring (1-5 scale) | `api_model`, `min_score`, `dimensions` |
| `llm_difficulty_score_filter` | LLM-based difficulty evaluation | `api_model`, `min_score`, `dimensions` |
| `llm_task_relevance_filter` | Relevance to a validation task | `api_model`, `task_description`, `min_score` |
| `llm_perplexity_filter` | Perplexity via HuggingFace model | `hf_model`, `max_ppl` |

#### Text Generation / Tagging Mappers

| Operator | Description | Key Params |
|---|---|---|
| `generate_qa_from_text_mapper` | Generate QA pairs from text | `api_model`, `qa_pair_num` |
| `generate_qa_from_examples_mapper` | Generate QA from seed examples | `api_model`, `seed_file`, `example_num` |
| `optimize_qa_mapper` | Optimize existing QA pairs | `api_model` |
| `text_tagging_by_prompt_mapper` | Tag text via LLM prompt | `hf_model` or `api_model` |
| `optimize_prompt_mapper` | Optimize prompts from examples | `api_model` |
| `pair_preference_mapper` | Generate preference pairs | `api_model` |
| `sentence_augmentation_mapper` | Augment sentences | `hf_model` |

#### Dialog Analysis Mappers

| Operator | Description | Key Params |
|---|---|---|
| `dialog_intent_detection_mapper` | Detect user intent in dialog | `api_model` |
| `dialog_sentiment_detection_mapper` | Detect sentiment in dialog | `api_model` |
| `dialog_sentiment_intensity_mapper` | Quantify sentiment intensity | `api_model` |
| `dialog_topic_detection_mapper` | Identify dialog topics | `api_model` |

#### Entity / Relation Extraction Mappers

| Operator | Description | Key Params |
|---|---|---|
| `extract_keyword_mapper` | Extract keywords via LLM | `api_model` |
| `extract_entity_attribute_mapper` | Extract entity attributes | `api_model` |
| `extract_nickname_mapper` | Identify nickname relationships | `api_model` |
| `extract_support_text_mapper` | Extract supporting text | `api_model` |
| `relation_identity_mapper` | Identify entity relationships | `api_model` |

#### Vision-Language / Multimodal Mappers

| Operator | Description | Key Params |
|---|---|---|
| `image_tagging_vlm_mapper` | Tag images via VLM | `api_model`, `tag_field_name` |
| `video_captioning_from_vlm_mapper` | Caption videos via VLM | `api_model`, `enable_vllm` |
| `mllm_mapper` | Visual QA with multimodal LLM | `api_model` |
| `image_captioning_from_gpt4v_mapper` | Image captioning via API | `api_model` |

#### Configuring Semantic Operators to Use Local Ollama

All semantic operators use the OpenAI-compatible API protocol. To route them through a local Ollama model, configure `api_model` and `model_params` in the YAML recipe:

**Per-operator configuration (in YAML recipe):**

```yaml
process:
  # Semantic ops — all pointed to local Ollama
  - generate_qa_from_text_mapper:
      api_model: "qwen3.5:0.8b"
      model_params:
        base_url: "http://localhost:11434/v1"
        api_key: "ollama"
      sampling_params:
        temperature: 0.7
  - llm_quality_score_filter:
      api_model: "qwen3.5:0.8b"
      model_params:
        base_url: "http://localhost:11434/v1"
        api_key: "ollama"
      min_score: 3
  - extract_keyword_mapper:
      api_model: "qwen3.5:0.8b"
      model_params:
        base_url: "http://localhost:11434/v1"
        api_key: "ollama"
```

**Global configuration (via environment variables):**

Alternatively, set these environment variables before running `dj-process` so ALL semantic operators default to Ollama:

```bash
export OPENAI_BASE_URL="http://localhost:11434/v1"
export OPENAI_API_KEY="ollama"
```

Then the recipe only needs the model name:

```yaml
process:
  - generate_qa_from_text_mapper:
      api_model: "qwen3.5:0.8b"
  - llm_quality_score_filter:
      api_model: "qwen3.5:0.8b"
      min_score: 3
```

#### Complete Example: Private Data with Semantic Ops

```yaml
project_name: private_qa_generation
dataset_path: ./sensitive_data.jsonl
export_path: ./sensitive_qa_output.jsonl
text_keys: [text]
np: 2

process:
  # Step 1: Basic cleaning (no LLM, safe for any data)
  - fix_unicode_mapper: {}
  - whitespace_normalization_mapper: {}
  - text_length_filter:
      min_len: 100
      max_len: 100000

  # Step 2: LLM-powered ops — all using local Ollama
  - llm_quality_score_filter:
      api_model: "qwen3.5:0.8b"
      model_params:
        base_url: "http://localhost:11434/v1"
        api_key: "ollama"
      min_score: 3
  - generate_qa_from_text_mapper:
      api_model: "qwen3.5:0.8b"
      model_params:
        base_url: "http://localhost:11434/v1"
        api_key: "ollama"

  # Step 3: Dedup (no LLM, safe for any data)
  - document_deduplicator:
      lowercase: true
```

> **Note**: Local small models (qwen3.5:0.8b) are less capable than cloud models for complex semantic tasks like QA generation. If quality is critical, consider using a larger local model (`qwen3.5:7b` or `qwen3.5:14b`). See [local_model_skills.md](./local_model_skills.md) for model options.

### Usage in YAML Recipe

Each operator goes under `process:` as a single-key dict:

```yaml
process:
  - operator_name: {}                 # no params
  - operator_with_params:
      param1: value1
      param2: value2
```

### Discover Operators via Retrieval

Use the `retrieve_operators` tool to find operators by intent:

```python
from data_juicer_agents.tools.retrieve import RETRIEVE_OPERATORS
from data_juicer_agents.core.tool import ToolContext

ctx = ToolContext(working_dir="./.djx")
result = RETRIEVE_OPERATORS.execute(
    ctx=ctx,
    raw_input={"intent": "remove duplicate documents", "top_k": 5}
)
if result.ok:
    for candidate in result.data.get("payload", {}).get("candidates", []):
        print(f"  {candidate['operator_name']}: {candidate['description']}")
```

Or list all available operators:

```bash
python -c "
from data_juicer_agents.tools.retrieve import get_available_operator_names
ops = get_available_operator_names()
print(f'Total operators: {len(ops)}')
for op in sorted(ops)[:20]:
    print(f'  - {op}')
"
```

---

## 5. Troubleshooting

### Error Quick Reference

| Error | Cause | Fix |
|---|---|---|
| `command not found: dj-process` | Not installed or venv not activated | `uv pip install py-data-juicer` + activate venv |
| `FileNotFoundError` | Dataset path doesn't exist | Check `dataset_path` in recipe |
| `PermissionError` | Can't write output | Check directory permissions |
| `KeyError` on operator | Operator name incorrect | Check Operator Catalog for valid names |
| `ModuleNotFoundError` | Missing dependency | Install required extras for the operator |
| YAML parse error | Malformed recipe | Validate YAML syntax |
| Timeout | Processing too slow | Reduce data, increase `np`, or sample first |
| API key error | Missing credentials | Set `DASHSCOPE_API_KEY` or relevant env var; for local mode set `DASHSCOPE_API_KEY=ollama` |
| Local model not responding | Ollama not running | Start Ollama: `ollama serve`; see [local_model_skills.md](./local_model_skills.md) |
| `enable_thinking` error in local mode | Local models don't support thinking | Set `DJA_LLM_THINKING=false` |

### Diagnostic Commands

```bash
# 1. Check dj-process is installed
which dj-process

# 2. Validate YAML
python -c "import yaml; yaml.safe_load(open('recipe.yaml')); print('YAML OK')"

# 3. Check dataset is valid JSONL
head -1 input.jsonl | python -m json.tool

# 4. Count dataset records
wc -l input.jsonl

# 5. Check operator exists
python -c "
from data_juicer.ops import load_ops
all_ops = load_ops()
target = 'operator_name'
found = any(target in ops for ops in all_ops.values())
print(f'{target}: {\"found\" if found else \"NOT FOUND\"}')"

# 6. Check Python environment
python --version
pip list | grep -i "data.juicer"
```

### Common Fixes

#### Recipe YAML Issues
- **Wrong process format**: Each operator must be `- operator_name: {params}`, not `- {name: ..., params: ...}`
- **text_keys as string**: Must be a list `[text]`, not `text`
- **Missing export_path**: Always specify where output goes

#### Operator Issues
- **Operator not found**: Check spelling against Operator Catalog
- **Wrong params**: Check operator docs; most use snake_case param names
- **Missing model files**: Some operators (perplexity, language_id) download models on first run

#### Performance Issues
- **Slow processing**: Increase `np` (parallel workers)
- **Out of memory**: Reduce `np`, or process in batches
- **Large dataset**: Use `executor_type: ray` for distributed processing
