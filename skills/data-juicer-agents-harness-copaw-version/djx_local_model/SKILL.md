---
name: djx_local_model
description: >-
  Data-Juicer local model processing: Ollama configuration, private data handling, offline workflows.
  Trigger keywords: local model, Ollama, private data, sensitive data, offline,
  do not send to cloud, local LLM.
  Use when processing sensitive/private data, running offline, or configuring local models.
  Related skills: djx_auth (authentication), data-juicer (main flow), djx_retrieve (vector mode).
allowed-tools: Bash, Read
argument-hint: ""
user-invocable: true
---

# Data-Juicer Skills: Local Model Processing

Process **sensitive or private data** — all operations use local models; data never leaves the machine.

---

## Core Rule: Use djx tool Only

**You must only use the `djx tool` CLI**. Do not use the session or cap modules.

---

## Prerequisites

| Condition | Requirement | Verification Command |
|-----------|-------------|---------------------|
| **Ollama installed** | Installed and running | `ollama --version` |
| **Model pulled** | At least one model downloaded | `ollama list` |
| **Service running** | Ollama service is running | `curl http://localhost:11434/v1/models` |

---

## Environment Configuration

Route all LLM calls to local Ollama:

```bash
export DJA_OPENAI_BASE_URL="http://localhost:11434/v1"
export DASHSCOPE_API_KEY="ollama"
export DJA_SESSION_MODEL="qwen3.5:0.8b"
export DJA_PLANNER_MODEL="qwen3.5:0.8b"
export DJA_LLM_THINKING="false"
```

| Variable | Reason for Value |
|----------|------------------|
| `DJA_OPENAI_BASE_URL` | Ollama's OpenAI-compatible endpoint |
| `DASHSCOPE_API_KEY` | Placeholder — Ollama does not validate keys |
| `DJA_SESSION_MODEL` / `DJA_PLANNER_MODEL` | Must match a pulled Ollama model |
| `DJA_LLM_THINKING` | `false` — local models do not support extended thinking |

---

## Ollama Setup

### Start Service

```bash
ollama serve &
```

### Pull Models

```bash
# Lightweight — fast, low resources
ollama pull qwen3.5:0.8b

# Balanced — better quality
ollama pull qwen3.5:2b

# High quality — best results, more resources
ollama pull qwen3.5:4b
```

### Verify

```bash
# List pulled models
ollama list

# Test endpoint
curl http://localhost:11434/v1/models
```

---

## Model Selection Guide

| Hardware | Recommended Model | Memory Usage |
|----------|-------------------|--------------|
| 8GB RAM | qwen3.5:0.8b | ~1GB |
| 16GB RAM | qwen3.5:2b | ~2GB |
| 32GB+ RAM | qwen3.5:4b | ~4GB |

---

## Local Processing Guide

### Fully Local Tools (No LLM Required)

These tools run entirely locally:

| Tool | Function |
|------|----------|
| `inspect_dataset` | Dataset analysis |
| `build_process_spec` | Spec validation |
| `build_dataset_spec` | Spec building |
| `apply_recipe` | Execution via `dj-process` |

### Local Operator Retrieval

`retrieve_operators` runs entirely locally — no API key, no cloud calls:

```bash
djx tool run retrieve_operators --input-json '{"intent": "<goal>", "top_k": 5}'
```

After selecting a candidate, use `get_operator_info` to inspect its parameter schema:

```bash
djx tool run get_operator_info --input-json '{"operator_name": "<operator_name>"}'
```

### Semantic Operators Using Local Models

When the pipeline includes LLM-based operators, configure them to use the local endpoint.

Operator parameters come from `retrieve_operators` output. If parameters are unclear, use empty `{}` — the operator will apply default values.

---

## Error Handling

| Scenario | Solution |
|----------|----------|
| `Connection refused` | Start Ollama: `ollama serve &` |
| `model not found` | Pull the model: `ollama pull <model>` |
| Port conflict (11434 in use) | Use a different port: `OLLAMA_HOST=0.0.0.0:11435 ollama serve &`, then update `DJA_OPENAI_BASE_URL` |
| `DJA_LLM_THINKING=true` error | Set to `false` for all local models |
| `auto` mode 401 fallback | Use `retrieve_operators` (already local, no API needed) |

---

## Must-Read Pitfalls

### 1. Always Verify Ollama Is Running

```bash
ollama list
curl http://localhost:11434/v1/models
```

### 2. retrieve_operators Is Already Local

No need to specify a special mode — `retrieve_operators` runs entirely locally by default:

```bash
djx tool run retrieve_operators --input-json '{"intent": "...", "mode": "auto"}'
```

### 3. Never Send Private Data to the Cloud

Configure all semantic operators to use the local endpoint.

### 4. Test with Small Samples Before Processing

Validate the pipeline with a small sample before processing the full dataset.

### 5. Pull Models in Advance

Pull models before starting the workflow to avoid mid-process downloads.

---

## Complete Local Workflow Example

```bash
# 1. Start Ollama
ollama serve &

# 2. Pull model (first time)
ollama pull qwen3.5:0.8b

# 3. Configure environment
export DJA_OPENAI_BASE_URL="http://localhost:11434/v1"
export DASHSCOPE_API_KEY="ollama"
export DJA_SESSION_MODEL="qwen3.5:0.8b"
export DJA_PLANNER_MODEL="qwen3.5:0.8b"
export DJA_LLM_THINKING="false"

# 4. Verify
ollama list
curl http://localhost:11434/v1/models

# 5. Inspect dataset
djx tool run inspect_dataset --input-json '{"dataset_path": "/data/sensitive.jsonl", "sample_size": 50}'

# 6. Retrieve operators locally (already local, no mode=vector needed)
djx tool run retrieve_operators --input-json '{"intent": "clean and filter sensitive data", "top_k": 10}'

# 7. Continue with main flow...
```

---

## Skill Responsibilities

| Scenario | Skill to Use |
|----------|--------------|
| Configure API Key (cloud) | djx_auth |
| Configure local models | **djx_local_model (this skill)** |
| Local operator retrieval | djx_retrieve (retrieve_operators, already local) |
| Main flow | data-juicer |
