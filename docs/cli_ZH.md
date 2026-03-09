# DJX CLI 参考

## 命令总览

| 命令 | 作用 | 源码 |
|---|---|---|
| `djx plan` | 生成/修订计划 YAML（LLM 驱动） | `data_juicer_agents/commands/plan_cmd.py` |
| `djx apply` | 校验并通过 `dj-process` 执行计划 | `data_juicer_agents/commands/apply_cmd.py` |
| `djx trace` | 查询 run 详情/列表/统计 | `data_juicer_agents/commands/trace_cmd.py` |
| `djx templates` | 列出/查看内置模板 | `data_juicer_agents/commands/templates_cmd.py` |
| `djx retrieve` | 基于 intent 检索候选算子 | `data_juicer_agents/commands/retrieve_cmd.py` |
| `djx dev` | 生成非侵入式自定义算子脚手架 | `data_juicer_agents/commands/dev_cmd.py` |
| `djx evaluate` | 批量评测案例 | `data_juicer_agents/commands/evaluate_cmd.py` |

其他入口：
- `dj-agents`：`data_juicer_agents/session_cli.py`

## 全局输出级别（`djx`）

所有 `djx` 子命令支持：
- `--quiet`（默认）：摘要输出
- `--verbose`：展开执行输出
- `--debug`：输出结构化原始调用细节

示例：

```bash
djx apply --plan ./plan.yaml --yes --quiet
djx apply --plan ./plan.yaml --yes --verbose
djx --debug plan "deduplicate" --dataset ./data.jsonl --export ./out.jsonl
```

## `djx plan`

```bash
djx plan "<intent>" --dataset <input.jsonl> --export <output.jsonl> [options]
```

关键参数：
- `--output`：计划输出路径（默认 `plans/<plan_id>.yaml`）
- `--base-plan`：基于已有计划修订
- `--from-run-id`：以历史 run 作为修订上下文（需配合 `--base-plan`）
- `--custom-operator-paths`：校验/执行时可加载的自定义算子路径
- `--from-template`：强制模板（`rag_cleaning` / `multimodal_dedup`）
- `--template-retrieve`：先 intent->template 匹配，再兜底 full-LLM
- `--llm-review` / `--no-llm-review`：控制生成后的语义 review

冲突规则：
- `--base-plan` 与 `--from-template`、`--template-retrieve` 互斥。
- 若同时给出 `--from-template` 与 `--template-retrieve`，后者会被忽略。

规划阶段顺序：
1. base-plan 修订（若提供 `--base-plan`）
2. 显式模板（若提供 `--from-template`）
3. 模板检索（若启用 `--template-retrieve`）
4. full-LLM 生成兜底

说明：
- planning 始终会使用 LLM（template+LLM 修订或 full-LLM）。
- 最终失败返回结构化错误信息（`error_type/error_code/stage/next_actions`）。

## `djx apply`

```bash
djx apply --plan <plan.yaml> [--yes] [--dry-run] [--timeout 300]
```

行为：
- 执行前校验计划
- 调用 `dj-process`
- 成功 run 落盘到 `.djx/runs.jsonl`
- 输出 `Run ID` 和 trace 指令提示

## `djx trace`

```bash
djx trace <run_id>
djx trace --plan-id <plan_id> [--limit 20]
djx trace --stats [--plan-id <plan_id>]
```

用途：
- 查看单次 run
- 查看同一 `plan_id` 的历史 run
- 查看成功率与错误聚合统计

## `djx templates`

```bash
djx templates
djx templates rag_cleaning
```

## `djx retrieve`

```bash
djx retrieve "<intent>" [--dataset <path>] [--top-k 10] [--mode auto|llm|vector] [--json]
```

返回：
- 候选算子排序
- 可选数据集画像（传入 dataset 时）
- 检索来源与备注

## `djx dev`

```bash
djx dev "<intent>" \
  --operator-name <snake_case_name> \
  --output-dir <dir> \
  [--type mapper|filter] \
  [--from-retrieve <json>] \
  [--smoke-check]
```

输出：
- 算子代码脚手架
- 测试脚手架
- 总结文档
- 可选 smoke-check 结果

默认是非侵入式流程（生成代码与说明，不自动安装）。

## `djx evaluate`

```bash
djx evaluate --cases <cases.jsonl> [options]
```

关键参数：
- `--execute none|dry-run|run`
- `--planning-mode template-llm|full-llm`
- `--retries`、`--jobs`、`--timeout`
- `--output`、`--errors-output`、`--history-file`、`--no-history`

兼容参数：
- `--llm-full-plan` 是 `--planning-mode full-llm` 的废弃别名。

## `dj-agents`

```bash
dj-agents [--dataset <path>] [--export <path>] [--verbose] [--ui plain|tui]
```

行为：
- 自然语言会话
- 内部 ReAct 原子工具编排
- 必须有 LLM 访问配置（缺少 key/model 会启动失败）

中断方式：
- plain 模式：按 `Ctrl+C` 中断当前轮，按 `Ctrl+D` 退出
- tui 模式：按 `Ctrl+C` 中断当前轮，按 `Ctrl+D` 退出

## 未来范围

- `DJX Studio`（API + Web UI）已调整为后续版本发布。
