---
name: djx_dev
description: >-
  Data-Juicer custom operator development: scaffold generation, testing, pipeline integration.
  Trigger keywords: develop_operator, custom operator, create operator, new operator,
  scaffold, extension.
  Use when existing operators don't meet requirements and custom processing logic is needed.
  Related skills: data-juicer (main flow), djx_plan (integrating custom operators).
allowed-tools: Bash, Read, Write
argument-hint: "<operator_name> <output_dir>"
user-invocable: true
---

# Data-Juicer Skills: Dev (Custom Operator Development)

Develop custom Data-Juicer operators — when existing operators don't meet your needs.

---

## Core Rule: Use djx tool Only

**You must only use the `djx tool` CLI**. Do not use the session or cap modules.

---

## Prerequisites

| Condition | Requirement |
|-----------|-------------|
| **Confirm no existing operator** | Run `retrieve_operators` first |
| **Python development skills** | Understanding of Python and Data-Juicer operator mechanism |

---

## Pre-Development Check

**Always confirm no existing operator meets the need first**:

```bash
djx tool run retrieve_operators --input-json '{"intent": "describe the functionality you need"}'
```

Only develop a custom operator if the search results truly cannot satisfy the requirement.

---

## Core Tool: develop_operator

Generates an operator scaffold (mapper or filter) based on a natural language intent.

### Input Schema

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `intent` | str | Yes | — | Operator functionality description (natural language) |
| `operator_name` | str | Yes | — | Operator name in snake_case format |
| `output_dir` | str | Yes | — | Output directory |
| `operator_type` | str | No | — | `mapper` or `filter` (can be inferred) |
| `from_retrieve` | str | No | — | Path to JSON file from `retrieve_operators` output |
| `smoke_check` | bool | No | false | Run basic validation after generation |

### Command

```bash
djx tool run develop_operator --yes --input-json '{
  "intent": "extract email addresses and mask them",
  "operator_name": "email_mask_mapper",
  "output_dir": "./custom_operators",
  "smoke_check": true
}'
```

---

## Output Structure

The tool generates three files:

```
output_dir/
├── <operator_name>.py         # Operator implementation
├── test_<operator_name>.py    # Test scaffold
└── summary.md                  # Design notes and usage instructions
```

### Generated Operator Characteristics

- Inherits from `Filter` or `Mapper` base class
- Uses `@OPERATORS.register_module('<operator_name>')` decorator
- Contains placeholder logic that needs custom implementation

> **The scaffold is a starting point** — review and customize the implementation logic.

---

## Naming Conventions

| Rule | Pattern | Example |
|------|---------|---------|
| Use snake_case | `my_custom_filter` | Yes |
| Include type suffix | `_filter`, `_mapper` | `email_mask_mapper` |
| Descriptive naming | Name reflects functionality | `phone_sanitizer_filter` |

---

## Pipeline Integration

### 1. Generate Operator Scaffold

```bash
djx tool run develop_operator --yes --input-json '{...}'
```

### 2. Customize Implementation

Edit the generated `.py` file to implement the specific logic.

### 3. Test

Run tests independently:
```bash
pytest test_email_mask_mapper.py
```

### 4. Integrate into Pipeline

Pass the custom operator path in `build_system_spec`:

```bash
djx tool run build_system_spec --input-json '{"custom_operator_paths": ["./custom_operators"]}'
```

Use the operator in `build_process_spec`:

```bash
djx tool run build_process_spec --input-json '{
  "operators": [
    {"name": "email_mask_mapper", "params": {}}
  ]
}'
```

> **The operator must be importable from the specified path** and registered with `@OPERATORS.register_module`.

---

## Complete Development Flow

```bash
# Step 1: Confirm no existing operator meets the need
djx tool run retrieve_operators --input-json '{"intent": "email masking"}'
# Results don't satisfy the requirement

# Step 2: Generate scaffold
djx tool run develop_operator --yes --input-json '{
  "intent": "extract email addresses from text and mask them",
  "operator_name": "email_mask_mapper",
  "output_dir": "./custom_operators",
  "smoke_check": true
}'

# Step 3: Review generated files
cat ./custom_operators/email_mask_mapper.py

# Step 4: Customize implementation
# Edit the .py file...

# Step 5: Test
pytest ./custom_operators/test_email_mask_mapper.py

# Step 6: Integrate into pipeline
djx tool run build_system_spec --input-json '{"custom_operator_paths": ["./custom_operators"]}'

# Step 7: Use in process_spec
djx tool run build_process_spec --input-json '{
  "operators": [{"name": "email_mask_mapper", "params": {}}]
}'
```

---

## Error Handling

| Scenario | Solution |
|----------|----------|
| `smoke_check` fails | Check the error — fix syntax or import issues in generated code |
| Operator name conflict | Use `retrieve_operators` to check and avoid naming conflicts |
| Runtime import error | Ensure operator directory is in `custom_operator_paths` |
| `from_retrieve` JSON invalid | Verify the file path and content come from `retrieve_operators` |

---

## Must-Read Pitfalls

### 1. Search Before Developing

Do not skip the `retrieve_operators` step. An existing operator may already meet the need.

### 2. Custom Implementation Is Required

The scaffold only generates the framework; the specific logic must be implemented by you.

### 3. Registration Name Must Match

The name in `@OPERATORS.register_module('<name>')` must match the name used in `build_process_spec`.

### 4. Path Configuration Must Be Correct

Ensure `custom_operator_paths` points to the directory containing the operator `.py` files.

---

## Skill Responsibilities

| Scenario | Skill to Use |
|----------|--------------|
| Search for existing operators | djx_retrieve |
| Develop custom operators | **djx_dev (this skill)** |
| Integrate into pipeline | djx_plan |
| Main flow | data-juicer |
