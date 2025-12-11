# Q&A Copilot

Q&A Copilot 是 InteRecipe 系统的智能问答组件，基于 AgentScope 框架构建的专业 Data-Juicer AI 助手。

### 核心组件

- Juicy Agent：基于 ReActAgent 的智能问答代理
- MCP 集成：通过 Serena MCP 服务器提供代码分析能力
- Redis 存储：支持会话历史和反馈数据持久化
- Web API：提供 RESTful 接口供前端调用

## 快速开始

### 环境要求

- Python >= 3.10
- Redis 服务器
- DashScope API Key（用于大语言模型调用）

### 安装

1. 安装依赖
   ```bash
   cd ../
   uv pip install .
   cd qa-copilot
   ```

2. 安装和启动 Redis
   ```bash
   # Ubuntu/Debian
   sudo apt-get install redis-server
   redis-server --daemonize yes
   
   # macOS
   brew install redis
   brew services start redis
   ```

### 配置

1. 设置环境变量
   ```bash
   export DASHSCOPE_API_KEY="your_dashscope_api_key"
   ```

2. 配置 Data-Juicer 路径
   
   编辑 `setup_server.sh` 文件，将 `DATA_JUICER_PATH` 替换为你本地 data-juicer 仓库的绝对路径：
   ```bash
   export DATA_JUICER_PATH="/path/to/your/data-juicer"
   ```

3. 启动服务
   ```bash
   bash setup_server.sh
   ```


## 使用说明

### Web API 接口

启动服务后，系统将提供以下 API 接口：

#### 1. 问答对话
```http
POST /process
Content-Type: application/json

{
  "input": [
    {
      "role": "user", 
      "content": [{"type": "text", "text": "如何使用Data-Juicer进行数据清洗？"}]
    }
  ],
  "session_id": "your_session_id"
}
```

#### 2. 获取会话历史
```http
POST /memory
Content-Type: application/json

{
  "session_id": "your_session_id"
}
```

#### 3. 清除会话历史
```http
POST /clear
Content-Type: application/json

{
  "session_id": "your_session_id"
}
```

#### 4. 提交反馈
```http
POST /feedback
Content-Type: application/json

{
  "message_id": "msg_id",
  "feedback": "like",  // "like" 或 "dislike"
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

### WebUI

你可以直接在终端中运行以下命令：

```bash
npx @agentscope-ai/chat agentscope-runtime-webui --url http://localhost:8080/process
```

更多信息请参考 [AgentScope Runtime WebUI](https://runtime.agentscope.io/en/webui.html#method-2-quick-start-via-npx)。

## 配置说明

### 模型配置

在 `app_deploy.py` 中可以配置使用的语言模型：

```python
model=DashScopeChatModel(
    "qwen-max",  # 模型名称
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    stream=True,  # 启用流式响应
)
```

### MCP 服务配置

系统使用 Serena MCP 服务器提供代码分析能力：

```python
serena_command = [
    "uvx", "--with", "pyright[nodejs]",
    "--from", "git+https://github.com/oraios/serena",
    "serena", "start-mcp-server",
    "--project", DATA_JUICER_PATH,
    "--mode", "planning",
]
```

## 故障排除

### 常见问题

1. Redis 连接失败
   - 确保 Redis 服务正在运行：`redis-cli ping`
   - 检查 Redis 端口是否被占用：`netstat -tlnp | grep 6379`

2. MCP 服务启动失败
   - 确保 `DATA_JUICER_PATH` 路径正确且存在
   - 检查是否安装了 Node.js（Serena MCP 依赖）

3. API Key 错误
   - 验证 `DASHSCOPE_API_KEY` 环境变量是否正确设置
   - 确认 API Key 有效且有足够的配额

## 许可证

本项目采用与主项目相同的许可证。详情请参阅 [LICENSE](../../LICENSE) 文件。

## 相关链接

- [InteRecipe 主项目](../README_ZH.md)
- [Data-Juicer 官方仓库](https://github.com/datajuicer/data-juicer)
- [AgentScope 框架](https://github.com/agentscope-ai/agentscope)
- [Serena MCP](https://github.com/oraios/serena)