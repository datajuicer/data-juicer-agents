<div align="center">
<img src="docs/imgs/dj_agents_logo.png" width=70%>
<br/>

# Data-Juicer Agents: Towards Agentic Data Processing

A Suite of Agents for **Agentic Data Processing**. Built on [Data-Juicer (DJ)](https://github.com/datajuicer/data-juicer) and [AgentScope](https://github.com/agentscope-ai/agentscope).

[简体中文](./README_ZH.md) | [English](./README.md)

🏗️ [Overview Doc](./docs/overview.md) • ⚡️ [Quick Start Doc](./docs/quick_start.md) • >_ [CLI Doc](./docs/cli.md) • 🔧 [Tools Doc](./docs/tools.md) • 🎯 [Roadmap](#roadmap)
</div>

## News

- 🚀 [2026-03-11] **Major refactor and upgrade of `data_juicer_agents` completed.**
  - The project architecture and CLI/session capabilities were comprehensively redesigned for better maintainability and extensibility.
  - 🏗️ [Overview](./docs/overview.md) | ⚡️ [Quick Start](./docs/quick_start.md) | >_ [CLI Doc](./docs/cli.md) | 🔧 [Tools](./docs/tools.md) | 🎯 [Roadmap](#roadmap)
  - Try processing data by chatting with the agent!

  <div align="center">
    <video src="https://github.com/user-attachments/assets/1ef8359f-78b9-45f4-9fa6-49836f7b9539" width="100%" controls loop></video>
  </div>

- 🚀[2026-01-15] [Q&A Copilot](./qa-copilot/README.md) has been deployed on the official [Doc Site](https://datajuicer.github.io/data-juicer/en/main/index.html) | [DingTalk](https://qr.dingtalk.com/action/joingroup?code=v1,k1,N78tgW54U447gJP5aMC95B6qgQhlkVQS4+dp7qQq6MpuRVJIwrSsXmL8oFqU5ajJ&_dt_no_comment=1&origin=11?) | [Discord](https://discord.gg/ngQbB9hEVK) of [Data-Juicer](https://github.com/datajuicer/data-juicer). Feel free to ask ***Juicer*** anything related to the Data-Juicer ecosystem!
  - 📃 [Deploy-ready codes](./qa-copilot/) | 🎬 [More demos](./qa-copilot/DEMO.md) | 🎯 [Roadmap](#roadmap).


<div align="center">
<img src="https://github.com/user-attachments/assets/d10a95a8-fb7a-494f-b858-f21e5996790b" width=90%>
</div>

## Roadmap

The long-term vision of **DJ-Agents** is to enable a **development-free data processing lifecycle**, allowing developers to focus on **what to do** rather than **how to do it**.

To achieve this vision, we are tackling two fundamental challenges:

- **Agents**: How to design and build powerful agents specialized in data processing
- **Services & Tools**: How to package these agents into ready-to-use, out-of-the-box products

We continuously iterate on both directions, and the roadmap may evolve accordingly as our understanding and capabilities improve.

---

### Agents

- [ ] ~~**Data-Juicer Data Processing Agent (DJ Process Agent)** & **Data-Juicer Code Development Agent (DJ Dev Agent)**~~
- [ ] We have stopped building scenario-specific data processing agents, and instead are building data processing `tools` for general-purpose agents. From there:
  - [x] Hard-orchestrate these tools into `capabilities`, exposed as the `djx` CLI
  - [ ] Soft-orchestrate them through prompts, packaged as `skills`
  - [x] Rely on agent self-orchestration to support conversational data processing

### Services & Tools

- [x] **Q&A Copilot**: a Q&A assistant for the Data-Juicer ecosystem
  - *[2026-01-15]*: already deployed on the official [Doc Site](https://datajuicer.github.io/data-juicer/en/main/index.html) of [Data-Juicer](https://github.com/datajuicer/data-juicer) | [DingTalk](https://qr.dingtalk.com/action/joingroup?code=v1,k1,N78tgW54U447gJP5aMC95B6qgQhlkVQS4+dp7qQq6MpuRVJIwrSsXmL8oFqU5ajJ&_dt_no_comment=1&origin=11?) | [Discord](https://discord.gg/ngQbB9hEVK)
- [ ] **InteRecipe**: interactive data recipe construction through natural language
  - *[2026-03-11]*: the current `./interactive_recipe` only shows workflow-based examples. The `dj-agents` CLI entry is already built and supports interactive data-recipe construction through natural language in the TUI. We are developing a frontend tool (`studio`) on top of this foundation as the next upgrade.

---

### Priority Items

- **DJ Skills**: use prompt-based soft orchestration to package `tools` into `skills` for general-purpose agents.
- **InteRecipe Studio**: support interactive data recipe construction through natural language, with multi-dimensional data and result views.
- **Plan Tool**: extend support for fuller Data-Juicer capability coverage, DJ Hub recipe matching, and more.
- **Dev Tool**: stabilization testing and optimization

### Long-term Directions

- **Continue building tools and skills for broader data-processing scenarios**, enabling wider and more flexible applications.
  - **RAG**
  - **Embodied Intelligence**
  - **Data Lakehouse architectures**

## Common Issues

**Q: How to get DashScope API key?**
A: Visit [DashScope official website](https://dashscope.aliyun.com/) to register an account and apply for an API key.

## Related Resources

- Data-Juicer has been used by a large number of Tongyi and Alibaba Cloud internal and external users, and has facilitated many research works. All code is continuously maintained and enhanced.

*Welcome to visit GitHub, Star, Fork, submit Issues, and join the community!*

- **Project Repositories**:
  - [Data-Juicer](https://github.com/datajuicer/data-juicer)
  - [AgentScope](https://github.com/agentscope-ai/agentscope)

**Contributing**: Welcome to submit Issues and Pull Requests to improve Data-Juicer Agents, Data-Juicer, and AgentScope. If you encounter problems during use or have feature suggestions, please feel free to contact us.
