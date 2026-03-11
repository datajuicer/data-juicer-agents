# 架构概览

`data_juicer_agents` 的核心思路是：先把数据处理能力沉淀为可复用的 Python 模块，再通过不同的用户入口把同一套能力透出出去。

这个包不是一个单体“大而全 Agent 产品”。它的主要架构单元是可复用的数据处理原语，而不是聊天壳子本身。

## 包的定位

当前对外暴露的主要入口有三类：

| 入口 | 角色 | 主入口文件 |
| --- | --- | --- |
| `djx` | 确定性 CLI，用于规划、检索、执行和脚手架生成 | `data_juicer_agents/cli.py` |
| `dj-agents` | 基于同一能力底座的会话式 ReAct 编排入口 | `data_juicer_agents/session_cli.py` |
| `skills`（未来） | 供外部通用智能体复用的 prompt 打包能力 | 当前尚未实现 |

设计目标是：

- `djx` 负责显式、文件导向、可复现的工作流
- `dj-agents` 负责在同一套原语之上的交互式编排
- 未来 `skills` 负责把这些原语以更轻量的方式暴露给其他智能体运行时

## 分层模型

理解这个包，最有效的方式是按四层看：

| 分层 | 目录 | 职责 | 常见依赖 |
| --- | --- | --- | --- |
| 表面适配层 | `commands/`、`cli.py`、`session_cli.py`、`tui/` | 解析用户输入、选择 UI、打印输出、在 shell/session 与结构化 payload 之间做转换 | capabilities、tools、utils |
| 用例编排层 | `capabilities/` | 定义“一个完整用户故事”应该如何组织，例如 plan 或 session | tools、utils |
| 领域原语层 | `tools/` | 存放 planner core、检索、执行、脚手架生成、session tool 适配和模型网关 | 外部运行时、utils |
| 基础设施层 | `utils/` | 日志、终端输入、小型公共辅助函数 | 标准库和外部库 |

如果用依赖方向来表达，大致是：

```text
djx CLI / dj-agents 会话 / future skills
        -> commands 或 session entrypoints
        -> capabilities
        -> tools
        -> 外部运行时（Data-Juicer CLI、LLM API、AgentScope）
```

这里最关键的规则是依赖方向：

- `commands` 可以依赖 `capabilities` 和部分 `tools`
- `capabilities` 可以依赖 `tools`
- `tools` 不应反向依赖 `commands`、`cli.py` 或 `tui/`
- 未来 `skills` 应依赖 `capabilities` 或 `tools`，而不是反过来通过 shell 调 `djx`

## 表面适配层

### `djx` CLI

`data_juicer_agents/cli.py` 定义了当前的确定性命令行入口：

- `djx plan`
- `djx apply`
- `djx retrieve`
- `djx dev`

`commands/` 的定位是“薄适配层”。它只负责参数校验、输出格式化、退出码处理，然后把请求交给 capability 或 tool API。

当前命令映射如下：

| 命令 | 主模块 | 下游依赖 |
| --- | --- | --- |
| `plan` | `commands/plan_cmd.py` | `capabilities.plan.PlanOrchestrator` |
| `apply` | `commands/apply_cmd.py` | `capabilities.apply.ApplyUseCase` + `tools.planner.PlanValidator` |
| `retrieve` | `commands/retrieve_cmd.py` | `tools.op_manager.retrieval_service` |
| `dev` | `commands/dev_cmd.py` | `capabilities.dev.DevUseCase` |

这层最重要的边界是：CLI 不是领域逻辑增长的地方，它只是适配层。

### `dj-agents` 会话入口

`data_juicer_agents/session_cli.py` 是会话式入口的表面适配层，负责：

- 启动参数解析
- plain / TUI 两种会话模式切换
- Ctrl+C / Ctrl+D 的终端行为
- 把每一轮消息交给 `DJSessionAgent`

