---
name: djx_retrieve
description: >-
  Data-Juicer operator retrieval reference: retrieve_operators modes, intent writing, result interpretation.
  Trigger keywords: retrieve_operators, search operators, find operator,
  which operator, intent, retrieval, LLM mode, vector mode.
  Use when searching for suitable operators, unsure which operator to use, or retrieve errors occur.
  Related skills: data-juicer (main flow), djx_auth (authentication), djx_local_model (local mode).
allowed-tools: Bash, Read
argument-hint: '"<intent>"'
user-invocable: true
---

# Data-Juicer Skills: Retrieve (Operator Retrieval)

> **Main flow**: See the `data-juicer` skill. This skill provides detailed reference for retrieve_operators.

---

## Prerequisites

| Condition | Requirement | Verification Command |
|-----------|-------------|---------------------|
| **LLM mode** | `DASHSCOPE_API_KEY` is set | `echo $DASHSCOPE_API_KEY` |
| **Vector mode** | No API Key needed | Runs locally |

---

## Core Concepts

| Concept | Description |
|---------|-------------|
| **intent** | Natural language description of the processing goal, used to retrieve matching operators |
| **mode** | Retrieval mode: `auto`, `llm`, `vector` |
| **top_k** | Maximum number of candidates to return |
| **operator** | Data processing unit containing name, type, description, params |

---

## Command Format

```bash
djx tool run retrieve_operators --input-json '{"intent": "<description>", "top_k": 15}'
```

> **Must use `djx tool run retrieve_operators --input-json '{...}'`**. Do not use `djx retrieve_operators`, `djx retrieve`, or other formats.

---

## Input Schema

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `intent` | str | Yes | — | Natural language description of the processing goal |
| `top_k` | int | No | 10 | Maximum number of candidates to return |
| `mode` | str | No | `auto` | `auto`, `llm`, `vector` |
| `dataset_path` | str | No | — | Dataset path for modality-aware retrieval |

> **The field name is `intent`, not `query`**. Using `query` will cause `input_validation_failed`.

---

## Retrieval Mode Comparison

| Mode | Requires API | Behavior | Use Case |
|------|-------------|----------|----------|
| `auto` | Yes (LLM) | LLM first, vector fallback | **Default recommended**, highest accuracy |
| `llm` | Yes | LLM-only semantic retrieval | Highest semantic relevance |
| `vector` | No (local) | Vector embedding similarity | Private data, offline environments, no API |

**Mode selection decision**:

```
Do you have an API Key?
├─ Yes → Use auto (default)
└─ No → Use vector

Is the data private?
├─ Yes → Use vector (no cloud sending)
└─ No → Use auto
```

---

## Intent Writing Guide

### Key Rule: Describe All Requirements at Once

**Do not** retrieve operators for different functionalities in multiple calls. Combine all requirements into a single intent:

**Wrong**: Multiple retrievals
```bash
# 1st call
djx tool run retrieve_operators --input-json '{"intent": "clean HTML"}'
# 2nd call
djx tool run retrieve_operators --input-json '{"intent": "filter short text"}'
# 3rd call
djx tool run retrieve_operators --input-json '{"intent": "deduplicate"}'
```

**Correct**: One retrieval covering all requirements
```bash
djx tool run retrieve_operators --input-json '{"intent": "remove HTML tags, normalize whitespace, fix unicode encoding, filter short text under 50 characters, deduplicate documents", "top_k": 15}'
```

### Good Intents

**Describe data processing goals**, not specific operator names:

| User Need | Intent |
|-----------|--------|
| Clean HTML, normalize whitespace, deduplicate | `"remove HTML tags, normalize whitespace, deduplicate near-identical documents"` |
| Clean text, fix encoding, filter, deduplicate | `"remove HTML artifacts, normalize whitespace, fix unicode encoding, filter text shorter than 50 characters, deduplicate exact duplicates"` |
| Filter low-quality images | `"filter low-quality images by resolution"` |
| Fix encoding, clean emails, filter by language | `"fix unicode encoding, remove email addresses, filter by language"` |
| Mask sensitive data | `"mask or remove sensitive information like phone numbers and emails"` |

### Bad Intents

| Bad Intent | Problem |
|------------|---------|
| `"use fix_unicode_mapper"` | Do not specify operator names — defeats the purpose of retrieval |
| `"clean the SSN records: 123-45-6789..."` | Do not include actual data content |
| `"filter"` | Too vague to match |
| `"clean HTML"` then `"normalize whitespace"` | Multiple retrievals — inefficient and may miss related operators |

### Common Functionality Keywords

| Functionality | Intent Keywords |
|---------------|-----------------|
| HTML cleaning | `remove HTML tags`, `clean HTML artifacts` |
| Whitespace normalization | `normalize whitespace`, `collapse multiple spaces` |
| Unicode fix | `fix unicode encoding`, `fix malformed unicode` |
| Length filtering | `filter text shorter than N characters`, `filter by text length` |
| Deduplication | `deduplicate documents`, `remove duplicates`, `exact deduplication` |
| Language filtering | `filter by language`, `keep only English text` |
| Quality filtering | `filter low quality text`, `remove nonsense text` |

