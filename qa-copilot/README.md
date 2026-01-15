# Q&A Copilot

Q&A Copilot is the intelligent question-answering component of the InteRecipe system, a professional Data-Juicer AI assistant built on the AgentScope framework.

### Core Components

- Juicy Agent: Intelligent Q&A agent based on ReActAgent
- FAQ RAG System: Fast and accurate FAQ retrieval powered by Qdrant vector database and DashScope text embedding model
- MCP Integration: Online GitHub search capabilities through GitHub MCP Server
- Redis Storage: Supports session history and feedback data persistence
- Web API: Provides RESTful interfaces for frontend integration

## Quick Start

### Prerequisites

- Python >= 3.10
- Docker (for running Qdrant vector database)
- Redis server (optional - can be disabled with `DISABLE_DATABASE=1`)
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

3. Install and start Redis (optional - skip if using `DISABLE_DATABASE=1`)
   ```bash
   # Ubuntu/Debian
   sudo apt-get install redis-server
   redis-server --daemonize yes
   
   # macOS
   brew install redis
   brew services start redis
   ```

   **Note**: If you set `DISABLE_DATABASE=1`, the system will run in memory-only mode without requiring Redis. Session history will be stored in memory with automatic cleanup after 20 seconds of inactivity.

### Configuration

1. Set environment variables
   ```bash
   export DASHSCOPE_API_KEY="your_dashscope_api_key"
   export GITHUB_TOKEN="your_github_token"
   
   # Optional: Disable database (Redis) - run in memory-only mode
   # export DISABLE_DATABASE=1
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

#### 4. Get Session List
```http
POST /sessions
Content-Type: application/json
{
  "user_id": "user_id"
}
```

#### 5. Submit User Feedback
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

### Model Configuration

In `app_deploy.py`, you can configure the language model to use:

```python
model=DashScopeChatModel(
    "qwen-max",  # Model name
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    stream=True,  # Enable streaming response
)
```

### FAQ RAG Configuration

The FAQ RAG system uses the following configuration:

- **Vector Database**: Qdrant (running in Docker container)
- **Embedding Model**: DashScope text-embedding-v4
- **Vector Dimension**: 1024
- **Data Source**: `qa-copilot/rag_utils/faq.txt`
- **Storage Location**: `qa-copilot/rag_utils/qdrant_storage`

The system automatically checks if RAG data is initialized on startup. If not initialized, it will automatically read the FAQ file and create vector indexes.

## Troubleshooting

### Common Issues

1. **Docker/Qdrant Issues**
   - Ensure Docker service is running: `docker --version`
   - Check Qdrant container status: `docker ps | grep qdrant`
   - Manually start Qdrant container: `docker start qdrant`
   - Check if Qdrant port is occupied: `netstat -tlnp | grep 6333`
   - To reinitialize RAG data, delete the `qa-copilot/rag_utils/qdrant_storage` directory and restart the service

2. **Redis connection failure**
   - Ensure Redis service is running: `redis-cli ping`
   - Check if Redis port is occupied: `netstat -tlnp | grep 6379`

3. **MCP service startup failure**
   - Ensure `GITHUB_TOKEN` is correct and exists

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
