# Data-Juicer Q&A Copilot

Q&A Copilot 是 Data-Juicer Agents 系统中的智能问答组件，基于 AgentScope 框架构建，是一款面向 Data-Juicer 的专业 AI 助手。

你可以在官方[文档页](https://datajuicer.github.io/data-juicer/zh_CN/main/index_ZH.html)和我们的 [问答 Copilot](./README.md) ***Juicer*** 聊天! 欢迎向 ***Juicer*** 提出任何与 Data-Juicer 生态相关的问题。

<div align="center">
<img src="https://github.com/user-attachments/assets/a0099ce2-4ed3-4fab-8cfa-b0bbd3beeac9" width=90%>
</div>

### 核心组件

- **Agent**：基于 ReActAgent 构建的智能问答代理
- **FAQ RAG 系统**：基于 Qdrant 向量数据库和 DashScope 文本嵌入模型，提供快速准确的 FAQ 检索能力
- **MCP 集成**：通过 GitHub MCP Server 提供在线 GitHub 搜索能力
- **Redis 存储**：支持会话历史记录和用户反馈数据的持久化存储
- **Web API**：提供 RESTful 接口，便于前端集成

## 快速开始

### 前置要求

- 3.10 <= Python <= 3.12
- Docker（用于运行 Qdrant 向量数据库）
- Redis 服务器（可选，通过 `SESSION_STORE_TYPE=redis` 启用）
- DashScope API Key（用于调用大语言模型和文本嵌入）

### 安装步骤

1. 安装依赖项
   ```bash
   cd ..
   uv pip install .[qa]
   cd qa-copilot
   ```

2. 安装 Docker（用于 Qdrant 向量数据库）
   ```bash
   # Ubuntu/Debian
   sudo apt-get install docker.io
   sudo systemctl start docker
   
   # macOS
   brew install docker
   ```

   **注意**：系统启动时会自动检查并启动 Qdrant Docker 容器。如果 FAQ 数据未初始化，系统会自动从 `qa-copilot/rag_utils/faq.txt` 文件读取并初始化 RAG 数据。

3. 安装并启动 Redis（可选 —— 使用默认 `SESSION_STORE_TYPE=json` 时可跳过）
   ```bash
   # Ubuntu/Debian
   sudo apt-get install redis-server
   redis-server --daemonize yes
   
   # macOS
   brew install redis
   brew services start redis
   ```

   **注意**：
   - 如果设置 `SESSION_STORE_TYPE=json`（默认），会话历史将作为 JSON 文件存储在 `SESSION_STORE_DIR` 目录中，并自动进行基于 TTL 的清理。
   - 如果设置 `SESSION_STORE_TYPE=redis`，需要运行 Redis 服务器。会话状态由 RedisMemory 自动管理，TTL 由 Redis 服务器配置处理。

### 配置说明

1. 设置必需环境变量
   ```bash
   export DASHSCOPE_API_KEY="your_dashscope_api_key"
   export GITHUB_TOKEN="your_github_token"  # 必需：用于 GitHub MCP 集成
   ```

2. 设置可选环境变量

   **会话存储配置：**
   ```bash
   # 会话存储类型："json"（默认）或 "redis"
   export SESSION_STORE_TYPE="json"  # 或 "redis"
   
   # JSON 模式（默认）：
   export SESSION_STORE_DIR="./sessions"  # 会话文件存储目录（默认："./sessions"）
   export SESSION_TTL_SECONDS="21600"  # 会话 TTL（秒）（默认：21600 = 6 小时）
   export SESSION_CLEANUP_INTERVAL="1800"  # 清理间隔（秒）（默认：1800 = 30 分钟）
   
   # Redis 模式：
   export REDIS_HOST="localhost"  # Redis 服务器主机（默认："localhost"）
   export REDIS_PORT="6379"  # Redis 服务器端口（默认：6379）
   export REDIS_DB="0"  # Redis 数据库编号（默认：0）
   export REDIS_PASSWORD=""  # Redis 密码（默认：None，可选）
   export REDIS_MAX_CONNECTIONS="10"  # Redis 最大连接数（默认：10）
   # 注意：Redis TTL 由 Redis 服务器配置处理，而非应用程序
   ```

   **模型配置：**
   ```bash
   export MAX_TOKENS="200000"  # 上下文窗口最大 token 数（默认：200000）
   # 注意：此值在传递给 DashScopeChatFormatter 时会乘以 3
   # 因为 CharTokenCounter 基于字符计数，中英文混合文本约 3 个字符 ≈ 1 个 token
   ```

   **Qdrant 向量数据库：**
   ```bash
   export QDRANT_HOST="127.0.0.1"  # Qdrant 服务器主机（默认："127.0.0.1"）
   export QDRANT_PORT="6333"  # Qdrant 服务器端口（默认：6333）
   ```

   **服务配置：**
   ```bash
   export DJ_COPILOT_SERVICE_HOST="127.0.0.1"  # 服务主机地址（默认："127.0.0.1"）
   export DJ_COPILOT_ENABLE_LOGGING="true"  # 启用会话日志（默认："true"）
   export DJ_COPILOT_LOG_DIR="./logs"  # 日志目录（默认："./logs"）
   ```

   **高级配置：**
   ```bash
   export FASTAPI_CONFIG_PATH=""  # FastAPI 配置 JSON 文件路径（可选）
   export SAFE_CHECK_HANDLER_PATH=""  # 自定义安全检查处理器模块路径（可选）
   ```

2. 配置 FAQ 文件（可选）
   
   系统默认使用 `qa-copilot/rag_utils/faq.txt` 作为 FAQ 数据源。您可以编辑此文件来自定义 FAQ 内容。FAQ 文件格式示例：
   ```
   'id': 'FAQ_001', 'question': '什么是 Data-Juicer?', 'answer': 'Data-Juicer 是一个...'
   'id': 'FAQ_002', 'question': '如何安装?', 'answer': '您可以通过...'
   ```

3. 启动服务
   ```bash
   bash setup_server.sh
   ```
   
   首次启动时，系统会自动：
   - 检查并启动 Qdrant Docker 容器（端口 6333）
   - 初始化 FAQ RAG 数据（如果尚未初始化）
   - 启动 Web API 服务

## 使用方式

### Web API 接口

服务启动后，系统将提供以下 API 接口：

#### 1. 问答对话
```http
POST /process
Content-Type: application/json

{
  "input": [
    {
      "role": "user", 
      "content": [{"type": "text", "text": "如何使用 Data-Juicer 进行数据清洗？"}]
    }
  ],
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

#### 2. 获取会话历史
```http
POST /memory
Content-Type: application/json

{
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

#### 3. 清除会话历史
```http
POST /clear
Content-Type: application/json

{
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

#### 4. 提交用户反馈
```http
POST /feedback
Content-Type: application/json

{
  "data": {
    "message_id": "message_id_here",
    "feedback_type": "like",
    "comment": "可选的用户评论"
  },
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

**参数说明：**
- `message_id`：要反馈的消息 ID（必填）
- `feedback_type`：反馈类型，可选值为 `"like"`（点赞）或 `"dislike"`（点踩）（必填）
- `comment`：可选的用户评论文本（选填）

**响应示例：**
```json
{
  "status": "ok",
  "message": "Feedback recorded successfully"
}
```

### WebUI 界面

您只需在终端中运行以下命令即可启动 WebUI：

```bash
npx @agentscope-ai/chat agentscope-runtime-webui --url http://localhost:8080/process
```

更多详情请参考 [AgentScope Runtime WebUI](https://runtime.agentscope.io/en/webui.html#method-2-quick-start-via-npx)。

## 配置详解

### 环境变量汇总

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `DASHSCOPE_API_KEY` | ✅ 是 | - | DashScope API 密钥，用于 LLM 和嵌入模型 |
| `GITHUB_TOKEN` | ✅ 是 | - | GitHub token，用于 MCP 集成 |
| `SESSION_STORE_TYPE` | ❌ 否 | `"json"` | 会话存储类型：`"json"` 或 `"redis"` |
| `SESSION_STORE_DIR` | ❌ 否 | `"./sessions"` | 会话文件目录（仅 JSON 模式） |
| `SESSION_TTL_SECONDS` | ❌ 否 | `21600` | 会话 TTL（秒）（仅 JSON 模式，6 小时） |
| `SESSION_CLEANUP_INTERVAL` | ❌ 否 | `1800` | 清理间隔（秒）（仅 JSON 模式，30 分钟） |
| `REDIS_HOST` | ❌ 否 | `"localhost"` | Redis 服务器主机（仅 Redis 模式） |
| `REDIS_PORT` | ❌ 否 | `6379` | Redis 服务器端口（仅 Redis 模式） |
| `REDIS_DB` | ❌ 否 | `0` | Redis 数据库编号（仅 Redis 模式） |
| `REDIS_PASSWORD` | ❌ 否 | `None` | Redis 密码（仅 Redis 模式，可选） |
| `REDIS_MAX_CONNECTIONS` | ❌ 否 | `10` | Redis 最大连接数（仅 Redis 模式） |
| `QDRANT_HOST` | ❌ 否 | `"127.0.0.1"` | Qdrant 服务器主机 |
| `QDRANT_PORT` | ❌ 否 | `6333` | Qdrant 服务器端口 |
| `MAX_TOKENS` | ❌ 否 | `200000` | 上下文窗口最大 token 数（传递给 CharTokenCounter 时会乘以 3） |
| `DJ_COPILOT_SERVICE_HOST` | ❌ 否 | `"127.0.0.1"` | 服务主机地址 |
| `DJ_COPILOT_ENABLE_LOGGING` | ❌ 否 | `"true"` | 启用会话日志 |
| `DJ_COPILOT_LOG_DIR` | ❌ 否 | `"./logs"` | 日志目录 |
| `FASTAPI_CONFIG_PATH` | ❌ 否 | `""` | FastAPI 配置 JSON 文件路径 |
| `SAFE_CHECK_HANDLER_PATH` | ❌ 否 | `""` | 自定义安全检查处理器路径 |

### 模型配置

在 `app_deploy.py` 文件中，您可以配置所使用的语言模型：

```python
model=DashScopeChatModel(
    "qwen3-max-2026-01-23",  # 模型名称
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    stream=True,  # 启用流式响应
    enable_thinking=True,  # 启用思考模式
)
```

格式化器使用 `MAX_TOKENS` 环境变量（默认：200000）来限制上下文窗口大小。由于 `CharTokenCounter` 基于字符计数，中英文混合文本约 3 个字符 ≈ 1 个 token，因此在传递给 `DashScopeChatFormatter` 时会将该值乘以 3。

### 会话存储配置

**JSON 模式（默认）：**
- 会话历史作为 JSON 文件存储在 `SESSION_STORE_DIR` 目录中
- 自动 TTL 清理每 `SESSION_CLEANUP_INTERVAL` 秒运行一次
- 会话在 `SESSION_TTL_SECONDS` 秒无活动后过期
- 无需外部依赖

**Redis 模式：**
- 会话历史存储在 Redis 中
- 会话状态由 `RedisMemory` 自动管理
- TTL 由 Redis 服务器配置处理（非应用层）

### FAQ RAG 配置

FAQ RAG 系统使用以下配置：

- **向量数据库**：Qdrant（通过 Docker 容器运行）
- **嵌入模型**：DashScope text-embedding-v4
- **向量维度**：1024
- **数据源**：`qa-copilot/rag_utils/faq.txt`
- **存储位置**：`qa-copilot/rag_utils/qdrant_storage`
- **Qdrant 主机**：可通过 `QDRANT_HOST` 配置（默认：`127.0.0.1`）
- **Qdrant 端口**：可通过 `QDRANT_PORT` 配置（默认：`6333`）

系统会在启动时自动检查 RAG 数据是否已初始化。如果未初始化，会自动读取 FAQ 文件并创建向量索引。

## 故障排查

### 常见问题

1. **Docker/Qdrant 相关问题**
   - 确保 Docker 服务正在运行：`docker --version`
   - 检查 Qdrant 容器状态：`docker ps | grep qdrant`
   - 手动启动 Qdrant 容器：`docker start qdrant`
   - 检查 Qdrant 端口是否被占用：`netstat -tlnp | grep 6333`
   - 如果需要重新初始化 RAG 数据，删除 `qa-copilot/rag_utils/qdrant_storage` 目录后重启服务

2. **Redis 连接失败**（使用 `SESSION_STORE_TYPE=redis` 时）
   - 确保 Redis 服务正在运行：`redis-cli ping`
   - 检查 Redis 端口是否被占用：`netstat -tlnp | grep 6379`（或您配置的 `REDIS_PORT`）
   - 验证 Redis 配置：检查 `REDIS_HOST`、`REDIS_PORT`、`REDIS_DB` 和 `REDIS_PASSWORD` 环境变量
   - 注意：Redis TTL 由 Redis 服务器管理，而非应用程序

3. **MCP 服务启动失败**
   - 确保 `GITHUB_TOKEN` 已设置且正确（必需环境变量）
   - 验证 GitHub token 是否具有 MCP 集成所需的权限

4. **API Key 错误**
   - 检查 `DASHSCOPE_API_KEY` 环境变量是否已正确配置
   - 确认该 API Key 有效且配额充足

5. **FAQ 检索无结果**
   - 确认 FAQ 文件 `qa-copilot/rag_utils/faq.txt` 存在且格式正确
   - 检查 Qdrant 容器是否正常运行
   - 查看日志确认 RAG 数据是否已成功初始化

## 致谢

本项目的部分代码参考并改编自以下开源项目：

- **FAQ RAG 系统 & GitHub MCP 集成**：基于 [AgentScope Samples - Alias](https://github.com/agentscope-ai/agentscope-samples/tree/main/alias) 项目的实现进行改编

感谢 AgentScope 团队提供的优秀框架和示例代码！

## 许可证

本项目采用与主项目相同的许可证。详细信息请参阅 [LICENSE](../LICENSE) 文件。

## 相关链接

- [Data-Juicer 官方仓库](https://github.com/datajuicer/data-juicer)
- [AgentScope 框架](https://github.com/agentscope-ai/agentscope)
- [AgentScope Samples](https://github.com/agentscope-ai/agentscope-samples)
- [GitHub MCP Server](https://github.com/github/github-mcp-server)