## Data-Juicer 问答 Copilot 示例（中文）

本文按案例展示 **输入问题（Input）** 与 **助手回答（Output）**，便于理解 QA Copilot 的实际效果。

你可以在官方[文档页](https://datajuicer.github.io/data-juicer/zh_CN/main/index_ZH.html)和我们的 [问答 Copilot](./README_ZH.md) ***Juicer*** 聊天! 欢迎向 ***Juicer*** 提出任何与 Data-Juicer 生态相关的问题。

<div align="center">
<img src="https://github.com/user-attachments/assets/a0099ce2-4ed3-4fab-8cfa-b0bbd3beeac9" width=90%>
</div>

---

---

### 案例 1 · 算子介绍（alphanumeric_filter，ZH）

- **类型**: `operator_qa`
- **语言**: `zh`

**输入（用户提问）**

> 介绍alphanumeric_filter

<details>
<summary><strong>输出（助手回答）</strong></summary>

`alphanumeric_filter` 是 Data-Juicer 中的一个**过滤器算子（Filter Operator）**，主要用于根据文本中**字母和数字字符（或 Token）的比例**来筛选数据样本。

### 📌 核心功能
该算子计算样本中字母数字内容（Alphanumeric）占整体内容（字符或 Token）的比例，并保留该比例在指定范围 `[min_ratio, max_ratio]` 内的样本。这有助于过滤掉那些包含过多特殊符号、乱码或非自然语言内容的低质量数据。

### ⚙️ 主要参数
| 参数名 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `tokenization` | `bool` | `False` | 是否基于 Token 计算比例。若为 `False`，则基于字符（Character）计算；若为 `True`，则使用 Hugging Face Tokenizer 分词后计算。 |
| `min_ratio` | `float` | `0.25` | 最小比例阈值。低于此值的样本将被过滤掉。 |
| `max_ratio` | `float` | `sys.maxsize` | 最大比例阈值。高于此值的样本将被过滤掉。 |

### 💡 工作原理
1. **计算指标**：
   - 如果 `tokenization=False`：计算 `alnum_ratio` = (字母+数字字符数) / (总字符数)。
   - 如果 `tokenization=True`：计算 `alpha_token_ratio` = (包含字母或数字的 Token 数) / (总 Token 数)。
2. **过滤判断**：检查计算出的比例是否在 `[min_ratio, max_ratio]` 区间内。
3. **缓存统计**：算子会将计算出的比例值缓存到样本的 `stats` 字段中，方便后续分析或可视化。

### 📊 效果示例
假设配置为 `min_ratio=0.2, max_ratio=0.9`：
- **保留**：`"a=1\nb\nc=1+2"`（字母数字占比适中）。
- **过滤**：`"，。、„”“«»１」"`（几乎全是特殊符号，字母数字占比极低）。

当启用 `tokenization=True` 且 `min_ratio=1.5` 时（注意：Token 模式下比例计算逻辑可能因 Tokenizer 而异，通常用于确保大部分 Token 都是有意义的字母数字组合）：
- **保留**：`"Do you need a cup of coffee?"`
- **过滤**：纯标点或乱码样本。

### 🔗 相关链接
- [官方文档](https://github.com/datajuicer/data-juicer/blob/main/docs/operators/filter/alphanumeric_filter.md)
- [源代码](https://github.com/datajuicer/data-juicer/blob/main/data_juicer/ops/filter/alphanumeric_filter.py)

这个算子通常用于数据清洗的早期阶段，以快速剔除明显非文本或格式混乱的数据。

</details>

---

### 案例 2 · 模块介绍（DJ-Agents，ZH）

- **类型**: `submodule_qa`
- **语言**: `zh`

**输入（用户提问）**

> 介绍DJ-Agents

<details>
<summary><strong>输出（助手回答）</strong></summary>

**Data-Juicer Agents (DJ-Agents)** 是 Data-Juicer 生态系统中的一个智能代理套件，旨在实现**代理式数据处理（Agentic Data Processing）**。它构建在 [Data-Juicer](https://github.com/datajuicer/data-juicer) 和 [AgentScope](https://github.com/agentscope-ai/agentscope) 之上，目标是让开发者从“如何实现”数据处理细节中解放出来，专注于“要做什么”，从而实现无代码或低代码的数据处理生命周期。

以下是 DJ-Agents 的核心介绍：

### 1. 核心愿景与定位
*   **智能副驾驶**：作为数据探索和数据处理流水线的智能助手。
*   **自然语言交互**：用户可以通过自然语言描述数据处理需求（例如“为 RAG 任务去重并清洗文本”），Agent 会自动规划、选择算子并生成执行方案。
*   **工具化与技能化**：将 Data-Juicer 的强大能力封装为 Agent 可调用的 `tools`（工具）和 `skills`（技能），支持通用大模型 Agent 的自主编排。

### 2. 主要功能模块
根据最新的架构重构（2026-03-11），DJ-Agents 主要包含以下部分：

*   **CLI 命令行工具 (`djx`)**：
    *   `djx retrieve`：根据自然语言意图检索合适的 Data-Juicer 算子。
    *   `djx plan`：分析数据集并生成处理计划（YAML 格式的 Recipe）。
    *   `djx apply`：应用生成的计划进行数据处理。
    *   `djx tool`：提供 JSON 格式的工具接口，便于与其他 Agent 系统或自动化流程集成。
*   **会话模式 (`dj-agents`)**：
    *   提供一个交互式界面（支持 TUI 终端用户界面或 AgentScope Studio），用户可以像聊天一样与 Agent 对话，逐步完成数据检查、算子推荐、方案生成和执行。
    *   支持中断当前操作 (`Ctrl+C`) 和退出 (`Ctrl+D`)。
*   **Q&A Copilot (Juicer)**：
    *   一个专门针对 Data-Juicer 生态的智能问答助手，已部署在官方文档网站、钉钉群和 Discord 社区中，帮助用户解答关于 DJ 算子、菜谱和使用方法的问题。

### 3. 技术架构特点
*   **基于 AgentScope**：利用 AgentScope 框架强大的多 Agent 协作和工具调用能力。
*   **模块化设计**：
    *   **Core**：包含完整的 `djx` 和 `dj-agents` 命令。
    *   **Harness**：最小化安装，仅包含用于自动化的 `djx tool` 核心工具集。
    *   **Full**：包含核心功能以及 Q&A Copilot 和交互式菜谱（InteRecipe）等高级功能。
*   **模型支持**：支持 DashScope（通义千问系列）以及其他 OpenAI 兼容的 API。

### 4. 快速开始示例
你可以通过以下步骤体验 DJ-Agents：

1.  **安装**：
    ```bash
    git clone https://github.com/datajuicer/data-juicer-agents.git
    cd data-juicer-agents
    uv pip install -e '.[full]'
    ```
2.  **配置 API Key**：
    ```bash
    export DASHSCOPE_API_KEY="your_api_key"
    ```
3.  **运行会话模式**：
    ```bash
    dj-agents --dataset ./data/demo-dataset.jsonl --export ./data/output.jsonl
    ```
    然后在终端中与 Agent 对话，例如输入：“帮我检查一下数据集的质量，并去除重复项。”

### 5. 未来路线图 (Roadmap)
*   **DJ Skills**：通过提示词软编排将工具打包为技能，供更通用的 Agent 使用。
*   **InteRecipe Studio**：开发前端界面，支持通过自然语言交互式构建数据菜谱，并提供多维度的数据和结果视图。
*   **扩展应用场景**：进一步支持 RAG（检索增强生成）、具身智能和数据湖仓架构等复杂场景的数据处理。

更多详细信息可以参考官方文档：
*   [Overview Doc](https://github.com/datajuicer/data-juicer-agents/blob/main/docs/overview.md)
*   [Quick Start Doc](https://github.com/datajuicer/data-juicer-agents/blob/main/docs/quick_start.md)
*   [CLI Doc](https://github.com/datajuicer/data-juicer-agents/blob/main/docs/cli.md)

</details>

---

### 案例 3 · 概念问题（基类算子，ZH）

- **类型**: `concept_qa`
- **语言**: `zh`

**输入（用户提问）**

> 介绍一下基类算子

<details>
<summary><strong>输出（助手回答）</strong></summary>

在 Data-Juicer (DJ) 中，**基类算子 (Base Operators)** 是所有具体数据处理算子的父类或抽象基础。它们定义了算子的基本结构、接口规范以及通用的执行逻辑，确保所有算子遵循统一的标准以便组合成流水线（Pipeline）。

为了给你提供最准确的介绍，我需要检索 Data-Juicer源码中关于基类算子的定义和文档。

在 Data-Juicer (DJ) 中，**基类算子 (Base Operators)** 是所有具体数据处理逻辑的抽象基础。它们位于 `data_juicer/ops/base_op.py` 文件中，定义了算子的通用接口、执行流程以及资源管理方式。

以下是 DJ 中主要基类算子的详细介绍：

### 1. `OP` (Operator Base Class)
这是所有算子的最顶层父类。它定义了算子的基本属性和通用方法。
*   **核心功能**：
    *   **参数初始化**：统一处理数据键名（如 `text_key`, `image_key`）、批处理大小 (`batch_size`)、加速设备 (`accelerator`: cpu/cuda) 以及并行度 (`num_proc`)。
    *   **资源管理**：支持 Ray 分布式执行所需的资源配置（如 `num_cpus`, `num_gpus`, `memory`）。
    *   **生命周期**：提供 `run()` 方法的模板，负责在执行前后添加元数据列（如 `meta`, `stats`）或索引。
*   **关键属性**：
    *   `_name`: 算子名称（由注册表自动设置）。
    *   `_accelerator`: 默认运行设备。
    *   `_batched_op`: 是否为批处理算子。

### 2. `Mapper` (映射算子)
继承自 `OP`，用于对数据进行**一对一**或**一对多**的转换和编辑。
*   **用途**：数据清洗、格式转换、内容增强、标注等。
*   **核心方法**：
    *   `process_single(sample)`: 处理单个样本。
    *   `process_batched(samples)`: 处理一批样本（如果算子支持批处理）。
*   **特点**：
    *   输入一个样本，输出一个修改后的样本（可能增加或删除字段）。
    *   支持异常捕获（`catch_map_batches_exception`），确保流水线在遇到错误时不会完全崩溃。
    *   示例：`clean_email_mapper` (删除邮箱), `image_face_blur_mapper` (人脸模糊)。

### 3. `Filter` (过滤算子)
继承自 `OP`，用于根据特定条件**筛选**数据。
*   **用途**：去除低质量数据、去重前的初步筛选、基于指标的过滤。
*   **核心方法**：
    *   `compute_stats_single(sample)`: 计算样本的统计指标（如文本长度、困惑度、图像相似度得分）。
    *   `process_single(sample)`: 根据计算出的 stats 返回 `True` (保留) 或 `False` (过滤)。
*   **特点**：
    *   分为两步：先计算统计信息 (`compute_stats`)，再根据阈值进行过滤 (`process`)。
    *   支持将统计结果导出 (`stats_export_path`) 以便分析数据分布。
    *   示例：`text_length_filter` (文本长度过滤), `image_face_count_filter` (人脸数量过滤)。

### 4. `Deduplicator` (去重算子)
继承自 `OP`，专门用于**去除重复数据**。
*   **用途**：MinHash 去重、精确哈希去重、语义去重。
*   **核心方法**：
    *   `compute_hash(sample)`: 为样本计算哈希值或指纹。
    *   `process(dataset)`: 在整个数据集层面根据哈希值移除重复项。
*   **特点**：
    *   通常在数据集全局范围内操作，而不仅仅是单样本。
    *   可以追踪并返回重复对 (`dup_pairs`)。
    *   示例：`ray_basic_deduplicator`。

### 5. `Selector` (选择算子)
继承自 `OP`，用于在**数据集级别**进行选择。
*   **用途**：随机采样、基于复杂逻辑的子集选择。
*   **核心方法**：
    *   `process(dataset)`: 接收整个数据集，返回选中的子集。
*   **特点**：
    *   与 `Filter` 不同，`Selector` 通常不依赖单样本的统计指标，而是基于全局逻辑（如“随机选择 10%”）。
    *   示例：`random_selector`。

### 6. `Grouper` (分组算子) & `Aggregator` (聚合算子)
这两个算子通常配合使用，用于处理**多对一**的逻辑。
*   **`Grouper`**：
    *   将多个样本组合成一个批次（Batch）。
    *   `process(dataset)`: 返回分组后的数据集。
*   **`Aggregator`**：
    *   对分组后的批次进行聚合处理，生成一个新的样本。
    *   `process_single(batched_sample)`: 输入一组样本，输出一个聚合后的样本。
*   **用途**：构建训练对（如 SFT 数据构造）、文档级上下文聚合。

### 7. `Pipeline` (流水线算子)
*   **用途**：将多个算子组合成一个复合算子。
*   **特点**：允许用户将常用的算子序列封装成一个独立的单元，方便复用。

---

### 基类算子的通用特性

1.  **注册机制 (`Registry`)**：
    所有算子通过 `@OPERATORS.register_module()` 装饰器注册，用户可以通过名称直接调用。
2.  **批处理支持 (`Batched Op`)**：
    基类支持 `_batched_op` 标记。如果设置为 `True`，算子将接收一个包含多个样本的字典（Dict of Lists），这在使用 GPU 加速模型（如 LLM、CLIP）时能显著提高效率。
3.  **异常容错**：
    基类提供了 `skip_op_error` 参数。如果开启，当某个样本处理失败时，算子会记录错误并跳过该样本，而不是中断整个任务。
4.  **Tracer 集成**：
    基类集成了 `tracer` 功能，可以自动记录数据在处理前后的变化（如文本被修改了多少字符，哪些样本被过滤了），便于数据溯源和分析。
5.  **分布式兼容**：
    所有基类都内置了对 Ray 分布式框架的支持，可以通过 `num_cpus`, `num_gpus` 等参数轻松扩展到多机多卡环境。

如果你想了解如何自定义一个新的算子，可以参考 [DeveloperGuide.md](https://github.com/datajuicer/data-juicer/blob/main/docs/DeveloperGuide.md)，其中详细说明了如何继承这些基类并实现 `process` 方法。

</details>

---

### 案例 4 · 快速开始（如何安装 DJ，ZH）

- **类型**: `quick_start_qa`
- **语言**: `zh`

**输入（用户提问）**

> 如何安装DJ？

<details>
<summary><strong>输出（助手回答）</strong></summary>

安装 Data-Juicer (DJ) 主要有几种方式，取决于您的使用场景（是作为 Python 库使用，还是使用 Docker 环境）。以下是基于官方文档的安装指南：

### 方法一：使用 pip 安装（推荐用于开发或作为库使用）

这是最通用的安装方式。建议您先创建一个虚拟环境。

1.  **创建并激活虚拟环境**（可选但推荐）：
    ```bash
    python -m venv dj_env
    source dj_env/bin/activate  # Linux/Mac
    # 或者在 Windows 上: dj_env\Scripts\activate
    ```

2.  **安装 Data-Juicer**：
    ```bash
    pip install data-juicer
    ```

3.  **安装额外依赖**（可选）：
    Data-Juicer 有很多算子依赖不同的第三方库（如 OCR、音频处理等）。如果您需要特定功能，可以安装 extras：
    ```bash
    # 例如，安装所有额外依赖
    pip install data-juicer[all]
    
    # 或者只安装特定模块的依赖，例如：
    pip install data-juicer[video]
    pip install data-juicer[audio]
    ```

### 方法二：使用 Docker 安装（推荐用于快速体验或隔离环境）

如果您不想配置本地 Python 环境，可以使用官方提供的 Docker 镜像。

1.  **拉取镜像**：
    ```bash
    docker pull datajuicer/data-juicer:latest
    ```

2.  **运行容器**：
    ```bash
    docker run -it --gpus all --shm-size 16g \
      -v /path/to/your/data:/data \
      -v /path/to/your/config:/config \
      datajuicer/data-juicer:latest \
      bash
    ```
    *注意：请根据您的实际需求调整挂载路径 (`-v`) 和 GPU 参数。*

### 方法三：从源码安装（用于贡献代码或获取最新特性）

1.  **克隆仓库**：
    ```bash
    git clone https://github.com/datajuicer/data-juicer.git
    cd data-juicer
    ```

2.  **安装依赖**：
    ```bash
    pip install -e .
    # 如果需要所有额外依赖
    pip install -e ".[all]"
    ```

### 验证安装

安装完成后，您可以在终端输入以下命令来验证是否安装成功：

```bash
dj --help
```

如果看到帮助信息，说明安装成功。

### 参考链接

*   **详细安装教程**: [Data-Juicer Installation Guide](https://github.com/datajuicer/data-juicer/blob/main/docs/tutorial/Installation.md)
*   **GitHub 仓库**: [datajuicer/data-juicer](https://github.com/datajuicer/data-juicer)

如果您在安装过程中遇到特定错误（如依赖冲突），请提供错误日志，我可以帮您进一步排查。

</details>

---

### 案例 5 · 最佳实践（使用 DJ 的建议，ZH）

- **类型**: `best_practice_qa`
- **语言**: `zh`

**输入（用户提问）**

> 你能给我一些使用DJ的最佳实践吗？

<details>
<summary><strong>输出（助手回答）</strong></summary>

当然可以！Data-Juicer (DJ) 是一个强大的多模态数据处理框架。为了帮助你更高效地使用它，我整理了一些基于官方文档和社区经验的最佳实践。

以下是使用 Data-Juicer 的关键最佳实践：

### 1. 明确数据处理流程 (Pipeline Design)
不要试图用一个巨大的配置文件完成所有事情。将数据处理分为几个逻辑阶段：
*   **基础清洗 (Basic Cleaning)**:去除空白、特殊字符、过短/过长文本等。
*   **质量过滤 (Quality Filtering)**:使用语言模型评分、困惑度（Perplexity）、毒性检测等算子。
*   **去重 (Deduplication)**:在高质量过滤后进行去重，以减少计算资源浪费。通常先做局部去重（MinHash），再做全局去重。
*   **增强与格式化 (Enhancement & Formatting)**:如添加元数据、转换格式等。

**建议**：参考 [Data-Juicer Hub](https://github.com/datajuicer/data-juicer-hub) 中的官方菜谱（Recipes），它们已经展示了经过验证的处理流程。

### 2. 合理选择算子 (Operator Selection)
*   **从小规模开始**：在大规模数据集上运行之前，先在小样本（例如 1000 条数据）上测试你的配置。这可以快速发现配置错误或性能瓶颈。
*   **利用 `retrieve_operators_api`**：如果你不确定哪个算子适合你的需求，可以使用自然语言描述你的意图，让系统推荐合适的算子。
    *   例如：*"我想过滤掉包含大量非ASCII字符的文本"*
*   **查看算子文档**：使用 `get_operator_info` 获取算子的详细参数说明和示例。确保你理解每个参数的含义，特别是阈值（thresholds）。

### 3. 性能优化 (Performance Optimization)
*   **并行处理**：Data-Juicer 支持多进程并行处理。根据你的 CPU 核心数调整 `parallelism` 参数。
*   **资源管理**：
    *   对于 CPU 密集型算子（如 MinHash 去重），确保有足够的内存。
    *   对于 GPU 密集型算子（如基于 LLM 的评分），注意显存限制，可能需要减小 batch size。
*   **缓存中间结果**：如果处理流程很长，建议在关键步骤后保存中间数据集。这样如果后续步骤失败或需要调整，可以从断点继续，而不必从头开始。

### 4. 监控与调试 (Monitoring & Debugging)
*   **启用日志**：设置适当的日志级别（INFO 或 DEBUG），以便跟踪处理进度和潜在错误。
*   **统计信息**：Data-Juicer 通常会输出每个算子处理前后的数据量变化。密切关注这些统计信息，如果某个算子过滤掉了过多数据（例如 >90%），可能需要检查其参数是否过于严格。
*   **可视化**：如果可能，使用可视化工具检查处理后的数据样本，确保数据质量符合预期。

### 5. 利用 Data-Juicer Hub
*   **复用现有 Recipes**：不要从头开始编写配置。浏览 [Recipe Gallery](https://github.com/datajuicer/data-juicer-hub/blob/main/docs/RecipeGallery.md)，找到与你的数据类型（文本、图像、音频、视频）和目标相似的场景，然后在此基础上进行修改。
*   **贡献与分享**：如果你开发了一个有效的处理流程，考虑将其贡献回 Hub，帮助社区其他成员。

### 6. 特定数据类型建议
*   **文本**：重点关注语言识别、毒性过滤和去重。
*   **图像**：关注分辨率、宽高比、美学评分和水印检测。
*   **多模态**：确保文本和图像/音频之间的对齐质量，使用多模态算子进行联合过滤。

### 示例：一个简单的文本处理流程
```yaml
# example_recipe.yaml
dataset_path: "path/to/your/dataset.jsonl"
export_path: "path/to/output/dataset.jsonl"

process:
  - filter: # 基础过滤
      op: "alphanumeric_filter"
      args:
        min_ratio: 0.5
  - filter: # 长度过滤
      op: "text_length_filter"
      args:
        min_len: 10
        max_len: 10000
  - deduplicator: # 去重
      op: "minhash_deduplicator"
      args:
        window_size: 5
        threshold: 0.8
```

希望这些最佳实践能帮助你更好地使用 Data-Juicer！如果你有具体的数据处理任务或遇到问题，欢迎提供更多细节，我可以给出更针对性的建议。

</details>

---

### 案例 6 · 越界问题（与 DJ 无关提问，ZH）

- **类型**: `off_topic_qa`
- **语言**: `zh`

**输入（用户提问）**

> 今天天气怎么样？

<details>
<summary><strong>输出（助手回答）</strong></summary>

Sorry, this question is unrelated to Data-Juicer.

</details>
