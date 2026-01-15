<div align="center">
<img src="docs/imgs/dj_agents_logo.png" width=60%>
<br/>
<br/>

# Data-Juicer Agents: Towards Agentic Data Processing

A Suite of Agents for **Agentic Data Processing**. Built on [Data-Juicer (DJ)](https://github.com/datajuicer/data-juicer) and [AgentScope](https://github.com/agentscope-ai/agentscope).

[简体中文](./README_ZH.md) | [English](./README.md)

[Overview](#overview) • [Quick Start](#quick-start) • [Documentation](https://datajuicer.github.io/data-juicer-agents/en/main/)
</div>

## News

🚀[2026-01-15] [Q&A Copilot](./qa-copilot/README.md) ***Juicer*** has been deployed on the official [documentation site](https://datajuicer.github.io/data-juicer/en/main/index.html) of Data-Juicer! Feel free to ask ***Juicer*** anything related to Data-Juicer ecosystem. Check [📃 Deploy-ready codes](./qa-copilot/) | 🎬[ More demos](./qa-copilot/DEMO.md) | 🎯 [Dev Roadmap](#roadmap).

<div align="center">
<video controls width="70%" height="auto" playsinline>
    <source src="https://cloud.video.taobao.com/vod/ZyuHZ2x-yhLIfzpO9nFWBaG0ymqppfbikFGwwBQImaM.mp4" type="video/mp4">
    Your browser does not support the video tag.
</video>
</div>

## Overview
This repo maintains a suite of agents that enable users to interact with Data-Juicer's powerful data processing capabilities through natural language.

- In Data-Juicer ecosystem, Data-Juicer Agents (DJ-Agents) play a key role in the interface layer, bridging users with the powerful Data-Juicer infrastructure and toolkit for building data-centric applications. 
- Unlike traditional API- or CLI-based interaction, DJ-Agents leverage agent-based interaction, tool use, and extensibility to enable non-expert users to access Data-Juicer’s data-processing capabilities through intuitive natural-language interactions.
- The long-term goal of DJ-Agents is to enable a **development-free data processing lifecycle**, allowing developers to focus on **what to do** rather than **how to do it**.

The Data-Juicer Agents family currently contains the following members:

- Data-Juicer Q&A Agent (DJ Q&A Agent)
- Data-Juicer Data Processing Agent (DJ Process Agent) [Beta version]
- Data-Juicer Code Development Agent (DJ Dev Agent) [Beta version]

Data-Juicer Agents adopts a **multi-agent routing architecture** for routing requests to the corresponding agent. Check [agent info](./docs/AgentIntro.md) for more details.

<p align="center">
  <img src="docs/imgs/dj_agents_workflow.png" width=70%>
</p>


## Quick Start

### Online Services

- [Q&A Copilot](./qa-copilot/README.md) ***Juicer*** has been deployed on the official [doc page](https://datajuicer.github.io/data-juicer/en/main/index.html) of Data-Juicer! Feel free to ask ***Juicer*** anything related to Data-Juicer ecosystem.

We are planning to release more online agentic services, check our [Roadmap](#roadmap).

### Local Deployment

Follow the [document](https://datajuicer.github.io/data-juicer-agents/en/main/docs/QuickStart.html) to locally launch DJ-Agents. 

If you encounter any issues, check [common issues](#common-issues) or ask our Q&A copilot ***Juicer*** at the doc page.

## Roadmap

The long-term vision of **DJ-Agents** is to enable a **development-free data processing lifecycle**, allowing developers to focus on **what to do** rather than **how to do it**.

To achieve this vision, we are tackling two fundamental challenges:

- **Agent Level**: How to design and build powerful agents specialized in data processing  
- **Service Level**: How to package these agents into ready-to-use, out-of-the-box products  

We continuously iterate on both directions, and the roadmap may evolve accordingly as our understanding and capabilities improve.

Below is the current development checklist.

---

### Agents

- **Data-Juicer Q&A Agent (DJ Q&A Agent)**  
  Answers Data-Juicer–related questions from both existing and potential users.  
  - [x] Implemented  
  - *[2026-01-15]*: The current [DJ Q&A Agent](./qa-copilot/) demonstrates strong performance in our internal evaluations and is considered production-ready.

- **Data-Juicer Data Processing Agent (DJ Process Agent)**  
  Automatically invokes Data-Juicer tools to fulfill data processing requests.  
  - [ ] In progress  
  - *[2026-01-15]*: The current [DJ Process Agent](./data_juicer_agents/) is in beta. We are actively benchmarking and optimizing its capabilities.

- **Data-Juicer Code Development Agent (DJ Dev Agent)**  
  Automatically develops new data processing operators based on user requirements.  
  - [ ] In progress  
  - *[2026-01-15]*: The current [DJ Dev Agent](./data_juicer_agents/) is in beta. Capability evaluation and optimization are ongoing.

---

### Services

- **Q&A Copilot — *Juicer***  
  - [ ] Overall service  
  - *[2026-01-15]*: ***Juicer*** is currently available on the [documentation site](https://datajuicer.github.io/data-juicer-agents/en/main/). We are working on deployments for community platforms.
    - [x] Documentation Website  
    - [ ] DingTalk Group  
    - [ ] Discord Server  

- **Interactive Data Analysis Studio** *(In Development)*  
  - *[2026-01-15]*: A [demo](./interactive_recipe/) is available. The current version primarily relies on predefined workflows. We are working on integrating agent-based intelligence.

- **MCP Service**  
  - [ ] Planned

---

### Future Directions

- **Workflows as Skills**  
  [Data-Juicer Hub](https://github.com/datajuicer/data-juicer-hub) hosts a growing collection of data processing recipes and workflows contributed by the Data-Juicer community.

  As data processing demands expand into new scenarios—such as **RAG**, **Embodied Intelligence**, and **Data Lakehouse architectures**—we plan to incorporate existing and newly developed workflows into DJ-Agents as reusable *skills*, enabling broader and more flexible data processing applications.

## Common Issues

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
- For more advanced data processing features (synthesis, Data-Model Co-Development), please refer to Data-Juicer [documentation](https://datajuicer.github.io/data-juicer/en/main/index.html)

---

## Related Resources

- DataJuicer has been used by a large number of Tongyi and Alibaba Cloud internal and external users, and has facilitated many research works. All code is continuously maintained and enhanced.

*Welcome to visit GitHub, Star, Fork, submit Issues, and join the community!*

- **Project Repositories**:
  - [Data-Juicer](https://github.com/datajuicer/data-juicer)
  - [AgentScope](https://github.com/agentscope-ai/agentscope)

**Contributing**: Welcome to submit Issues and Pull Requests to improve Data-Juicer Agents, Data-Juicer, and AgentScope. If you encounter problems during use or have feature suggestions, please feel free to contact us.
