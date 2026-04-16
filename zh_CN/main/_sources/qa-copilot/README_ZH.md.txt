# Data-Juicer Q&A Copilot

Q&A Copilot 是 Data-Juicer Agents 的问答组件。它以 AgentScope Web 服务的形式运行，通过大模型推理、GitHub MCP 检索和算子查询工具来回答 Data-Juicer 生态相关问题。

你可以在官方 [Data-Juicer 文档站](https://datajuicer.github.io/data-juicer/zh_CN/main/index_ZH.html) 与 ***Juicer*** 进行对话。

<div align="center">
<img src="https://github.com/user-attachments/assets/a0099ce2-4ed3-4fab-8cfa-b0bbd3beeac9" width=90%>
</div>

## 核心组件

- **Agent**：基于 ReActAgent 的问答服务
- **GitHub MCP 集成**：`search_repositories`、`search_code`、`get_file_contents`
- **算子工具**：`retrieve_operators_api` 与 `get_operator_info`
- **会话存储**：默认 JSON，可选 Redis
- **Web API**：提供对话、历史、清空和反馈接口

## 快速开始

### 前置要求

- Python `>=3.10, <=3.12`
- DashScope API Key
- GitHub Token
- Redis 仅在需要 `SESSION_STORE_TYPE=redis` 时才需要

### 安装步骤

1. 安装依赖。
   ```bash
   cd ..
   uv pip install '.[copilot]'
   cd qa-copilot
   ```

2. 设置必需环境变量。
   ```bash
   export DASHSCOPE_API_KEY="your_dashscope_api_key"
   export GITHUB_TOKEN="your_github_token"
   ```

3. 可选的会话存储配置。
   ```bash
   export SESSION_STORE_TYPE="json"  # 或 "redis"

   # JSON 模式
   export SESSION_STORE_DIR="./sessions"
   export SESSION_TTL_SECONDS="21600"
   export SESSION_CLEANUP_INTERVAL="1800"

   # Redis 模式
   export REDIS_HOST="localhost"
   export REDIS_PORT="6379"
   export REDIS_DB="0"
   export REDIS_PASSWORD=""
   export REDIS_MAX_CONNECTIONS="10"
   ```

4. 可选的服务配置。
   ```bash
   export DJ_COPILOT_SERVICE_HOST="127.0.0.1"
   export DJ_COPILOT_SERVICE_PORT="8080"
   export DJ_COPILOT_ENABLE_LOGGING="true"
   export DJ_COPILOT_LOG_DIR="./logs"
   export FASTAPI_CONFIG_PATH=""
   export SAFE_CHECK_HANDLER_PATH=""
   ```

5. 启动服务。
   ```bash
   bash setup_server.sh
   ```

## 运行时行为

### 模型

- 默认模型：`qwen3.6-plus`
- 传输方式：DashScope OpenAI-compatible endpoint
- 流式输出：开启
- 当前运行时会通过 `OpenAIChatFormatter` 在本地执行上下文截断
- 服务端真实上下文窗口为 `1M` tokens；本地 formatter 保守地在 `0.8M` tokens 处截断，为 DashScope/Qwen 服务端分词与本地 OpenAI-compatible token counter 之间可能存在的不一致预留余量

### 当前挂载工具

当前 QA 运行时挂载以下工具：

- GitHub MCP：
  - `search_repositories`
  - `search_code`
  - `get_file_contents`
- 算子工具：
  - `retrieve_operators_api`
  - `get_operator_info`

其中 `retrieve_operators_api` 在 QA 中被包装为固定使用 `llm` 模式。

## API

### 1. 问答对话

```http
POST /process
Content-Type: application/json

{
  "input": [
    {
      "role": "user",
      "content": [{"type": "text", "text": "如何使用 Data-Juicer 做数据清洗？"}]
    }
  ],
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

### 2. 获取会话历史

```http
POST /memory
Content-Type: application/json

{
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

### 3. 清除会话历史

```http
POST /clear
Content-Type: application/json

{
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

### 4. 提交用户反馈

```http
POST /feedback
Content-Type: application/json

{
  "data": {
    "message_id": "message_id_here",
    "feedback_type": "like",
    "comment": "可选评论"
  },
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

反馈参数：

- `message_id`：目标消息 ID
- `feedback_type`：`like` 或 `dislike`
- `comment`：可选文本评论

## WebUI

可以通过下面的命令启动 Runtime WebUI：

```bash
npx @agentscope-ai/chat agentscope-runtime-webui --url http://localhost:8080/process
```

如果修改了 `DJ_COPILOT_SERVICE_PORT`，这里的 WebUI URL 也要同步改成对应端口。

更多信息见 [AgentScope Runtime WebUI](https://runtime.agentscope.io/en/webui.html#method-2-quick-start-via-npx)。

## 环境变量

其中 JSON 会话配置只在 `SESSION_STORE_TYPE=json` 时生效，Redis 配置只在 `SESSION_STORE_TYPE=redis` 时生效。

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `DASHSCOPE_API_KEY` | ✅ 是 | - | DashScope API 密钥 |
| `GITHUB_TOKEN` | ✅ 是 | - | GitHub MCP Token |
| `SESSION_STORE_TYPE` | ❌ 否 | `"json"` | 会话存储类型：`"json"` 或 `"redis"` |
| `SESSION_STORE_DIR` | ❌ 否 | `"./sessions"` | JSON 模式下的会话目录 |
| `SESSION_TTL_SECONDS` | ❌ 否 | `21600` | JSON 模式下的 TTL |
| `SESSION_CLEANUP_INTERVAL` | ❌ 否 | `1800` | JSON 模式下的清理间隔 |
| `REDIS_HOST` | ❌ 否 | `"localhost"` | Redis 主机 |
| `REDIS_PORT` | ❌ 否 | `6379` | Redis 端口 |
| `REDIS_DB` | ❌ 否 | `0` | Redis 数据库编号 |
| `REDIS_PASSWORD` | ❌ 否 | 未设置 | Redis 密码 |
| `REDIS_MAX_CONNECTIONS` | ❌ 否 | `10` | Redis 最大连接数 |
| `DJ_COPILOT_SERVICE_HOST` | ❌ 否 | `"127.0.0.1"` | 服务监听地址 |
| `DJ_COPILOT_SERVICE_PORT` | ❌ 否 | `8080` | 服务监听端口 |
| `DJ_COPILOT_ENABLE_LOGGING` | ❌ 否 | `"true"` | 是否启用会话日志 |
| `DJ_COPILOT_LOG_DIR` | ❌ 否 | `qa-copilot/logs` | 日志目录；未设置时会写入 `session_logger.py` 同级的 `logs` 目录 |
| `FASTAPI_CONFIG_PATH` | ❌ 否 | `""` | 可选 FastAPI 配置 JSON 文件 |
| `SAFE_CHECK_HANDLER_PATH` | ❌ 否 | `""` | 可选安全检查处理器模块 |

## 故障排查

### 常见问题

1. `SESSION_STORE_TYPE=redis` 时 Redis 连接失败
   - 检查 `redis-cli ping`
   - 核对 `REDIS_HOST`、`REDIS_PORT`、`REDIS_DB`、`REDIS_PASSWORD`

2. MCP 启动失败
   - 确保 `GITHUB_TOKEN` 已导出
   - 确认 Token 具备 GitHub MCP 所需权限

3. DashScope 鉴权或配额失败
   - 检查 `DASHSCOPE_API_KEY`
   - 检查 Model Studio 配额和模型可用性

4. 自定义配置或安全检查模块加载失败
   - 确认 `FASTAPI_CONFIG_PATH` 指向合法 JSON
   - 确认 `SAFE_CHECK_HANDLER_PATH` 指向可导入的 Python 模块

## 致谢

部分服务脚手架与 MCP 集成改编自 [AgentScope Samples - Alias](https://github.com/agentscope-ai/agentscope-samples/tree/main/alias)。

## 许可证

本项目与主项目使用相同许可证，详见 [LICENSE](../LICENSE)。

## 相关链接

- [Data-Juicer 官方仓库](https://github.com/datajuicer/data-juicer)
- [Data-Juicer Agents](https://github.com/datajuicer/data-juicer-agents)
- [AgentScope 框架](https://github.com/agentscope-ai/agentscope)
- [GitHub MCP Server](https://github.com/github/github-mcp-server)
