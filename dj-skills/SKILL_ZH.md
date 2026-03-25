---
name: data-juicer
description: "由 Data-Juicer 驱动的端到端数据处理技能。指导智能体完成环境设置、数据集检查、算子选择、YAML 配方生成和 dj-process 执行，以自主地清洗、过滤、去重和转换数据集。"
auto_load: true
---

# Data-Juicer 智能体技能

Data-Juicer 是一个用于构建高质量数据集的数据中心处理工具包。这些技能指导您端到端地清洗、过滤、去重和转换数据集。

## 核心工作流程

```
用户请求
  ↓
解析意图（要对数据做什么）
  ↓
隐私检查 ← 用户是否表明数据是敏感/私密的？
  │
  ├── 是（私密数据）──→ 切换到本地模型（Ollama）
  │   │                      • 设置 DJA_OPENAI_BASE_URL=http://localhost:11434/v1
  │   │                      • 数据不会离开本机
  │   ↓
  │   本地数据探测（仅使用本地 LLM 检查）
  │   ↓
  │   选择算子（词汇检索，不使用云端嵌入）
  │   ↓
  │   生成 YAML 配方（通过本地模型）
  │
  ├── 否（普通数据）──→ 检查数据集（云端 LLM 可用）
  │   ↓
  │   选择算子（LLM/向量检索）
  │   ↓
  │   生成 YAML 配方
  │
  └──→（两条路径汇合）
       ↓
       通过 djx tool run apply_recipe 执行
       ↓
       验证并返回结果
```

> **重要**：如果用户提到任何与隐私相关的关键词（敏感、私密、机密、PII、医疗、金融、内部、专有等），您**必须**走左侧（本地）路径。切勿将私密数据样本发送到云端 API 进行探测或分析。有关设置说明，请参阅 [本地模型技能](./local_model_skills.md)。

---

## 1. 环境设置

### 前提条件

