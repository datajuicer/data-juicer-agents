---
name: data-juicer
description: CLI toolbox for AI agents to process datasets with Data-Juicer operators
auto_load: true
---

# Data Juicer Skills - Router

Load specific skills based on context state. This file is always loaded as the entry point.

## Context -> Skill Mapping

| Context State | Load Skill | Action |
|---------------|------------|--------|
| User wants to process dataset + no plan exists | [plan.md](plan.md) | Generate execution plan |
| Plan file exists (.yaml) | [apply.md](apply.md) | Execute the plan |
| User asks about available operators | [retrieve.md](retrieve.md) | Search operators (optional) |
| User needs custom operator | [dev.md](dev.md) | Generate operator scaffold |
| User prefers conversational mode | [session.md](session.md) | Start dj-agents |
| Execution failed / error occurred | [debug.md](debug.md) | Troubleshoot issues |

---

## Quick Decision Tree

```
User Request
    │
    ├─ "Process/clean/filter my dataset"
    │   └─> plan.md -> apply.md
    │
    ├─ "I need a custom operator"
    │   └─> dev.md -> plan.md -> apply.md
    │
    ├─ "What operators are available?"
    │   └─> retrieve.md (optional, plan.md does this internally)
    │
    ├─ "I want interactive mode"
    │   └─> session.md
    │
    └─ "Something failed / error"
        └─> debug.md -> patches/
```

---

## Standard Workflows

### Workflow 1: Process Dataset (Most Common)

```bash
djx plan "<intent>" --dataset ./input.jsonl --export ./output.jsonl
djx apply --plan ./plans/plan_xxx.yaml --yes
```

### Workflow 2: Custom Operator Development

```bash
djx dev "<intent>" --operator-name my_filter --output-dir ./custom_ops --type filter
djx plan "<intent>" --dataset ./input.jsonl --export ./output.jsonl --custom-operator-paths ./custom_ops
djx apply --plan ./plans/plan_xxx.yaml --yes
```

### Workflow 3: Conversational Mode

```bash
dj-agents --dataset ./input.jsonl --export ./output.jsonl
```

---

## Environment Variables (Quick Reference)

| Variable | Purpose |
|----------|---------|
| `DASHSCOPE_API_KEY` | API credential (primary) |
| `DJA_PLANNER_MODEL` | Model for `djx plan` |
| `DJA_SESSION_MODEL` | Model for `dj-agents` |

See [debug.md](debug.md) for troubleshooting API issues.

---

## Skill Index

| Skill | When to Load |
|-------|--------------|
| [plan.md](plan.md) | Generate plan from intent |
| [apply.md](apply.md) | Execute existing plan |
| [retrieve.md](retrieve.md) | Explore operators |
| [dev.md](dev.md) | Create custom operators |
| [session.md](session.md) | Conversational interface |
| [debug.md](debug.md) | Troubleshoot errors |

### Patches (Load on specific errors)

| Patch | Trigger |
|-------|---------|
| [patches/api-keys.md](patches/api-keys.md) | API/auth errors |
| [patches/timeout.md](patches/timeout.md) | Timeout errors |
| [patches/custom-ops.md](patches/custom-ops.md) | Operator not found |
| [patches/dataset.md](patches/dataset.md) | Dataset format errors |
