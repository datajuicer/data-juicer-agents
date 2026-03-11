# DJX 架构概览

`data-juicer-agents` 将 DJX 定位为一组面向 Data-Juicer 工作流的可组合能力。

主要入口：
- `djx`：确定性 CLI，目前提供 `plan`、`apply`、`retrieve`、`dev`
- `dj-agents`：基于同一能力底座的自然语言 ReAct 会话入口

## 项目定位

DJX 是能力层，不是一个“大一统超级 Agent”。

核心目标：
- 稳定的命令与工具边界
- 结构化输入输出
- 执行前的确定性 plan 收敛
- 便于被上层 Agent 和 skill 复用

## 核心流程

### 1) CLI 规划与执行

1. `djx retrieve` 可选地探查数据集模态，并返回候选算子排序。
2. `djx plan` 内部先做算子检索，再让模型生成 draft spec，最后通过确定性 planner core 收敛成 plan。
3. `PlanValidator` 检查 schema、文件路径、自定义算子路径和本地已安装算子可用性。
4. plan 以 YAML 落盘。
5. `djx apply` 再次校验 plan，在 `.djx/recipes/` 下写出 recipe，并执行 `dj-process` 或 dry-run。

### 2) 会话式编排

`dj-agents` 使用一个 ReAct agent 调用已注册的 session tools。

典型 planning 链路：

`inspect_dataset -> retrieve_operators -> plan_build -> plan_validate -> plan_save`

`apply_recipe` 在执行前必须拿到显式确认。

### 3) 运行产物

- `.djx/recipes/`：执行时生成的 recipe
- `.djx/session_plans/`：会话工具保存的 plan
- 用户通过 `--output` 指定的 plan YAML
- 用户指定的导出数据路径

## 范围说明

- 本文档当前覆盖的用户入口是 `djx` 与 `dj-agents`。
- 旧版 `trace`、`templates`、`evaluate` 命令流不属于当前 CLI。
- `interactive_recipe/` 与 `qa-copilot/` 仍是独立子系统。