- **Python**：3.10 – 3.12（推荐 3.11）
- **包管理器**：[uv](https://github.com/astral-sh/uv) — 如果未安装，请运行：`curl -LsSf https://astral.sh/uv/install.sh | sh`

### 步骤 1：创建虚拟环境

```bash
uv venv --python 3.11 .venv
source .venv/bin/activate    # macOS / Linux
# .venv\Scripts\activate     # Windows
```

### 步骤 2：安装 Data-Juicer

PyPI 包名为 `py-data-juicer`（最新版：v1.5.1）。

**基础安装：**
```bash
uv pip install py-data-juicer
```

**升级到最新版本（如果已安装）：**
```bash
uv pip install --upgrade py-data-juicer
```

> **注意**：由于需要编译一些依赖项，这可能需要一段时间。请耐心等待安装完成。

**使用可选 extras**（按需安装）：
```bash
# 单个 extra
uv pip install "py-data-juicer[vision]"

# 多个 extras
uv pip install "py-data-juicer[vision,nlp]"

# 完整安装（所有功能）
uv pip install "py-data-juicer[all]"
```

**可用 Extras：**

| Extra | 用途 | 适用于 |
|-------|------|--------|
| `generic` | ML/DL 框架（torch、transformers、vllm） | 通用 ML 操作 |
| `vision` | 计算机视觉（opencv、ultralytics、diffusers） | 图像处理算子 |
| `nlp` | NLP/文本（nltk、fasttext、kenlm、spacy-pkuseg） | `perplexity_filter`、`language_id_score_filter` |
| `audio` | 音频处理（torchaudio、soundfile） | 音频算子 |
| `distributed` | 分布式计算（ray、pyspark） | `executor_type: ray` |
| `ai_services` | AI 集成（dashscope、openai） | 基于 API 的算子 |
| `dev` | 开发工具（pytest、black、sphinx） | 贡献代码 |
| `all` | 以上所有 | 完整功能集 |

### 步骤 3：安装 Data-Juicer-Agents（必需）

需要以编程方式访问算子检索和配方工具：

```bash
uv pip install data-juicer-agents
```

**升级到最新版本（如果已安装）：**
```bash
uv pip install --upgrade data-juicer-agents
```

> **注意**：由于需要下载模型和依赖项，这可能需要一段时间。请耐心等待安装完成。

### 验证安装

```bash
# 检查 CLI 工具是否可用
dj-process --help
dj-analyze --help
djx --help

# 检查 Data-Juicer 版本
python -c "import data_juicer; print(data_juicer.__version__)"

# 检查 data-juicer-agents
python -c "import data_juicer_agents; print('data-juicer-agents OK')"
```

### 可用 CLI 工具

安装 `py-data-juicer` 提供以下命令行工具：

| 命令 | 用途 |
|------|------|
| `dj-process` | 执行 YAML 配方流水线 |
| `dj-analyze` | 分析数据集 |
| `dj-install` | 安装算子特定的依赖 |
| `dj-mcp` | 用于工具集成的 MCP 服务器 |

安装 `data-juicer-agents` 提供 `djx` CLI：

| 命令 | 用途 |
|------|------|
| `djx tool list` | 列出所有可用的原子工具 |
| `djx tool schema <tool>` | 获取工具的 JSON 输入模式 |
| `djx tool run <tool> --input-json '{...}'` | 使用 JSON 输入执行原子工具 |
| `djx --version` | 打印已安装的包版本 |

> **智能体提示**：使用 `djx tool list` 发现工具，`djx tool schema <tool>` 了解输入要求，`djx tool run <tool>` 执行。所有输出都是结构化 JSON。

### 设置故障排除

| 问题 | 解决方法 |
|------|----------|
| `command not found: dj-process` | 确保 venv 已激活；重新运行 `uv pip install py-data-juicer` |
| `command not found: uv` | 安装 uv：`curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python 版本不匹配 | 显式使用 `python3.11` |
| `ModuleNotFoundError: kenlm` | 安装 nlp extra：`uv pip install "py-data-juicer[nlp]"` |
| `ModuleNotFoundError: cv2` | 安装 vision extra：`uv pip install "py-data-juicer[vision]"` |
| `perplexity_filter` 失败 | 需要 nlp extra：`uv pip install "py-data-juicer[nlp]"` |
| `language_id_score_filter` 失败 | 需要 nlp extra：`uv pip install "py-data-juicer[nlp]"` |
| Ray 执行器不可用 | 安装 distributed extra：`uv pip install "py-data-juicer[distributed]"` |

---

## 2. 生成 YAML 配方

本节指导您如何根据用户的数据处理意图创建与 dj-process 兼容的 YAML 配方。

### 推荐方法：djx 工具链

对于智能体工作流，逐步链接原子工具以在每个决策点获得完全控制：

```
djx tool run inspect_dataset   → 理解数据
        ↓
djx tool run retrieve_operators → 查找合适的算子
        ↓
（智能体决定算子和参数）
        ↓
djx tool run build_dataset_spec  → 锁定数据集 IO
djx tool run build_process_spec  → 锁定算子流水线
djx tool run build_system_spec   → 锁定系统配置
        ↓
djx tool run assemble_plan       → 组装计划
djx tool run plan_validate       → 验证
djx tool run plan_save           → 持久化
        ↓
djx tool run apply_recipe        → 执行
```

#### 逐步示例

```bash
# 1. 检查数据集结构
djx tool run inspect_dataset --input-json '{"dataset_path":"./data/corpus.jsonl","sample_size":5}'

# 2. 检索算子候选
djx tool run retrieve_operators --input-json '{"intent":"deduplicate and clean text for RAG","top_k":10,"dataset_path":"./data/corpus.jsonl"}'

# 3. 构建规格（将 inspect_dataset 输出作为 dataset_profile）
djx tool run build_dataset_spec --input-json '{
  "intent":"deduplicate and clean text for RAG",
  "dataset_path":"./data/corpus.jsonl",
  "export_path":"./data/corpus_cleaned.jsonl",
  "dataset_profile": {"...": "paste inspect_dataset output here"}
}'

# 4. 构建处理规格（智能体从检索结果中选择算子）
djx tool run build_process_spec --input-json '{
  "operators": [
    {"name":"fix_unicode_mapper","params":{}},
    {"name":"text_length_filter","params":{"min_len":50,"max_len":100000}},
    {"name":"document_deduplicator","params":{"lowercase":true}}
  ]
}'

# 5. 构建系统规格
djx tool run build_system_spec --input-json '{"np":4,"executor_type":"default"}'

# 6. 组装、验证并保存
djx tool run assemble_plan --input-json '{
  "intent":"deduplicate and clean text for RAG",
  "dataset_spec": {"...": "from step 3"},
  "process_spec": {"...": "from step 4"},
  "system_spec": {"...": "from step 5"}
}'
djx tool run plan_validate --input-json '{"plan_payload": {"...": "from assemble_plan"}}'
djx tool run plan_save --yes --input-json '{"plan_payload": {"...": "from assemble_plan"},"output_path":"./plans/my_plan.yaml"}'

