<div align="center">
<img src="docs/imgs/dj_agents_logo.png" width=70%>
<br/>

# Data-Juicer Agents：迈向智能体驱动的数据处理

基于 [Data-Juicer (DJ)](https://github.com/datajuicer/data-juicer) 和 [AgentScope](https://github.com/agentscope-ai/agentscope) 构建的 **智能体数据处理** 套件。

[简体中文](./README_ZH.md) | [English](./README.md)

🏗️ [架构文档](./docs/overview_ZH.md) • ⚡️ [快速开始](./docs/quick_start_ZH.md) • >_ [CLI 文档](./docs/cli_ZH.md) • 🔧 [工具文档](./docs/tools_ZH.md) • 🎯 [路线图](#路线图)
</div>

## 最新动态

- 🚀 [2026-03-11] **`data_juicer_agents` 已完成一次大规模重构与升级。**
  - 我们对项目架构、CLI/会话能力进行了系统性重设计，以提升可维护性与可扩展性。
  - 🏗️ [架构文档](./docs/overview_ZH.md) | ⚡️ [快速开始](./docs/quick_start_ZH.md) | >_ [CLI 文档](./docs/cli_ZH.md) | 🔧 [工具文档](./docs/tools_ZH.md) | 🎯 [路线图](#路线图)
  - 试试通过和agent对话来处理数据！

  <div align="center">
    <video src="https://github.com/user-attachments/assets/1ef8359f-78b9-45f4-9fa6-49836f7b9539" width="100%" controls loop></video>
  </div>


- 🚀[2026-01-15] [Q&A Copilot](./qa-copilot/README_ZH.md) 已部署在 [Data-Juicer](https://github.com/datajuicer/data-juicer) 的官方 [文档网站](https://datajuicer.github.io/data-juicer/zh/main/index.html) | [钉钉群聊](https://qr.dingtalk.com/action/joingroup?code=v1,k1,N78tgW54U447gJP5aMC95B6qgQhlkVQS4+dp7qQq6MpuRVJIwrSsXmL8oFqU5ajJ&_dt_no_comment=1&origin=11?) | [Discord频道](https://discord.gg/ngQbB9hEVK) 上。欢迎向 ***Juicer*** 提出任何与 Data-Juicer 生态相关的问题！
  - 📃 [一键部署代码](./qa-copilot/) | 🎬 [更多演示](./qa-copilot/DEMO_ZH.md) | 🎯 [路线图](#路线图)。

<div align="center">
<img src="https://github.com/user-attachments/assets/a0099ce2-4ed3-4fab-8cfa-b0bbd3beeac9" width=90%>
</div>

## 路线图

**DJ-Agents** 的长期愿景是实现一个**零开发的数据处理生命周期**，让开发者能够把精力集中在 **“做什么”** 而不是 **“怎么做”** 上。

为实现这一愿景，我们正在解决两个核心问题：

- **智能体**：如何设计并构建在数据处理方面足够强大的智能体  
- **服务&工具**：如何把这些智能体打包成即开即用、开箱即用的产品  

我们会在这两个方向上持续迭代，路线图也会随着理解的加深与能力的提升而不断演进。

---

### 智能体

- [ ] ~~**Data-Juicer 数据处理智能体（DJ Process Agent** & **Data-Juicer 代码开发智能体（DJ Dev Agent）**~~
- [ ] 我们放弃了针对场景开发数据处理智能体，转而为通用智能体开发数据处理`工具 (tools)`，随后
  - [x] 通过工作流硬编排这些工具为`能力 (capabilities)`，透出为`djx命令行工具 (CLI)`
  - [ ] 通过prompt软编排，打包为`技能 (skills)`
  - [x] 依赖agent的自动编排，支持`会话式数据处理`

---

### 服务&工具

- [x] **Q&A Copilot**: 围绕Data-Juicer生态系统的问答助手
  - *[2026-01-15]*：已部署在 [Data-Juicer](https://github.com/datajuicer/data-juicer) 的官方 [文档网站](https://datajuicer.github.io/data-juicer/zh/main/index.html) | [钉钉群聊](https://qr.dingtalk.com/action/joingroup?code=v1,k1,N78tgW54U447gJP5aMC95B6qgQhlkVQS4+dp7qQq6MpuRVJIwrSsXmL8oFqU5ajJ&_dt_no_comment=1&origin=11?) | [Discord频道](https://discord.gg/ngQbB9hEVK)。
- [ ] **InteRecipe**：通过自然语言交互式的数据菜谱构建
  - *[2026-03-11]*: 当前`./interecipe`下仅展示基于工作流的样例。目前dj-agents CLI入口已构建完成，支持在TUI中通过自然语言交互式构建数据菜谱，我们正在开发以此为基础构建更多功能的前端工具(studio)作为升级。


---

### 优先开发项

- **DJ Skills**: 通过prompt软编排，将`工具 (tools)`打包为`技能 (skills)`透出，供通用智能体使用。
- **InteRecipe Studio**: 支持自然语言交互式的数据菜谱构建，提供多维度展示数据信息以及处理结果。
- **Plan工具**：功能扩展以支持完整的Data-Juicer能力/基于DJ Hub中的recipe匹配模式/...
- **Dev工具**：稳定性测试和优化

### 长期方向

- **持续构建工具/技能以支持更多场景的数据处理需求**，从而支持更广泛、更灵活的数据处理应用。
  - **RAG**
  - **具身智能（Embodied Intelligence）**
  - **数据湖仓（Data Lakehouse）架构**

## 常见问题

**问：如何获取 DashScope 的 API key？**  
答：请访问 [DashScope 官网](https://dashscope.aliyun.com/) 注册账户并申请 API key。

## 相关资源

- Data-Juicer 已在大量通义及阿里云内外部用户场景中落地实践，并支撑了多项研究工作；所有代码都在持续维护与增强中。

*欢迎访问 GitHub，Star、Fork、提交 Issue，并加入社区交流！*

- **项目仓库**：
  - [Data-Juicer](https://github.com/datajuicer/data-juicer)
  - [AgentScope](https://github.com/agentscope-ai/agentscope)

**贡献方式**：欢迎通过 Issue 和 Pull Request 来改进 Data-Juicer Agents、Data-Juicer 以及 AgentScope。如果你在使用中遇到问题或有新功能建议，欢迎随时与我们联系。
