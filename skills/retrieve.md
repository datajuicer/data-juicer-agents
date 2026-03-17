---
name: retrieve
description: Search operators by intent
when:
  - user_intent contains ["search operator", "what operators", "find operator", "搜索算子", "有哪些算子", "查找"]
priority: low
note: Optional - djx plan already retrieves internally
---

# Retrieve Skill

Search Data-Juicer operators by natural language intent.

**Note**: This is an **optional** step. `djx plan` already retrieves operators internally.

## When to Use

- Exploring available operators before planning
- Debugging operator selection
- Getting context for custom operator development

## Command

```bash
djx retrieve "<intent>" [--top-k 10] [--mode auto|llm|vector] [--dataset <path>] [--json]
```

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `intent` | Required | Natural language search query |
| `--top-k` | 10 | Maximum number of results |
| `--mode` | auto | Retrieval mode: `auto`, `llm`, or `vector` |
| `--dataset` | None | Dataset for schema probing |
| `--json` | false | Output in JSON format |

---

## Examples

### Basic search

```bash
djx retrieve "filter text by length"
```

### JSON output for scripting

```bash
djx retrieve "deduplicate images" --json
```

### With dataset context

```bash
djx retrieve "process multimodal data" --dataset ./data/multimodal.jsonl
```

### Limit results

```bash
djx retrieve "text cleaning" --top-k 5
```

---

## Output

### Human-readable (default)

```
1. text_length_filter (0.95) - Filter samples by text length
2. document_deduplicator (0.87) - Remove duplicate documents
...
```

### JSON format (`--json`)

```json
{
  "candidates": [
    {"operator_name": "text_length_filter", "description": "...", "score": 0.95}
  ],
  "source": "vector",
  "notes": "..."
}
```

---

## Use Cases

### 1. Exploration before planning

```bash
# See what's available
djx retrieve "text quality filtering" --top-k 15

# Then plan with knowledge
djx plan "filter low quality text" --dataset ./input.jsonl --export ./output.jsonl
```

### 2. Context for custom operator

```bash
# Find similar operators
djx retrieve "sentiment analysis" --json > context.json

# Use as reference for development
djx dev "sentiment filter" \
    --operator-name sentiment_filter \
    --output-dir ./custom_ops \
    --from-retrieve context.json
```

### 3. Debugging operator selection

```bash
# Check what operators match your intent
djx retrieve "clean HTML tags" --json | jq '.candidates[].operator_name'
```

---

## Retrieval Modes

| Mode | Description |
|------|-------------|
| `auto` | Automatically choose best method |
| `vector` | Semantic vector search |
| `llm` | LLM-based matching |

---

## Reminder

For most use cases, skip this step and go directly to [plan.md](plan.md):

```bash
djx plan "your intent" --dataset ./input.jsonl --export ./output.jsonl
```

The plan command handles retrieval internally.
