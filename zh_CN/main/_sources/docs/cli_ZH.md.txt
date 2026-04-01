# DJX CLI 参考

## 命令总览

| 命令 | 作用 | 源码 |
|---|---|---|
| `djx plan` | 基于 intent、检索证据、分阶段 spec 和 LLM 生成的 operator list 生成 plan YAML | `data_juicer_agents/commands/plan_cmd.py` |
| `djx apply` | 读取已保存的 plan，物化 recipe，并执行或 dry-run `dj-process` | `data_juicer_agents/commands/apply_cmd.py` |
| `djx retrieve` | 基于 intent 检索候选算子 | `data_juicer_agents/commands/retrieve_cmd.py` |
| `djx dev` | 生成非侵入式自定义算子脚手架 | `data_juicer_agents/commands/dev_cmd.py` |
| `djx tool` | 通过统一的 JSON-first 外壳观察或执行任意已注册原子工具 | `data_juicer_agents/commands/tool_cmd.py` |

其他入口：
- `dj-agents`：`data_juicer_agents/session_cli.py`
- `djx --version`：输出当前安装包版本

CLI 不包含 `trace`、`templates`、`evaluate`。

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
1. 内部先根据 intent 和可选数据集模态信号做算子检索
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
- CLI 不会自动执行独立的 `plan_validate` 步骤
- CLI 不提供独立的 trace 查询命令
- `--dry-run` 也会生成 recipe 文件

## `djx retrieve`

```bash
djx retrieve "<intent>" [--dataset <path>] [--type <op_type>] [--tags <tag> ...] [--top-k 10] [--mode auto|llm|vector|bm25|regex] [--json]
```

关键参数：
- `--dataset`：可选数据集路径；提供后，CLI 会通过 retrieval 层内的数据集探测逻辑识别数据集模态（text / image / multimodal / audio / video），并将其转换为算子标签用于过滤
- `--type`：按算子类型过滤（如 `filter`、`mapper`、`deduplicator`）
- `--tags`：按算子标签过滤（如 `text`、`image`、`multimodal`）；可与 `--dataset` 组合使用（标签会合并）
- `--top-k`：最大候选数量（默认 10）
- `--mode`：检索后端选择
- `--json`：以 JSON 格式输出完整 payload，而非人类可读摘要

返回：
- 候选算子排序
- 检索来源、trace 与备注
- 当提供 `--dataset` 且成功检测到模态时，payload 中包含 `inferred_tags`
- `auto` 顺序为 `llm -> vector -> bm25 -> lexical`（无 API Key 时为 `bm25 -> lexical`）
- `regex` 使用 Python 正则表达式匹配算子名称、描述和参数字段（独立模式，不参与 auto fallback 链）

基于数据集的过滤：
- 当提供 `--dataset` 时，CLI 会在 retrieval 层内部运行数据集探测逻辑来识别数据集模态
- 检测到的模态会映射为算子标签（如 `image` → `["image"]`，`multimodal` → `["multimodal"]`）
- 这些标签会传递给检索后端，后端据此过滤算子目录，仅返回标签匹配的算子
- 如果模态检测失败，检索将不带标签过滤继续执行

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

## `djx tool`

```bash
djx tool list [--tag <tag>]
djx tool schema <tool-name>
djx tool run <tool-name> (--input-json '<json>' | --input-file <input.json>) [--working-dir <path>] [--yes]
```

用途：
- 直接透出原子 `ToolSpec` 层，便于 agents、skills 和自动化调用
- 保持 `plan`、`apply`、`retrieve`、`dev` 这些工作流命令不变
- 避免为每个 tool 单独维护一套 CLI 适配层

默认行为：
- `list`、`schema`、`run` 都输出 JSON
- 写入 / 执行类工具默认非交互；如果工具声明了 `confirmation=recommended|required`，必须显式传 `--yes`

子命令：
- `list`：返回已注册工具的元数据（`name`、`tags`、`effects`、`confirmation`、输入/输出模型名）
- `schema`：返回工具元数据和输入模型的 JSON Schema
- `run`：读取 JSON 输入，构造最小 `ToolContext`，执行工具并返回标准化结果

退出码：
- `0`：成功
- `2`：CLI 用法错误、未知工具、JSON 输入非法、或输入模型校验失败
- `3`：需要显式确认但未提供
- `4`：工具已执行，但返回失败 payload

示例：

```bash
djx tool list --tag plan
djx tool schema inspect_dataset
djx tool run list_system_config --input-json '{}'
djx tool run inspect_dataset --input-json '{"dataset_path":"./data/demo-dataset.jsonl","sample_size":5}'
djx tool run write_text_file --yes --input-json '{"file_path":"./tmp.txt","content":"hello"}'
djx tool run plan_validate --input-file ./examples/plan_payload.json
```

说明：
- 该工具接口只输出 JSON，不会把每个工具输入模型字段展开成单独 CLI flags
- CLI 暴露的上下文面仅包含 `--working-dir`
- `ToolContext.env` 和 `runtime_values` 不通过 CLI 暴露
- `tool run` 的主要设计目标是机器间调用，稳定 JSON 输出是第一契约
- `--quiet`、`--verbose`、`--debug` 仅用于与其他 `djx` 子命令保持 CLI 形态一致，不会改变 `djx tool` 的输出
- 安装 `data-juicer-agents[harness]` 后可设置 `DJX_TOOL_PROFILE=harness`，将 `djx tool` 限制在 harness 工具组（`apply`、`context`、`retrieve`、`plan`）
- 不在当前 profile 内的工具不会出现在 `list` 中，直接调用会返回结构化 JSON 错误

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
- 如需做算子发现和 schema 查看，优先使用 `retrieve_operators` / `retrieve_operators_api`，再用 `get_operator_info`。

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
- `DJX_TOOL_PROFILE`：可选工具目录 profile；设为 `harness` 时，`djx tool` 只暴露 harness 工具集
