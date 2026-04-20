# Data-Juicer Q&A Copilot

Q&A Copilot is the question-answering component of Data-Juicer Agents. It runs as an AgentScope-based web service and answers Data-Juicer ecosystem questions with a combination of LLM reasoning, GitHub MCP retrieval, and operator lookup tools.

You can chat with ***Juicer*** on the official [Data-Juicer documentation site](https://datajuicer.github.io/data-juicer/en/main/index.html).

<div align="center">
<img src="https://github.com/user-attachments/assets/d10a95a8-fb7a-494f-b858-f21e5996790b" width=90%>
</div>

## Core Components

- **Agent**: ReActAgent-based Q&A service
- **GitHub MCP Integration**: `search_repositories`, `search_code`, and `get_file_contents`
- **Operator Tools**: `retrieve_operators_api` (llm mode) and `get_operator_info`
- **Session Storage**: JSON-based storage by default, Redis optional
- **Web API**: REST endpoints for chat, memory, clear, and feedback

## Quick Start

### Prerequisites

- Python `>=3.10, <=3.12`
- DashScope API key
- GitHub token
- Redis server only if you want `SESSION_STORE_TYPE=redis`

### Installation

1. Install dependencies.
   ```bash
   cd ..
   uv pip install '.[copilot]'
   cd qa-copilot
   ```

2. Export required environment variables.
   ```bash
   export DASHSCOPE_API_KEY="your_dashscope_api_key"
   export GITHUB_TOKEN="your_github_token"
   ```

3. Optional session storage configuration.
   ```bash
   export SESSION_STORE_TYPE="json"  # or "redis"

   # JSON mode
   export SESSION_STORE_DIR="./sessions"
   export SESSION_TTL_SECONDS="21600"
   export SESSION_CLEANUP_INTERVAL="1800"

   # Redis mode
   export REDIS_HOST="localhost"
   export REDIS_PORT="6379"
   export REDIS_DB="0"
   export REDIS_PASSWORD=""
   export REDIS_MAX_CONNECTIONS="10"
   ```

4. Optional service configuration.
   ```bash
   export DJ_COPILOT_SERVICE_HOST="127.0.0.1"
   export DJ_COPILOT_SERVICE_PORT="8080"
   export DJ_COPILOT_ENABLE_LOGGING="true"
   export DJ_COPILOT_LOG_DIR="./logs"
   export FASTAPI_CONFIG_PATH=""
   export SAFE_CHECK_HANDLER_PATH=""
   ```

5. Start the service.
   ```bash
   bash setup_server.sh
   ```

## Runtime Behavior

### Model

- Default model: `qwen3.6-plus`
- Transport: DashScope OpenAI-compatible endpoint
- Streaming: enabled
- The runtime applies local formatter-based truncation with `OpenAIChatFormatter`.
- Provider-side context window is `1M` tokens; the local formatter conservatively truncates at `0.8M` tokens to leave headroom for tokenizer mismatch between DashScope/Qwen serving and the local OpenAI-compatible token counter.

### Mounted Tools

The current QA runtime mounts these tools:

- GitHub MCP:
  - `search_repositories`
  - `search_code`
  - `get_file_contents`
- Operator tools:
  - `retrieve_operators_api`
  - `get_operator_info`

`retrieve_operators_api` is wrapped so that QA always uses `llm` retrieval mode internally.

## API

### 1. Q&A Conversation

```http
POST /process
Content-Type: application/json

{
  "input": [
    {
      "role": "user",
      "content": [{"type": "text", "text": "How do I use Data-Juicer for data cleaning?"}]
    }
  ],
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

### 2. Get Session History

```http
POST /memory
Content-Type: application/json

{
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

### 3. Clear Session History

```http
POST /clear
Content-Type: application/json

{
  "session_id": "your_session_id",
  "user_id": "user_id"
}
```

### 4. Submit User Feedback

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

Feedback parameters:

- `message_id`: target message id
- `feedback_type`: `like` or `dislike`
- `comment`: optional free-form comment

## WebUI

You can launch the Runtime WebUI with:

```bash
npx @agentscope-ai/chat agentscope-runtime-webui --url http://localhost:8080/process
```

If you change `DJ_COPILOT_SERVICE_PORT`, update the WebUI URL accordingly.

See [AgentScope Runtime WebUI](https://runtime.agentscope.io/en/webui.html#method-2-quick-start-via-npx) for more details.

## Environment Variables

JSON session settings only apply when `SESSION_STORE_TYPE=json`. Redis settings only apply when `SESSION_STORE_TYPE=redis`.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DASHSCOPE_API_KEY` | ✅ Yes | - | DashScope API key |
| `GITHUB_TOKEN` | ✅ Yes | - | GitHub token for MCP integration |
| `SESSION_STORE_TYPE` | ❌ No | `"json"` | Session storage type: `"json"` or `"redis"` |
| `SESSION_STORE_DIR` | ❌ No | `"./sessions"` | Session file directory in JSON mode |
| `SESSION_TTL_SECONDS` | ❌ No | `21600` | Session TTL in JSON mode |
| `SESSION_CLEANUP_INTERVAL` | ❌ No | `1800` | Cleanup interval in JSON mode |
| `REDIS_HOST` | ❌ No | `"localhost"` | Redis host in Redis mode |
| `REDIS_PORT` | ❌ No | `6379` | Redis port in Redis mode |
| `REDIS_DB` | ❌ No | `0` | Redis database number |
| `REDIS_PASSWORD` | ❌ No | unset | Redis password |
| `REDIS_MAX_CONNECTIONS` | ❌ No | `10` | Redis max connections |
| `DJ_COPILOT_SERVICE_HOST` | ❌ No | `"127.0.0.1"` | Service host |
| `DJ_COPILOT_SERVICE_PORT` | ❌ No | `8080` | Service port |
| `DJ_COPILOT_ENABLE_LOGGING` | ❌ No | `"true"` | Enable session logging |
| `DJ_COPILOT_LOG_DIR` | ❌ No | `qa-copilot/logs` | Log directory. If unset, logs are written under the `logs` directory next to `session_logger.py` |
| `FASTAPI_CONFIG_PATH` | ❌ No | `""` | Optional FastAPI config JSON file |
| `SAFE_CHECK_HANDLER_PATH` | ❌ No | `""` | Optional safe-check handler module |

## Troubleshooting

### Common Issues

1. Redis connection failure in `SESSION_STORE_TYPE=redis`
   - Check `redis-cli ping`
   - Verify `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, and `REDIS_PASSWORD`

2. MCP startup failure
   - Ensure `GITHUB_TOKEN` is exported
   - Confirm the token has the required access for GitHub MCP

3. DashScope authentication or quota failure
   - Verify `DASHSCOPE_API_KEY`
   - Check Model Studio quota and model availability

4. Custom config or safe-check handler not loading
   - Verify `FASTAPI_CONFIG_PATH` points to a valid JSON file
   - Verify `SAFE_CHECK_HANDLER_PATH` points to an importable Python module

## Acknowledgments

Parts of the service scaffolding and MCP integration were adapted from [AgentScope Samples - Alias](https://github.com/agentscope-ai/agentscope-samples/tree/main/alias).

## License

This project uses the same license as the main project. See [LICENSE](../LICENSE) for details.

## Related Links

- [Data-Juicer Official Repository](https://github.com/datajuicer/data-juicer)
- [Data-Juicer Agents](https://github.com/datajuicer/data-juicer-agents)
- [AgentScope Framework](https://github.com/agentscope-ai/agentscope)
- [GitHub MCP Server](https://github.com/github/github-mcp-server)
