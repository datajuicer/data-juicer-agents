---
name: session
description: Conversational interface for Data-Juicer
when:
  - user prefers conversational/interactive mode
  - user_intent contains ["interactive", "conversational", "chat", "对话", "交互", "dj-agents"]
---

# Session Skill

Start conversational interface (`dj-agents`) for interactive Data-Juicer operations.

## Command

```bash
dj-agents --dataset <path> --export <path> [--ui plain|tui] [--verbose]
```

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--dataset` | Required | Input dataset path |
| `--export` | Required | Output dataset path |
| `--ui` | tui | Interface mode: `tui` or `plain` |
| `--verbose` | false | Verbose output |

---

## Examples

### Default TUI mode

```bash
dj-agents --dataset ./data/input.jsonl --export ./data/output.jsonl
```

### Plain terminal mode

```bash
dj-agents --ui plain --dataset ./data/input.jsonl --export ./data/output.jsonl
```

### With verbose output

```bash
dj-agents --verbose --dataset ./data/input.jsonl --export ./data/output.jsonl
```

---

## Controls

| Key | Action |
|-----|--------|
| `Ctrl+C` | Interrupt current turn (can continue) |
| `Ctrl+D` | Exit session |

---

## Internal Tool Chain

The session agent typically uses this sequence:

```
inspect_dataset
    -> retrieve_operators
    -> build_dataset_spec
    -> build_process_spec
    -> build_system_spec
    -> assemble_plan
    -> plan_validate
    -> plan_save
    -> apply_recipe
```

---

## When to Use

| Scenario | Recommendation |
|----------|----------------|
| Simple, well-defined task | Use `djx plan` + `djx apply` instead |
| Complex, exploratory task | Use `dj-agents` |
| Need iterative refinement | Use `dj-agents` |
| Scripting/automation | Use `djx` CLI commands |

---

## Requirements

- LLM API access required
- Set `DASHSCOPE_API_KEY` or `MODELSCOPE_API_TOKEN`
- Optionally configure `DJA_SESSION_MODEL`

---

## Environment Configuration

```bash
# Required: API key
export DASHSCOPE_API_KEY="your_key"

# Optional: Custom model
export DJA_SESSION_MODEL="qwen3-max-2026-01-23"

# Optional: Fallback models
export DJA_MODEL_FALLBACKS="qwen-max,qwen-plus"
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Session won't start | Check API key is set |
| Model errors | Try different model in `DJA_SESSION_MODEL` |
| Session interrupted | Press `Ctrl+C` to resume, `Ctrl+D` to exit |

See [debug.md](debug.md) for detailed troubleshooting.

---

## Comparison: CLI vs Session

| Feature | `djx` CLI | `dj-agents` |
|---------|-----------|-------------|
| Explicit control | Yes | No |
| Scriptable | Yes | No |
| Interactive refinement | No | Yes |
| LLM required | Only for `plan` | Always |
