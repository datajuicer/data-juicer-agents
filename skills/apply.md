---
name: apply
description: Execute a saved plan
when:
  - plan.yaml file exists
  - user_intent contains ["execute", "run", "apply", "执行", "运行"]
prev: plan.md
---

# Apply Skill

Execute a saved Data-Juicer plan.

## Command

```bash
djx apply --plan <plan.yaml> [--yes] [--dry-run] [--timeout 300]
```

## Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--plan` | Yes | - | Path to plan YAML file |
| `--yes` | No | false | Skip confirmation prompt |
| `--dry-run` | No | false | Validate only, don't execute |
| `--timeout` | No | 300 | Execution timeout in seconds |

---

## Examples

### Standard execution

```bash
djx apply --plan ./plans/plan_abc123.yaml --yes
```

### Validate before execution

```bash
djx apply --plan ./plans/plan_abc123.yaml --dry-run
```

### Large dataset (increase timeout)

```bash
djx apply --plan ./plans/plan_abc123.yaml --yes --timeout 1800
```

---

## Behavior

1. Loads plan YAML
2. Writes recipe to `.djx/recipes/<plan_id>.yaml`
3. Executes `dj-process` (unless `--dry-run`)
4. Reports execution status

## Output

```
Execution ID: <id>
Status: success
Recipe: .djx/recipes/plan_abc123.yaml
```

---

## Workflow Integration

### Standard 2-step flow

```bash
# Step 1: Generate plan
djx plan "clean text data" --dataset ./input.jsonl --export ./output.jsonl

# Step 2: Execute
djx apply --plan ./plans/plan_xxx.yaml --yes
```

### Safe execution pattern

```bash
# Validate first
djx apply --plan ./plans/plan_xxx.yaml --dry-run

# Then execute
djx apply --plan ./plans/plan_xxx.yaml --yes
```

---

## Status Codes

| Status | Meaning |
|--------|---------|
| `success` | Execution completed |
| `failed` | Execution error |
| `interrupted` | User cancelled or timeout |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Timeout | Increase with `--timeout 1800` |
| Operator not found | Check custom operator paths in plan |
| Dataset error | Verify input file exists and is valid JSONL |

See [debug.md](debug.md) for detailed troubleshooting.

### Common Errors

**"Plan file not found"**
```bash
# Check plan exists
ls ./plans/
```

**"Execution timeout"**
```bash
# Use longer timeout for large datasets
djx apply --plan ./plans/plan_xxx.yaml --yes --timeout 3600
```
