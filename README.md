# DataJuicer Agents

A multi-agent data processing system built on [AgentScope](https://github.com/agentscope-ai/agentscope) and [Data-Juicer (DJ)](https://github.com/datajuicer/data-juicer). This project demonstrates how to leverage the natural language understanding capabilities of large language models, enabling non-expert users to easily harness the powerful data processing capabilities of Data-Juicer.

## 🎯 Why DataJuicer Agents?

In the actual work of large model R&D and applications, **data processing remains a high-cost, low-efficiency, and hard-to-reproduce process**. Many teams spend more time on data analysis, cleaning and synthesis than on model training, requirement alignment and app development.

We hope to liberate developers from tedious script assembly through agent technology, making data R&D closer to a "think and get" experience.

**Data directly defines the upper limit of model capabilities**. What truly determines model performance are multiple dimensions such as **quality, diversity, harmfulness control, and task matching** of data. Optimizing data is essentially optimizing the model itself. To do this efficiently, we need a systematic toolset.

DataJuicer Agents is designed to support the new paradigm of **data-model co-optimization** as an intelligent collaboration system.

## 📋 Table of Contents

- [DataJuicer Agents](#datajuicer-agents)
  - [🎯 Why DataJuicer Agents?](#-why-datajuicer-agents)
  - [📋 Table of Contents](#-table-of-contents)
  - [What Does This Agent Do?](#what-does-this-agent-do)
  - [Architecture](#architecture)
    - [Multi-Agent Routing Architecture](#multi-agent-routing-architecture)
    - [Two Integration Modes](#two-integration-modes)
  - [Roadmap](#roadmap)
    - [Data-Juicer Q\&A Agent (Demo Available)](#data-juicer-qa-agent-demo-available)
    - [Interactive Data Analysis and Visualization Agent (In Development)](#interactive-data-analysis-and-visualization-agent-in-development)
    - [Other Directions](#other-directions)
    - [Common Issues](#common-issues)
    - [Optimization Recommendations](#optimization-recommendations)
  - [Related Resources](#related-resources)

## What Does This Agent Do?

Data-Juicer (DJ) is an **open-source processing system covering the full lifecycle of large model data**, providing four core capabilities:

- **Full-Stack Operator Library (DJ-OP)**: Nearly 200 high-performance, reusable multimodal operators covering text, images, and audio/video
- **High-Performance Engine (DJ-Core)**: Built on Ray, supporting TB-level data, 10K-core distributed computing, with operator fusion and multi-granularity fault tolerance
- **Collaborative Development Platform (DJ-Sandbox)**: Introduces A/B Test and Scaling Law concepts, using small-scale experiments to drive large-scale optimization
- **Natural Language Interaction Layer (DJ-Agents)**: Enables developers to build data pipelines through conversational interfaces using Agent technology

DataJuicer Agents is not a simple Q&A bot, but an **intelligent collaborator for data processing**. Specifically, it can:

- **Intelligent Query**: Automatically match the most suitable operators based on natural language descriptions (precisely locating from nearly 200 operators)
- **Automated Pipeline**: Describe data processing needs, automatically generate Data-Juicer YAML configurations and execute them
- **Custom Extension**: Help users develop custom operators and seamlessly integrate them into local environments

**Our goal: Let developers focus on "what to do" rather than "how to do it"**.

## Architecture

### Multi-Agent Routing Architecture

DataJuicer Agents adopts a **multi-agent routing architecture**, which is key to system scalability. When a user inputs a natural language request, the **Router Agent** first performs task triage to determine whether it's a standard data processing task or a custom requirement that needs new capabilities.

```
User Query  
  ↓  
Router Agent (Filtering & Decision) ← query_dj_operators (operator retrieval)  
  │  
  ├─ High-match operator found  
  │  ↓  
  │  DJ Agent (Standard Data Processing Task)  
  |  ├── Preview data samples (confirm field names and data formats)  
  │  ├── get_ops_signature (retrieve full parameter signatures)  
  │  ├── Generate YAML configuration  
  │  └── execute_safe_command (run dj-process, dj-analyze)  
  │  
  └─ No high-match operator found  
     ↓  
     Dev Agent (Custom Operator Development & Integration)  
     ├── get_basic_files (retrieve base classes and registration mechanism)  
     ├── get_operator_example (retrieve similar operator examples)  
     └── Generate compliant operator code  
     └── Local integration (register to user-specified path)
```

### Two Integration Modes

Agent integration with DataJuicer has two modes to adapt to different usage scenarios:

- **Tool Binding Mode**: Agent calls DataJuicer command-line tools (such as `dj-analyze`, `dj-process`), compatible with existing user habits, low migration cost
- **MCP Binding Mode**: Agent directly calls DataJuicer's MCP (Model Context Protocol) interface, no need to generate intermediate YAML files, directly run operators or data recipes, better performance

These two modes are automatically selected by the Agent based on task complexity and performance requirements, ensuring both flexibility and efficiency.

## Roadmap

The Data-Juicer agent ecosystem is rapidly expanding. Here are the new agents currently in development or planned:

### Data-Juicer Q&A Agent (Demo Available)

Provides users with detailed answers about Data-Juicer operators, concepts, and best practices.

<video controls width="100%" height="auto" playsinline>
    <source src="https://github.com/user-attachments/assets/a8392691-81cf-4a25-94da-967dcf92c685" type="video/mp4">
    Your browser does not support the video tag.
</video>

The Q&A agent can currently be viewed and tried out [here](https://github.com/datajuicer/data-juicer-agents/blob/main/interactive_recipe/qa-copilot).

### Interactive Data Analysis and Visualization Agent (In Development)

We are building a more advanced **human-machine collaborative data optimization workflow** that introduces human feedback:
- Users can view statistics, attribution analysis, and visualization results
- Dynamically edit recipes, approve or reject suggestions
- Underpinned by `dj.analyzer` (data analysis), `dj.attributor` (effect attribution), and `dj.sandbox` (experiment management)
- Supports closed-loop optimization based on validation tasks

This interactive recipe can currently be viewed and tried out [here](https://github.com/datajuicer/data-juicer-agents/blob/main/interactive_recipe/README.md).

### Other Directions

- **Data Processing Agent Benchmarking**: Quantify the performance of different Agents in terms of accuracy, efficiency, and robustness
- **Data "Health Check Report" & Data Intelligent Recommendation**: Automatically diagnose data problems and recommend optimization solutions
- **Router Agent Enhancement**: More seamless, e.g., when operators are lacking → Code Development Agent → Data Processing Agent
- **MCP Further Optimization**: Embedded LLM, users can directly use MCP connected to their local environment (e.g., IDE) to get an experience similar to current data processing agents
- **Knowledge Base and RAG-oriented Data Agents**
- **Better Automatic Processing Solution Generation**: Less token usage, more efficient, higher quality processing results
- **Data Workflow Template Reuse and Automatic Tuning**: Based on DataJuicer community data recipes
- ......

### Common Issues

**Q: How to get DashScope API key?**
A: Visit [DashScope official website](https://dashscope.aliyun.com/) to register an account and apply for an API key.

**Q: Why does operator retrieval fail?**
A: Please check network connection and API key configuration, or try switching to vector retrieval mode.

**Q: How to debug custom operators?**
A: Ensure Data-Juicer path is configured correctly and check the example code provided by the code development agent.

**Q: What to do if MCP service connection fails?**
A: Check if the MCP server is running and confirm the URL address in the configuration file is correct.

**Q: Error: requests.exceptions.HTTPError: 400 Client Error: Bad Request for url: http://localhost:3000/trpc/pushMessage**
A: Agents handle data via file references (paths) rather than direct uploads. Please confirm whether any non-text files were submitted.

### Optimization Recommendations

- For large-scale data processing, it is recommended to use DataJuicer's distributed mode
- Set batch size appropriately to balance memory usage and processing speed
- For more advanced data processing features (synthesis, Data-Model Co-Development), please refer to DataJuicer [documentation](https://datajuicer.github.io/data-juicer/en/main/index.html)

---

## Related Resources

- DataJuicer has been used by a large number of Tongyi and Alibaba Cloud internal and external users, and has facilitated many research works. All code is continuously maintained and enhanced.

*Welcome to visit GitHub, Star, Fork, submit Issues, and join the community!*

- **Project Repositories**:
  - [AgentScope](https://github.com/agentscope-ai/agentscope)
  - [DataJuicer](https://github.com/datajuicer/data-juicer)

**Contributing**: Welcome to submit Issues and Pull Requests to improve AgentScope, DataJuicer Agents, and DataJuicer. If you encounter problems during use or have feature suggestions, please feel free to contact us.