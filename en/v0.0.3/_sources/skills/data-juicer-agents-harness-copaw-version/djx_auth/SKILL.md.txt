---
name: djx_auth
description: >-
  Data-Juicer authentication and configuration: API Key setup, model selection, environment variables, cloud/local backend switching.
  Trigger keywords: authentication, auth, API Key, DASHSCOPE, MODELSCOPE, environment variables,
  401 Unauthorized, token, API key configuration, model configuration.
  Use when configuring API Keys, switching models, configuring backends, or encountering authentication errors.
  Related skills: djx_install (installation), djx_local_model (local models), data-juicer (main flow).
allowed-tools: Bash, Read
argument-hint: ""
user-invocable: true
---

# Data-Juicer Skills: Authentication & Configuration

Environment variable configuration — API access, model selection, backend routing.

---

## Core Rule: Use djx tool Only

**You must only use the `djx tool` CLI**. Do not use the session or cap modules.

---

## Environment Variable Reference

| Variable | Purpose | Required | Default |
|----------|---------|----------|---------|
| `DASHSCOPE_API_KEY` | DashScope/Aliyun API authentication | Yes (cloud) | — |
| `MODELSCOPE_API_TOKEN` | ModelScope API authentication (alternative) | Alternative | — |
| `DJA_OPENAI_BASE_URL` | LLM endpoint override | No | DashScope default |
| `DJA_SESSION_MODEL` | dj-agents session model | No | `qwen-max` |
| `DJA_PLANNER_MODEL` | djx plan generation model | No | `qwen-max` |
| `DJA_MODEL_FALLBACKS` | Comma-separated fallback models | No | — |
| `DJA_LLM_THINKING` | Enable extended thinking mode | No | `false` |

---

## Configuration Options

### Cloud: DashScope (Default)

```bash
export DASHSCOPE_API_KEY="sk-your-api-key-here"

# Optional overrides
export DJA_SESSION_MODEL="qwen-max"
export DJA_PLANNER_MODEL="qwen-max"
export DJA_LLM_THINKING="true"
```

### Cloud: Custom OpenAI-Compatible Endpoint

```bash
export DJA_OPENAI_BASE_URL="https://your-custom-endpoint.com/v1"
export DASHSCOPE_API_KEY="your-endpoint-api-key"
export DJA_SESSION_MODEL="gpt-4o"
export DJA_PLANNER_MODEL="gpt-4o"
```

### Local: Ollama

See **djx_local_model** skill for details. Quick configuration:

```bash
export DJA_OPENAI_BASE_URL="http://localhost:11434/v1"
export DASHSCOPE_API_KEY="ollama"
export DJA_SESSION_MODEL="qwen3.5:0.8b"
export DJA_PLANNER_MODEL="qwen3.5:0.8b"
export DJA_LLM_THINKING="false"
```

---

## Credential Priority

1. Environment variables (highest)
2. `.env` file in project root
3. None (error)

---

## Verify Configuration

```bash
# Check current configuration
env | grep -E "DASHSCOPE|DJA_|MODELSCOPE"

# Test connection
djx tool run retrieve_operators --input-json '{"intent":"test","top_k":1,"mode":"llm"}'
```

---

## Error Handling

| Scenario | Solution |
|----------|----------|
| `401 Unauthorized` | Verify `DASHSCOPE_API_KEY` is set and valid |
| Connection timeout | Check that `DJA_OPENAI_BASE_URL` is reachable |
| `DJA_LLM_THINKING=true` model doesn't support it | Set to `false` for local/unsupported models |
| Mixed cloud/local behavior | Update **all** related variables when switching backends |

---

## Must-Read Pitfalls

### 1. Never Hardcode API Keys

Use environment variables or `.env` files; never write keys into code.

### 2. Update All Variables When Switching Backends

```bash
# Switch to local
export DJA_OPENAI_BASE_URL="http://localhost:11434/v1"
export DASHSCOPE_API_KEY="ollama"
export DJA_SESSION_MODEL="qwen3.5:0.8b"
export DJA_PLANNER_MODEL="qwen3.5:0.8b"
export DJA_LLM_THINKING="false"
```

### 3. Verify Configuration Before Execution

```bash
env | grep -E "DASHSCOPE|DJA_"
```

### 4. Use Fallbacks in Production

```bash
export DJA_MODEL_FALLBACKS="qwen-max,qwen-plus,qwen-turbo"
```

---

## Configuration File Locations

| Method | Location |
|--------|----------|
| Environment variables | Shell config (`~/.bashrc`, `~/.zshrc`) |
| `.env` file | Project root directory |
| Temporary settings | Current shell session |

---

## Skill Responsibilities

| Scenario | Skill to Use |
|----------|--------------|
| Install environment | djx_install |
| Configure API Key / model | **djx_auth (this skill)** |
| Configure local models | djx_local_model |
| Start processing data | data-juicer |
