# DataJuicer 智能体

基于 [AgentScope](https://github.com/agentscope-ai/agentscope) 和 [Data-Juicer (DJ)](https://github.com/datajuicer/data-juicer) 构建的数据处理多智能体系统。该项目展示了如何利用大模型的自然语言理解能力，让非专家用户也能轻松使用 Data-Juicer 的强大数据处理能力。

## 🎯 为什么需要 DataJuicer Agents？

在大模型研发和应用的实际工作中，**数据处理仍然是一个高成本、低效率、难复现的环节**。很多团队花在数据分析、清洗、合成等阶段的时间，往往超过模型训练、需求对齐、应用功能开发。

我们希望通过智能体技术，把开发者从繁琐的脚本拼凑中解放出来，让数据研发更接近"所想即所得"的体验。

**数据直接定义了模型能力的上限**。真正决定模型表现的，是数据的**质量、多样性、有害性控制、任务匹配度**等多个维度。优化数据，本质上就是在优化模型本身。而要高效地做这件事，我们需要一套系统化的工具。

DataJuicer Agents 正是为支撑**数据与模型协同优化**这一新范式而设计的智能协作系统。

## 📋 目录

- [DataJuicer 智能体](#datajuicer-智能体)
  - [🎯 为什么需要 DataJuicer Agents？](#-为什么需要-datajuicer-agents)
  - [📋 目录](#-目录)
  - [这个智能体做了什么？](#这个智能体做了什么)
  - [架构](#架构)
    - [多智能体路由架构](#多智能体路由架构)
    - [两种集成方式](#两种集成方式)
  - [Roadmap](#roadmap)
    - [Data-Juicer 问答智能体 (演示可用)](#data-juicer-问答智能体-演示可用)
    - [交互式数据分析与可视化智能体 (开发中)](#交互式数据分析与可视化智能体-开发中)
    - [其它方向](#其它方向)
    - [常见问题](#常见问题)
    - [优化建议](#优化建议)
  - [相关资源](#相关资源)

## 这个智能体做了什么？

Data-Juicer (DJ) 是一个**覆盖大模型数据全生命周期的开源处理系统**，提供四个核心能力：

- **全栈算子库（DJ-OP）**：近 200 个高性能、可复用的多模态算子，覆盖文本、图像、音视频
- **高性能引擎（DJ-Core）**：基于 Ray 构建，支持 TB 级数据、万核分布式计算，具备算子融合与多粒度容错
- **协同开发平台（DJ-Sandbox）**：引入 A/B Test 与 Scaling Law 思想，用小规模实验驱动大规模优化
- **自然语言交互层（DJ-Agents）**：通过 Agent 技术，让开发者用对话方式构建数据流水线

DataJuicer Agents 不是一个简单的问答机器人，而是一个**数据处理的智能协作者**。具体来说，它能：

- **智能查询**：根据自然语言描述，自动匹配最合适的算子（从近200个算子中精准定位）
- **自动化流程**：描述数据处理需求，自动生成 Data-Juicer YAML 配置并执行
- **自定义扩展**：帮助用户开发自定义算子，无缝集成到本地环境

**我们的目标是：让开发者专注于"做什么"，而不是"怎么做"**。

## 架构

### 多智能体路由架构

DataJuicer Agents 采用**多智能体路由架构**，当用户输入一个自然语言请求，首先由 **Router Agent** 进行任务分诊，判断这是标准的数据处理任务，还是需要开发新能力的定制需求。

```
用户查询
  ↓
Router Agent (筛选&决策) ← query_dj_operators （算子检索）
  │
  ├─ 找到高匹配算子
  │  ↓
  │  DJ Agent (标准数据处理任务)
  |  ├── 预览数据样本（确认字段名和数据格式）
  │  ├── get_ops_signature（获取完整参数签名）
  │  ├── 生成 YAML 配置
  │  └── execute_safe_command (执行 dj-process, dj-analyze)
  │
  └─ 未找到高匹配算子
     ↓
     Dev Agent (自定义算子开发集成)
     ├── get_basic_files (获取基类和注册机制)
     ├── get_operator_example (获取相似算子示例)
     └── 生成符合规范的算子代码
     └── 本地集成（注册到用户指定路径）
```

### 两种集成方式

Agent 与 DataJuicer 的集成有两种方式，以适应不同使用场景：

- **绑定工具模式**：Agent 调用 DataJuicer 的命令行工具（如 `dj-analyze`、`dj-process`），兼容现有用户习惯，迁移成本低
- **绑定 MCP 模式**：Agent 直接调用 DataJuicer 的 MCP（Model Context Protocol）接口，无需生成中间 YAML 文件，直接运行算子或数据菜谱，性能更优

这两种方式由 Agent 根据任务复杂度和性能需求自动选择，确保灵活性与效率兼得。

## Roadmap

Data-Juicer 智能体生态系统正在快速扩展，以下是当前正在开发或计划中的新智能体：

### Data-Juicer 问答智能体 (演示可用)

为用户提供关于 Data-Juicer 算子、概念和最佳实践的详细解答。

<video controls width="100%" height="auto" playsinline>
    <source src="https://github.com/user-attachments/assets/a8392691-81cf-4a25-94da-967dcf92c685" type="video/mp4">
    您的浏览器不支持视频标签。
</video>

问答智能体目前可在[此处](https://github.com/datajuicer/data-juicer-agents/blob/main/qa-copilot)查看并试用。

### 交互式数据分析与可视化智能体 (开发中)

我们正在构建更高级的**人机协同数据优化工作流**，引入人类反馈：
- 用户可查看统计、归因分析以及可视化结果
- 动态编辑菜谱，批准或拒绝建议
- 底层由 `dj.analyzer`（数据分析）、`dj.attributor`（效果归因）、`dj.sandbox`（实验管理）共同支撑
- 支持基于验证任务的闭环优化

该交互式菜谱目前可在[此处](https://github.com/datajuicer/data-juicer-agents/blob/main/interactive_recipe/README_ZH.md)查看并试用。

### 其它方向

- **数据处理智能体 Benchmarking**：量化不同 Agent 在准确性、效率、鲁棒性上的表现
- **数据"体检报告" & 数据智能推荐**：自动诊断数据问题并推荐优化方案
- **Router Agent 增强**：更无感丝滑，譬如当缺乏算子时→代码开发Agent→数据处理agent
- **MCP 进一步优化**：内嵌 LLM，用户可直接使用 MCP 链接自己本地环境如IDE，获得目前数据处理 agent 类似的体验
- **面向知识库、RAG 的数据智能体**
- **更好的处理方案自动生成**：更少 token 用量，更高效，更优质处理结果
- **数据工作流模版复用及自动调优**：基于 DataJuicer 社区数据菜谱
- ......

### 常见问题

**Q: 如何获取 DashScope API 密钥？**
A: 访问 [DashScope 官网](https://dashscope.aliyun.com/) 注册账号并申请 API 密钥。

**Q: 为什么算子检索失败？**
A: 请检查网络连接和 API 密钥配置，或尝试切换到向量检索模式。

**Q: 如何调试自定义算子？**
A: 确保 Data-Juicer 路径配置正确，并查看代码开发智能体提供的示例代码。

**Q: MCP 服务连接失败怎么办？**
A: 检查 MCP 服务器是否正在运行，确认配置文件中的 URL 地址正确。

**Q: 报错requests.exceptions.HTTPError: 400 Client Error: Bad Request for url: http://localhost:3000/trpc/pushMessage**
A: 请检查是否在agentscope studio中上传了非文本信息（例如数据文件），agent通过文件路径等进行数据处理，暂不接受直接上传文件。

### 优化建议

- 对于大规模数据处理，建议使用DataJuicer提供的分布式模式
- 合理设置批处理大小以平衡内存使用和处理速度
- 更多进阶数据处理（合成、Data-Model Co-Development）等特性能力请参考DataJuicer[文档页](https://datajuicer.github.io/data-juicer/zh_CN/main/index_ZH)

---

## 相关资源
- DataJuicer 已经被用于大量通义和阿里云内外部用户，背后也衍生了多项研究。所有代码持续维护增强中。

*欢迎访问 GitHub，Star、Fork、提 Issue，以及加入社区共建！*
- **项目地址**：
  - [AgentScope](https://github.com/agentscope-ai/agentscope)
  - [DataJuicer](https://github.com/datajuicer/data-juicer)

**贡献指南**：欢迎提交 Issue 和 Pull Request 来改进 agentscope、DataJuicer Agents 及 DataJuicer。如果您在使用过程中遇到问题或有功能建议，请随时联系我们。
