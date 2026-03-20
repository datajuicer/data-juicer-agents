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
Inspect Dataset (check format, fields, modality)
  ↓
Select Operators (see Operator Catalog section)
  ↓
Generate YAML Recipe
  ↓
Run dj-process --config recipe.yaml
  ↓
Verify & Return Results
```

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
User Intent → Inspect Dataset → Choose Operators → Write YAML → Validate → Save
```

### Step 1: Parse User Intent

Identify from the user's request:
- **Input dataset path** (JSONL file)
- **Output path** (where to save processed data)
- **Processing goals** (clean text? remove duplicates? filter quality? etc.)

### Step 2: Inspect Dataset

Examine the dataset to understand its structure:

```python
import json

with open("input.jsonl") as f:
    samples = [json.loads(line) for line in f][:5]

# Show first record structure
print("Fields:", list(samples[0].keys()))
print("Sample:", json.dumps(samples[0], indent=2, ensure_ascii=False))

# Identify text fields (usually "text", "content", "instruction", etc.)
# Identify image fields (if any URL/path patterns)
```

Key things to determine:
- **text_keys**: Which fields contain the main text (e.g., `["text"]`)
- **image_key**: Field for image paths/URLs (if multimodal)
- **Modality**: text-only, image, multimodal

### Step 3: Choose Operators

Based on the user's goals, select operators from the Operator Catalog. Common patterns:

**Text Cleaning Pipeline:**
- `fix_unicode_mapper` → `whitespace_normalization_mapper` → `clean_html_mapper` → `text_length_filter` → `words_num_filter`

**Deduplication Pipeline:**
- `document_deduplicator` (exact) or `document_minhash_deduplicator` (fuzzy)

**Quality Filtering Pipeline:**
- `language_id_score_filter` → `perplexity_filter` → `alphanumeric_filter` → `text_length_filter`

**Full Pipeline (clean + filter + dedup):**
- `fix_unicode_mapper` → `clean_html_mapper` → `whitespace_normalization_mapper` → `text_length_filter` → `words_num_filter` → `special_characters_filter` → `document_minhash_deduplicator`

### Step 4: Write YAML Recipe

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

### Step 5: Validate Recipe

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

### Step 6: Save Recipe

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
| `most_relavant_entities_aggregator` | Find most relevant entities |
| `nested_aggregator` | Hierarchical aggregation |
| `meta_tags_aggregator` | Aggregate metadata tags |

### Usage in YAML Recipe

Each operator goes under `process:` as a single-key dict:

```yaml
process:
  - operator_name: {}                 # no params
  - operator_with_params:
      param1: value1
      param2: value2
```

### Discover More Operators

```bash
python -c "
from data_juicer.ops import load_ops
ops = load_ops()
for op_type, op_list in ops.items():
    print(f'{op_type}: {len(op_list)} operators')
    for op in sorted(op_list):
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
| API key error | Missing credentials | Set `DASHSCOPE_API_KEY` or relevant env var |

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