# 7. 执行
djx tool run apply_recipe --yes --input-json '{"plan_path":"./plans/my_plan.yaml","confirm":true}'
```

> **注意**：每个 `djx tool run` 返回结构化 JSON。将一步的输出输入到下一步。使用 `djx tool schema <tool>` 发现确切的输入要求。

### 手动方法：逐步配方生成

如需更多控制，或需要自定义特定步骤时，请遵循下面的手动流程。

### 核心流程

```
用户意图 → 隐私检查 → [如果是私密数据：激活本地模型] → 检查数据集 → 检索算子 → 选择算子 → 编写 YAML → 验证 → 保存
```

### 步骤 1：解析用户意图

从用户请求中识别：
- **输入数据集路径**（JSONL 文件）
- **输出路径**（保存处理后数据的位置）
- **处理目标**（清洗文本？删除重复？过滤质量？等）
- **数据敏感性**（数据是否私密、敏感或机密？）

#### 隐私检测

扫描用户请求中的以下信号：
- **显式关键词**："敏感"、"私密"、"机密"、"秘密"、"内部"、"专有"
- **数据类型**："PII"、"医疗记录"、"患者数据"、"金融数据"、"个人信息"、"工资"、"社保号"、"身份证"
- **合规性**："GDPR"、"HIPAA"、"SOC2"、"合规"、"受监管"
- **意图信号**："不想让数据离开"、"保持本地"、"不上云"、"气隙"、"离线处理"

**如果检测到任何隐私信号** → 设置 `private_mode = True` 并继续下面的步骤 1.5。
**否则** → 跳过步骤 1.5 直接进入步骤 2。

### 步骤 1.5：激活本地模型（仅私密数据）

> **当用户数据敏感时，此步骤是必需的。** 您必须在检查数据集或将任何数据内容发送到 LLM 之前完成此步骤。

1. **检查 Ollama 是否正在运行** 且本地模型可用：

```bash
# 检查 Ollama 是否正在运行
curl -s http://localhost:11434/api/tags | python -m json.tool
```

2. **切换到本地模式** — 将所有 LLM 调用重定向到 localhost：

```bash
export DJA_OPENAI_BASE_URL="http://localhost:11434/v1"
export DASHSCOPE_API_KEY="ollama"
export DJA_SESSION_MODEL="qwen3.5:0.8b"
export DJA_PLANNER_MODEL="qwen3.5:0.8b"
export DJA_LLM_THINKING="false"
```

或 source 预配置文件：
```bash
source ~/.dja_local_env   # 有关设置请参阅 local_model_skills.md
```

3. **向用户确认** 私密模式已激活，数据不会发送到外部 API。

> **从现在开始**，所有步骤（检查数据集、检索算子、生成配方）都将使用本地模型。数据样本、字段值和内容永远不会发送到云端。

### 步骤 2：检查数据集

检查数据集以了解其结构。

> **⚠️ 私密数据**：如果 `private_mode = True`（来自步骤 1），您必须首先完成步骤 1.5。下面的所有数据集检查应仅使用本地工具。**切勿**将数据样本打印、记录或发送到任何云端 API。位于 `localhost:11434` 的本地 LLM 是您可用于内容理解的唯一模型。

#### 数据集检查

```bash
djx tool run inspect_dataset --input-json '{"dataset_path":"./input.jsonl","sample_size":5}'
```

输出 JSON 包括检测到的模态、字段名称、类型、样本统计和内容样本。将此输出用作 `build_dataset_spec` 的 `dataset_profile`。

> **私密数据**：如果 `private_mode = True`，在运行触发 LLM 调用的工具之前，确保 `DJA_OPENAI_BASE_URL` 指向 localhost。`inspect_dataset` 本身是安全的 — 它只读取文件元数据和样本。

需要确定的关键事项：
- **text_keys**：哪些字段包含主文本（例如，`["text"]`）
- **image_key**：图像路径/URL 的字段（如果是多模态）
- **模态**：纯文本、图像、多模态

### 步骤 3：检索算子候选

```bash
djx tool run retrieve_operators --input-json '{
  "intent": "remove duplicate documents and filter short texts",
  "top_k": 5,
  "mode": "auto",
  "dataset_path": "./input.jsonl"
}'
```

**检索模式：**
- `auto`：自动选择最佳方法（推荐）
- `llm`：基于 LLM 的语义检索
- `vector`：向量相似性搜索

> **私密数据**：在私密模式下，描述任务意图，而不是数据内容。检索查询会发送到 LLM。

输出 JSON 包含按排名的候选，包括算子名称、类型、描述、相关性分数和参数预览。

### 步骤 4：选择算子

根据检索结果和用户目标选择算子。常见模式：

**文本清洗流水线：**
- `fix_unicode_mapper` → `whitespace_normalization_mapper` → `clean_html_mapper` → `text_length_filter` → `words_num_filter`

**去重流水线：**
- `document_deduplicator`（精确）或 `document_minhash_deduplicator`（模糊）

**质量过滤流水线：**
- `language_id_score_filter` → `perplexity_filter` → `alphanumeric_filter` → `text_length_filter`

**完整流水线（清洗 + 过滤 + 去重）：**
- `fix_unicode_mapper` → `clean_html_mapper` → `whitespace_normalization_mapper` → `text_length_filter` → `words_num_filter` → `special_characters_filter` → `document_minhash_deduplicator`

**语义 / LLM 流水线（QA 生成、标签、评分）：**
- `fix_unicode_mapper` → `text_length_filter` → `llm_quality_score_filter` → `generate_qa_from_text_mapper` → `document_deduplicator`

> **⚠️ 语义算子 + 私密数据**：如果流水线包含**任何**语义/LLM 算子（请参阅算子目录 → 语义 / LLM 算子），且数据敏感，您**必须**将每个语义算子配置为使用本地 Ollama 端点（`api_model: "qwen3.5:0.8b"` + `model_params.base_url: "http://localhost:11434/v1"`），或全局设置 `OPENAI_BASE_URL=http://localhost:11434/v1`。这些算子将实际数据内容发送到 LLM — 如果没有本地路由，内容将发送到云端 API。

