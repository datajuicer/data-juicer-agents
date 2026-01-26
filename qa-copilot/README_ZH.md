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

- Python >= 3.10
- Docker（用于运行 Qdrant 向量数据库）
- Redis 服务器（可选 —— 可通过设置 `DISABLE_DATABASE=1` 禁用）
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

3. 安装并启动 Redis（可选 —— 若使用 `DISABLE_DATABASE=1` 则可跳过）
   ```bash
   # Ubuntu/Debian
   sudo apt-get install redis-server
   redis-server --daemonize yes
   
   # macOS
   brew install redis
   brew services start redis
   ```

   **注意**：如果设置了 `DISABLE_DATABASE=1`，系统将以纯内存模式运行，无需 Redis。会话历史将仅保存在内存中，并在用户 6 小时无操作后自动清理。

### 配置说明

1. 设置环境变量
   ```bash
   export DASHSCOPE_API_KEY="your_dashscope_api_key"
   export GITHUB_TOKEN="your_github_token"
   
   # 可选：禁用数据库（Redis）—— 启用纯内存模式
   # export DISABLE_DATABASE=1
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

#### 4. 获取会话列表
```http
POST /sessions
Content-Type: application/json
{
  "user_id": "user_id"
}
```

#### 5. 提交用户反馈
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

### 模型配置

在 `app_deploy.py` 文件中，您可以配置所使用的语言模型：

```python
model=DashScopeChatModel(
    "qwen-max",  # 模型名称
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    stream=True,  # 启用流式响应
)
```

### FAQ RAG 配置

FAQ RAG 系统使用以下配置：

- **向量数据库**：Qdrant（通过 Docker 容器运行）
- **嵌入模型**：DashScope text-embedding-v4
- **向量维度**：1024
- **数据源**：`qa-copilot/rag_utils/faq.txt`
- **存储位置**：`qa-copilot/rag_utils/qdrant_storage`

系统会在启动时自动检查 RAG 数据是否已初始化。如果未初始化，会自动读取 FAQ 文件并创建向量索引。

## 故障排查

### 常见问题

1. **Docker/Qdrant 相关问题**
   - 确保 Docker 服务正在运行：`docker --version`
   - 检查 Qdrant 容器状态：`docker ps | grep qdrant`
   - 手动启动 Qdrant 容器：`docker start qdrant`
   - 检查 Qdrant 端口是否被占用：`netstat -tlnp | grep 6333`
   - 如果需要重新初始化 RAG 数据，删除 `qa-copilot/rag_utils/qdrant_storage` 目录后重启服务

2. **Redis 连接失败**
   - 确保 Redis 服务正在运行：`redis-cli ping`
   - 检查 Redis 端口是否被占用：`netstat -tlnp | grep 6379`

3. **MCP 服务启动失败**
   - 确认 `GITHUB_TOKEN` 已正确设置且有效

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