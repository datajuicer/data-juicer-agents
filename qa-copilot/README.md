# Q&A Copilot

Q&A Copilot is the intelligent question-answering component of the InteRecipe system, a professional Data-Juicer AI assistant built on the AgentScope framework.

### Core Components

- Juicy Agent: Intelligent Q&A agent based on ReActAgent
- MCP Integration: Code analysis capabilities through Serena MCP server
- Redis Storage: Supports session history and feedback data persistence
- Web API: Provides RESTful interfaces for frontend integration

## Quick Start

### Prerequisites

- Python >= 3.10
- Redis server
- DashScope API Key (for large language model calls)

### Installation

1. Install dependencies
   ```bash
   cd ..
   uv pip install .[qa]
   cd qa-copilot
   ```

2. Install and start Redis
   ```bash
   # Ubuntu/Debian
   sudo apt-get install redis-server
   redis-server --daemonize yes
   
   # macOS
   brew install redis
   brew services start redis
   ```

### Configuration

1. Set environment variables
   ```bash
   export DASHSCOPE_API_KEY="your_dashscope_api_key"
   ```

2. Configure Data-Juicer path
   
   Edit the `setup_server.sh` file and replace `DATA_JUICER_PATH` with the absolute path to your local data-juicer repository:
   ```bash
   export DATA_JUICER_PATH="/path/to/your/data-juicer"
   ```

3. Start the service
   ```bash
   bash setup_server.sh
   ```

## Usage

### Web API Interfaces

After starting the service, the system provides the following API interfaces:

#### 1. Q&A Conversation
```http
POST /process
Content-Type: application/json

{
  "input": [
    {
      "role": "user", 
      "content": [{"type": "text", "text": "How to use Data-Juicer for data cleaning?"}]
    }
  ],
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

#### 2. Get Session History
```http
POST /memory
Content-Type: application/json

{
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

#### 3. Clear Session History
```http
POST /clear
Content-Type: application/json

{
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

#### 4. Get Session List
```http
POST /sessions
Content-Type: application/json
{
  "user_id": "user_id"
}
```

### WebUI

you can simply run the following command in your terminal:

```bash
npx @agentscope-ai/chat agentscope-runtime-webui --url http://localhost:8080/process
```

Refer to [AgentScope Runtime WebUI](https://runtime.agentscope.io/en/webui.html#method-2-quick-start-via-npx) for more information.

## Configuration Details

### Model Configuration

In `app_deploy.py`, you can configure the language model to use:

```python
model=DashScopeChatModel(
    "qwen-max",  # Model name
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    stream=True,  # Enable streaming response
)
```

### MCP Service Configuration

The system uses Serena MCP server to provide code analysis capabilities:

```python
serena_command = [
    "uvx", "--with", "pyright[nodejs]",
    "--from", "git+https://github.com/oraios/serena",
    "serena", "start-mcp-server",
    "--project", DATA_JUICER_PATH,
    "--mode", "planning",
]
```

## Troubleshooting

### Common Issues

1. Redis connection failure
   - Ensure Redis service is running: `redis-cli ping`
   - Check if Redis port is occupied: `netstat -tlnp | grep 6379`

2. MCP service startup failure
   - Ensure `DATA_JUICER_PATH` is correct and exists
   - Check if Node.js is installed (Serena MCP dependency)

3. API Key error
   - Verify `DASHSCOPE_API_KEY` environment variable is correctly set
   - Confirm API Key is valid and has sufficient quota

## License

This project uses the same license as the main project. For details, please refer to the [LICENSE](../LICENSE) file.

## Related Links

- [Data-Juicer Official Repository](https://github.com/datajuicer/data-juicer)
- [AgentScope Framework](https://github.com/agentscope-ai/agentscope)
- [Serena MCP](https://github.com/oraios/serena)
