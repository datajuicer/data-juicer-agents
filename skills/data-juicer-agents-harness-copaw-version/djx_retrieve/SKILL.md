---
name: djx_retrieve
description: >-
  Data-Juicer operator retrieval reference: retrieve_operators (local), retrieve_operators_api (API), get_operator_info, list_operator_catalog.
  Trigger keywords: retrieve_operators, retrieve_operators_api, search operators, find operator,
  which operator, intent, retrieval, bm25, regex, LLM mode, vector mode, operator info, operator catalog.
  Use when searching for suitable operators, unsure which operator to use, or retrieve errors occur.
  Related skills: data-juicer (main flow), djx_auth (authentication), djx_local_model (local mode).
allowed-tools: Bash, Read
argument-hint: "<intent>"
user-invocable: true
---

# Data-Juicer Skills: Retrieve (Operator Retrieval)

> **Main flow**: See the `data-juicer` skill. This skill provides detailed reference for operator retrieval tools.

---

## Tool Overview

| Tool | Surface | Modes | Use Case |
|------|---------|-------|----------|
| `retrieve_operators` | Harness (default) | `auto`, `bm25`, `regex` | Local retrieval, no API needed |
| `retrieve_operators_api` | Full (not in harness) | `auto`, `llm`, `vector` | API-backed semantic retrieval |
| `get_operator_info` | Harness | — | Inspect one operator's parameter schema |
| `list_operator_catalog` | Harness | — | Browse full operator catalog (fallback) |

---

## Prerequisites

| Condition | Requirement | Verification Command |
|-----------|-------------|---------------------|
| **retrieve_operators** (local) | No API key needed | Runs locally |
| **retrieve_operators_api** (API) | `DASHSCOPE_API_KEY` is set | `echo $DASHSCOPE_API_KEY` |

---

## Core Concepts

| Concept | Description |
|---------|-------------|
| **intent** | Natural language description of the processing goal, used to retrieve matching operators |
| **mode (local)** | `retrieve_operators` modes: `auto` (routes to bm25/regex), `bm25`, `regex` |
| **mode (API)** | `retrieve_operators_api` modes: `auto` (tries llm→vector), `llm`, `vector` |
| **top_k** | Maximum number of candidates to return |
| **operator** | Data processing unit containing name, type, description, params |

---

## Command Format

```bash
# Local retrieval (harness default)
djx tool run retrieve_operators --input-json '{"intent": "<description>", "top_k": 15}'

# API-backed retrieval (full surface only, not in harness)
djx tool run retrieve_operators_api --input-json '{"intent": "<description>", "top_k": 15}'

# Inspect one operator's parameter schema
djx tool run get_operator_info --input-json '{"operator_name": "<operator_name>"}'

# Browse operator catalog (fallback)
djx tool run list_operator_catalog --input-json '{"include_parameters": false}'
```

> **Must use `djx tool run <tool_name> --input-json '{...}'`**. Do not use `djx retrieve_operators`, `djx retrieve`, or other formats.

---

## Input Schemas

### retrieve_operators (local)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `intent` | str | Yes | — | Natural language description, or regex pattern for `regex` mode |
| `top_k` | int | No | 10 | Maximum number of candidates to return |
| `mode` | str | No | `auto` | `auto`, `bm25`, `regex` |
| `op_type` | str | No | — | Type filter: `mapper`, `filter`, `deduplicator`, etc. |
| `tags` | list | No | `[]` | Modality/resource tags (`text`, `image`, etc.), match-all semantics |
| `dataset_path` | str | No | — | Dataset path for automatic modality detection |

### retrieve_operators_api (API)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `intent` | str | Yes | — | Plain-text description of the desired operators |
| `top_k` | int | No | 10 | Maximum number of candidates to return |
| `mode` | str | No | `auto` | `auto`, `llm`, `vector` |
| `op_type` | str | No | — | Type filter: `mapper`, `filter`, `deduplicator`, etc. |
| `tags` | list | No | `[]` | Modality/resource tags, match-all semantics |
| `dataset_path` | str | No | — | Dataset path for automatic modality detection |

### get_operator_info

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `operator_name` | str | Yes | — | Canonical or approximate operator name to inspect |

### list_operator_catalog

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `op_type` | str | No | — | Type filter |
| `tags` | list | No | `[]` | Tag filter, match-all semantics |
| `include_parameters` | bool | No | `false` | Include full parameter schemas (heavy, use cautiously) |
| `limit` | int | No | 0 | Max operators to return (0 = all) |

