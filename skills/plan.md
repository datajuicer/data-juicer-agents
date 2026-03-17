---
name: plan
description: Generate execution plan from natural language intent
when:
  - user_intent contains ["process", "clean", "filter", "deduplicate", "plan", "处理", "清洗", "过滤", "去重"]
  - no plan.yaml exists in context
next: apply.md
---

# Plan Skill

Generate a Data-Juicer execution plan from natural language intent.

## Command

```bash
djx plan "<intent>" --dataset <input.jsonl> --export <output.jsonl> [--output <plan.yaml>]
```

## Required Arguments

| Argument | Description |
|----------|-------------|
| `intent` | Natural language task description (quoted) |
| `--dataset` | Input dataset path (JSONL format) |
| `--export` | Output dataset path |

## Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--output` | `plans/plan_<id>.yaml` | Custom plan output path |
| `--custom-operator-paths` | None | Directories with custom operators |

---

## Examples

### Basic text cleaning

```bash
djx plan "clean text: remove duplicates, filter short samples" \
    --dataset ./data/input.jsonl \
    --export ./data/output.jsonl
```

### Language filtering

```bash
djx plan "filter to keep only English text with min length 100" \
    --dataset ./data/input.jsonl \
    --export ./data/english_only.jsonl
```

### Multimodal deduplication

```bash
djx plan "deduplicate images and text" \
    --dataset ./data/multimodal.jsonl \
    --export ./data/deduped.jsonl
```

### With custom operators

```bash
djx plan "filter by sentiment score" \
    --dataset ./data/input.jsonl \
    --export ./data/output.jsonl \
    --custom-operator-paths ./custom_ops
```

---

## Behavior

1. Internally retrieves matching operators (no need for separate `djx retrieve`)
2. Builds dataset spec from input file schema
3. Calls LLM to generate operator sequence
4. Validates plan and saves to YAML

## Output

```
Plan generated: plans/plan_abc123.yaml
Modality: text
Operators: whitespace_normalization_mapper, text_length_filter, document_deduplicator
```

---

## Common Intent Patterns

| Goal | Intent Example |
|------|----------------|
| Remove duplicates | "deduplicate text documents" |
| Filter by length | "filter text by length, keep 100-5000 chars" |
| Clean whitespace | "normalize whitespace and punctuation" |
| Language filter | "keep only English text" |
| Quality filter | "filter low quality text samples" |

---

## Next Step

After plan generation, execute with [apply.md](apply.md):

```bash
djx apply --plan ./plans/plan_xxx.yaml --yes
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Plan generation fails | Check API key: `echo $DASHSCOPE_API_KEY` |
| Wrong operators selected | Be more specific in intent |
| Custom operator not found | Verify `--custom-operator-paths` |

See [debug.md](debug.md) for detailed troubleshooting.