`tui/` 也属于表面适配层，而不是领域层。它的职责是渲染 session capability 发出的事件流，不应该拥有 plan 或 apply 的业务逻辑。

### `skills`（未来）

未来的 `skills` 入口，应该把当前可复用的能力打包给外部智能体。理想的接入边界是：

- 结构化的 `tools/*`
- 部分稳定的 `capabilities/*`

不应该依赖的内容包括：

- CLI 参数解析
- 面向 shell 的输出文本
- TUI 渲染逻辑
- 通过解析 `djx` stdout 来恢复结构化状态

## Capabilities

`capabilities/` 是用例编排层。它回答的问题是：“我们准备把哪一种完整工作流暴露给用户？”

### `capabilities.plan`

这是当前最有实质内容的 capability。

`capabilities/plan/service.py` 里的 `PlanOrchestrator` 负责把下面几部分接起来：

1. `tools.op_manager.retrieval_service.retrieve_operator_candidates`
2. `PlanDraftGenerator`
3. `tools.llm_gateway.call_model_json`
4. `tools.planner.PlannerCore`
5. `tools.planner.PlanValidator`

它本身不拥有 planner 的语义定义；它的职责是编排固定链路：

`先检索证据 -> 再生成 draft spec -> 再收敛为确定性 plan -> 最后校验`

### `capabilities.session`

`capabilities/session/orchestrator.py` 里的 `DJSessionAgent` 是会话式编排的核心边界。

它负责：

- 初始化 session state
- 构建 AgentScope 的 `ReActAgent`
- 通过 `build_session_toolkit` 注册工具
- 中断控制
- 事件发射，供 plain/TUI 渲染
- 会话级 system prompt 与 turn protocol

这里有一个很重要的架构点：会话层不是去调用 CLI 命令，而是直接调用可复用的 Python 工具和 session runtime。

### `capabilities.apply` 与 `capabilities.dev`

这两个 capability 当前都比较薄，主要是 CLI-facing 的兼容包装：

- `capabilities.apply` 直接 re-export `tools.apply_tool_api.ApplyUseCase`
- `capabilities.dev` 直接 re-export `tools.dev_tool_api.DevUseCase`

也就是说，当前 apply/dev 这两条主链路的架构重心其实还在 `tools/`，而不在 `capabilities/` 里新增复杂编排。

## Tools

`tools/` 是当前包里最重要的可复用核心层，也是最值得被未来 `skills` 直接消费的边界。

### `tools.planner`

这是 CLI 和 session 共用的确定性 planner core。

主要由几部分组成：

- `schema.py`：`PlanDraftSpec`、`PlanContext`、`PlanModel`、`OperatorStep`
- `core.py`：`PlannerCore`
- `validation.py`：`PlanValidator`
- `tool_api.py`：供 session tools 使用的 JSON 友好 API

从架构上看，这一层才是 plan 语义的中心；其他模块只是给它提供输入，或消费它的输出。

### `tools.op_manager`

这一层负责算子发现与归一化：

- `retrieval_service.py`：给 CLI 和 session 返回结构化检索结果
- `operator_registry.py`：本地已安装算子查询、规范名归一化
- `op_retrieval.py`：底层向量/LLM 检索实现与 fallback 逻辑

它的契约是：“给定 intent 和可选的数据集信息，返回 grounded 的候选算子”。它不应该知道 CLI 怎么打印，也不应该知道 session 怎么渲染。

### `tools.llm_gateway`

这是包里尽量收口的 LLM 边界，负责：

- OpenAI-compatible 调用
- API key / base URL 解析
- JSON 提取
- 模型 fallback

plan 链路通过 `PlanDraftGenerator` 调它，而不是把模型调用散落到命令层和会话层。

### `tools.apply_tool_api`

这一层负责确定性执行：

- 把 `PlanModel` 转成 Data-Juicer recipe YAML
- 调起 `dj-process`
- 对失败做分类
- 返回结构化的 `ApplyResult`

