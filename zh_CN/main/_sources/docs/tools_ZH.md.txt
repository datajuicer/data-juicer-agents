# Tools 架构说明

本文档描述当前 `data_juicer_agents` 的工具层架构。

## 1. 设计目标

工具层是 `data_juicer_agents` 内部稳定的原子能力定义层。

它服务三类消费方：

- CLI / 命令入口
- 基于 AgentScope 的 `dj-agents` 会话入口
- skills

核心规则是：

- 工具定义本身保持 runtime-agnostic，且输入 / 输出必须显式
- 上层不能依赖隐藏的 session 默认值或工具内部 fallback
- runtime adapter 只处理传输和 schema 展示，不改变工具语义

## 2. 核心工具抽象

核心抽象位于：

- `data_juicer_agents/core/tool/contracts.py`
- `data_juicer_agents/core/tool/registry.py`
- `data_juicer_agents/core/tool/catalog.py`

定义内容包括：

- `ToolSpec`
- `ToolContext`
- `ToolResult`
- `ToolRegistry`

职责：

- 定义工具是什么
- 定义显式输入 / 输出 schema
- 注册内置工具规格
- 避免直接依赖 AgentScope、TUI、session state 或 CLI 渲染层

## 3. 工具组划分

`data_juicer_agents/tools/` 按工具组组织。

每个组通过 `registry.py` 暴露 `TOOL_SPECS`。

具体工具通常放在各自的子目录下，并按如下结构组织：

- `input.py`：输入模型
- `logic.py`：可复用实现
- `tool.py`：`ToolSpec` 绑定

包级 `__init__.py` 负责导出稳定 API；部分工具组还会在 `_shared/` 或同级模块中放置共享模型与校验逻辑。

### `tools/context`

- 文件：
  - `context/registry.py`
  - `context/inspect_dataset/{input.py,logic.py,tool.py}`
  - `context/list_system_config/{input.py,logic.py,tool.py}`
  - `context/list_dataset_fields/{input.py,logic.py,tool.py}`
  - `context/list_dataset_formatters/{input.py,logic.py,tool.py}`
  - `context/list_dataset_load_strategies/{input.py,logic.py,tool.py}`
- 主要职责：
  - 数据集探查
  - system / dataset 配置发现
  - 数据集字段、formatter、load strategy 枚举

### `tools/retrieve`

- 文件：
  - `retrieve/registry.py`
  - `retrieve/_shared/logic.py`
  - `retrieve/_shared/operator_registry.py`
  - `retrieve/_shared/backend/`（子包）：
    - `backend.py`：共享检索入口（`retrieve_ops_with_meta`、`retrieve_ops`、`get_op_catalog` 等）
    - `cache.py`：`RetrievalCacheManager`，管理向量索引、工具信息和目录缓存
    - `catalog.py`：算子目录构建器（采集 `class_name`、`class_desc`、`class_type`、`class_tags`）
    - `result_builder.py`：共享检索结果整形辅助和 `trace_step`
    - `retriever.py`：`RetrieverBackend` 抽象基类及具体后端（`LLMRetriever`、`VectorRetriever`、`BM25Retriever`、`RegexRetriever`）
  - `retrieve/retrieve_operators/{input.py,logic.py,tool.py}`
  - `retrieve/retrieve_operators_api/{input.py,logic.py,tool.py}`
  - `retrieve/get_operator_info/{input.py,logic.py,tool.py}`
  - `retrieve/list_operator_catalog/{input.py,logic.py,tool.py}`
- 主要职责：
  - 主包的算子检索入口
  - 区分本地检索面和 API 检索面
  - 共享多后端检索逻辑与目录缓存
  - 算子类型和标签过滤
  - 算子名称归一化
  - 已安装算子查询
  - 算子详情查询与全量目录枚举

工具拆分：

- `retrieve_operators`：本地检索面（`auto|bm25|regex`）
- `retrieve_operators_api`：API 检索面（`auto|llm|vector`）
- `get_operator_info`：解析单个算子并返回 schema / 详情
- `list_operator_catalog`：按需列出当前算子目录

