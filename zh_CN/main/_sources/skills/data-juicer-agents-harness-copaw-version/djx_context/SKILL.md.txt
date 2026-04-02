---
name: djx_context
description: >-
  Data-Juicer dataset inspection: inspect_dataset usage, field analysis, modality detection, statistics.
  Trigger keywords: inspect_dataset, inspect dataset, dataset structure, fields, modality,
  statistics, sample, profile, data overview.
  Use when you need to understand dataset structure, view fields, detect modality, or get statistics.
  Related skills: data-juicer (main flow), djx_plan (plan building).
allowed-tools: Bash, Read
argument-hint: "<dataset_path>"
user-invocable: true
---

# Data-Juicer Skills: Context (Dataset Inspection)

Dataset inspection — the first step of the Data-Juicer workflow.

---

## Core Rule: Use djx tool Only

**You must only use the `djx tool` CLI**. Do not use the session or cap modules.

---

## Prerequisites

| Condition | Requirement |
|-----------|-------------|
| **Dataset format** | JSONL or JSON |
| **File encoding** | UTF-8 |
| **File exists** | Path is correct and accessible |

---

## Core Concepts

| Concept | Description |
|---------|-------------|
| **dataset_profile** | Dataset metadata including fields, statistics, and samples |
| **modality** | Data modality: text, image, audio, video, multimodal |
| **sample_size** | Number of samples used for analysis (not a full scan) |

---

## Core Tool: inspect_dataset

Analyzes dataset metadata, field types, modality, statistics, and sample content.

### Input Schema

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `dataset_path` | str | Yes | — | Dataset file path (JSONL format) |
| `sample_size` | int | No | 20 | Number of samples for analysis |

### Command

```bash
djx tool run inspect_dataset --input-json '{"dataset_path": "<path>", "sample_size": 50}'
```

### Output Fields

| Field | Description |
|-------|-------------|
| `modality` | Detected data modality |
| `fields` | List of field names |
| `sample_count` | Actual number of samples read |
| `statistics` | Field-level statistics (length, type, distribution) |
| `samples` | Raw sample preview |

> **Do not assume field names or modality** — always read from the output.

---

## Data Flow

The `dataset_profile` output is a **required input** for `build_dataset_spec`:

```
inspect_dataset → dataset_profile → build_dataset_spec → dataset_spec
```

Save the complete profile output and pass it to subsequent steps.

---

## Sample Size Configuration Guide

| Use Case | Recommended Value | Time Estimate |
|----------|-------------------|---------------|
| Quick check | 5 | ~1s |
| Regular analysis | 20 | ~3s |
| Production planning | 50+ | ~5-10s |

> **Note**: Statistics are based on `sample_size`, not the full dataset. Larger samples are more accurate but take longer.

---

## Modality & Operator Compatibility

The detected modality determines which operators are available:

| Modality | Compatible Operators |
|----------|---------------------|
| text | Text cleaning, filtering, deduplication |
| image | Image filtering, resolution detection |
| audio | Audio processing |
| video | Video processing |
| multimodal | Cross-modal processing |

**Ensure selected operators are compatible with the dataset modality**.

---

## Error Handling

| Scenario | Solution |
|----------|----------|
| `FileNotFoundError` | Verify the dataset path exists and is accessible |
| `JSONDecodeError` | File is not valid JSONL — each line must be a valid JSON object |
| Empty output (`sample_count: 0`) | Dataset has no records — verify the file has content |
| `UnicodeDecodeError` | Convert the file to UTF-8 encoding |
| Nested JSON fields | Operators only access top-level fields — flatten nested structures if needed |

---

## Typical Usage

```bash
# Regular inspection
djx tool run inspect_dataset --input-json '{"dataset_path": "/data/articles.jsonl", "sample_size": 50}'

# Quick check
djx tool run inspect_dataset --input-json '{"dataset_path": "/data/articles.jsonl", "sample_size": 5}'

# View full schema
djx tool schema inspect_dataset
```

---

## Key Principles

1. **Always run inspect_dataset first** — it is the first step of the workflow
2. **Save the output** — `dataset_profile` is a required input for subsequent steps
3. **Privacy safe** — runs entirely locally with no cloud API calls
4. **Check modality** — determines which operators are compatible

---

## Skill Responsibilities

| Scenario | Skill to Use |
|----------|--------------|
| Inspect dataset structure | **djx_context (this skill)** |
| Main flow | data-juicer |
| Search for operators | djx_retrieve |
| Build plan | djx_plan |
