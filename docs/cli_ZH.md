# DJX CLI 参考

## 命令总览

| 命令 | 作用 | 源码 |
|---|---|---|
| `djx plan` | 基于 intent、检索证据、分阶段 spec 和 LLM 生成的 operator list 生成 plan YAML | `data_juicer_agents/commands/plan_cmd.py` |
| `djx apply` | 校验已保存的 plan，并执行或 dry-run `dj-process` | `data_juicer_agents/commands/apply_cmd.py` |
| `djx retrieve` | 基于 intent 检索候选算子 | `data_juicer_agents/commands/retrieve_cmd.py` |
| `djx dev` | 生成非侵入式自定义算子脚手架 | `data_juicer_agents/commands/dev_cmd.py` |

其他入口：
- `dj-agents`：`data_juicer_agents/session_cli.py`

当前 CLI 不包含 `trace`、`templates`、`evaluate`。

## 全局输出级别（`djx`）

所有 `djx` 子命令支持：
- `--quiet`（默认）：摘要输出
- `--verbose`：展开执行输出
- `--debug`：输出更完整的结构化调试 payload

示例：

```bash
djx plan "文本去重" --dataset ./data.jsonl --export ./out.jsonl --quiet
djx plan "文本去重" --dataset ./data.jsonl --export ./out.jsonl --verbose
djx --debug retrieve "文本去重" --dataset ./data.jsonl
```

## `djx plan`

```bash
djx plan "<intent>" --dataset <input.jsonl> --export <output.jsonl> [options]
```

关键参数：
- `--output`：计划输出路径（默认 `plans/<plan_id>.yaml`）
- `--custom-operator-paths`：校验和后续执行时可用的自定义算子目录或文件

执行行为：
1. 内部先根据 intent 和可选数据集画像做算子检索
2. 根据数据集 IO 和画像信息构建确定性的 dataset spec
3. 调用模型只生成 process spec 所需的 operator list
4. 依次构建 process spec、system spec，并 assemble 为最终 plan
5. 校验最终 plan，并将 plan 以 YAML 落盘

CLI 输出：
- 摘要输出：`Plan generated`、`Modality`、`Operators`
- `--verbose`：输出 planning meta（`planner_model`、`retrieval_source`、`retrieval_candidate_count`）
- `--debug`：输出 retrieval payload、dataset spec、process spec、system spec、validation payload 和 planning meta payload

失败行为：
- 非零退出，并打印面向用户的错误信息

## `djx apply`

```bash
djx apply --plan <plan.yaml> [--yes] [--dry-run] [--timeout 300]
```

行为：
- 读取已保存的 plan YAML，并要求顶层为 mapping
- 在 `.djx/recipes/<plan_id>.yaml` 下生成 recipe
- 若未指定 `--dry-run`，则执行 `dj-process`
- 输出 `Execution ID`、`Status` 和生成的 recipe 路径

说明：
- 当前 CLI 不会自动执行独立的 `plan_validate` 步骤
- 当前 CLI 不提供独立的 trace 查询命令
- `--dry-run` 也会生成 recipe 文件

## `djx retrieve`

```bash
djx retrieve "<intent>" [--dataset <path>] [--top-k 10] [--mode auto|llm|vector] [--json]
```

返回：
- 候选算子排序
- 检索来源、trace 与备注
- 当前输出 payload 不包含 dataset profile

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
- 算子脚手架
- 测试脚手架
- 总结 Markdown
- 可选 smoke-check 结果

默认是非侵入式流程：生成代码和说明，但不自动安装算子。

## `dj-agents`

```bash
dj-agents [--dataset <path>] [--export <path>] [--verbose] [--ui plain|tui|as_studio] [--studio-url <url>]
```

行为：
- 基于同一套 planning、retrieval、apply、dev 原语做自然语言会话
- 使用已注册 session toolkit 的 ReAct agent
- 启动时必须能访问 LLM

常见内部 planning 链路：
- `inspect_dataset -> retrieve_operators -> build_dataset_spec -> build_process_spec -> build_system_spec -> assemble_plan -> plan_validate -> plan_save`

中断方式：
- plain 模式：`Ctrl+C` 中断当前轮，`Ctrl+D` 退出
- tui 模式：`Ctrl+C` 中断当前轮，`Ctrl+D` 退出
- as_studio 模式：交互由 AgentScope Studio 驱动

## 环境变量

- `DASHSCOPE_API_KEY` 或 `MODELSCOPE_API_TOKEN`：API 凭证
- `DJA_OPENAI_BASE_URL`：OpenAI 兼容接口地址
- `DJA_SESSION_MODEL`：`dj-agents` 使用的模型
- `DJA_STUDIO_URL`：`dj-agents --ui as_studio` 使用的 AgentScope Studio 地址
- `DJA_PLANNER_MODEL`：`djx plan` 使用的模型
- `DJA_MODEL_FALLBACKS`：`data_juicer_agents/utils/llm_gateway.py` 使用的逗号分隔模型兜底链
- `DJA_LLM_THINKING`：控制模型请求中的 `enable_thinking`