### `tools/plan`

- 文件：
  - `plan/registry.py`
  - `plan/<tool_name>/{input.py,logic.py,tool.py}`
  - `plan/_shared/*.py`
- 主要职责：
  - 分阶段的 dataset/process/system spec 与最终 plan 模型
  - 确定性 planner core
  - plan 校验
  - 显式的 plan 组装与持久化辅助

### `tools/apply`

- 文件：
  - `apply/registry.py`
  - `apply/apply_recipe/{input.py,logic.py,tool.py}`
- 主要职责：
  - recipe 物化
  - plan 执行
  - 结构化执行结果

### `tools/dev`

- 文件：
  - `dev/registry.py`
  - `dev/develop_operator/{input.py,logic.py,tool.py,scaffold.py}`
- 主要职责：
  - 自定义算子脚手架生成
  - 可选 smoke-check

### `tools/files`

- 文件：
  - `files/registry.py`
  - `files/{view_text_file,write_text_file,insert_text_file}/...`
- 主要职责：
  - 文本文件读 / 写 / 插入

### `tools/process`

- 文件：
  - `process/registry.py`
  - `process/{execute_shell_command,execute_python_code}/...`
- 主要职责：
  - shell 执行
  - Python 代码片段执行

## 4. Runtime Adapter 层

runtime 相关适配不再放在工具组内部。

### AgentScope adapter

- `data_juicer_agents/adapters/agentscope/tools.py`
- `data_juicer_agents/adapters/agentscope/schema_utils.py`

职责：

- 将 `ToolSpec` 转成 AgentScope 所需 callable / schema
- 统一规范 JSON schema，保持 agent 调用浅层且显式
- 将 `ToolResult` 转成 AgentScope 响应
- 统一处理参数预览截断

### Session runtime / toolkit

- `data_juicer_agents/capabilities/session/toolkit.py`
- `data_juicer_agents/capabilities/session/runtime.py`

职责：

- 创建 session runtime
- 发射工具生命周期事件，供 TUI / CLI 观察
- 选择哪些已注册工具暴露给 `DJSessionAgent`
- 让 session memory 保持为观察性状态，而不是工具语义的一部分

## 5. 默认 Registry 与 Session Toolkit

内置工具注册通过：

- `data_juicer_agents/core/tool/catalog.py`

该 catalog 会扫描 `data_juicer_agents/tools/` 下的工具组，并加载每组的 `TOOL_SPECS`。当前所有内置工具组都通过 `registry.py` 暴露这些定义，然后交给：

- `build_default_tool_registry()`

session toolkit 当前直接使用默认 registry，并按功能组优先级排序工具。它不再依赖写在 `ToolSpec` 里的 `session` tag。

## 6. 当前 Session 工具集合

默认 registry 当前向 session runtime 暴露这些工具：

- `list_dataset_fields`
- `list_dataset_formatters`
- `list_dataset_load_strategies`
- `list_system_config`
- `inspect_dataset`
- `get_operator_info`
- `list_operator_catalog`
- `retrieve_operators`
- `retrieve_operators_api`
- `build_dataset_spec`
- `build_process_spec`
- `build_system_spec`
- `validate_dataset_spec`
- `validate_process_spec`
- `validate_system_spec`
- `assemble_plan`
- `plan_validate`
- `plan_save`
- `apply_recipe`
- `develop_operator`
- `view_text_file`
- `write_text_file`
- `insert_text_file`
- `execute_shell_command`
- `execute_python_code`

这些工具保持通用语义。session 编排必须基于上一步工具输出，显式传入下一步所需参数。

## 7. 边界总结

- `core/tool/*` 定义工具抽象、发现与 registry
- `tools/<group>/*` 只定义原子工具
- `adapters/agentscope/*` 负责 AgentScope 传输 / schema 适配
- `capabilities/session/*` 以会话方式编排工具，但不改变工具语义

未来无论是 atomic CLI 还是 skills，都应建立在这套内部结构之上。
