# Data-Juicer Q&A Copilot

Q&A Copilot is the intelligent question-answering component of the Data-Juicer Agents system, a professional Data-Juicer AI assistant built on the AgentScope framework.

You can chat with our [Q&A Copilot](./README.md) ***Juicer*** on the official [documentation site](https://datajuicer.github.io/data-juicer/en/main/index.html) of Data-Juicer! Feel free to ask ***Juicer*** anything related to Data-Juicer ecosystem.

<div align="center">
<img src="https://github.com/user-attachments/assets/d10a95a8-fb7a-494f-b858-f21e5996790b" width=90%>
</div>

### Core Components

- **Agent**: Intelligent Q&A agent based on ReActAgent
- **FAQ RAG System**: Fast and accurate FAQ retrieval powered by Qdrant vector database and DashScope text embedding model
- **MCP Integration**: Online GitHub search capabilities through GitHub MCP Server
- **Redis Storage**: Supports session history and feedback data persistence
- **Web API**: Provides RESTful interfaces for frontend integration

## Quick Start

### Prerequisites

- 3.10 <= Python <= 3.12
- Docker (for running Qdrant vector database)
- Redis server (optional, activated by `SESSION_STORE_TYPE=redis`)
- DashScope API Key (for large language model calls and text embedding)

### Installation

1. Install dependencies
   ```bash
   cd ..
   uv pip install .[qa]
   cd qa-copilot
   ```

2. Install Docker (for Qdrant vector database)
   ```bash
   # Ubuntu/Debian
   sudo apt-get install docker.io
   sudo systemctl start docker
   
   # macOS
   brew install docker
   ```

   **Note**: The system will automatically check and start the Qdrant Docker container on startup. If FAQ data is not initialized, the system will automatically read from `qa-copilot/rag_utils/faq.txt` and initialize the RAG data.

3. Install and start Redis (optional - skip if using the default `SESSION_STORE_TYPE=json`)
   ```bash
   # Ubuntu/Debian
   sudo apt-get install redis-server
   redis-server --daemonize yes
   
   # macOS
   brew install redis
   brew services start redis
   ```

   **Note**: 
   - If you set `SESSION_STORE_TYPE=json` (default), session history will be stored as JSON files in the `SESSION_STORE_DIR` directory with automatic TTL-based cleanup.
   - If you set `SESSION_STORE_TYPE=redis`, you need to have Redis server running. Session state is automatically managed by RedisMemory, and TTL is handled by Redis server configuration.

### Configuration

1. Set required environment variables
   ```bash
   export DASHSCOPE_API_KEY="your_dashscope_api_key"
   export GITHUB_TOKEN="your_github_token"  # Required: for GitHub MCP integration
   ```

2. Set optional environment variables

   **Session Storage Configuration:**
   ```bash
   # Session store type: "json" (default) or "redis"
   export SESSION_STORE_TYPE="json"  # or "redis"
   
   # For JSON mode (default):
   export SESSION_STORE_DIR="./sessions"  # Session file storage directory (default: "./sessions")
   export SESSION_TTL_SECONDS="21600"  # Session TTL in seconds (default: 21600 = 6 hours)
   export SESSION_CLEANUP_INTERVAL="1800"  # Cleanup interval in seconds (default: 1800 = 30 minutes)
   
   # For Redis mode:
   export REDIS_HOST="localhost"  # Redis server host (default: "localhost")
   export REDIS_PORT="6379"  # Redis server port (default: 6379)
   export REDIS_DB="0"  # Redis database number (default: 0)
   export REDIS_PASSWORD=""  # Redis password (default: None, optional)
   export REDIS_MAX_CONNECTIONS="10"  # Redis max connections (default: 10)
   # Note: Redis TTL is handled by Redis server configuration, not by application
   ```

   **Model Configuration:**
   ```bash
   export MAX_TOKENS="200000"  # Maximum tokens for context window (default: 200000)
   # Note: This value is multiplied by 3 when passed to DashScopeChatFormatter
   # because CharTokenCounter counts characters, and ~3 chars ≈ 1 token for mixed CHN & ENG text
   ```

   **Qdrant Vector Database:**
   ```bash
   export QDRANT_HOST="127.0.0.1"  # Qdrant server host (default: "127.0.0.1")
   export QDRANT_PORT="6333"  # Qdrant server port (default: 6333)
   ```

   **Service Configuration:**
   ```bash
   export DJ_COPILOT_SERVICE_HOST="127.0.0.1"  # Service host address (default: "127.0.0.1")
   export DJ_COPILOT_ENABLE_LOGGING="true"  # Enable session logging (default: "true")
   export DJ_COPILOT_LOG_DIR="./logs"  # Log directory (default: "./logs")
   ```

   **Advanced Configuration:**
   ```bash
   export FASTAPI_CONFIG_PATH=""  # Path to FastAPI config JSON file (optional)
   export SAFE_CHECK_HANDLER_PATH=""  # Path to custom safe check handler module (optional)
   ```

2. Configure FAQ file (optional)
   
   The system uses `qa-copilot/rag_utils/faq.txt` as the FAQ data source by default. You can edit this file to customize FAQ content. FAQ file format example:
   ```
   'id': 'FAQ_001', 'question': 'What is Data-Juicer?', 'answer': 'Data-Juicer is a...'
   'id': 'FAQ_002', 'question': 'How to install?', 'answer': 'You can install by...'
   ```

3. Start the service
   ```bash
   bash setup_server.sh
   ```
   
   On first startup, the system will automatically:
   - Check and start the Qdrant Docker container (port 6333)
   - Initialize FAQ RAG data (if not already initialized)
   - Start the Web API service

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

#### 4. Submit User Feedback
```http
POST /feedback
Content-Type: application/json

{
  "data": {
    "message_id": "message_id_here",
    "feedback_type": "like",
    "comment": "optional user comment"
  },
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

**Parameters:**
- `message_id`: The ID of the message to provide feedback on (required)
- `feedback_type`: Type of feedback, either `"like"` or `"dislike"` (required)
- `comment`: Optional user comment text (optional)

**Response example:**
```json
{
  "status": "ok",
  "message": "Feedback recorded successfully"
}
```

### WebUI

you can simply run the following command in your terminal:

```bash
npx @agentscope-ai/chat agentscope-runtime-webui --url http://localhost:8080/process
```

Refer to [AgentScope Runtime WebUI](https://runtime.agentscope.io/en/webui.html#method-2-quick-start-via-npx) for more information.

## Configuration Details

### Environment Variables Summary

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DASHSCOPE_API_KEY` | ✅ Yes | - | DashScope API key for LLM and embedding |
| `GITHUB_TOKEN` | ✅ Yes | - | GitHub token for MCP integration |
| `SESSION_STORE_TYPE` | ❌ No | `"json"` | Session storage type: `"json"` or `"redis"` |
| `SESSION_STORE_DIR` | ❌ No | `"./sessions"` | Session file directory (JSON mode only) |
| `SESSION_TTL_SECONDS` | ❌ No | `21600` | Session TTL in seconds (JSON mode only, 6 hours) |
| `SESSION_CLEANUP_INTERVAL` | ❌ No | `1800` | Cleanup interval in seconds (JSON mode only, 30 minutes) |
| `REDIS_HOST` | ❌ No | `"localhost"` | Redis server host (Redis mode only) |
| `REDIS_PORT` | ❌ No | `6379` | Redis server port (Redis mode only) |
| `REDIS_DB` | ❌ No | `0` | Redis database number (Redis mode only) |
| `REDIS_PASSWORD` | ❌ No | `None` | Redis password (Redis mode only, optional) |
| `REDIS_MAX_CONNECTIONS` | ❌ No | `10` | Redis max connections (Redis mode only) |
| `QDRANT_HOST` | ❌ No | `"127.0.0.1"` | Qdrant server host |
| `QDRANT_PORT` | ❌ No | `6333` | Qdrant server port |
| `MAX_TOKENS` | ❌ No | `200000` | Maximum tokens for context window (multiplied by 3 for CharTokenCounter) |
| `DJ_COPILOT_SERVICE_HOST` | ❌ No | `"127.0.0.1"` | Service host address |
| `DJ_COPILOT_ENABLE_LOGGING` | ❌ No | `"true"` | Enable session logging |
| `DJ_COPILOT_LOG_DIR` | ❌ No | `"./logs"` | Log directory |
| `FASTAPI_CONFIG_PATH` | ❌ No | `""` | Path to FastAPI config JSON file |
| `SAFE_CHECK_HANDLER_PATH` | ❌ No | `""` | Path to custom safe check handler |

### Model Configuration

In `app_deploy.py`, you can configure the language model to use:

```python
model=DashScopeChatModel(
    "qwen3-max-2026-01-23",  # Model name
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    stream=True,  # Enable streaming response
    enable_thinking=True,  # Enable thinking mode
)
```

The formatter uses `MAX_TOKENS` environment variable (default: 200000) to limit the context window size. Since `CharTokenCounter` counts characters and approximately 3 characters ≈ 1 token for mixed Chinese and English text, the value is multiplied by 3 when passed to `DashScopeChatFormatter`.

### Session Storage Configuration

**JSON Mode (Default):**
- Session history is stored as JSON files in `SESSION_STORE_DIR` directory
- Automatic TTL-based cleanup runs every `SESSION_CLEANUP_INTERVAL` seconds
- Sessions expire after `SESSION_TTL_SECONDS` seconds of inactivity
- No external dependencies required

**Redis Mode:**
- Session history is stored in Redis
- Session state is automatically managed by `RedisMemory`
- TTL is handled by Redis server configuration (not application-level)
- Requires Redis server to be running

### FAQ RAG Configuration

The FAQ RAG system uses the following configuration:

- **Vector Database**: Qdrant (running in Docker container)
- **Embedding Model**: DashScope text-embedding-v4
- **Vector Dimension**: 1024
- **Data Source**: `qa-copilot/rag_utils/faq.txt`
- **Storage Location**: `qa-copilot/rag_utils/qdrant_storage`
- **Qdrant Host**: Configurable via `QDRANT_HOST` (default: `127.0.0.1`)
- **Qdrant Port**: Configurable via `QDRANT_PORT` (default: `6333`)

The system automatically checks if RAG data is initialized on startup. If not initialized, it will automatically read the FAQ file and create vector indexes.

## Troubleshooting

### Common Issues

1. **Docker/Qdrant Issues**
   - Ensure Docker service is running: `docker --version`
   - Check Qdrant container status: `docker ps | grep qdrant`
   - Manually start Qdrant container: `docker start qdrant`
   - Check if Qdrant port is occupied: `netstat -tlnp | grep 6333`
   - To reinitialize RAG data, delete the `qa-copilot/rag_utils/qdrant_storage` directory and restart the service

2. **Redis connection failure** (when using `SESSION_STORE_TYPE=redis`)
   - Ensure Redis service is running: `redis-cli ping`
   - Check if Redis port is occupied: `netstat -tlnp | grep 6379` (or your configured `REDIS_PORT`)
   - Verify Redis configuration: Check `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, and `REDIS_PASSWORD` environment variables
   - Note: Redis TTL is managed by Redis server, not by the application

3. **MCP service startup failure**
   - Ensure `GITHUB_TOKEN` is set and correct (required environment variable)
   - Verify GitHub token has necessary permissions for MCP integration

4. **API Key error**
   - Verify `DASHSCOPE_API_KEY` environment variable is correctly set
   - Confirm API Key is valid and has sufficient quota

5. **FAQ retrieval returns no results**
   - Confirm FAQ file `qa-copilot/rag_utils/faq.txt` exists and is properly formatted
   - Check if Qdrant container is running normally
   - Review logs to confirm RAG data was successfully initialized

## Acknowledgments

Parts of this project's code are adapted from the following open-source projects:

- **FAQ RAG System & GitHub MCP Integration**: Adapted from the implementation in [AgentScope Samples - Alias](https://github.com/agentscope-ai/agentscope-samples/tree/main/alias)

Special thanks to the AgentScope team for their excellent framework and sample code!

## License

This project uses the same license as the main project. For details, please refer to the [LICENSE](../LICENSE) file.

## Related Links

- [Data-Juicer Official Repository](https://github.com/datajuicer/data-juicer)
- [AgentScope Framework](https://github.com/agentscope-ai/agentscope)
- [AgentScope Samples](https://github.com/agentscope-ai/agentscope-samples)
- [GitHub MCP Server](https://github.com/github/github-mcp-server)
