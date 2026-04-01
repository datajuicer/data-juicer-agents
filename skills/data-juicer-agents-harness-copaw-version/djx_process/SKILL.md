---
name: djx_process
description: >-
  Data-Juicer execution and file management: shell command execution, Python code execution, file read/write/insert operations.
  Trigger keywords: execute_shell, execute_python, view_file, write_file, insert_file,
  shell command, run Python, read file, write file.
  Use when you need to execute system commands, run Python code snippets, or manipulate text files.
  Note: Data processing should use Data-Juicer operators, not Python scripts.
  Related skills: data-juicer (main flow), djx_apply (execution).
allowed-tools: Bash, Read, Write
argument-hint: "<command_or_code>"
user-invocable: true
---

# Data-Juicer Skills: Process & Files

Execution tools (shell/Python) and file management tools (read/write/insert).

---

## Core Rule: Use djx tool Only

**You must only use the `djx tool` CLI**. Do not use the session or cap modules.

---

## Prerequisites

| Condition | Requirement |
|-----------|-------------|
| **Environment** | `djx tool list` runs successfully |
| **File operations** | Read/write permissions on target paths |

---

## When to Use This Skill

| Scenario | Use djx_process | Alternative |
|----------|------------------|-------------|
| Count dataset lines | No | Run `wc -l <file>` directly |
| View first few lines of dataset | No | Run `head -n 5 <file>` directly |
| Quick data analysis | Yes | `execute_python_code` |
| System diagnostics | Yes | `execute_shell_command` |
| Manipulate plan/recipe files | Yes | `view_text_file` / `write_text_file` |
| **Data processing** | No | Use the **data-juicer** main flow |

> **Use Data-Juicer operators for data processing** — do not write Python scripts to process data.

---

## 1. Execution Tools

### execute_shell_command

Execute a shell command on the host.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `command` | str | Yes | — | Shell command |
| `timeout` | int | No | 120 | Timeout in seconds |

**Output**: `{stdout, stderr, exit_code}`

```bash
djx tool run execute_shell_command --input-json '{"command": "ls -la", "timeout": 30}'
```

### execute_python_code

Execute a Python code snippet.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `code` | str | Yes | — | Python code |
| `timeout` | int | No | 120 | Timeout in seconds |

**Output**: `{stdout, stderr, exit_code}`

```bash
djx tool run execute_python_code --input-json '{"code": "import json; print(json.dumps({\"a\": 1}))"}'
```

### Timeout Configuration Guide

| Operation Type | Recommended Timeout |
|----------------|---------------------|
| Quick commands (ls, wc, env) | 30s |
| Data exploration/analysis | 60-120s |
| dj-process processing | 300-600s |
| Long-running tasks | 900s+ |

---

## 2. File Tools

### view_text_file

Read text file contents.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | Yes | — | File path |
| `limit` | int | No | — | Maximum lines to return |
| `offset` | int | No | 0 | Starting line offset (0-based) |

```bash
djx tool run view_text_file --input-json '{"file_path": "/path/to/file.yaml", "limit": 50}'
```

### write_text_file

Write or overwrite a text file.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | Yes | — | File path |
| `content` | str | Yes | — | Content to write |
| `ranges` | list | No | — | Line ranges (partial write) |

**Requires `--yes` flag**.

```bash
djx tool run write_text_file --yes --input-json '{"file_path": "/path/to/file.txt", "content": "Hello World"}'
```

### insert_text_file

Insert content at a specified line (does not overwrite existing content).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file_path` | str | Yes | — | File path |
| `content` | str | Yes | — | Content to insert |
| `line_number` | int | Yes | — | Insert position (1-based) |

**Requires `--yes` flag**.

```bash
djx tool run insert_text_file --yes --input-json '{"file_path": "/path/to/file.txt", "content": "New line", "line_number": 10}'
```

---

## Common Command Examples

### Shell Commands

```bash
# List files
djx tool run execute_shell_command --input-json '{"command": "ls -la /data"}'

# Count lines
djx tool run execute_shell_command --input-json '{"command": "wc -l /data/dataset.jsonl"}'

# View first few lines
djx tool run execute_shell_command --input-json '{"command": "head -n 5 /data/dataset.jsonl"}'

# Check environment
djx tool run execute_shell_command --input-json '{"command": "env | grep DJA_"}'
```

### Python Analysis

```bash
# JSON parsing
djx tool run execute_python_code --input-json '{"code": "import json; data = json.load(open(\"/data/sample.jsonl\")); print(len(data))"}'

# Quick statistics
djx tool run execute_python_code --input-json '{"code": "import json; lengths = [len(json.loads(line)) for line in open(\"/data/dataset.jsonl\")]; print(f\"Avg: {sum(lengths)/len(lengths):.1f}\")"}'
```

---

## Error Handling

| Scenario | Solution |
|----------|----------|
| Command timeout | Increase timeout value |
| Shell special characters | Properly escape within JSON strings |
| Python import error | Verify the package is installed in the environment |
| Interactive commands (vim, less) | Avoid them; use non-interactive alternatives |
| File not found | Verify the path exists |
| Permission denied | Check file/directory permissions |
| Non-UTF-8 encoding | Ensure the file is UTF-8 encoded |

---

## Privacy Rules

When handling sensitive data:
- **Do not** pipe data content to external APIs via shell commands
- Python code should only be used for local data validation
- Model calls should only use localhost endpoints
- Log metadata (counts, lengths), not actual content
- Verify endpoint URLs before making requests

---

## Key Principles

1. **Choose the right tool**: `execute_shell_command` for system tasks, `execute_python_code` for data analysis, file tools for config file operations
2. **Always check results**: Verify `exit_code` and `stderr` after execution
3. **Read before write**: Check file content with `view_text_file` before modifying
4. **Use --yes for write operations**: write/insert operations require `--yes` in automated workflows
5. **Keep Python code focused**: Use for exploration and diagnostics; complex processing should use Data-Juicer operators

---

## Skill Responsibilities

| Scenario | Skill to Use |
|----------|--------------|
| Data processing (cleaning, filtering, dedup) | data-juicer |
| Execute shell/Python | **djx_process (this skill)** |
| Manipulate plan/recipe files | **djx_process (this skill)** |
| Execute recipes | djx_apply |