### 步骤 5：编写 YAML 配方

**配方格式**（这是 `dj-process --config` 期望的）：

```yaml
project_name: my_project
dataset_path: ./input.jsonl
export_path: ./output.jsonl

# 数据集字段
text_keys:
  - text
# image_key: image       # 多模态时取消注释
# audio_key: audio       # 音频时取消注释

# 系统设置
np: 4                     # 并行进程
executor_type: default    # 或 "ray" 用于分布式
open_tracer: false
skip_op_error: false

# 算子流水线 — 每个条目是 {operator_name: {params}}
process:
  - fix_unicode_mapper: {}
  - whitespace_normalization_mapper: {}
  - text_length_filter:
      min_len: 50
      max_len: 100000
```

### 关键格式规则

1. **`process`** 是单键字典的列表：`- operator_name: {params}`
2. 对于没有参数的算子使用 `{}`
3. **`text_keys`** 必须是 YAML 列表，不是字符串
4. **`np`** ≥ 1（并行工作进程数）

### 步骤 6：验证配方

```bash
# 通过工具链验证（如果您构建了计划）
djx tool run plan_validate --input-json '{"plan_payload": {"...": "your assembled plan"}}'
```

或进行简单的 YAML 语法验证：
```bash
python -c "import yaml; yaml.safe_load(open('recipe.yaml')); print('YAML OK')"
```

### 步骤 7：保存配方

```bash
# 通过 plan_save 保存（如果您有组装的计划负载）
djx tool run plan_save --yes --input-json '{"plan_payload": {"...": "your assembled plan"},"output_path":"./recipe.yaml"}'
```

或手动编写 YAML：
```bash
djx tool run write_text_file --yes --input-json '{"file_path":"./recipe.yaml","content":"... your YAML recipe content ..."}'
```

### 完整示例

#### 示例 1：RAG 语料库清洗
```yaml
project_name: rag_cleaning
dataset_path: ./data/rag_corpus.jsonl
export_path: ./data/rag_cleaned.jsonl
text_keys: [text]
np: 4
process:
  - fix_unicode_mapper: {}
  - clean_html_mapper: {}
  - whitespace_normalization_mapper: {}
  - punctuation_normalization_mapper: {}
  - text_length_filter:
      min_len: 100
      max_len: 100000
  - words_num_filter:
      min_num: 20
      max_num: 100000
      lang: en
  - special_characters_filter:
      min_ratio: 0.0
      max_ratio: 0.25
  - document_deduplicator:
      lowercase: true
      ignore_non_character: true
```

#### 示例 2：中文文本处理
```yaml
project_name: chinese_clean
dataset_path: ./data/zh_corpus.jsonl
export_path: ./data/zh_cleaned.jsonl
text_keys: [text]
np: 4
process:
  - fix_unicode_mapper: {}
  - chinese_convert_mapper:
      mode: s2t
  - whitespace_normalization_mapper: {}
  - text_length_filter:
      min_len: 50
  - language_id_score_filter:
      lang: zh
      min_score: 0.5
  - document_minhash_deduplicator:
      tokenization: character
      window_size: 5
      num_permutations: 256
      jaccard_threshold: 0.7
```

#### 示例 3：多模态数据过滤
```yaml
project_name: mm_filter
dataset_path: ./data/multimodal.jsonl
export_path: ./data/mm_filtered.jsonl
text_keys: [text]
image_key: image
np: 2
process:
  - image_aspect_ratio_filter:
      min_ratio: 0.333
      max_ratio: 3.0
  - image_size_filter:
      min_size: 100
      max_size: 20000
  - text_length_filter:
      min_len: 10
      max_len: 50000
```

---

## 3. 执行配方

直接在 YAML 配方上运行 `dj-process`，或在保存的计划上使用 `djx tool run apply_recipe`。

### 方法 1：djx tool run apply_recipe（推荐）

执行保存的计划：

```bash
djx tool run apply_recipe --yes --input-json '{"plan_path":"./plans/my_plan.yaml","confirm":true,"timeout":300}'
```

试运行（验证并编写配方，但不执行）：

```bash
djx tool run apply_recipe --yes --input-json '{"plan_path":"./plans/my_plan.yaml","confirm":true,"dry_run":true}'
```

