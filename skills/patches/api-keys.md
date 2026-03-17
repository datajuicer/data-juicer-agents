---
name: api-keys
description: API key configuration issues
when:
  - error contains ["API", "key", "unauthorized", "401", "authentication", "credential"]
---

# Patch: API Key Configuration

## Problem

API or authentication errors when running `djx plan` or `dj-agents`.

## Symptoms

- "API key not found"
- "Unauthorized" or "401"
- "Authentication failed"
- "Invalid API key"

---

## Solution

### Step 1: Set primary API key

```bash
export DASHSCOPE_API_KEY="your_key"
```

Or use alternative:

```bash
export MODELSCOPE_API_TOKEN="your_key"
```

### Step 2: Verify key is set

```bash
echo $DASHSCOPE_API_KEY
# Should print your key
```

### Step 3: For OpenAI-compatible endpoints

```bash
export DJA_OPENAI_BASE_URL="https://your-endpoint/v1"
export DASHSCOPE_API_KEY="your_key"
```

---

## API Key Priority

The system checks in this order:
1. `DASHSCOPE_API_KEY`
2. `MODELSCOPE_API_TOKEN`

---

## Model Configuration

```bash
# Model for djx plan
export DJA_PLANNER_MODEL="qwen3-max-2026-01-23"

# Model for dj-agents
export DJA_SESSION_MODEL="qwen3-max-2026-01-23"

# Fallback models (comma-separated)
export DJA_MODEL_FALLBACKS="qwen-max,qwen-plus"
```

---

## Thinking Mode

Some models don't support the thinking flag:

```bash
# Disable if model rejects thinking
export DJA_LLM_THINKING="false"
```

---

## Verify Configuration

```bash
# Test with simple retrieve command
djx retrieve "test" --top-k 1

# If successful, API is configured correctly
```
