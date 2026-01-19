## Data-Juicer 问答 Copilot 示例（中文）

本文按案例展示 **输入问题（Input）** 与 **助手回答（Output）**，便于理解 QA Copilot 的实际效果。

你可以在官方[文档页](https://datajuicer.github.io/data-juicer/zh_CN/main/index_ZH.html)和我们的 [问答 Copilot](./README.md) ***Juicer*** 聊天! 欢迎向 ***Juicer*** 提出任何与 Data-Juicer 生态相关的问题。

<div align="center">
<img src="../docs/imgs/dj_copilot_demo_ZH.gif" width=90%>
</div>

---

### 案例 1 · 算子介绍（alphanumeric_filter，ZH）

- **类型**: `operator_qa`
- **语言**: `zh`

**输入（用户提问）**

> 介绍alphanumeric_filter

<details>
<summary><strong>输出（助手回答）</strong></summary>

`alphanumeric_filter` 是 Data-Juicer 中的一个**过滤算子（Filter Operator）**，用于根据样本中**字母数字字符（或词元）的比例**筛选数据。它保留那些字母数字比例落在指定区间内的样本，常用于清洗低质量或非自然语言文本（如代码、乱码、广告等）。

---

## 📌 核心功能

- **字符级或词元级计算**：  
  通过 `tokenization` 参数控制：
  - 若为 `False`（默认），按**字符数**计算字母数字占比 → 使用字段 `'alnum_ratio'`
  - 若为 `True`，使用 Hugging Face tokenizer 按**词元（token）**计算 → 使用字段 `'alpha_token_ratio'`

- **范围过滤**：  
  通过 `min_ratio` 和 `max_ratio` 设置保留样本的合法比例区间 [min, max]。

---

## ⚙️ 参数说明

| 参数名        | 类型    | 描述                                       |
|---------------|---------|--------------------------------------------|
| `tokenization`| `bool`  | 是否启用词元化计算（默认 False → 字符级） |
| `min_ratio`   | `float` | 最小字母数字比例阈值                       |
| `max_ratio`   | `float` | 最大字母数字比例阈值                       |

> 💡 示例：设置 `min_ratio=0.25`, `max_ratio=1.0` 可过滤掉字母数字比例低于 25% 的样本（如纯符号、乱码文本）。

---

## 🧩 使用示例（YAML 配置）

```yaml
process:
  - alphanumeric_filter:
      tokenization: false
      min_ratio: 0.25
      max_ratio: 1.0
```

---

## 📚 参考资料

- 算子源码：[alphanumeric_filter.py](https://github.com/datajuicer/data-juicer/blob/main/data_juicer/ops/filter/alphanumeric_filter.py)
- 单元测试：[test_alphanumeric_filter.py](https://github.com/datajuicer/data-juicer/blob/main/tests/ops/filter/test_alphanumeric_filter.py)
- 官方文档：[alphanumeric_filter.md](https://datajuicer.github.io/data-juicer/en/main/docs/operators/filter/alphanumeric_filter.md)

</details>

---

### 案例 2 · 模块介绍（DJ-Agents，ZH）

- **类型**: `submodule_qa`
- **语言**: `zh`

**输入（用户提问）**

> 介绍DJ-Agents

<details>
<summary><strong>输出（助手回答）</strong></summary>

Data-Juicer Agents（DJ-Agents）是 Data-Juicer 生态中的智能代理模块，旨在通过对话式交互和可视化界面，帮助用户快速构建、调试和优化数据处理菜谱（Recipe）。它结合了大语言模型（如通义千问）与 Data-Juicer 的算子能力，实现“需求描述 → 自动生成菜谱 → 交互式调试”的闭环流程。

---

### ✅ 核心功能

1. **对话式菜谱生成**  
   用户只需用自然语言描述数据处理需求（例如：“帮我过滤掉中文文本中长度小于50的样本”），Agent 会自动生成对应的 YAML 菜谱配置。

2. **交互式调试与优化**  
   支持在运行过程中动态修改参数、增删算子、查看中间结果，并实时反馈调整效果。

3. **支持自定义算子开发**  
   若需扩展新算子，可结合本地 Data-Juicer 源码进行开发，Agent 会自动识别并集成新增算子。

4. **双模式运行**  
   - **命令行模式**：适合快速测试与脚本化使用。
   - **AgentScope Studio 可视化模式**：提供图形化界面，便于教学、演示和协作。

---

### 🚀 快速开始

#### 系统要求
- Python 3.10+
- DashScope API Key（用于调用大模型）
- （可选）本地 Data-Juicer 源码路径（用于自定义算子）

#### 安装步骤

```bash
# 安装 uv（推荐）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆并安装 DJ-Agents
git clone https://github.com/datajuicer/data-juicer-agents.git
cd data-juicer-agents
uv pip install -e .
```

> 如需开发自定义算子，请同时安装 Data-Juicer：
```bash
git clone https://github.com/datajuicer/data-juicer.git
cd data-juicer
uv pip install -e .
```

#### 配置环境变量

```bash
export DASHSCOPE_API_KEY="your-dashscope-key"
export DATA_JUICER_PATH="/path/to/data-juicer"  # 可选
```

#### 启动方式

- **命令行模式**（默认）：
  ```bash
  dj-agents
  ```

- **可视化模式**（需先安装 AgentScope Studio）：
  ```bash
  npm install -g @agentscope/studio
  as_studio  # 启动 Studio
  dj-agents --use-studio
  ```

---

### 💡 使用示例

你可以这样与 Agent 对话：

> “帮我写一个菜谱：读取 JSONL 文件，过滤掉英文文本中单词数少于10的样本，再按语言聚合并保存。”

Agent 将返回结构化的 YAML 配置，并支持你进一步调整参数或添加新步骤。

---

📌 **提示**：所有操作均可通过自然语言完成，无需记忆 YAML 语法或算子名称！

---

### 🔗 参考资料

- [DJ-Agents QuickStart 文档](https://github.com/datajuicer/data-juicer-agents/blob/main/docs/QuickStart.md)
- [Data-Juicer GitHub 主仓库](https://github.com/datajuicer/data-juicer)
- [AgentScope Studio 官网](https://github.com/modelscope/agentscope)

</details>

---

### 案例 3 · 概念问题（基类算子，ZH）

- **类型**: `concept_qa`
- **语言**: `zh`

**输入（用户提问）**

> 介绍一下基类算子

<details>
<summary><strong>输出（助手回答）</strong></summary>

在 Data-Juicer 系统中，**基类算子（Base Operator）** 是所有具体算子（如 Mapper、Filter、Deduplicator 等）的抽象父类，定义了数据处理算子的基本结构、通用属性和核心方法。它位于 `data_juicer/ops/base_op.py` 文件中，是整个算子体系的基石。

---

## 🧱 基类结构概览

### 1. **顶层基类 `OP`**

所有算子都继承自 `OP` 类，该类使用元类 `OPMetaClass` 实现实例化时自动记录初始化参数：

```python
class OP(metaclass=OPMetaClass):
```

#### ✅ 核心功能：

- **统一数据字段键名管理**：如 `text_key`, `image_key`, `audio_key`, `video_key`, `query_key`, `response_key`, `history_key` 等。
- **硬件加速支持**：通过 `accelerator` 属性支持 CPU/CUDA 自动切换。
- **批处理模式控制**：`_batched_op` 和 `batch_mode` 控制是否启用批处理。
- **资源调度配置**：支持 Ray 分布式执行时的资源配置（`num_cpus`, `num_gpus`, `memory`, `runtime_env`, `ray_execution_mode`）。
- **错误容忍机制**：通过 `skip_op_error` 控制是否跳过处理异常样本。
- **运行时并发计算**：`runtime_np()` 方法根据资源限制自动计算并行进程数。
- **嵌套数据访问封装**：通过 `wrap_func_with_nested_access` 自动支持嵌套字段访问。
- **通用运行入口 `run()`**：
  - 自动为 Tagging 类算子添加 `meta` 字段；
  - 为 Filter 类算子添加 `stats` 字段；
  - 支持为样本添加索引（`index_key`）。

---

### 2. **五大核心子类算子**

从 `OP` 派生出五类专用基类，分别对应不同数据处理范式：

| 类型          | 基类           | 功能描述                             | 输入 → 输出              |
|---------------|----------------|--------------------------------------|--------------------------|
| 数据映射      | `Mapper`       | 修改或增强样本内容                   | sample → sample          |
| 数据过滤      | `Filter`       | 根据条件保留/丢弃样本                | sample → bool            |
| 数据去重      | `Deduplicator` | 计算样本哈希并移除重复项             | dataset → dataset        |
| 数据选择      | `Selector`     | 在数据集级别选择子集（如Top-K采样）  | dataset → dataset        |
| 数据聚合      | `Aggregator`   | 将分组样本聚合成单个样本             | batched sample → sample  |

> 💡 每个子类都强制要求实现特定方法（如 `process_single`, `compute_stats`），并通过装饰器自动包装为支持批处理和错误捕获的版本。

---

## ⚙️ 关键设计特性

### 🔁 自动批处理与单样本兼容

- 若 `_batched_op = True` 或用户设置 `batch_mode=True`，系统自动将 `process_single` 包装为批处理逻辑。
- 所有输入统一转换为 Python dict（支持 Arrow Table 自动转换）。
- 提供 `convert_list_dict_to_dict_list` / `convert_dict_list_to_list_dict` 工具函数用于格式互转。

### 🛡️ 错误容忍机制

- 使用 `catch_map_single_exception` / `catch_map_batches_exception` 装饰器捕获单样本或批次处理中的异常。
- 可选跳过错误样本（`skip_op_error=True`），避免整个流程中断。

### 📊 数据追踪支持（Tracer）

- 自动包装 `process` 方法，在处理前后记录样本变化（适用于 Mapper/Filter）。
- 支持可视化调试和质量分析。

### 🧩 注册机制

- 所有算子通过 `Registry("Operators")` 注册，便于动态发现和调用。
- 特殊类型算子（如不可 fork 的、非统计型 Filter、Tagging 算子等）也有独立注册表。

---

## 🧩 示例：自定义一个简单 Mapper

```python
from data_juicer.ops import Mapper

class MyTextMapper(Mapper):
    def process_single(self, sample):
        sample[self.text_key] = sample[self.text_key].upper()
        return sample
```

系统会自动为其添加：
- 批处理支持
- 错误捕获
- 嵌套字段访问
- Tracer 集成

---

## 📚 参考资料

- 基类源码: https://github.com/datajuicer/data-juicer/blob/main/data_juicer/ops/base_op.py
- 算子文档: https://github.com/datajuicer/data-juicer/blob/main/docs/Operators.md
- 教程: https://github.com/datajuicer/data-juicer/tree/main/docs/tutorial

</details>

---

### 案例 4 · 快速开始（如何安装 DJ，ZH）

- **类型**: `quick_start_qa`
- **语言**: `zh`

**输入（用户提问）**

> 如何安装DJ？

<details>
<summary><strong>输出（助手回答）</strong></summary>

安装 Data-Juicer（DJ）有多种方式，您可以根据需求选择适合的安装方法：

---

## 🐍 基础安装（推荐）

### 前提条件：
- Python 3.10 ~ 3.12
- 推荐使用 `uv` 包管理器（更快更稳定）

```bash
# 安装 uv（任选其一）
curl -LsSf https://astral.sh/uv/install.sh | sh
# 或
pip install uv

# 安装 DJ 核心功能
uv pip install py-data-juicer
```

> 此方式仅包含核心数据处理能力：数据加载、文件操作、并行处理等。

---

## 🧩 场景化安装（按需组合）

根据您的任务类型，可选择安装特定模块：

```bash
# 通用机器学习/深度学习支持
uv pip install "py-data-juicer[generic]"

# 自然语言处理
uv pip install "py-data-juicer[nlp]"

# 计算机视觉
uv pip install "py-data-juicer[vision]"

# 音频处理
uv pip install "py-data-juicer[audio]"

# 分布式计算
uv pip install "py-data-juicer[distributed]"

# AI服务/API支持
uv pip install "py-data-juicer[ai_services]"

# 开发与测试工具
uv pip install "py-data-juicer[dev]"
```

### 常用组合示例：

```bash
# 文本处理完整环境
uv pip install "py-data-juicer[generic,nlp]"

# 视觉处理完整环境
uv pip install "py-data-juicer[generic,vision]"

# 全功能安装（除沙箱外）
uv pip install "py-data-juicer[all]"
```

---

## 🛠️ 从源码安装（获取最新特性）

```bash
git clone https://github.com/datajuicer/data-juicer.git
cd data-juicer
uv pip install -e .                  # 安装核心
uv pip install -e ".[vision]"        # 安装特定模块
```

> `-e` 表示“可编辑模式”，便于开发调试。

---

## 🐳 Docker 安装

### 拉取官方镜像：

```bash
docker pull datajuicer/data-juicer:<version_tag>
# 示例：
docker pull datajuicer/data-juicer:v0.2.0
```

### 或自行构建镜像：

```bash
docker build -t datajuicer/data-juicer:v0.2.0 .
```

---

## ⚙️ 特定算子依赖安装

如果只想为某个配置文件中的算子安装最小依赖：

```bash
# 仅适用于源码安装
python tools/dj_install.py --config your_config.yaml
# 或使用命令行工具
dj-install --config your_config.yaml
```

---

## 📌 注意事项

1. **视频处理**：如需使用视频相关算子，请先安装 **FFmpeg** 并确保其在 `$PATH` 中。
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg
   # macOS
   brew install ffmpeg
   ```

2. **验证安装**：
   ```python
   import data_juicer as dj
   print(dj.__version__)
   ```

3. **遇到问题**：
   - 优先查阅文档或 GitHub Issues
   - 可提交 Issue 或加入社区讨论

---

✅ 推荐首次用户使用 `uv pip install py-data-juicer` 快速上手，再根据具体任务扩展模块。

---

**参考文档**：
- [Installation Guide](https://github.com/datajuicer/data-juicer/blob/main/docs/tutorial/Installation.md)

</details>

---

### 案例 5 · 处理指导（过滤脏话文本，ZH）

- **类型**: `processing_qa`
- **语言**: `zh`

**输入（用户提问）**

> 我想过滤文本数据中的脏话，告诉我怎么做

<details>
<summary><strong>输出（助手回答）</strong></summary>

要过滤文本数据中的脏话，你可以使用 **`remove_words_with_incorrect_substrings_mapper`** 算子。虽然该算子默认用于移除包含如 "http"、"www" 等子串的词，但你可以通过自定义 `substrings` 参数传入脏话关键词列表，从而实现脏话过滤。

---

### ✅ 使用方法

在你的 Data-Juicer 配置文件（如 `config.yaml`）中添加如下配置：

```yaml
process:
  - remove_words_with_incorrect_substrings_mapper:
      lang: "en"  # 或 "zh" 等其他语言
      tokenization: false  # 若无需分词可设为 false
      substrings: ["fuck", "shit", "bitch", "asshole"]  # 替换为你想过滤的脏话关键词
```

---

### 📌 说明

- **`lang`**: 指定文本语言，影响分句和分词行为。
- **`tokenization`**: 是否使用 Hugging Face tokenizer 进行分词。若设为 `false`，则按空格或标点简单切分。
- **`substrings`**: 关键参数！填入你希望屏蔽的所有脏话或敏感词子串（支持部分匹配）。

> ⚠️ 注意：该算子会**删除包含指定子串的整个词**。例如，若 `substrings` 包含 `"ass"`，则 `"classic"` 也会被误删。建议尽量使用完整脏词，避免过度匹配。

---

### 🧪 示例输入/输出

**输入文本**：
```
This is a fucking bad example, don't be an asshole.
```

**处理后输出**：
```
This is a bad example, don't be .
```

---

### 📚 参考资料

- 算子代码：https://github.com/datajuicer/data-juicer/blob/main/data_juicer/ops/mapper/remove_words_with_incorrect_substrings_mapper.py
- 使用文档：https://datajuicer.github.io/data-juicer/en/main/docs/operators/mapper/remove_words_with_incorrect_substrings_mapper.md
- 测试用例：https://github.com/datajuicer/data-juicer/blob/main/tests/ops/mapper/test_remove_words_with_incorrect_substrings_mapper.py

如需更智能的脏话识别（如语义或上下文感知），可结合外部敏感词库或模型进行预处理，再接入 Data-Juicer 流程。

</details>

---

### 案例 6 · 最佳实践（使用 DJ 的建议，ZH）

- **类型**: `best_practice_qa`
- **语言**: `zh`

**输入（用户提问）**

> 你能给我一些使用DJ的最佳实践吗？

<details>
<summary><strong>输出（助手回答）</strong></summary>

以下是使用 Data-Juicer (DJ) 的一些最佳实践，结合官方文档、示例菜谱和社区经验整理而成：

---

## ✅ 1. **模块化安装，按需加载**
- **不要一次性安装全部依赖**。DJ 支持按场景安装，避免环境臃肿：
  ```bash
  # 文本处理基础
  uv pip install "py-data-juicer[generic,nlp]"

  # 图像处理
  uv pip install "py-data-juicer[vision]"

  # 分布式处理
  uv pip install "py-data-juicer[distributed]"
  ```
- 对于特定菜谱（Recipe），可使用 `dj-install` 工具自动安装最小依赖：
  ```bash
  dj-install --config your_recipe.yaml
  ```

> 📌 参考：[Installation Guide](https://github.com/datajuicer/data-juicer/blob/main/docs/tutorial/Installation.md)

---

## ✅ 2. **从官方菜谱库学习与复用**
- DJ Hub 提供了大量经过验证的菜谱，涵盖文本、图像、视频等模态：
  - 预训练数据清洗（如 RedPajama、BLOOM）
  - 指令微调数据优化（如 Alpaca-CoT）
  - 多模态合成（如 Img-Diff、LLaVA）
  - 视频数据处理（如 HumanVBench）

👉 推荐路径：
```text
data-juicer-hub/refined_recipes/
├── pretrain/           # 预训练数据精炼
├── alpaca_cot/         # 指令微调数据优化
├── image/              # 图像数据处理
└── video/              # 视频数据处理
```

> 📌 参考：[Data-Juicer Recipe Gallery](https://github.com/datajuicer/data-juicer-hub/blob/main/docs/RecipeGallery.md)

---

## ✅ 3. **合理组合算子（Operators）**
- 根据任务选择合适的 OP 类型：
  - **Filter（过滤器）**：去除低质量样本（如 `language_id_score_filter`, `image_nsfw_filter`）
  - **Mapper（映射器）**：增强或转换数据（如 `image_captioning_mapper`, `generate_qa_from_text_mapper`）
  - **Deduplicator（去重器）**：消除重复内容（如 `document_simhash_deduplicator`）
  - **Selector（选择器）**：基于评分筛选优质样本（如 `topk_specified_field_selector`）

💡 示例：构建高质量图文数据集
```yaml
process:
  - image_aspect_ratio_filter: { min_ratio: 0.5, max_ratio: 2.0 }
  - image_nsfw_filter: { score_threshold: 0.8 }
  - image_text_matching_filter: { model: "clip", min_score: 0.2 }
  - image_captioning_mapper: { model: "blip" }
```

> 📌 参考：[Operator Schemas](https://github.com/datajuicer/data-juicer/blob/main/docs/Operators.md)

---

## ✅ 4. **利用批处理与分布式加速**
- 对大规模数据，启用 Ray 分布式后端：
  ```yaml
  # 在 config.yaml 中启用
  use_ray: true
  ray_num_nodes: 4
  ```
- 使用 `grouper` 和 `pipeline` 算子实现批量推理，提升 GPU 利用率。

---

## ✅ 5. **评估与迭代**
- 所有精炼后的数据集都应进行下游任务验证（如 LLM 训练、多模态模型微调）。
- 官方案例显示，经 DJ 处理的数据在多个基准上显著提升模型性能（如 LLaVA、T2V-Turbo）。

📊 示例：LLaVA 使用 DJ 优化预训练数据后，在 MM-Bench 上提升 +0.5，MM-Vet 提升 +1.3。

> 📌 参考：[RecipeGallery 中的评估表格](https://github.com/datajuicer/data-juicer-hub/blob/main/docs/RecipeGallery.md#61-evaluation-and-verification)

---

## ✅ 6. **贡献与协作**
- 如果你开发了新算子或优化了菜谱，欢迎提交 PR 至 [data-juicer-hub](https://github.com/datajuicer/data-juicer-hub)。
- 社区共建的菜谱会被收录到 Gallery，并获得官方致谢。

---

## ✅ 7. **调试与日志**
- 启用详细日志便于调试：
  ```yaml
  # config.yaml
  log_level: "INFO"
  save_stats_in_one_file: true
  ```
- 使用内置测试数据验证算子效果：
  ```bash
  python -m tests.ops.test_your_operator
  ```

---

遵循以上最佳实践，你可以高效、稳定地使用 Data-Juicer 构建高质量数据集，为大模型训练提供坚实基础。

---

### 🔗 参考资料
- [Data-Juicer Installation Guide](https://github.com/datajuicer/data-juicer/blob/main/docs/tutorial/Installation.md)
- [Data-Juicer Recipe Gallery](https://github.com/datajuicer/data-juicer-hub/blob/main/docs/RecipeGallery.md)
- [Data-Juicer Operators Documentation](https://github.com/datajuicer/data-juicer/blob/main/docs/Operators.md)

</details>

---

### 案例 7 · 越界问题（与 DJ 无关提问，ZH）

- **类型**: `off_topic_qa`
- **语言**: `zh`

**输入（用户提问）**

> 今天天气怎么样？

<details>
<summary><strong>输出（助手回答）</strong></summary>

Sorry, this question is unrelated to Data-Juicer.

</details>