### 方法 2：直接 dj-process（用于手动 YAML 配方）

如果您手动编写了 YAML 配方（不是通过计划链），直接运行 `dj-process`：

```bash
dj-process --config recipe.yaml
```

### 推荐流程

#### 1. 预检

```bash
# 预检：验证数据集存在且工具可用
djx tool run inspect_dataset --input-json '{"dataset_path":"./input.jsonl","sample_size":1}'
```

#### 2. 执行

```bash
dj-process --config recipe.yaml
```

监控 stdout 以查看进度。命令在成功时以退出代码 0 退出。

#### 3. 验证结果

```bash
# 统计记录数
wc -l input.jsonl output.jsonl

# 抽查输出
head -1 output.jsonl | python -m json.tool
```

### 退出代码参考

| 退出代码 | 含义 | 操作 |
|----------|------|------|
| 0 | 成功 | 验证输出 |
| 1 | 一般错误 | 检查 stderr，请参阅故障排除部分 |
| 124 | 超时 | 减少数据大小或增加资源 |
| 130 | 中断 | 如需则重新运行 |

---

## 3.5. djx tool 命令

`djx tool` 命令直接暴露所有注册的原子工具，用于自动化和检查。

### 列出可用工具

```bash
djx tool list [--tag <tag>]
```

示例：
```bash
djx tool list --tag plan
```

返回注册的工具元数据：`name`、`tags`、`effects`、`confirmation`、输入/输出模型名称。

### 获取工具模式

```bash
djx tool schema <tool-name>
```

示例：
```bash
djx tool schema inspect_dataset
```

返回工具元数据以及输入模型 JSON 模式。

### 运行工具

```bash
djx tool run <tool-name> (--input-json '<json>' | --input-file <input.json>) [--working-dir <path>] [--yes]
```

示例：
```bash
# 列出系统配置
djx tool run list_system_config --input-json '{}'

# 检查数据集
djx tool run inspect_dataset --input-json '{"dataset_path":"./data/demo-dataset.jsonl","sample_size":5}'

# 写入文件（需要 --yes 确认）
djx tool run write_text_file --yes --input-json '{"file_path":"./tmp.txt","content":"hello"}'

# 验证计划
djx tool run plan_validate --input-file ./examples/plan_payload.json
```

退出代码：
- `0`：成功
- `2`：CLI 误用、未知工具、无效 JSON 输入或输入模型验证失败
- `3`：需要显式确认但未授予
- `4`：工具执行并返回失败负载

### 可用原子工具

| 工具 | 用途 | 标签 |
|------|------|------|
| `inspect_dataset` | 数据集检查和模式探测 | context |
| `list_system_config` | 列出系统配置 | context |
| `retrieve_operators` | 按意图检索算子候选 | retrieve |
| `build_dataset_spec` | 构建数据集规格 | plan |
| `build_process_spec` | 构建处理规格 | plan |
| `build_system_spec` | 构建系统规格 | plan |
| `validate_dataset_spec` | 验证数据集规格 | plan |
| `validate_process_spec` | 验证处理规格 | plan |
| `validate_system_spec` | 验证系统规格 | plan |
| `assemble_plan` | 从规格组装最终计划 | plan |
| `plan_validate` | 验证组装的计划 | plan |
| `plan_save` | 保存计划到文件 | plan |
| `apply_recipe` | 执行计划/配方 | apply |
| `develop_operator` | 生成自定义算子脚手架 | dev |
| `view_text_file` | 读取文本文件内容 | files |
| `write_text_file` | 写入文本文件 | files |
| `insert_text_file` | 插入内容到文本文件 | files |
| `execute_shell_command` | 执行 shell 命令 | process |
| `execute_python_code` | 执行 Python 代码片段 | process |

---

## 3.6. 自定义算子开发

生成自定义算子脚手架：

```bash
djx tool run develop_operator --yes --input-json '{
  "intent": "filter records by custom domain-specific quality metric",
  "operator_name": "domain_quality_filter",
  "output_dir": "./my_operators",
  "operator_type": "filter",
  "smoke_check": true
}'
```

输出包括：
- 算子脚手架（Python 模块）
- 测试脚手架
- 摘要 markdown
- 可选的冒烟检查结果

默认行为是非侵入式的：生成代码和指导，但不自动安装算子。

---

## 4. 算子目录

Data-Juicer 在 8 个类别中提供 190+ 算子。以下是最常用的。

### Mappers（转换/编辑）

