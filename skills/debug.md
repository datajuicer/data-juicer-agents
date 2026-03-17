---
name: debug
description: Troubleshoot errors and issues
when:
  - execution failed
  - error message present
  - user_intent contains ["error", "failed", "not working", "出错", "失败", "排查", "问题"]
patches:
  - patches/api-keys.md
  - patches/timeout.md
  - patches/custom-ops.md
  - patches/dataset.md
---

# Debug Skill

Troubleshoot Data-Juicer errors and issues.

## Quick Diagnosis

| Error Pattern | Likely Cause | Go To |
|---------------|--------------|-------|
| `API`, `key`, `unauthorized`, `401` | API configuration | [patches/api-keys.md](patches/api-keys.md) |
| `timeout`, `timed out` | Execution timeout | [patches/timeout.md](patches/timeout.md) |
| `operator not found`, `custom` | Custom operator path | [patches/custom-ops.md](patches/custom-ops.md) |
| `JSONL`, `parse`, `invalid`, `field` | Dataset format | [patches/dataset.md](patches/dataset.md) |

---

## Common Issues

### 1. API/Model Errors

**Symptoms:**
- "API key not found"
- "Unauthorized"
- "Model not available"

**Quick Fix:**
```bash
# Check API key
echo $DASHSCOPE_API_KEY

# Set if missing
export DASHSCOPE_API_KEY="your_key"
```

See [patches/api-keys.md](patches/api-keys.md) for details.

---

### 2. Timeout Errors

**Symptoms:**
- "Execution timed out"
- Process hangs

**Quick Fix:**
```bash
djx apply --plan ./plans/plan_xxx.yaml --yes --timeout 1800
```

See [patches/timeout.md](patches/timeout.md) for details.

---

### 3. Operator Not Found

**Symptoms:**
- "Operator 'xxx' not found"
- Plan validation fails

**Quick Fix:**
```bash
# Verify custom operator path
ls ./custom_ops/

# Include in plan command
djx plan "..." --custom-operator-paths ./custom_ops
```

See [patches/custom-ops.md](patches/custom-ops.md) for details.

---

### 4. Dataset Errors

**Symptoms:**
- "Invalid JSONL"
- "Field 'text' not found"
- Parse errors

**Quick Fix:**
```bash
# Validate JSONL format
head -1 ./data/input.jsonl | jq .

# Check dataset with retrieve
djx retrieve "check" --dataset ./data/input.jsonl
```

See [patches/dataset.md](patches/dataset.md) for details.

---

## Diagnostic Commands

### Check environment

```bash
# API key
echo $DASHSCOPE_API_KEY

# Model configuration
echo $DJA_PLANNER_MODEL
echo $DJA_SESSION_MODEL
```

### Validate plan without execution

```bash
djx apply --plan ./plans/plan_xxx.yaml --dry-run
```

### Check dataset schema

```bash
djx retrieve "inspect" --dataset ./data/input.jsonl --json | jq '.dataset_profile'
```

### Test CLI

```bash
djx --help
djx retrieve "test" --top-k 1
```

---

## Debug Flags

| Flag | Command | Purpose |
|------|---------|---------|
| `--verbose` | All | Expanded output |
| `--debug` | `djx` | Raw structured payloads |
| `--dry-run` | `apply` | Validate without execution |
| `--json` | `retrieve` | Machine-readable output |

---

## Log Locations

- Execution logs: `data/log/`
- Recipes: `.djx/recipes/`
- Plans: `plans/` or custom `--output` path

---

## Still Stuck?

1. Check all patches in `patches/` directory
2. Verify environment variables are set correctly
3. Try with `--verbose` or `--debug` for more details
4. Test with a minimal dataset to isolate the issue
