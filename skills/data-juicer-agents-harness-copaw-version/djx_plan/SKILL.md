---
name: djx_plan
description: >-
  Data-Juicer plan building reference: detailed schema and parameter documentation for build_dataset_spec,
  build_process_spec, build_system_spec, assemble_plan, and plan_save.
  Trigger keywords: build_spec, assemble_plan, plan_save, build plan, YAML, specification,
  dataset spec, process spec, system spec.
  Use when building plans and needing to check detailed parameters, or when spec building fails.
  Related skills: data-juicer (main flow), djx_retrieve (operator retrieval), djx_apply (execution).
allowed-tools: Bash, Read
argument-hint: "<intent> <dataset_path> <export_path>"
user-invocable: true
---

# Data-Juicer Skills: Plan (Plan Building)

> **Main flow**: See the `data-juicer` skill. This skill provides detailed schemas for plan building tools.

---

## Prerequisites

| Condition | Source |
|-----------|--------|
| **dataset_profile** | `inspect_dataset` output |
| **operators list** | `retrieve_operators` output |
| **input/output paths** | User-specified or default rules |

---

## Core Concepts

| Concept | Description |
|---------|-------------|
| **dataset_spec** | Dataset specification: input/output paths, field mapping, modality info |
| **process_spec** | Process specification: operator list and their parameters |
| **system_spec** | System specification: parallelism, custom operator paths |
| **plan** | Complete processing plan, assembled from the three specs above |

---

## Data Flow

```
inspect_dataset ─────────────────────────────────┐
                                                  │
retrieve_operators ──────────────────────────────┐│
                                                 ││
build_dataset_spec ◄─────────────────────────────┤│
        │                                        ││
        ▼                                        ││
build_process_spec ◄─────────────────────────────┘│
        │                                         │
        ▼                                         │
build_system_spec                                 │
        │                                         │
        ▼                                         │
assemble_plan ◄───────────────────────────────────┘
        │
        ▼
plan_save ──→ plan.yaml
```

---

## 1. build_dataset_spec

Build the dataset specification.

### Input Schema

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `intent` | str | Yes | Processing intent description |
| `dataset_path` | str | Yes | Input dataset path |
| `export_path` | str | Yes | Output dataset path |
| `dataset_profile` | dict | Yes | Complete output from `inspect_dataset` |

### Optional Hint Fields

| Parameter | Description |
|-----------|-------------|
| `modality_hint` | Data modality: text, image, audio, video, multimodal |
| `text_keys_hint` | List of text field names |
| `image_key_hint` | Image field name |
| `audio_key_hint` | Audio field name |
| `video_key_hint` | Video field name |

### Command

```bash
djx tool run build_dataset_spec --input-json '{
  "intent": "<PROCESSING_GOAL>",
  "dataset_path": "<INPUT_PATH>",
  "export_path": "<OUTPUT_PATH>",
  "dataset_profile": <PASTE_FULL_INSPECT_OUTPUT>
}'
```

---

## 2. build_process_spec

Build the process specification, defining the operator pipeline.

### Input Schema

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `operators` | list | Yes | Operator configuration list |

### Operator Configuration Format

```json
{"name": "<OPERATOR_NAME>", "params": {...}}
```

### Ordering Rules

Operators **must** be ordered as follows:
1. **Mappers** — Transform data
2. **Filters** — Filter data
3. **Deduplicators** — Remove duplicates

### Command

```bash
djx tool run build_process_spec --input-json '{
  "operators": [
    {"name": "<MAPPER>", "params": {}},
    {"name": "<FILTER>", "params": {"min_len": 100}},
    {"name": "<DEDUP>", "params": {}}
  ]
}'
```

### Parameter Handling

| Scenario | Approach |
|----------|----------|
| Parameters are clear | Use specific values: `{"min_len": 100}` |
| Parameters are uncertain | Use empty object: `{}` (applies defaults) |

---

## 3. build_system_spec

Build the system specification, configuring the execution environment.

### Input Schema

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `custom_operator_paths` | list | No | List of custom operator directory paths |

### Command

```bash
# Most cases use empty input
djx tool run build_system_spec --input-json '{}'

# With custom operators
djx tool run build_system_spec --input-json '{"custom_operator_paths": ["./custom_operators"]}'
```

---

## 4. assemble_plan

Assemble the complete plan.

### Input Schema

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `intent` | str | Yes | Processing intent |
| `dataset_spec` | dict | Yes | `build_dataset_spec` output |
| `process_spec` | dict | Yes | `build_process_spec` output |
| `system_spec` | dict | Yes | `build_system_spec` output |

### Command

```bash
djx tool run assemble_plan --input-json '{
  "intent": "<PROCESSING_GOAL>",
  "dataset_spec": <DATASET_SPEC>,
  "process_spec": <PROCESS_SPEC>,
  "system_spec": <SYSTEM_SPEC>
}'
```

---

## 5. plan_save

Save the plan to a YAML file.

### Input Schema

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `plan_payload` | dict | Yes | `assemble_plan` output |
| `output_path` | str | Yes | Output YAML file path |

> **The parameter name is `output_path`, not `path`**. The `--yes` flag is required.

### Command

```bash
djx tool run plan_save --yes --input-json '{
  "plan_payload": <PLAN_PAYLOAD>,
  "output_path": ".djx/plans/my_plan.yaml"
}'
```

---

## Must-Read Pitfalls

### 1. plan_save Parameter Is output_path

**Wrong**
```bash
djx tool run plan_save --input-json '{"plan_payload": ..., "path": "plan.yaml"}'
```

**Correct**
```bash
djx tool run plan_save --yes --input-json '{"plan_payload": ..., "output_path": "plan.yaml"}'
```

### 2. Operator Names Must Come from retrieve_operators

Do not guess or use operator names from memory.

### 3. Operators Must Be Ordered by Type

```bash
# Correct order: Mapper → Filter → Deduplicator
[
  {"name": "clean_html_mapper", "params": {}},      # Mapper
  {"name": "text_length_filter", "params": {...}},  # Filter
  {"name": "document_deduplicator", "params": {}}   # Deduplicator
]
```

### 4. dataset_profile Must Be the Complete Output

Paste the **complete JSON output** from `inspect_dataset` — do not extract only partial fields.

---

## Error Handling

| Scenario | Solution |
|----------|----------|
| Unknown operator name | Verify it comes from `retrieve_operators` results |
| Parameter type mismatch | Check the params definition in `retrieve_operators` output |
| Missing dataset_profile | Run `inspect_dataset` first |
| plan_save blocks | Add the `--yes` flag |

---

## Skill Responsibilities

| Scenario | Skill to Use |
|----------|--------------|
| Main flow | data-juicer |
| Search for operators | djx_retrieve |
| Build spec/plan | **djx_plan (this skill)** |
| Execute plan | djx_apply |