| 算子 | 描述 | 关键参数 |
|------|------|----------|
| `fix_unicode_mapper` | 修复损坏的 unicode | — |
| `whitespace_normalization_mapper` | 规范化空白字符 | — |
| `punctuation_normalization_mapper` | 规范化标点符号 | — |
| `clean_html_mapper` | 去除 HTML 标签 | — |
| `clean_email_mapper` | 删除电子邮件地址 | — |
| `clean_links_mapper` | 删除 URL | — |
| `clean_ip_mapper` | 删除 IP 地址 | — |
| `remove_header_mapper` | 删除文档标题 | — |
| `remove_long_words_mapper` | 删除过长的单词 | `min_len`, `max_len` |
| `remove_specific_chars_mapper` | 删除指定字符 | `chars_to_remove` |
| `sentence_split_mapper` | 拆分为句子 | `lang` |
| `chinese_convert_mapper` | 简体中文 ↔ 繁体中文 | `mode` (s2t/t2s) |
| `remove_repeat_sentences_mapper` | 删除重复的句子 | `min_repeat_sentence_length` |
| `replace_content_mapper` | 基于正则的文本替换 | `pattern`, `repl` |

### Filters（质量门）

| 算子 | 描述 | 关键参数 |
|------|------|----------|
| `text_length_filter` | 按字符长度过滤 | `min_len`, `max_len` |
| `words_num_filter` | 按单词数过滤 | `min_num`, `max_num`, `lang` |
| `alphanumeric_filter` | 按字母数字比例过滤 | `min_ratio`, `max_ratio` |
| `special_characters_filter` | 按特殊字符比例过滤 | `min_ratio`, `max_ratio` |
| `average_line_length_filter` | 按平均行长度过滤 | `min_len`, `max_len` |
| `maximum_line_length_filter` | 按最大行长度过滤 | `min_len`, `max_len` |
| `language_id_score_filter` | 按语言分数过滤 | `lang`, `min_score` |
| `perplexity_filter` | 按 LM 困惑度过滤 | `lang`, `max_ppl` |
| `flagged_words_filter` | 按有毒/标记词过滤 | `lang`, `max_ratio` |
| `text_action_filter` | 按动作关键词过滤 | `min_ratio` |
| `image_aspect_ratio_filter` | 按图像宽高比过滤 | `min_ratio`, `max_ratio` |
| `image_size_filter` | 按图像文件大小过滤 | `min_size`, `max_size` |
| `audio_duration_filter` | 按音频时长过滤 | `min_duration`, `max_duration` |
| `video_duration_filter` | 按视频时长过滤 | `min_duration`, `max_duration` |
| `token_num_filter` | 按 token 数过滤 | `min_num`, `max_num`, `hf_tokenizer` |
| `suffix_filter` | 按文件后缀过滤 | `suffixes` |
| `image_text_similarity_filter` | 按 CLIP 相似度过滤 | `min_score`, `max_score` |

### Deduplicators（去重）

| 算子 | 描述 | 关键参数 |
|------|------|----------|
| `document_deduplicator` | 精确文档去重 | `lowercase`, `ignore_non_character` |
| `document_minhash_deduplicator` | MinHash LSH 模糊去重 | `tokenization`, `window_size`, `num_permutations`, `jaccard_threshold` |
| `document_simhash_deduplicator` | SimHash 模糊去重 | `tokenization`, `window_size`, `num_blocks`, `hamming_distance` |
| `image_deduplicator` | 图像精确匹配去重 | `method` |
| `ray_document_deduplicator` | 分布式精确去重 | （与 document_deduplicator 相同） |
| `ray_image_deduplicator` | 分布式图像去重 | （与 image_deduplicator 相同） |

### Selectors（排序）

| 算子 | 描述 |
|------|------|
| `topk_specified_field_selector` | 按字段值选择 top-K |
| `frequency_specified_field_selector` | 按字段频率选择 |
| `range_specified_field_selector` | 按字段值范围选择 |
| `random_selector` | 随机子采样 |

### Aggregators（聚合）

| 算子 | 描述 |
|------|------|
| `entity_attribute_aggregator` | 聚合实体属性 |
| `most_relevant_entities_aggregator` | 查找最相关的实体 |
| `nested_aggregator` | 分层聚合 |
| `meta_tags_aggregator` | 聚合元数据标签 |

### Semantic / LLM 算子

这些算子调用 LLM API 处理每个样本。它们将**实际数据内容**发送到模型端点。默认情况下它们使用云端 API（`OPENAI_BASE_URL`），但它们可以 —— 且对于私密数据**应该** —— 指向本地 Ollama 模型。

> **⚠️ 私密数据**：如果用户的数据敏感，配方中的**每个**语义算子必须使用本地 Ollama 端点。否则数据内容将发送到云端 API。使用指向 `http://localhost:11434/v1` 的 `model_params` 配置每个算子，或全局设置 `OPENAI_BASE_URL`。

#### LLM Filters（语义质量门）

