---
name: custom-ops
description: Custom operator path and resolution issues
when:
  - error contains ["operator not found", "custom", "not registered", "unknown operator"]
---

# Patch: Custom Operator Issues

## Problem

Custom operator not found during plan validation or execution.

## Symptoms

- "Operator 'xxx' not found"
- "Unknown operator"
- Plan validation fails
- Custom operator not recognized

---

## Solution

### Step 1: Verify operator file exists

```bash
ls ./custom_ops/
# Should show: my_operator.py, test_my_operator.py, etc.
```

### Step 2: Check operator name matches

The operator name in the plan must match the file name and class name:

| File Name | Class Name | Operator Name in Plan |
|-----------|------------|----------------------|
| `sentiment_filter.py` | `SentimentFilter` | `sentiment_filter` |
| `my_mapper.py` | `MyMapper` | `my_mapper` |

### Step 3: Include path in plan command

```bash
djx plan "filter by sentiment" \
    --dataset ./input.jsonl \
    --export ./output.jsonl \
    --custom-operator-paths ./custom_ops
```

---

## Naming Convention

| Type | File Pattern | Class Pattern |
|------|--------------|---------------|
| Filter | `*_filter.py` | `*Filter` |
| Mapper | `*_mapper.py` | `*Mapper` |

### Examples

**Filter:**
```
File: sentiment_threshold_filter.py
Class: SentimentThresholdFilter
Usage: sentiment_threshold_filter
```

**Mapper:**
```
File: unicode_normalizer_mapper.py
Class: UnicodeNormalizerMapper
Usage: unicode_normalizer_mapper
```

---

## Multiple Custom Directories

```bash
djx plan "process data" \
    --custom-operator-paths ./custom_ops,./more_ops
```

---

## Verify Operator Structure

Minimum operator file structure:

```python
from data_juicer.ops.filter import Filter  # or Mapper

class MyCustomFilter(Filter):
    def __init__(self, threshold=0.5, **kwargs):
        super().__init__(**kwargs)
        self.threshold = threshold
    
    def compute(self, sample):
        # Return True to keep, False to drop
        return sample.get('score', 0) > self.threshold
```

---

## Path Resolution

Paths can be:
- **Relative**: `./custom_ops` (relative to current directory)
- **Absolute**: `/path/to/custom_ops`

```bash
# Check current directory
pwd

# Use absolute path if relative doesn't work
djx plan "..." --custom-operator-paths /full/path/to/custom_ops
```

---

## Regenerate Operator

If issues persist, regenerate with `djx dev`:

```bash
djx dev "my filter logic" \
    --operator-name my_filter \
    --output-dir ./custom_ops \
    --type filter \
    --smoke-check
```

The `--smoke-check` flag validates the generated operator.