---

## Result Interpretation

`retrieve_operators` returns a list of operators, each containing:

| Field | Description |
|-------|-------------|
| `name` | Operator name — **this is the only value usable in build_process_spec** |
| `type` | Type: `mapper`, `filter`, `deduplicator` |
| `description` | Functionality description |
| `params` | Parameter definitions including field names, types, default values |

**Example output**:
```json
[
  {
    "name": "clean_html_mapper",
    "type": "mapper",
    "description": "Remove HTML tags from text fields",
    "params": {"text_key": {"type": "str", "default": "text"}}
  },
  {
    "name": "text_length_filter",
    "type": "filter",
    "description": "Filter text by length",
    "params": {"min_len": {"type": "int", "default": 10}, "max_len": {...}}
  }
]
```

> **This is all the information you will get**. No other tool can provide more operator details. Do not try to use `djx tool schema` for operators (it only supports the 8 djx tools).

---

## Error Handling

| Scenario | Solution |
|----------|----------|
| `401 Unauthorized` | Verify `DASHSCOPE_API_KEY` is correct |
| Empty results | Retry with a broader intent |
| `input_validation_failed` | Use `intent` instead of `query` |
| `auto` mode 401 | Explicitly use `mode=vector` |
| Operator results are not ideal | Use a more specific description in retrieval, e.g., `normalize all whitespace including internal spaces` instead of just `normalize whitespace` |

---

## Retrieval Result Validation

After retrieving operators, check if they meet requirements:

| Requirement | Possible Operators | Validation Points |
|-------------|-------------------|-------------------|
| HTML cleaning | `clean_html_mapper` | Does it clean both tags and entities |
| Whitespace normalization | `whitespace_normalization_mapper`, `fix_unicode_mapper` | Does it handle internal multiple spaces |
| Unicode fix | `fix_unicode_mapper` | Does it handle various encoding issues |
| Length filtering | `text_length_filter` | Parameter is `min_len`, not `min_length` |
| Deduplication | `document_deduplicator`, `document_minhash_deduplicator` | Exact vs approximate dedup |

> **Tip**: If an operator doesn't perform as expected, you may need to:
> 1. Re-retrieve with a more specific intent
> 2. Combine multiple operators (e.g., `whitespace_normalization_mapper` + `fix_unicode_mapper`)
> 3. Check if operator parameters are set correctly

---

## Must-Read Pitfalls

### 1. Parameter Name Is intent, Not query

**Wrong**
```bash
djx tool run retrieve_operators --input-json '{"query": "clean HTML"}'
# → input_validation_failed
```

**Correct**
```bash
djx tool run retrieve_operators --input-json '{"intent": "clean HTML"}'
```

### 2. Do Not Guess Operator Names

Retrieval results are the **only source**. Do not use operators from memory or guessing.

**Wrong**: Making up names
```bash
{"name": "html_cleaner", ...}  # Does not exist!
```

**Correct**: Select from retrieval results
```bash
# Retrieve first
djx tool run retrieve_operators --input-json '{"intent": "clean HTML", "top_k": 5}'
# Select name from output
{"name": "clean_html_mapper", ...}  # From retrieval results
```

### 3. Use vector Mode for Private Data

```bash
djx tool run retrieve_operators --input-json '{"intent": "...", "mode": "vector"}'
```

---

## Ray-Prefixed Operator Warning

Operators prefixed with `ray_` require a running Ray cluster. Use alternatives in single-machine environments:

| Ray Operator | Single-Machine Alternative |
|--------------|---------------------------|
| `ray_bts_minhash_deduplicator` | `document_minhash_deduplicator` |
| `ray_*` | Find non-ray versions or implement your own |

---

## Typical Usage

```bash
# Standard retrieval - describe all requirements at once
djx tool run retrieve_operators --input-json '{
  "intent": "remove HTML tags, normalize whitespace, fix unicode encoding, filter text shorter than 50 characters, deduplicate documents",
  "top_k": 15
}'

# Private data (local vector mode)
djx tool run retrieve_operators --input-json '{"intent": "clean HTML, normalize whitespace, deduplicate", "mode": "vector"}'

# More results
djx tool run retrieve_operators --input-json '{"intent": "...", "top_k": 20}'

# Combined with dataset modality
djx tool run retrieve_operators --input-json '{"intent": "filter images", "dataset_path": "/data/images.jsonl"}'

# Complex cleaning task
djx tool run retrieve_operators --input-json '{
  "intent": "clean HTML artifacts, normalize all whitespace including internal spaces, fix malformed unicode characters, filter by text length minimum 100 characters, deduplicate exact and near-duplicate documents",
  "top_k": 20
}'
```

---

## Skill Responsibilities

| Scenario | Skill to Use |
|----------|--------------|
| Main flow | data-juicer |
| Search for operators | **djx_retrieve (this skill)** |
| Authentication configuration | djx_auth |
| Local models | djx_local_model |
| Build plan | djx_plan |
