# 定制化与扩展

## 自定义 Prompts

所有 Agent 的系统提示词都定义在 `prompts.py` 文件中。

## 更换模型

你可以在 `main.py` 中为不同 Agent 指定不同模型。例如：
- 主 Agent 使用 `qwen-max` 处理复杂推理
- 开发 Agent 使用 `qwen3-coder-480b-a35b-instruct` 优化代码生成质量

同时，Formatter 和 Memory 也可替换。这种设计让系统既能开箱即用，又能适配企业级需求。

## 扩展新智能体

DataJuicer Agents 是一个开放框架。核心在于 `agents2toolkit` 函数——它能将任意 Agent 自动包装为 Router 可调用的工具。

只需将你的 Agent 实例加入 `agents` 列表，Router 就会在运行时动态生成对应工具，并根据任务语义自动路由。

这意味着，你可以基于此框架，快速构建领域专属的数据智能体。

*扩展性，是我们设计的重要原则*。
