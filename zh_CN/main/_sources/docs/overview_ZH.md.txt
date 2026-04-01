# 架构概览

`data_juicer_agents` 当前围绕“可复用的数据处理能力”组织，而不是围绕单一 agent shell 组织。

目前最重要的内部层次有四层：

- 表面适配层
- capability 编排层
- Tools 层
- runtime adapter 层

## 用户入口

当前对外入口：

| 入口 | 角色 | 文件 |
| --- | --- | --- |
| `djx` | 工程师使用的 CLI | `data_juicer_agents/cli.py` |
| `dj-agents` | 会话式编排入口 | `data_juicer_agents/session_cli.py` |
| skills | 面向其他 agent 的打包能力 | 已可用 |

当前架构意图是：

- `djx` 继续作为显式、工程师导向的工作流入口
- `dj-agents` 通过 AgentScope 编排更底层的工具
- skills 未来应建立在稳定的 atomic tools 上，而不是建立在 shell 文本解析之上

## 当前分层模型

| 分层 | 主要目录 | 职责 |
| --- | --- | --- |
| 表面适配层 | `commands/`、`cli.py`、`session_cli.py`、`tui/` | 解析输入、展示输出、选择交互模式 |
| Capabilities | `capabilities/` | 定义 plan/apply/dev/session 等端到端用例 |
| Tools | `core/tool/`、`tools/` | 定义原子工具契约与分组工具集 |
| Runtime adapters / infra | `adapters/`、`utils/` | 将工具接入 AgentScope/session，并提供公共辅助 |

依赖方向：

```text
CLI / session / skills
    -> capabilities
    -> tools
    -> runtime adapters / backend implementations
```

最关键的规则是：

- 核心工具契约保持 runtime-agnostic
- runtime-specific 行为放在 adapter / binding 层，而不是塞进 tool spec

## 模块边界

理解这个包最有效的方式，是先把每一层的职责边界收紧。

- `commands/`、`cli.py`、`session_cli.py`、`tui/` 负责用户入口、参数解析和展示层
- `capabilities/` 负责 plan、apply、dev、session 这类端到端用例编排
- `core/tool/` 和 `tools/` 负责可复用的原子能力、共享工具契约和分组工具定义
- `adapters/` 和 `utils/` 负责 runtime 集成、框架绑定和非领域公共辅助

边界规则：

- 如果某个行为应被 `djx`、`dj-agents` 和 skills 共同复用，它应进入 tool 层
- 如果某个行为定义的是面向用户的工作流或多步编排，它应进入 capabilities 或 surface adapters
- 如果某个行为只是把核心系统接入特定 runtime，它应进入 adapters

## 透出口设计

同一个包通过不同表面暴露，是当前架构的刻意设计。

- `djx` 暴露显式、工程师导向的操作入口，保持稳定的命令边界
- `dj-agents` 在同一套 capability 和 tool 底座上提供自然语言会话式编排
- skills 未来也应复用同一套原子契约，而不是引入面向 shell 的特例包装

这意味着，架构目标不是让所有入口长得一样，而是让不同入口共享同一套内部能力栈，而不复制领域逻辑。

## 阅读指引

- 命令行为、参数和输出约定见 [CLI 参考](cli_ZH.md)
- 工具契约、分组工具结构和 runtime 绑定见 [Tools 架构](tools_ZH.md)
- 端到端使用方式见 [快速开始](quick_start_ZH.md)