它的职责更接近运行时，而不是展示层。

### `tools.dev_tool_api`

这一层负责自定义算子脚手架生成和可选的 smoke check，封装：

- 必填参数检查
- scaffold 生成
- smoke check 结果序列化

### `tools.session`

这一层是会话出口和底层原语之间的桥接层。

它包括：

- `runtime.py`：可变 `SessionState`、事件发射、plan 存取辅助
- `registry.py`：session tool 注册
- `context_tools.py`：会话上下文与数据集探查
- `operator_tools.py`：检索工具
- `planner_tools.py`：draft plan 的 build / validate / save
- `apply_tools.py`：会话内 apply
- `dev_tools.py`：会话内开发新算子
- file/process tools：诊断和编辑辅助

这里最重要的架构价值是：`dj-agents` 并不是包一层 `djx` 壳，而是通过 agent-tool 接口直接重新暴露底层原语。

## 边界与依赖说明

这个包里最关键的架构边界有四个：

### 1. Commands 是展示适配层

它们应该负责：

- argparse 契约
- 终端输出
- 退出码
- human/debug 展示格式

不应该成为 plan、retrieve、apply 语义扩张的主战场。

### 2. Capabilities 定义用例

它们回答的是：

- 这个用户故事应该按什么固定链路执行
- 哪些状态需要在一轮会话中延续
- 执行前需要什么确认策略

但它们不应该吸收 UI 细节。

### 3. Tools 定义可复用契约

它们返回的应该是结构化 payload，供下游多种入口复用：

- CLI commands
- session tools
- 未来 skills
- 测试

所以像 `PlanModel`、retrieval payload、`ApplyResult` 这样的结构化对象，比终端输出文本更重要。

### 4. Session 不是对 shell 命令的包装

`dj-agents` 的主链路是：

`session_cli -> DJSessionAgent -> SessionToolRuntime + session toolkit -> tools/*`

这种设计让会话式编排保持：

- 结构化
- 可中断
- 可观测（事件流）

而不是把 shell stdout 再反向解析成状态。

## 关键调用链

### `djx plan`

```text
cli.py
-> commands/plan_cmd.py
-> capabilities.plan.PlanOrchestrator
-> op_manager.retrieval_service
-> capabilities.plan.PlanDraftGenerator
-> tools.llm_gateway
-> tools.planner.PlannerCore
-> tools.planner.PlanValidator
-> 落盘 plan YAML
```

### `djx apply`

```text
cli.py
-> commands/apply_cmd.py
-> tools.planner.PlanValidator
-> ApplyUseCase
-> 在 .djx/recipes/ 下生成 recipe
-> 调起 dj-process
```

### `dj-agents`

```text
session_cli.py
-> DJSessionAgent
-> build_session_toolkit
-> AgentScope ReActAgent
-> session tool functions
-> tools.planner / tools.op_manager / ApplyUseCase / DevUseCase / file/process helpers
```

## 运行时状态与产物

当前几个关键的磁盘产物：

- `.djx/recipes/`：执行前生成的 recipe
- `.djx/session_plans/`：会话工具保存的 plan
- `djx plan` 输出的 plan YAML
- 用户指定的导出数据路径

会话侧几个关键内存状态在 `SessionState` 里：

- 当前 dataset/export 路径
- 当前 plan 路径
- 当前 draft plan
- 上一次 retrieval payload
- 上一次 inspect dataset 的结果

正是这些状态，支持一次会话从 inspect 到 retrieve，再到 build / validate / save / apply 的逐步推进。

## 设计意图

这个包未来希望稳定在下面这组分工上：

- `tools`：稳定的 machine-facing 原语
- `capabilities`：围绕这些原语形成可复用的编排模式
- `djx`：确定性的操作者入口
- `dj-agents`：会话式编排入口
- 未来 `skills`：面向外部智能体的轻量封装
