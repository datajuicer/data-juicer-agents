## Data-Juicer Q&A Copilot Demo

This document shows end-to-end examples of the QA Copilot. Each case lists the **user query (input)** and the **assistant answer (output)**.

You can chat with our [Q&A Copilot](./README.md) ***Juicer*** on the official [documentation site](https://datajuicer.github.io/data-juicer/en/main/index.html) of Data-Juicer! Feel free to ask ***Juicer*** anything related to Data-Juicer ecosystem.

<div align="center">
<img src="https://github.com/user-attachments/assets/d10a95a8-fb7a-494f-b858-f21e5996790b" width=90%>
</div>

---

---

### Case 1 · Operator Introduction (alphanumeric_filter, EN)

- **Type**: `operator_qa`
- **Language**: `en`

**Input (user query)**

> Introduce alphanumeric_filter

<details>
<summary><strong>Output (assistant answer)</strong></summary>

I will retrieve the operator information for `alphanumeric_filter` to provide you with its details.

I will search for the `alphanumeric_filter` in the Data-Juicer codebase to find its implementation and documentation.

I will retrieve the contents of the `alphanumeric_filter.md` documentation file to provide a detailed introduction.

The `alphanumeric_filter` is a **filter operator** in Data-Juicer designed to retain text samples where the ratio of alphanumeric characters (or tokens) falls within a specified range. It is commonly used to clean datasets by removing samples that are either too sparse in alphanumeric content (e.g., mostly symbols or whitespace) or too dense (e.g., code-like or random character strings), depending on the configured thresholds.

### 📋 Key Features
- **Metric Calculation**: It calculates the ratio of alphanumeric characters to total characters. If tokenization is enabled, it calculates the ratio of alphanumeric tokens to total tokens using a Hugging Face tokenizer.
- **Filtering Logic**: Samples are kept if their ratio is between `min_ratio` and `max_ratio`. Samples outside this range are discarded.
- **Stats Caching**: The computed ratio (`alnum_ratio` or `alpha_token_ratio`) is cached in the sample's stats for transparency and reuse.

### ⚙️ Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `tokenization` | `bool` | `False` | If `True`, uses a Hugging Face tokenizer to compute the ratio based on tokens. If `False`, computes based on characters. |
| `min_ratio` | `float` | `0.25` | The minimum acceptable alphanumeric ratio. Samples below this value are filtered out. |
| `max_ratio` | `float` | `sys.maxsize` | The maximum acceptable alphanumeric ratio. Samples above this value are filtered out. |

### 💡 Usage Example

In a Data-Juicer recipe (YAML), you might configure it like this:

```yaml
process:
  - alphanumeric_filter:
      min_ratio: 0.2
      max_ratio: 0.9
      tokenization: false
```

### 🔍 Effect Demonstration

- **Character-based filtering** (`tokenization=False`):
  - Input: `"，。、„”“«»１」「《》´∶：？！（）；–—．～’…━〈〉【】％►"` (Mostly symbols)
  - Result: **Filtered out** because the alphanumeric ratio is very low (below `min_ratio`).
  - Input: `"Do you need a cup of coffee?"`
  - Result: **Kept** because the ratio of letters/spaces to total characters is within the typical range.

- **Token-based filtering** (`tokenization=True`):
  - This mode is useful for detecting samples where the *semantic* tokens are largely non-alphanumeric or when the tokenization behavior of specific models is relevant to the data quality.

For more details, you can refer to the [official documentation](https://github.com/datajuicer/data-juicer/blob/main/docs/operators/filter/alphanumeric_filter.md) or the [source code](https://github.com/datajuicer/data-juicer/blob/main/data_juicer/ops/filter/alphanumeric_filter.py).

</details>

---

### Case 2 · Module Introduction (DJ-Agents, EN)

- **Type**: `submodule_qa`
- **Language**: `en`

**Input (user query)**

> Introduce DJ-Agents

<details>
<summary><strong>Output (assistant answer)</strong></summary>

I'll help you learn about DJ-Agents (Data-Juicer Agents). Let me search for information about this project.

## Introduction to DJ-Agents (Data-Juicer Agents)

**DJ-Agents** is a suite of intelligent agents designed for **agentic data processing**, built on top of [Data-Juicer](https://github.com/datajuicer/data-juicer) and [AgentScope](https://github.com/agentscope-ai/agentscope). Its goal is to enable a **development-free data processing lifecycle**, allowing users to focus on *what* they want to do with their data rather than *how* to implement it.

### 🎯 Core Vision
Instead of writing complex data processing pipelines manually, DJ-Agents allows you to interact with your data through natural language conversations or high-level commands. The agents automatically plan, retrieve appropriate operators, and execute data processing tasks.

### 🏗️ Architecture
DJ-Agents is organized into four main layers:
1.  **Surface Adapters**: User-facing interfaces like the `djx` CLI and the interactive `dj-agents` session.
2.  **Capability Orchestration**: End-to-end workflows such as planning, applying, and development.
3.  **Tools**: Atomic, reusable capabilities (e.g., operator retrieval, dataset inspection).
4.  **Runtime Adapters**: Integration with underlying frameworks like AgentScope.

### 🚀 Key Features & Interfaces

#### 1. Interactive Session (`dj-agents`)
This is the conversational interface where you can chat with an agent to process your data.
-   **TUI (Terminal User Interface)**: A rich interactive experience in your terminal.
-   **Plain Mode**: Simple text-based interaction.
-   **AgentScope Studio**: Integration with a visual studio for monitoring agent behavior.
-   **Workflow**: The agent typically follows a path of `inspect_dataset -> retrieve_operators -> build_plan -> validate -> save`.

#### 2. Engineer CLI (`djx`)
A command-line tool for explicit, engineer-focused workflows:
-   **`djx retrieve`**: Find candidate Data-Juicer operators for a specific intent (e.g., "remove duplicate text").
-   **`djx plan`**: Generate a complete data processing plan (YAML) based on a natural language description.
-   **`djx apply`**: Execute a saved plan on your dataset.
-   **`djx tool`**: Access atomic tools for automation or integration with other agents.

#### 3. Q&A Copilot
A specialized assistant deployed on the official Data-Juicer documentation site, DingTalk, and Discord to answer questions about the entire Data-Juicer ecosystem.

### ⚡ Quick Start Example

To get started, you need Python 3.10+ and an API key (DashScope or OpenAI-compatible).

1.  **Install**:
    ```bash
    uv pip install -e '.[full]'
    ```
2.  **Configure Model**:
    ```bash
    export DASHSCOPE_API_KEY="<your_key>"
    export DJA_SESSION_MODEL="qwen3-max-2026-01-23"
    ```
3.  **Interactive Processing**:
    ```bash
    dj-agents --dataset ./data/demo-dataset.jsonl --export ./data/output.jsonl
    ```
4.  **CLI Planning**:
    ```bash
    djx plan "deduplicate and clean text for RAG" \
      --dataset ./data/demo-dataset.jsonl \
      --output ./data/demo-plan.yaml
    djx apply --plan ./data/demo-plan.yaml --yes
    ```

### 🔮 Roadmap
The project is continuously evolving with a focus on:
-   **DJ Skills**: Packaging tools into soft-orchestrated skills for general-purpose agents.
-   **InteRecipe Studio**: A frontend for interactive recipe construction via natural language.
-   **Broader Scenarios**: Expanding support for RAG, Embodied Intelligence, and Data Lakehouse architectures.

For more detailed documentation, you can visit the [DJ-Agents GitHub Repository](https://github.com/datajuicer/data-juicer-agents).

</details>

---

### Case 3 · Concept Question (Base Operator, EN)

- **Type**: `concept_qa`
- **Language**: `en`

**Input (user query)**

> Tell me about the base class of operators

<details>
<summary><strong>Output (assistant answer)</strong></summary>

I'll help you find information about the base class of operators in Data-Juicer. Let me search for this in the codebase.

Great! I found the base operator file. Let me examine it to understand the base class structure.

Perfect! Now I have a comprehensive understanding of the base class structure for operators in Data-Juicer. Let me provide you with a detailed explanation.

## Base Class of Operators in Data-Juicer

In Data-Juicer, all operators inherit from a common base class **`OP`** (Operator), which is defined in [`data_juicer/ops/base_op.py`](https://github.com/datajuicer/data-juicer/blob/main/data_juicer/ops/base_op.py).

### Core Base Class: `OP`

The **`OP`** class serves as the foundation for all operator types and provides:

#### Key Attributes:
- **`_name`**: The operator name (automatically set by the registry)
- **`_accelerator`**: Hardware accelerator ("cpu" or "cuda")
- **`_batched_op`**: Whether this operator processes batches
- **`_requirements`**: Extra package requirements

#### Common Parameters (in `__init__`):
- **Data keys**: `text_key`, `image_key`, `audio_key`, `video_key`, `image_bytes_key`
- **Chat format keys**: `system_key`, `instruction_key`, `query_key`, `response_key`, `history_key`
- **Processing config**: `batch_size`, `work_dir`, `skip_op_error`, `accelerator`
- **Resource allocation**: `num_cpus`, `num_gpus`, `memory`, `runtime_env`
- **Parallelism**: `auto_op_parallelism`, `num_proc`

#### Important Methods:
- **`process()`**: Abstract method - must be implemented by subclasses
- **`run(dataset)`**: Executes the operator on a dataset
- **`runtime_np()`**: Calculates the number of processes to use
- **`use_cuda()`**: Checks if CUDA acceleration is available
- **`is_batched_op()`**: Determines if batch processing is enabled
- **`get_env_spec()`**: Returns environment specification for dependencies

---

### Operator Type Subclasses

Data-Juicer defines **6 main operator types**, each extending `OP`:

#### 1. **`Mapper`** - Data Transformation
- **Purpose**: Modifies/transforms samples (sample → sample)
- **Key methods**: 
  - `process_single(sample)`: Process one sample
  - `process_batched(samples)`: Process batch of samples
- **Examples**: Text cleaning, image resizing, content replacement

#### 2. **`Filter`** - Sample Filtering
- **Purpose**: Removes samples based on criteria (sample → Boolean)
- **Key methods**:
  - `compute_stats_single(sample)`: Calculate filtering metrics
  - `process_single(sample)`: Return True/False for keep/filter
- **Features**: Supports min/max thresholds, closed/open intervals, reversed ranges
- **Examples**: Length filters, quality filters, toxicity filters

#### 3. **`Deduplicator`** - Duplicate Removal
- **Purpose**: Identifies and removes duplicate samples
- **Key methods**:
  - `compute_hash(sample)`: Generate hash for deduplication
  - `process(dataset)`: Perform deduplication on dataset
- **Examples**: MinHash dedup, exact match dedup

#### 4. **`Selector`** - Dataset-Level Selection
- **Purpose**: Selects subsets of data at dataset level (dataset → dataset)
- **Key method**: `process(dataset)`
- **Examples**: Top-k selection, range-based selection

#### 5. **`Grouper`** - Sample Grouping
- **Purpose**: Groups samples together (dataset → grouped dataset)
- **Key method**: `process(dataset)`
- **Examples**: Key-value grouping, bucket grouping

#### 6. **`Aggregator`** - Batch Aggregation
- **Purpose**: Aggregates grouped samples (batched sample → single sample)
- **Key method**: `process_single(sample)`
- **Note**: Must be used after a Grouper
- **Examples**: Merging grouped texts, combining annotations

#### 7. **`Pipeline`** - Processing Pipeline
- **Purpose**: Represents a complete data processing pipeline
- **Key method**: `run(dataset)`
- **Examples**: Multi-step workflows

---

### Key Design Features

1. **Registry System**: All operators are registered using the `OPERATORS` registry for automatic discovery

2. **Batch Processing Support**: Operators can work in single-sample or batch mode via `_batched_op` flag

3. **Error Handling**: Built-in exception catching with `catch_map_batches_exception` and `catch_map_single_exception`

4. **Tracing Integration**: Wrappers (`wrap_mapper_with_tracer`, `wrap_filter_with_tracer`) enable sample-level change tracking

5. **Ray Integration**: Support for distributed processing with configurable CPU/GPU/memory resources

6. **CUDA Acceleration**: Automatic detection and utilization of GPU when available

7. **Metaclass**: `OPMetaClass` captures initialization arguments for serialization/replay

---

### Usage Pattern

When creating a custom operator, you typically:
1. Inherit from the appropriate type (Mapper, Filter, etc.)
2. Implement the required `process_*` methods
3. Register it with the decorator `@OPERATORS.register_module()`

For more details on implementing operators, see the [Operators Documentation](https://github.com/datajuicer/data-juicer/blob/main/docs/Operators.md).

</details>

---

### Case 4 · Quick Start (Install DJ, EN)

- **Type**: `quick_start_qa`
- **Language**: `en`

**Input (user query)**

> How to install DJ?

<details>
<summary><strong>Output (assistant answer)</strong></summary>

To install Data-Juicer (DJ), you can follow the official installation guide. Here are the common methods:

### 1. Install from PyPI (Recommended for most users)
This is the simplest way to install the core Data-Juicer package.

```bash
pip install data-juicer
```

### 2. Install from Source (For development or latest features)
If you want to use the latest features or contribute to the project, you can clone the repository and install it in editable mode.

```bash
git clone https://github.com/datajuicer/data-juicer.git
cd data-juicer
pip install -e .
```

### 3. Install with Extra Dependencies
Data-Juicer supports various data modalities (text, image, audio, video). You may need to install extra dependencies depending on your use case.

*   **For full functionality (including all modalities):**
    ```bash
    pip install data-juicer[all]
    ```
*   **For specific modalities:**
    *   Text only: `pip install data-juicer`
    *   Image support: `pip install data-juicer[image]`
    *   Audio support: `pip install data-juicer[audio]`
    *   Video support: `pip install data-juicer[video]`

### 4. Docker Installation
You can also use Docker to run Data-Juicer without setting up the environment locally. Pre-built images are often available in the repository's Docker instructions.

```bash
# Example command (check the latest tag in the repo)
docker pull datajuicer/data-juicer:latest
```

### Verification
After installation, you can verify it by running:

```bash
dj --help
```

For detailed instructions, including system requirements and troubleshooting, please refer to the official [Installation Guide](https://github.com/datajuicer/data-juicer/blob/main/docs/tutorial/Installation.md).

</details>

---

### Case 5 · Best Practices (Using DJ, EN)

- **Type**: `best_practice_qa`
- **Language**: `en`

**Input (user query)**

> Could you give me some best practices for using DJ?

<details>
<summary><strong>Output (assistant answer)</strong></summary>

To provide you with the most accurate best practices for using Data-Juicer (DJ), I will search for official documentation, tutorials, and community guidelines within the Data-Juicer repositories.

I will now look for the official Data-Juicer repository to find best practices and documentation.

I will now examine the `data-juicer-hub` repository, as its description mentions "best practices," and also look at the main `data-juicer` documentation.

I will examine the `DeveloperGuide.md` and the `RecipeGallery.md` in the `data-juicer-hub` to find best practices.

I will now look at the `RecipeGallery.md` in the `data-juicer-hub` repository to find more best practices and community-contributed recipes.

I will also check the `awesome_llm_data.md` file in the main repository, as it likely contains valuable insights and best practices for data processing.

Based on the official Data-Juicer documentation, Developer Guide, and the Data-Juicer Hub, here are the best practices for using Data-Juicer (DJ):

### 1. Leverage the Data Recipe Gallery 📚
Instead of building pipelines from scratch, start with existing **Recipes** from the [Data-Juicer Hub](https://github.com/datajuicer/data-juicer-hub).
*   **Reproduce & Refine:** Use community-contributed recipes that reproduce popular datasets like RedPajama, The Pile, or LLaVA.
*   **Iterative Improvement:** DJ provides "refined" versions of these datasets. For example, using a simple 3-σ rule to filter outliers in RedPajama subsets can significantly improve model performance while retaining ~90-95% of the data.
*   **Modality-Specific Recipes:** Utilize specific recipes for Text, Image-Text (e.g., LCS-558k), and Video (e.g., InternVid/Panda-70M) processing.

### 2. Adopt an Iterative "Alpha-to-Stable" Development Process 🛠️
When creating custom Operators (OPs), follow the tiered contribution model:
*   **Alpha Version:** Focus on basic functionality. Implement `compute_stats_single` and `process_single`.
*   **Beta Version:** Add robustness. Include unit tests (`tests/ops/...`) and comprehensive docstrings. Update `config_all.yaml` so your OP appears in the help menus.
*   **Stable Version:** Optimize for performance. 
    *   Enable **Batched Processing** by setting `_batched_op = True` and implementing `process_batched`.
    *   Enable **GPU Acceleration** by setting `_accelerator = 'cuda'` if using models.
    *   Implement **OP Fusion** by registering intermediate variables (like `words` or `lines`) to avoid redundant calculations across multiple filters.

### 3. Master Configuration & Dependency Management ⚙️
*   **Hierarchical Configs:** Use YAML files with dot notation (e.g., `--text_length_filter.min 10`). DJ automatically registers configs from operator docstrings, keeping your code and config in sync.
*   **Lazy Loading:** DJ uses a lazy loading system. You don't need to install every dependency upfront. Dependencies are installed on-demand when an operator is first used.
*   **Environment Management:** Use `uv` for fast virtual environment management and dependency resolution as recommended in the Developer Guide.

### 4. Prioritize Data-Centric Evaluation 📊
*   **Bad Data Exhibition:** Regularly check the [Bad Data Exhibition](https://github.com/datajuicer/data-juicer/blob/main/docs/BadDataExhibition.md) to understand common data quality issues (e.g., repetition, low information density).
*   **Statistical Filtering:** Use statistical methods (like the 3-σ rule) to set hyperparameters for operators rather than guessing thresholds.
*   **Model-as-a-Judge:** Leverage DJ's ability to use MLLMs as evaluators (e.g., for toxicity, aesthetics, or cross-modal alignment) to create high-quality synthetic data or filter existing datasets.

### 5. Utilize Advanced Features for Scale 🚀
*   **Distributed Processing:** For large-scale datasets, use DJ's distributed mode (often powered by Ray) to parallelize processing across multiple nodes.
*   **Caching & Checkpoints:** Enable caching and partitioning to handle long-running jobs. This allows you to resume processing from the last checkpoint if a job fails.
*   **Tracing:** Use the built-in tracing features to monitor the flow of data and identify bottlenecks in your processing pipeline.

### 6. Community Contribution & Co-development 🤝
*   **Share Your Recipes:** If you develop a successful processing pipeline, contribute it to the Data-Juicer Hub. This promotes reuse and helps establish best practices for specific domains (e.g., medical or legal text).
*   **Operator Fusion:** When developing new operators, consider how they might share intermediate results with existing ones to speed up the entire pipeline.

For more detailed technical steps, refer to the [Developer Guide](https://github.com/datajuicer/data-juicer/blob/main/docs/DeveloperGuide.md) and the [Operators Documentation](https://github.com/datajuicer/data-juicer/blob/main/docs/Operators.md).

</details>

---

### Case 6 · Off-topic Question (Weather, EN)

- **Type**: `off_topic_qa`
- **Language**: `en`

**Input (user query)**

> How's the weather today?

<details>
<summary><strong>Output (assistant answer)</strong></summary>

Sorry, this question is unrelated to Data-Juicer.

</details>
