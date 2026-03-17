---
name: timeout
description: Execution timeout issues
when:
  - error contains ["timeout", "timed out", "exceeded", "deadline"]
  - process hangs or takes too long
---

# Patch: Timeout Handling

## Problem

Execution times out or takes too long.

## Symptoms

- "Execution timed out"
- Process hangs without output
- "Deadline exceeded"

---

## Solution

### Increase execution timeout

Default timeout is 300 seconds (5 minutes).

```bash
# Increase to 30 minutes
djx apply --plan ./plans/plan_xxx.yaml --yes --timeout 1800

# Increase to 1 hour for very large datasets
djx apply --plan ./plans/plan_xxx.yaml --yes --timeout 3600
```

---

## Planning Timeout

Planning timeout is not configurable via CLI. If planning times out:

### Option 1: Simplify intent

```bash
# Instead of complex intent
djx plan "clean, deduplicate, filter by length, normalize, remove special chars" ...

# Use simpler intent
djx plan "clean and deduplicate text" ...
```

### Option 2: Reduce dataset for planning

The planner samples the dataset. If the dataset is too large:

```bash
# Create a smaller sample for planning
head -1000 ./data/large.jsonl > ./data/sample.jsonl

# Plan with sample
djx plan "clean data" --dataset ./data/sample.jsonl --export ./data/output.jsonl

# Modify plan to use full dataset, then apply
```

### Option 3: Check model availability

Slow responses might indicate model issues:

```bash
# Try a different model
export DJA_PLANNER_MODEL="qwen-plus"
```

---

## Timeout Guidelines

| Dataset Size | Recommended Timeout |
|--------------|---------------------|
| < 10K samples | 300 (default) |
| 10K - 100K | 900 (15 min) |
| 100K - 1M | 1800 (30 min) |
| > 1M | 3600+ (1+ hour) |

---

## Parallel Processing

For large datasets, consider using more processes:

```yaml
# In the generated recipe
np: 4  # Use 4 parallel processes
```

Note: This requires manual recipe editing after plan generation.
