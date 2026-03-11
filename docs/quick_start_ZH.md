# 快速开始

## 1. 环境前置

- Python `>=3.10,<3.13`
- Data-Juicer 运行时（`py-data-juicer`）
- DashScope 或 OpenAI 兼容 API Key

## 2. 安装

```bash
cd ./data-juicer-agents
uv venv .venv
source .venv/bin/activate
uv pip install -e .
```

## 3. 配置模型访问

```bash
export DASHSCOPE_API_KEY="<your_key>"
# 或：
# export MODELSCOPE_API_TOKEN="<your_key>"

# 可选覆盖
export DJA_OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export DJA_SESSION_MODEL="qwen3-max-2026-01-23"
export DJA_PLANNER_MODEL="qwen3-max-2026-01-23"
export DJA_MODEL_FALLBACKS="qwen-max,qwen-plus"
export DJA_LLM_THINKING="true"
```

## 4. 最短 CLI 路径

可选的观察步骤：

```bash
djx retrieve "去除重复文本" \
  --dataset ./data/demo-dataset.jsonl \
  --top-k 8
```

生成 plan：

```bash
djx plan "做 RAG 清洗和文本去重" \
  --dataset ./data/demo-dataset.jsonl \
  --export ./data/demo-dataset-processed.jsonl \
  --output ./data/demo-plan.yaml
```

执行已保存的 plan：

```bash
djx apply --plan ./data/demo-plan.yaml --yes
```

只做 dry-run，不真正执行 `dj-process`：

```bash
djx apply --plan ./data/demo-plan.yaml --yes --dry-run
```

说明：
- `djx plan` 在构建最终 plan 之前会先做内部算子检索。
- `djx retrieve` 仍适合用于观察和调试候选算子。

## 5. 会话模式（`dj-agents`）

默认 TUI：

```bash
dj-agents --dataset ./data/demo-dataset.jsonl --export ./data/demo-dataset-processed.jsonl
```

纯终端模式：

```bash
dj-agents --ui plain --dataset ./data/demo-dataset.jsonl --export ./data/demo-dataset-processed.jsonl
```

说明：
- `dj-agents` 需要可用的 LLM 访问配置。
- 会话中按 `Ctrl+C` 可中断当前轮，按 `Ctrl+D` 退出。
- 会话内常见 planning 链路是 `inspect_dataset -> retrieve_operators -> plan_build -> plan_validate -> plan_save`。

## 6. 最小检查

```bash
djx --help
djx retrieve "过滤长文本" --dataset ./data/demo-dataset.jsonl --json
djx plan "过滤长文本" --dataset ./data/demo-dataset.jsonl --export ./data/out.jsonl --verbose
djx apply --plan ./data/demo-plan.yaml --yes --dry-run
dj-agents --help
```

## 7. 故障排查

如果 planning 或 session 启动时出现模型 / API 错误，优先检查：
- `DASHSCOPE_API_KEY` 或 `MODELSCOPE_API_TOKEN`
- `DJA_OPENAI_BASE_URL`
- `DJA_SESSION_MODEL` 和 `DJA_PLANNER_MODEL`
- 期望模型兜底时的 `DJA_MODEL_FALLBACKS`
- 如果服务端不接受 thinking 参数，检查 `DJA_LLM_THINKING`
