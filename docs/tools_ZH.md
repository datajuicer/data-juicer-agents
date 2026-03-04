# DJX 工具与服务原子能力说明

本文档描述 DJX 的底层原子能力，以及它们如何被 capability/command/session 组合使用。

## 1) 原子工具层（`data_juicer_agents/tools`）

### `dataset_probe.py`

- 入口：`inspect_dataset_schema(dataset_path, sample_size=20)`
- 作用：
  - 数据采样结构概览
  - 模态识别（`text` / `image` / `multimodal` / `unknown`）
  - 候选文本/图像字段与统计信息

### `llm_gateway.py`

- 入口：`call_model_json(...)`
- 作用：
  - 调用 OpenAI 兼容聊天接口
  - 强约束 JSON 输出
  - 支持通过 `DJA_MODEL_FALLBACKS` 配置模型兜底链

### `op_manager/retrieval_service.py`

- 入口：`retrieve_operator_candidates(intent, top_k, mode, dataset_path)`
- 作用：
  - intent 到算子候选的检索
  - `auto|llm|vector` 后端选择与词法兜底
  - 可选数据集上下文增强

### `op_manager/operator_registry.py`

- 入口：
  - `get_available_operator_names()`
  - `resolve_operator_name(raw_name, available_ops)`
- 作用：
  - 算子名归一化
  - 算子可用性检查

### `router_helpers.py`

- 入口：
  - `retrieve_workflow(user_intent)`
  - `select_workflow(user_intent)`
  - `explain_routing(user_intent)`
- 作用：
  - 模板规划路径下的 workflow 路由选择

### `dev_scaffold.py`

- 入口：
  - `generate_operator_scaffold(...)`
  - `run_smoke_check(scaffold)`
- 作用：
  - 生成自定义 Data-Juicer 算子脚手架
  - 可选本地非侵入 smoke 校验

### 检索内部模块（索引/元数据）

- `op_manager/op_retrieval.py`
- `op_manager/create_dj_func_info.py`

作用：
- 检索索引/缓存与算子元信息准备

## 2) 能力编排层（`data_juicer_agents/capabilities`）

### Plan capability

- 文件：`capabilities/plan/service.py`
- 组合内容：
  - workflow 路由
  - 候选算子检索
  - 算子名规范化
  - LLM patch/full 生成

### Apply capability

- 文件：`capabilities/apply/service.py`
- 组合内容：
  - recipe 物化
  - `dj-process` 执行
  - 超时与取消行为

### Dev capability

- 文件：`capabilities/dev/service.py`
- 组合内容：
  - 脚手架生成
  - 可选 smoke 检查

### Trace capability

- 文件：`capabilities/trace/repository.py`
- 组合内容：
  - trace 落盘、查询、统计

### Session capability

- 文件：`capabilities/session/orchestrator.py`
- 组合内容：
  - ReAct agent
  - 工具暴露
  - 事件上报与中断处理

## 3) 会话层已暴露工具列表

当前注册到 ReAct 的工具：
- `get_session_context`
- `set_session_context`
- `inspect_dataset`
- `retrieve_operators`
- `plan_retrieve_candidates`
- `plan_generate`
- `plan_validate`
- `plan_save`
- `apply_recipe`
- `trace_run`
- `develop_operator`
- `view_text_file`
- `write_text_file`
- `insert_text_file`
- `execute_shell_command`
- `execute_python_code`

说明：
- 代码中仍有 `tool_plan(...)` 兼容方法，但当前并未注册进 ReAct toolkit。
- 会话 planning prompt 已约束：在 `plan_generate` 前优先利用 inspect/retrieve 信息。

## 4) 命令到能力映射

- `djx plan` -> `PlanUseCase` + `PlanValidator`
- `djx apply` -> `ApplyUseCase`
- `djx trace` -> `TraceStore`
- `djx retrieve` -> retrieval service
- `djx dev` -> `DevUseCase`
- `djx evaluate` -> `PlanUseCase` + `ApplyUseCase` 批量编排

## 5) 可观测与错误面

会话/工具事件：
- `tool_start`
- `tool_end`
- `reasoning_step`
- `interrupt_requested` / `interrupt_ack` / `interrupt_ignored`（runtime 事件）

命令行输出分级：
- `--quiet` 摘要
- `--verbose` 扩展日志
- `--debug` 原始结构化 payload

持久化 trace：
- `.djx/runs.jsonl`（可通过 `djx trace` 查询）

## 6) 设计边界

- tools 是原子能力。
- capabilities 负责组合 tools 成场景流程。
- commands 与 session 是同一能力底座上的两种交互入口。
- `dev` 默认保持非侵入式（生成代码与说明，不自动安装）。