| 算子 | 描述 | 关键参数 |
|------|------|----------|
| `llm_quality_score_filter` | 基于 LLM 的质量评分（1-5 分制） | `api_model`, `min_score`, `dimensions` |
| `llm_difficulty_score_filter` | 基于 LLM 的难度评估 | `api_model`, `min_score`, `dimensions` |
| `llm_task_relevance_filter` | 与验证任务的相关性 | `api_model`, `task_description`, `min_score` |
| `llm_perplexity_filter` | 通过 HuggingFace 模型的困惑度 | `hf_model`, `max_ppl` |

#### Text Generation / Tagging Mappers

| 算子 | 描述 | 关键参数 |
|------|------|----------|
| `generate_qa_from_text_mapper` | 从文本生成 QA 对 | `api_model`, `qa_pair_num` |
| `generate_qa_from_examples_mapper` | 从种子示例生成 QA | `api_model`, `seed_file`, `example_num` |
| `optimize_qa_mapper` | 优化现有 QA 对 | `api_model` |
| `text_tagging_by_prompt_mapper` | 通过 LLM 提示标记文本 | `hf_model` 或 `api_model` |
| `optimize_prompt_mapper` | 从示例优化提示 | `api_model` |
| `pair_preference_mapper` | 生成偏好对 | `api_model` |
| `sentence_augmentation_mapper` | 增强句子 | `hf_model` |

#### Dialog Analysis Mappers

| 算子 | 描述 | 关键参数 |
|------|------|----------|
| `dialog_intent_detection_mapper` | 检测对话中的用户意图 | `api_model` |
| `dialog_sentiment_detection_mapper` | 检测对话中的情感 | `api_model` |
| `dialog_sentiment_intensity_mapper` | 量化情感强度 | `api_model` |
| `dialog_topic_detection_mapper` | 识别对话主题 | `api_model` |

#### Entity / Relation Extraction Mappers

| 算子 | 描述 | 关键参数 |
|------|------|----------|
| `extract_keyword_mapper` | 通过 LLM 提取关键词 | `api_model` |
| `extract_entity_attribute_mapper` | 提取实体属性 | `api_model` |
| `extract_nickname_mapper` | 识别昵称关系 | `api_model` |
| `extract_support_text_mapper` | 提取支持文本 | `api_model` |
| `relation_identity_mapper` | 识别实体关系 | `api_model` |

#### Vision-Language / Multimodal Mappers

| 算子 | 描述 | 关键参数 |
|------|------|----------|
| `image_tagging_vlm_mapper` | 通过 VLM 标记图像 | `api_model`, `tag_field_name` |
| `video_captioning_from_vlm_mapper` | 通过 VLM 为视频添加字幕 | `api_model`, `enable_vllm` |
| `mllm_mapper` | 使用多模态 LLM 进行视觉 QA | `api_model` |
| `image_captioning_from_gpt4v_mapper` | 通过 API 为图像添加字幕 | `api_model` |

#### 配置语义算子使用本地 Ollama

所有语义算子都使用 OpenAI 兼容的 API 协议。要将它们路由通过本地 Ollama 模型，请在 YAML 配方中配置 `api_model` 和 `model_params`：

**每个算子配置（在 YAML 配方中）：**

```yaml
process:
  # 语义算子 — 全部指向本地 Ollama
  - generate_qa_from_text_mapper:
      api_model: "qwen3.5:0.8b"
      model_params:
        base_url: "http://localhost:11434/v1"
        api_key: "ollama"
      sampling_params:
        temperature: 0.7
  - llm_quality_score_filter:
      api_model: "qwen3.5:0.8b"
      model_params:
        base_url: "http://localhost:11434/v1"
        api_key: "ollama"
      min_score: 3
  - extract_keyword_mapper:
      api_model: "qwen3.5:0.8b"
      model_params:
        base_url: "http://localhost:11434/v1"
        api_key: "ollama"
```

**全局配置（通过环境变量）：**

或者，在运行 `dj-process` 之前设置这些环境变量，使所有语义算子默认使用 Ollama：

```bash
export OPENAI_BASE_URL="http://localhost:11434/v1"
export OPENAI_API_KEY="ollama"
```

然后配方只需要模型名称：

```yaml
process:
  - generate_qa_from_text_mapper:
      api_model: "qwen3.5:0.8b"
  - llm_quality_score_filter:
      api_model: "qwen3.5:0.8b"
      min_score: 3
```

#### 完整示例：私密数据与语义算子

```yaml
project_name: private_qa_generation
dataset_path: ./sensitive_data.jsonl
export_path: ./sensitive_qa_output.jsonl
text_keys: [text]
np: 2

process:
  # 步骤 1：基础清洗（无 LLM，对任何数据都安全）
  - fix_unicode_mapper: {}
  - whitespace_normalization_mapper: {}
  - text_length_filter:
      min_len: 100
      max_len: 100000

  # 步骤 2：LLM 驱动的算子 — 全部使用本地 Ollama
  - llm_quality_score_filter:
      api_model: "qwen3.5:0.8b"
      model_params:
        base_url: "http://localhost:11434/v1"
        api_key: "ollama"
      min_score: 3
  - generate_qa_from_text_mapper:
      api_model: "qwen3.5:0.8b"
      model_params:
        base_url: "http://localhost:11434/v1"
        api_key: "ollama"

  # 步骤 3：去重（无 LLM，对任何数据都安全）
  - document_deduplicator:
      lowercase: true
```

