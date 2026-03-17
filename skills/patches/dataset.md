---
name: dataset
description: Dataset format and parsing issues
when:
  - error contains ["JSONL", "JSON", "parse", "invalid", "field", "text", "format"]
---

# Patch: Dataset Format Issues

## Problem

Dataset parsing fails or fields are not recognized.

## Symptoms

- "Invalid JSONL format"
- "Field 'text' not found"
- "JSON parse error"
- "Unexpected format"

---

## Solution

### Step 1: Validate JSONL format

Each line must be valid JSON:

```bash
# Check first line
head -1 ./data/input.jsonl | jq .

# Check all lines (slow for large files)
cat ./data/input.jsonl | jq -c . > /dev/null
```

### Step 2: Check required fields

Default text field is `text`. Verify it exists:

```bash
head -1 ./data/input.jsonl | jq 'keys'
# Should include "text" or your text field
```

---

## Valid JSONL Format

**Correct:**
```jsonl
{"text": "Sample 1", "id": 1}
{"text": "Sample 2", "id": 2}
{"text": "Sample 3", "id": 3}
```

**Wrong - array format:**
```json
[
  {"text": "Sample 1"},
  {"text": "Sample 2"}
]
```

**Wrong - invalid JSON:**
```
{text: "Missing quotes"}
{"text": "Trailing comma",}
```

---

## Custom Text Field

If your dataset uses a different field name (e.g., `content` instead of `text`):

The planner should detect this automatically. If not:

```bash
# Check schema with retrieve
djx retrieve "inspect" --dataset ./data/input.jsonl --json
```

---

## Multimodal Datasets

For image/video datasets, ensure the image field exists:

```jsonl
{"text": "Description", "image": "path/to/image.jpg"}
{"text": "Another", "image": "path/to/image2.jpg"}
```

Verify image paths are valid:

```bash
# Check first image path
head -1 ./data/input.jsonl | jq -r '.image' | xargs ls -la
```

---

## Common Fixes

### Fix 1: Convert array to JSONL

```bash
# If you have JSON array
jq -c '.[]' input.json > input.jsonl
```

### Fix 2: Remove BOM or special characters

```bash
# Remove BOM
sed -i '1s/^\xEF\xBB\xBF//' input.jsonl

# Or on macOS
sed -i '' '1s/^\xEF\xBB\xBF//' input.jsonl
```

### Fix 3: Fix encoding

```bash
# Convert to UTF-8
iconv -f ISO-8859-1 -t UTF-8 input.jsonl > input_utf8.jsonl
```

### Fix 4: Add missing text field

```bash
# If your field is named 'content', add 'text' alias
jq -c '. + {text: .content}' input.jsonl > input_with_text.jsonl
```

---

## Verify with retrieve

Use retrieve to check dataset profile:

```bash
djx retrieve "check dataset" --dataset ./data/input.jsonl --json
```

This probes the dataset schema and reports detected fields.
