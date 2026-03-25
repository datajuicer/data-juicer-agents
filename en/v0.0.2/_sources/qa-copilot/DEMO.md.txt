## Data-Juicer Q&A Copilot Demo

This document shows end-to-end examples of the QA Copilot. Each case lists the **user query (input)** and the **assistant answer (output)**.

You can chat with our [Q&A Copilot](./README.md) ***Juicer*** on the official [documentation site](https://datajuicer.github.io/data-juicer/en/main/index.html) of Data-Juicer! Feel free to ask ***Juicer*** anything related to Data-Juicer ecosystem.

<div align="center">
<img src="https://github.com/user-attachments/assets/d10a95a8-fb7a-494f-b858-f21e5996790b" width=90%>
</div>

---

### Case 1 · Operator Introduction (alphanumeric_filter, EN) 

- **Type**: `operator_qa`
- **Language**: `en`

**Input (user query)**

> Introduce alphanumeric_filter

<details>
<summary><strong>Output (assistant answer)</strong></summary>

The `alphanumeric_filter` is a Data-Juicer operator designed to filter text samples based on the ratio of alphanumeric characters (or tokens) to the total number of characters (or tokens). It helps ensure data quality by retaining only those samples that fall within a specified alphanumeric ratio range.

### Key Features:
- **Character-based or Token-based**: Depending on the `tokenization` parameter, it can calculate the ratio either by counting characters or by using a Hugging Face tokenizer to count tokens.
- **Caching Metrics**: The computed metric — `'alpha_token_ratio'` (if tokenized) or `'alnum_ratio'` (if character-based) — is cached in the sample’s stats field for potential reuse.
- **Flexible Range Control**: You define `min_ratio` and `max_ratio` to specify the acceptable range of alphanumeric content.

### Parameters:
- `tokenization` (`bool`):  
  If `True`, uses tokenization via Hugging Face tokenizer; if `False`, counts characters directly.
- `min_ratio` (`float`):  
  Minimum acceptable alphanumeric ratio.
- `max_ratio` (`float`):  
  Maximum acceptable alphanumeric ratio.

### Example Usage in Config:
```yaml
process:
  - alphanumeric_filter:
      tokenization: False
      min_ratio: 0.3
      max_ratio: 0.9
```

This configuration keeps samples where 30% to 90% of characters are alphanumeric.

</details>

---

### Case 2 · Module Introduction (DJ-Agents, EN)

- **Type**: `submodule_qa`
- **Language**: `en`

**Input (user query)**

> Introduce DJ-Agents

<details>
<summary><strong>Output (assistant answer)</strong></summary>

Data-Juicer Agents (DJ-Agents) is an intelligent, agent-based framework designed to assist users in interactively creating and optimizing Data-Juicer recipes through natural language conversations. It leverages large language models (LLMs) via DashScope API to interpret user intent, recommend suitable operators, generate configuration code, and even support custom operator development.

### Key Features:

1. **Interactive Recipe Generation**  
   Users can describe their data processing goals in plain language (e.g., “I want to filter out non-English text”), and DJ-Agents will automatically suggest appropriate operators and generate a working recipe.

2. **Custom Operator Development Support**  
   If existing operators don’t meet your needs, DJ-Agents can guide you through creating new ones — including scaffolding code templates and updating configurations — especially when paired with a local Data-Juicer source installation.

3. **Flexible Running Modes**  
   - **Command Line Mode**: Default mode for quick interactions.
   - **AgentScope Studio Mode**: A visual, interactive web interface for richer debugging and step-by-step guidance (requires installing `@agentscope/studio` via npm).

4. **Environment Setup**  
   - Requires Python 3.10+.
   - Needs a valid DashScope API key (export as `DASHSCOPE_API_KEY`).
   - Optional: Set `DATA_JUICER_PATH` environment variable if developing custom operators.

5. **Installation**  
   Uses `uv` (a fast Python package installer) for streamlined setup:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   uv pip install -e .
   ```

For custom operator development, clone and install Data-Juicer in editable mode:
```bash
git clone https://github.com/datajuicer/data-juicer.git
pip install -e /path/to/data-juicer
```

---

**References:**

- [DJ-Agents Quick Start Guide](https://github.com/datajuicer/data-juicer-agents/blob/main/docs/QuickStart.md)

</details>

---

### Case 3 · Concept Question (Base Operator, EN)

- **Type**: `concept_qa`
- **Language**: `en`

**Input (user query)**

> Tell me about the base class of operators

<details>
<summary><strong>Output (assistant answer)</strong></summary>

The base class for operators in Data-Juicer is defined in the file `base_op.py`, located at `data_juicer/ops/base_op.py`. This class serves as the foundational structure from which all specific operators (such as filters, mappers, etc.) inherit. It provides common functionalities and interfaces required for consistent operator behavior across the Data-Juicer ecosystem.

Typical responsibilities of the base operator class include:
- Defining standard method signatures (e.g., `process`).
- Handling configuration and initialization parameters.
- Providing utilities for logging, statistics, or error handling.

For implementation details, you can explore the source code directly.

**References:**
- [Base Operator Source Code](https://github.com/datajuicer/data-juicer/blob/6fcef06620d210cb182cc076012612b725feeeaa/data_juicer/ops/base_op.py)

</details>

---

### Case 4 · Quick Start (Install DJ, EN)

- **Type**: `quick_start_qa`
- **Language**: `en`

**Input (user query)**

> How to install DJ?

<details>
<summary><strong>Output (assistant answer)</strong></summary>

To install Data-Juicer (DJ), follow these steps based on your needs:

---

## 🧩 **Prerequisites**
- Python version: `>= 3.10` and `<= 3.12`
- Git (if installing from source)
- **uv** (recommended package installer). Install it via:
  ```bash
  # Using curl
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Or using pip
  pip install uv
  ```

---

## 🚀 **Basic Installation**
Install the minimal version from PyPI (core data processing only):
```bash
uv pip install py-data-juicer
```

This includes:
- Data loading & manipulation
- File system operations
- Parallel processing
- Basic I/O utilities

---

## 🎯 **Scenario-Based Installation**

Install extra components based on your use case:

### Core ML/DL
```bash
uv pip install "py-data-juicer[generic]"
```

### Domain-Specific
```bash
# Computer Vision
uv pip install "py-data-juicer[vision]"

# Natural Language Processing
uv pip install "py-data-juicer[nlp]"

# Audio Processing
uv pip install "py-data-juicer[audio]"
```

### Additional Features
```bash
# Distributed Computing
uv pip install "py-data-juicer[distributed]"

# AI Services & APIs
uv pip install "py-data-juicer[ai_services]"

# Development Tools
uv pip install "py-data-juicer[dev]"
```

---

## 📦 **Common Installation Patterns**

### 1. Text Processing
```bash
uv pip install "py-data-juicer[generic,nlp]"
```

### 2. Vision Processing
```bash
uv pip install "py-data-juicer[generic,vision]"
```

### 3. Full Pipeline
```bash
uv pip install "py-data-juicer[generic,nlp,vision,distributed]"
```

### 4. Complete Installation
```bash
uv pip install "py-data-juicer[all]"
```

---

## 🛠️ **Install from Source**
For latest features or development:
```bash
git clone https://github.com/datajuicer/data-juicer.git
cd data-juicer
uv pip install -e .
# Optional: install specific extras
uv pip install -e ".[vision]"
```

> 💡 Use `-e` for editable mode.

---

## ⚙️ **OP-Based / Recipe-Based Installation**
For lightweight setups targeting specific operators or recipes:
```bash
# Install dependencies for a specific config file
python tools/dj_install.py --config path_to_your_config_file
# OR
dj-install --config path_to_your_config_file
```

> ✅ Only available when installing from source.

---

## 🐳 **Docker Installation**
Pull pre-built image:
```bash
docker pull datajuicer/data-juicer:<version_tag>
# e.g., docker pull datajuicer/data-juicer:v0.2.0
```

Or build from source:
```bash
docker build -t datajuicer/data-juicer:<version_tag> .
```

---

## 📌 **Notes & Troubleshooting**

✅ **Verify Installation**
```python
import data_juicer as dj
print(dj.__version__)
```

🎬 **For Video Operators**:  
Install **FFmpeg** and ensure it’s in your `$PATH`.  
- Debian/Ubuntu: `sudo apt install ffmpeg`  
- macOS: `brew install ffmpeg`  
- [Official FFmpeg Download](https://ffmpeg.org/download.html)

🆘 **Need Help?**  
- Check [documentation](https://github.com/datajuicer/data-juicer/tree/main/docs)  
- Open a [GitHub Issue](https://github.com/datajuicer/data-juicer/issues)  
- Join community discussions

---

### 🔗 References
- [Installation Guide](https://github.com/datajuicer/data-juicer/blob/main/docs/tutorial/Installation.md)

</details>

---

### Case 5 · Processing Guidance (Dirty Words Filter, EN)

- **Type**: `processing_qa`
- **Language**: `en`

**Input (user query)**

> I want to filter text data with dirty word, tell me how to do it

<details>
<summary><strong>Output (assistant answer)</strong></summary>

To filter text data containing dirty or flagged words, you should use the **`flagged_words_filter`** operator. This operator is specifically designed to calculate the ratio of flagged (e.g., offensive, dirty, or sensitive) words in a text sample and filters out samples that exceed a specified threshold.

---

### ✅ How to Use `flagged_words_filter`

This operator:
- Computes the ratio of flagged words in each text sample.
- Keeps only those samples where the flagged-word ratio falls within your defined range (e.g., `[0, 0.1]` to allow up to 10% flagged words).

#### Example Configuration in a Recipe (YAML):

```yaml
# config.yaml
process:
  - flagged_words_filter:
      lang: "en"
      tokenization: false
      lowercase: true
      flagged_ratio_min: 0
      flagged_ratio_max: 0.05  # Keep samples with <= 5% flagged words
```

#### Parameters:
- `lang`: Language of the text (default: `"en"`).
- `tokenization`: Whether to tokenize text before matching (default: `false`).
- `lowercase`: Convert text to lowercase for case-insensitive matching (default: `true`).
- `flagged_ratio_min/max`: Range of acceptable flagged word ratios.

---

### 📌 Notes:
- You can customize the list of flagged words by providing your own dictionary file via the `words_file` parameter.
- The default flagged word list covers common profanity and sensitive terms in multiple languages.

---

### 🔍 Next Step:
If you need details on how to provide a custom flagged word list or see code examples, I can retrieve the full operator documentation for you.

---

**References**:
- [Data-Juicer Operators Documentation](https://github.com/datajuicer/data-juicer/blob/main/docs/Operators.md)
- [FlaggedWordsFilter Source Code](https://github.com/datajuicer/data-juicer/blob/main/data_juicer/operators/filter/flagged_words_filter.py)
**References**:
- [Data-Juicer Operators Documentation](https://github.com/datajuicer/data-juicer/blob/main/docs/Operators.md)
- [FlaggedWordsFilter Source Code](https://github.com/datajuicer/data-juicer/blob/main/data_juicer/operators/filter/flagged_words_filter.py)
</details>

---

### Case 6 · Best Practices (Using DJ, EN)

- **Type**: `best_practice_qa`
- **Language**: `en`

**Input (user query)**

> Could you give me some best practices for using DJ?

<details>
<summary><strong>Output (assistant answer)</strong></summary>

Here are some best practices for using Data-Juicer (DJ) effectively:

---

## ✅ 1. **Start with Minimal Examples**
- Use the [Minimal Example Recipes](https://github.com/datajuicer/data-juicer-hub/tree/main/demo) to get familiar with DJ’s basic functionality.
- These recipes demonstrate core workflows and help you understand configuration structure.

---

## ✅ 2. **Leverage Pre-Built Recipes from DJ-Hub**
- Explore the [Recipe Gallery](https://github.com/datajuicer/data-juicer-hub/blob/main/docs/RecipeGallery.md) for real-world use cases:
  - Reproduce datasets like RedPajama or BLOOM.
  - Improve existing datasets (e.g., LLaVA, Alpaca-CoT).
  - Synthesize multimodal data (e.g., Img-Diff, HumanVBench).
- Each recipe includes:
  - Configuration files
  - Sample retention rates
  - Performance benchmarks
  - Download links (Aliyun, HuggingFace, ModelScope)

> 💡 Tip: Reuse and adapt these recipes instead of building from scratch.

---

## ✅ 3. **Install Only What You Need**
- Use modular installation to avoid bloat:
  ```bash
  # For text processing
  uv pip install "py-data-juicer[generic,nlp]"

  # For vision tasks
  uv pip install "py-data-juicer[generic,vision]"

  # For full pipeline
  uv pip install "py-data-juicer[generic,nlp,vision,distributed]"
  ```
- For video operators, ensure **FFmpeg** is installed and in your `$PATH`.

> 📌 Reference: [Installation Guide](https://github.com/datajuicer/data-juicer/blob/main/docs/tutorial/Installation.md)

---

## ✅ 4. **Choose the Right Operators**
- DJ provides over 180 operators categorized into 8 types:
  - `mapper`: Transform samples (e.g., clean text, augment images)
  - `filter`: Remove low-quality samples (e.g., by perplexity, image aesthetics)
  - `deduplicator`: Remove duplicates (text, image, video)
  - `aggregator`, `grouper`, `selector`, etc.

> 🔍 Use `search_operators()` or browse [Operators.md](https://github.com/datajuicer/data-juicer/blob/main/docs/Operators.md) to find the right operator for your task.

---

## ✅ 5. **Use 3-σ Rule for Hyperparameter Tuning**
- In many refined recipes (e.g., RedPajama), thresholds for filters are set using a **3-sigma statistical rule** — keep values within 3 standard deviations from the mean.
- This ensures you retain high-quality samples while removing outliers.

---

## ✅ 6. **Validate with Benchmarks**
- After processing, validate performance improvements:
  - For LLMs: Use downstream task accuracy (e.g., MM-Bench, VQAv2).
  - For video models: Use VBench scores.
- Example: Refined LLaVA pretraining data improved 10 out of 12 evaluation metrics.

---

## ✅ 7. **Automate Dependency Installation**
- If installing from source, use:
  ```bash
  python tools/dj_install.py --config your_config.yaml
  ```
  or
  ```bash
  dj-install --config your_config.yaml
  ```
  → Automatically installs only dependencies needed for your config.

---

## ✅ 8. **Use Docker for Reproducibility**
- Pull official images:
  ```bash
  docker pull datajuicer/data-juicer:<version_tag>
  ```
- Ensures consistent environments across machines.

---

## ✅ 9. **Contribute Back to the Community**
- Submit your own recipes to [data-juicer-hub](https://github.com/datajuicer/data-juicer-hub).
- Add new operators following the [Developer Guide](https://github.com/datajuicer/data-juicer/blob/main/docs/DeveloperGuide.md).

---

## ✅ 10. **Monitor Retention Rates & Quality Metrics**
- Track how many samples survive each filtering stage.
- Compare before/after model performance to quantify impact.
- Use selectors (`topk_specified_field_selector`, etc.) to curate final high-quality subsets.

---

By following these practices, you’ll maximize efficiency, reproducibility, and effectiveness when using Data-Juicer for your data processing pipelines.

---

### 📚 References:
- [Data-Juicer Minimal Example Recipes](https://github.com/datajuicer/data-juicer-hub/tree/main/demo)
- [Recipe Gallery](https://github.com/datajuicer/data-juicer-hub/blob/main/docs/RecipeGallery.md)
- [Installation Guide](https://github.com/datajuicer/data-juicer/blob/main/docs/tutorial/Installation.md)
- [Operators Documentation](https://github.com/datajuicer/data-juicer/blob/main/docs/Operators.md)

</details>

---

### Case 7 · Off-topic Question (Weather, EN)

- **Type**: `off_topic_qa`
- **Language**: `en`

**Input (user query)**

> How's the weather today?

<details>
<summary><strong>Output (assistant answer)</strong></summary>

Sorry, this question is unrelated to Data-Juicer.

</details>