> **注意**：本地小模型（qwen3.5:0.8b）在复杂的语义任务（如 QA 生成）上不如云端模型能力强。如果质量至关重要，请考虑使用更大的本地模型（`qwen3.5:7b` 或 `qwen3.5:14b`）。有关模型选项，请参阅 [local_model_skills.md](./local_model_skills.md)。

### 在 YAML 配方中使用

每个算子作为单键字典放在 `process:` 下：

```yaml
process:
  - operator_name: {}                 # 无参数
  - operator_with_params:
      param1: value1
      param2: value2
```

### 通过检索发现算子

```bash
# 按意图查找算子
djx tool run retrieve_operators --input-json '{"intent":"remove duplicate documents","top_k":5}'

# 列出所有可用工具
djx tool list
```

---

## 5. 故障排除

### 错误快速参考

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `command not found: dj-process` | 未安装或 venv 未激活 | `uv pip install py-data-juicer` + 激活 venv |
| `command not found: djx` | data-juicer-agents 未安装 | `uv pip install data-juicer-agents` |
| `FileNotFoundError` | 数据集路径不存在 | 检查配方中的 `dataset_path` |
| `PermissionError` | 无法写入输出 | 检查目录权限 |
| `KeyError` on operator | 算子名称不正确 | 对照算子目录检查有效名称 |
| `ModuleNotFoundError` | 缺少依赖 | 安装算子所需的 extras |
| YAML parse error | 配方格式错误 | 验证 YAML 语法 |
| Timeout | 处理太慢 | 减少数据，增加 `np`，或先采样 |
| API key error | 缺少凭证 | 设置 `DASHSCOPE_API_KEY` 或相关环境变量；本地模式设置 `DASHSCOPE_API_KEY=ollama` |
| Local model not responding | Ollama 未运行 | 启动 Ollama：`ollama serve`；请参阅 [local_model_skills.md](./local_model_skills.md) |
| `enable_thinking` error in local mode | 本地模型不支持 thinking | 设置 `DJA_LLM_THINKING=false` |

### 环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | DashScope 的 API 凭证 | - |
| `MODELSCOPE_API_TOKEN` | 替代 API 凭证 | - |
| `DJA_OPENAI_BASE_URL` | OpenAI 兼容端点的基础 URL | DashScope 兼容端点 |
| `DJA_SESSION_MODEL` | LLM 基础工具使用的模型 | `qwen3-max-2026-01-23` |
| `DJA_PLANNER_MODEL` | 规划工具使用的模型 | `qwen3-max-2026-01-23` |
| `DJA_MODEL_FALLBACKS` | 逗号分隔的备用模型 | - |
| `DJA_LLM_THINKING` | 在模型请求中切换 `enable_thinking` | `true` |

### 诊断命令

```bash
# 1. 检查 dj-process 是否已安装
which dj-process

# 2. 检查 djx 是否已安装
which djx
djx --help

# 3. 验证 YAML
python -c "import yaml; yaml.safe_load(open('recipe.yaml')); print('YAML OK')"

# 4. 检查数据集是否为有效的 JSONL
head -1 input.jsonl | python -m json.tool

# 5. 统计数据集记录数
wc -l input.jsonl

# 6. 检查算子是否存在
python -c "
from data_juicer.ops import load_ops
all_ops = load_ops()
target = 'operator_name'
found = any(target in ops for ops in all_ops.values())
print(f'{target}: {\"found\" if found else \"NOT FOUND\"}')"

# 7. 检查 Python 环境
python --version
pip list | grep -i "data.juicer"

# 8. 列出可用的 djx 工具
djx tool list

# 9. 测试算子检索
djx tool run retrieve_operators --input-json '{"intent":"filter short text","top_k":3}'
```

### 常见修复

#### 配方 YAML 问题
- **错误的 process 格式**：每个算子必须是 `- operator_name: {params}`，不是 `- {name: ..., params: ...}`
- **text_keys 作为字符串**：必须是列表 `[text]`，不是 `text`
- **缺少 export_path**：始终指定输出位置

#### 算子问题
- **算子未找到**：对照算子目录检查拼写
- **错误的参数**：检查算子文档；大多数使用 snake_case 参数名
- **缺少模型文件**：某些算子（perplexity、language_id）在首次运行时下载模型

#### 性能问题
- **处理缓慢**：增加 `np`（并行工作进程）
- **内存不足**：减少 `np`，或分批处理
- **大数据集**：使用 `executor_type: ray` 进行分布式处理
