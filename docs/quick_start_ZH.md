# DJX 快速开始

## 1. 环境前置

- Python `>=3.10,<3.13`
- Data-Juicer 运行时（`py-data-juicer`）
- DashScope/OpenAI 兼容 API Key

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
# 可选覆盖
export DJA_OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export DJA_SESSION_MODEL="qwen3-max-2026-01-23"
export DJA_PLANNER_MODEL="qwen3-max-2026-01-23"
export DJA_VALIDATOR_MODEL="qwen3-max-2026-01-23"
```

## 4. 最短 CLI 路径：retrieve -> plan -> apply -> trace

```bash
# 1) 检索候选算子
djx retrieve "去除重复文本" \
  --dataset ./data/demo-dataset.jsonl \
  --top-k 8

# 2) 生成 plan
djx plan "做 RAG 清洗和文本去重" \
  --dataset ./data/demo-dataset.jsonl \
  --export ./data/demo-dataset-processed.jsonl \
  --output ./data/demo-plan.yaml

# 可选：显式指定模板
djx plan "做 RAG 清洗" \
  --dataset ./data/demo-dataset.jsonl \
  --export ./data/demo-dataset-processed.jsonl \
  --from-template rag_cleaning \
  --output ./data/demo-rag-plan.yaml

# 3) 执行
djx apply --plan ./data/demo-plan.yaml --yes

# 4) 查看 trace
djx trace <run_id>
djx trace --stats
```

## 5. 修订模式示例（base plan）

```bash
djx plan "把长度阈值收紧到 <=1000 字符" \
  --base-plan ./data/demo-plan.yaml \
  --output ./data/demo-plan-v2.yaml
```

## 6. 会话模式（`dj-agents`）

默认 TUI：

```bash
dj-agents --dataset ./data/demo-dataset.jsonl --export ./data/demo-dataset-processed.jsonl
```

纯终端模式：

```bash
dj-agents --ui plain --dataset ./data/demo-dataset.jsonl --export ./data/demo-dataset-processed.jsonl
```

说明：
- `dj-agents` 必须可访问 LLM（需 API Key/模型配置）。
- 在会话模式下可按 `Ctrl+C` 中断当前轮，按 `Ctrl+D` 退出。

## 7. DJX Studio（未来项）

- Studio API + Web 前端能力已延后到后续版本。
- 当前快速开始仅覆盖 `djx` 与 `dj-agents`。

## 8. 最小检查

```bash
djx templates
djx trace --stats
djx --debug plan "过滤长文本" --dataset ./data/demo-dataset.jsonl --export ./data/out.jsonl
```

若 planning/session 出现模型或 API 错误，优先检查：
- `DASHSCOPE_API_KEY`
- endpoint/model 配置
- 本地 `.djx/config.json` profile
