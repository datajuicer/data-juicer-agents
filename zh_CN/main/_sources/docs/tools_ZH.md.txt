# 工具与服务原子能力说明

本文档描述 DJX 当前的原子能力，以及 CLI / session 如何基于这些能力进行组合。

## 1) 原子工具层（`data_juicer_agents/tools`）

### `dataset_probe.py`

- 入口：`inspect_dataset_schema(dataset_path, sample_size=20)`
- 作用：
  - 轻量级数据采样
  - 模态识别（`text` / `image` / `multimodal` / `unknown`）
  - 候选文本 / 图像字段发现

### `llm_gateway.py`

- 入口：`call_model_json(...)`
- 作用：
  - 调用 OpenAI 兼容聊天接口
  - 强约束 JSON 响应
  - 通过 `DJA_MODEL_FALLBACKS` 支持模型兜底

### `op_manager/retrieval_service.py`

- 入口：`retrieve_operator_candidates(intent, top_k, mode, dataset_path)`
- 作用：
  - 基于 intent 检索候选 Data-Juicer 算子
  - 结合检索后端与词法兜底
  - 可选附带数据集画像提示

### `op_manager/operator_registry.py`

- 入口：
  - `get_available_operator_names()`
  - `resolve_operator_name(raw_name, available_ops)`
- 作用：
  - 读取本地已安装算子名
  - 归一化模型生成的算子名

### `planner/schema.py`

- 主要模型：
  - `PlanDraftSpec`
  - `PlanModel`
  - `OperatorStep`
- 作用：
  - 定义当前 draft spec 与最终 plan schema
  - 表达不包含 workflow/template 元数据的可执行 plan

### `planner/core.py`

- 入口：`PlannerCore.build_plan(...)`
- 作用：
  - 规范化 planner 输入上下文
  - 将 draft spec 收敛为确定性的最终 plan
  - 在校验前先做算子名归一化

### `planner/validation.py`

- 入口：
  - `validate_plan_schema(plan)`
  - `PlanValidator.validate(plan)`
- 作用：
  - 校验 schema 和模态约束
  - 校验数据路径、导出路径、自定义算子路径
  - 根据本地已安装的 Data-Juicer 元数据校验算子可用性

### `planner/tool_api.py`

- 入口：
  - `plan_build(...)`
  - `plan_build_from_json(...)`
  - `plan_validate(...)`
- 作用：
  - 向 session tools 暴露 planner core API
  - 将 JSON draft spec 桥接为最终 plan

### `apply_tool_api.py`

- 主要类型：
  - `ApplyUseCase`
  - `ApplyResult`
- 作用：
  - 在 `.djx/recipes/` 下物化 recipe YAML
  - 执行或 dry-run `dj-process`
  - 返回结构化执行摘要

### `dev_scaffold.py`

- 入口：
  - `generate_operator_scaffold(...)`
  - `run_smoke_check(scaffold)`
- 作用：
  - 生成自定义算子脚手架
  - 可选执行本地 smoke-check

### `session/*`

- 主要模块：
  - `context_tools.py`
  - `operator_tools.py`
  - `planner_tools.py`
  - `apply_tools.py`
  - `dev_tools.py`
  - `file_tools.py`
  - `process_tools.py`
  - `runtime.py`
  - `registry.py`
- 作用：
  - 将底层 API 适配为 ReAct session toolkit
  - 维护会话状态、事件上报以及文件 / 进程边界

## 2) 能力编排层（`data_juicer_agents/capabilities`）

### Plan capability

- 文件：
  - `capabilities/plan/generator.py`
  - `capabilities/plan/service.py`
- 组合内容：
  - 算子检索
  - 基于 LLM 的 plan draft 生成
  - 确定性 planner core 和 validation

### Apply capability

- 文件：`capabilities/apply/service.py`
- 组合内容：
  - 对 `tools/apply_tool_api.py` 的 CLI 封装

### Dev capability

- 文件：`capabilities/dev/service.py`
- 组合内容：
  - 脚手架生成
  - 可选 smoke-check

### Session capability

- 文件：`capabilities/session/orchestrator.py`
- 组合内容：
  - ReAct agent
  - session toolkit 注册
  - reasoning / tool 事件上报与中断处理

## 3) 会话层已暴露工具列表

当前注册到 ReAct 的工具：
- `get_session_context`
- `set_session_context`
- `inspect_dataset`
- `retrieve_operators`
- `plan_build`
- `plan_validate`
- `plan_save`
- `apply_recipe`
- `develop_operator`
- `view_text_file`
- `write_text_file`
- `insert_text_file`
- `execute_shell_command`
- `execute_python_code`

说明：
- 当前没有注册 `plan_generate`、`plan_retrieve_candidates`、`trace_run`
- `plan_build` 依赖会话 agent 将用户目标、数据探查结果和检索结果合成为 `draft_spec_json`
- `apply_recipe` 需要显式确认后才能执行

## 4) 命令到能力映射

- `djx plan` -> `PlanOrchestrator` -> `PlanDraftGenerator` + `PlannerCore` + `PlanValidator`
- `djx apply` -> `ApplyUseCase`
- `djx retrieve` -> retrieval service
- `djx dev` -> `DevUseCase`
- `dj-agents` -> `DJSessionAgent` + `tools/session/*`

## 5) 可观测与产物

会话 / 工具事件：
- `tool_start`
- `tool_end`
- `reasoning_step`

命令行输出分级：
- `--quiet` 摘要
- `--verbose` 展开执行输出
- `--debug` 结构化调试 payload

持久化产物：
- `.djx/recipes/`
- `.djx/session_plans/`
- 用户指定的 plan YAML 和导出路径

## 6) 设计边界

- tools 是原子能力
- capabilities 负责组合 tools 到 CLI 或 session 工作流
- plan 是基于 LLM draft spec 收敛得到的确定性产物
- `dev` 默认仍保持非侵入式
