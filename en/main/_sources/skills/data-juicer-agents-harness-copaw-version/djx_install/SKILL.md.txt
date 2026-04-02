---
name: djx_install
description: >-
  Data-Juicer Agents installation and setup guide: environment setup, dependency installation, version verification, common issues.
  Trigger keywords: install, setup, environment configuration, pip install, uv install,
  djx command not found, ModuleNotFoundError, version issues, Python version.
  Use for first-time installation, environment problems, installation failures, or version incompatibilities.
  Related skills: djx_auth (authentication), data-juicer (main flow).
allowed-tools: Bash, Read
argument-hint: ""
user-invocable: true
---

# Data-Juicer Skills: Installation & Setup

Install and configure the Data-Juicer Agents environment.

---

## Prerequisites

| Requirement | Specification | Notes |
|-------------|---------------|-------|
| **Python version** | 3.10, 3.11, or 3.12 | Python 3.13+ is **not supported** |
| **Package manager** | `uv` (recommended) or `pip` | uv is 10-100x faster than pip |
| **Git** | Latest stable version | For cloning and development |
| **Virtual environment** | Required | Never install globally |

---

## Installation Steps

### 1. Get the Code

```bash
cd /path/to/your/workspace
git clone https://github.com/data-juicer/data-juicer-agents.git
cd data-juicer-agents
```

### 2. Create Virtual Environment

```bash
# Recommended: using uv
uv venv --python 3.11 .venv
source .venv/bin/activate

# Alternative: using Python built-in
python3.11 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# Recommended: editable mode installation
uv pip install -e .

# Development dependencies (pytest, black, etc.)
uv pip install -e ".[dev]"

# QA / vector search dependencies
uv pip install -e ".[qa]"

# All optional dependencies
uv pip install -e ".[dev,qa]"
```

### 4. Verify Installation

```bash
# Check djx command
djx --help

# List all tools
djx tool list

# Check tool schema
djx tool schema inspect_dataset

# Verify core dependency
python -c "import data_juicer; print(data_juicer.__version__)"

# Check virtual environment
which djx
# Expected: /path/to/data-juicer-agents/.venv/bin/djx
```

---

## Core Dependencies

Base installation includes:

| Dependency | Purpose |
|------------|---------|
| `agentscope` | Agent framework |
| `py-data-juicer>=1.4.0` | Core Data-Juicer library |
| `fastapi` | API server framework |
| `transformers` | HuggingFace transformers |
| `faiss-cpu` | Vector similarity search |

---

## Quick Verification Checklist

Run these checks after installation:

```bash
# □ 1. Check Python version
python --version  # Should show 3.10/3.11/3.12

# □ 2. Check virtual environment is active
which djx  # Should point to .venv/bin/djx

# □ 3. List available tools
djx tool list  # Should show 8 tools

# □ 4. Check core library
python -c "import data_juicer; print('OK')"

# □ 5. Test a simple command
djx tool run inspect_dataset --input-json '{"dataset_path": "test.jsonl", "sample_size": 5}'
# If no test file exists, it will report file not found, but confirms the tool is available
```

---

## Error Handling

### `uv: command not found`

**Cause**: uv is not installed.

**Solution**:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart shell or source config
source ~/.bashrc  # or ~/.zshrc
```

### Python Version Incompatible

**Cause**: `pyproject.toml` requires `>=3.10,<3.13`.

**Solution**:
```bash
# Check current version
python --version

# Install correct version
uv python install 3.12
uv venv --python 3.12
```

### `djx: command not found` After Installation

**Cause**: Virtual environment not activated or PATH issue.

**Solution**:
```bash
# Activate virtual environment
source .venv/bin/activate

# Or run directly
.venv/bin/djx --help
```

### `ModuleNotFoundError: No module named 'data_juicer'`

**Cause**: py-data-juicer not installed or wrong environment.

**Solution**:
```bash
# Ensure you're in the virtual environment
source .venv/bin/activate
uv pip install py-data-juicer
```

### Dependency Conflicts

**Cause**: Global packages conflict with project dependencies.

**Solution**: Use an isolated virtual environment:
```bash
rm -rf .venv
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e .
```

### Permission Errors

**Cause**: Attempting global installation or using sudo.

**Solution**: Never use `sudo`. Always use a virtual environment.

### Slow Installation

**Cause**: Using pip instead of uv.

**Solution**:
```bash
# pip: ~15 minutes
pip install -e .

# uv: ~2 minutes (10x faster)
uv pip install -e .
```

---

## Best Practices

| Practice | Description |
|----------|-------------|
| **Always use virtual environments** | Avoid dependency conflicts and global pollution |
| **Prefer uv** | 10-100x faster than pip |
| **Explicitly specify Python version** | Create a `.python-version` file |
| **Verify after installation** | Run `djx tool list` to confirm |
| **Reinstall after pulling code** | Dependencies may have changed: `git pull && uv pip install -e .` |
| **Update uv regularly** | `uv self update` |

---

## Environment Variables

After installation, configure runtime environment variables:

```bash
# API Key (for LLM mode)
export DASHSCOPE_API_KEY="your-api-key"

# Model configuration
export DJA_SESSION_MODEL="qwen-max"
export DJA_PLANNER_MODEL="qwen-max"
```

See **djx_auth** skill for details.

---

## Skill Responsibilities

| Scenario | Skill to Use |
|----------|--------------|
| Installation / environment issues | **djx_install (this skill)** |
| Authentication / API Key configuration | djx_auth |
| Start processing data | data-juicer |
