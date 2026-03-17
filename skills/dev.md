---
name: dev
description: Generate custom operator scaffold
when:
  - user_intent contains ["custom", "new operator", "develop", "自定义", "新算子", "开发"]
  - no built-in operator matches user requirement
next: plan.md
---

# Dev Skill

Generate custom operator scaffold for Data-Juicer.

## Command

```bash
djx dev "<intent>" --operator-name <name> --output-dir <dir> [--type mapper|filter] [--smoke-check]
```

## Required Arguments

| Argument | Description |
|----------|-------------|
| `intent` | Description of what the operator should do |
| `--operator-name` | Operator name in snake_case |
| `--output-dir` | Output directory for generated files |

## Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--type` | auto | Operator type: `mapper` or `filter` |
| `--from-retrieve` | None | Path to retrieve JSON for context |
| `--smoke-check` | false | Run validation test after generation |

---

## Examples

### Create a filter operator

```bash
djx dev "Filter samples by sentiment score above threshold" \
    --operator-name sentiment_threshold_filter \
    --output-dir ./custom_ops \
    --type filter \
    --smoke-check
```

### Create a mapper operator

```bash
djx dev "Normalize Unicode characters to ASCII" \
    --operator-name unicode_normalizer_mapper \
    --output-dir ./custom_ops \
    --type mapper
```

### With context from retrieve

```bash
# Step 1: Get similar operators for context
djx retrieve "sentiment analysis" --json > context.json

# Step 2: Generate with context
djx dev "Filter by sentiment score" \
    --operator-name sentiment_filter \
    --output-dir ./custom_ops \
    --from-retrieve context.json
```

---

## Output Files

| File | Description |
|------|-------------|
| `<name>.py` | Operator implementation |
| `test_<name>.py` | Test scaffold |
| `<name>_SUMMARY.md` | Usage documentation |

## Naming Convention

| Type | Class Name Pattern |
|------|-------------------|
| Filter | `<Name>Filter` |
| Mapper | `<Name>Mapper` |

Example: `sentiment_threshold_filter` -> `SentimentThresholdFilter`

---

## Complete Workflow

```bash
# 1. (Optional) Search similar operators
djx retrieve "sentiment analysis" --json > context.json

# 2. Generate operator scaffold
djx dev "Filter by sentiment score threshold" \
    --operator-name sentiment_threshold_filter \
    --output-dir ./custom_ops \
    --type filter \
    --from-retrieve context.json \
    --smoke-check

# 3. Edit generated code as needed
# vim ./custom_ops/sentiment_threshold_filter.py

# 4. Use in plan
djx plan "filter by sentiment" \
    --dataset ./input.jsonl \
    --export ./output.jsonl \
    --custom-operator-paths ./custom_ops

# 5. Execute
djx apply --plan ./plans/plan_xxx.yaml --yes
```

---

## Operator Types

### Filter

- Decides whether to keep or drop a sample
- Returns `True` to keep, `False` to drop
- Use for: quality filtering, language filtering, length filtering

### Mapper

- Transforms a sample
- Returns modified sample
- Use for: text normalization, field extraction, format conversion

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Smoke check fails | Review generated code, fix errors |
| Operator not found in plan | Verify `--custom-operator-paths` includes the directory |
| Name mismatch | Use snake_case for `--operator-name` |

See [debug.md](debug.md) for detailed troubleshooting.