> **The field name is `intent`, not `query`**. Using `query` will cause `input_validation_failed`.

---

## Retrieval Mode Comparison

### retrieve_operators (local modes)

| Mode | Requires API | Behavior | Use Case |
|------|-------------|----------|----------|
| `auto` | No | Routes to `regex` for regex-like queries, otherwise `bm25` | **Default recommended** |
| `bm25` | No | BM25 keyword matching | Deterministic keyword search |
| `regex` | No | Regex pattern matching on operator names | When operator naming pattern is known |

### retrieve_operators_api (API modes)

| Mode | Requires API | Behavior | Use Case |
|------|-------------|----------|----------|
| `auto` | Yes | Tries `llm` first, falls back to `vector` | Highest accuracy when API available |
| `llm` | Yes | LLM semantic ranking | Best semantic relevance |
| `vector` | Yes | FAISS vector similarity | Semantic search without LLM ranking |

**Mode selection decision**:

```
In harness mode?
├─ Yes → Use retrieve_operators (local, mode=auto)
└─ No (full surface) →
    Do you have an API Key?
    ├─ Yes → Use retrieve_operators_api (mode=auto)
    └─ No → Use retrieve_operators (mode=auto, already local)
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

> **After selecting a candidate**, call `get_operator_info` to inspect its full parameter schema before filling `build_process_spec`. Do not guess parameter names from operator names alone.

---

## Error Handling

| Scenario | Solution |
|----------|----------|
| `401 Unauthorized` | API key issue; use `retrieve_operators` (local) instead, or verify `DASHSCOPE_API_KEY` |
| Empty results | Retry with a broader intent, or use `list_operator_catalog` as fallback |
| `input_validation_failed` | Use `intent` instead of `query` |
| `invalid local retrieval mode` | `retrieve_operators` only accepts `auto`, `bm25`, `regex`; for `llm`/`vector`, use `retrieve_operators_api` |
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

### 3. Local Retrieval Needs No API Key

`retrieve_operators` runs entirely locally. No cloud calls, no API key needed:

```bash
djx tool run retrieve_operators --input-json '{"intent": "...", "mode": "auto"}'
```

For API-backed semantic retrieval (outside harness), use `retrieve_operators_api`:

```bash
djx tool run retrieve_operators_api --input-json '{"intent": "...", "mode": "vector"}'
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
# Standard local retrieval - describe all requirements at once
djx tool run retrieve_operators --input-json '{
  "intent": "remove HTML tags, normalize whitespace, fix unicode encoding, filter text shorter than 50 characters, deduplicate documents",
  "top_k": 15
}'

# Regex mode - when operator naming pattern is known
djx tool run retrieve_operators --input-json '{"intent": ".*dedup.*", "mode": "regex"}'

# BM25 mode - deterministic keyword matching
djx tool run retrieve_operators --input-json '{"intent": "filter images by resolution", "mode": "bm25"}'

# Inspect a specific operator's parameters
djx tool run get_operator_info --input-json '{"operator_name": "text_length_filter"}'

# Browse catalog (fallback when retrieval is insufficient)
djx tool run list_operator_catalog --input-json '{"op_type": "filter", "include_parameters": false, "limit": 20}'

# Combined with dataset modality
djx tool run retrieve_operators --input-json '{"intent": "filter images", "dataset_path": "/data/images.jsonl"}'

# API-backed retrieval (full surface only, requires API key)
djx tool run retrieve_operators_api --input-json '{
  "intent": "clean HTML artifacts, normalize all whitespace, deduplicate documents",
  "top_k": 20
}'
```

---

## Recommended Retrieval Pattern

1. Use `retrieve_operators` with `mode="auto"` for ordinary natural-language operator discovery.
2. Use `mode="bm25"` when you want deterministic keyword retrieval.
3. Use `mode="regex"` when the operator naming pattern is already known.
4. If `retrieve_operators` does not return valid candidates, call `list_operator_catalog` as a fallback.
5. Use `list_operator_catalog` cautiously: `include_parameters=true` is heavy. Prefer filtered calls (`op_type`, `tags`, `limit`).
6. After selecting a candidate, call `get_operator_info` before filling `build_process_spec`.

---

## Skill Responsibilities

| Scenario | Skill to Use |
|----------|--------------|
| Main flow | data-juicer |
| Search for operators | **djx_retrieve (this skill)** |
| Authentication configuration | djx_auth |
| Local models | djx_local_model |
| Build plan | djx_plan |
