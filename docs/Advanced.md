# Advanced Features

## Operator Retrieval

Operator retrieval is the core of whether the Agent can work accurately. DJ Agent implements an intelligent operator retrieval tool that quickly finds the most relevant operators from Data-Juicer's nearly 200 operators through an independent LLM query process. This is a key component enabling the data processing agent and code development agent to run accurately.

We don't use a single solution, but provide three modes that can be flexibly selected via the `-r` parameter:

### Retrieval Modes

**LLM Retrieval (default)**
- Uses Qwen-Turbo to understand user requirements from a semantic level, suitable for complex and vague descriptions
- Provides detailed matching reasons and relevance scores
- Higher token consumption, but highest matching accuracy

**Vector Retrieval (vector)**
- Based on DashScope text embedding + FAISS similarity search
- Fast, suitable for batch tasks or rapid prototyping
- No need to call LLM, lower cost

**Auto Mode (auto)**
- Prioritizes LLM retrieval, automatically falls back to vector retrieval on failure

### Usage

Specify the retrieval mode using the `-r` or `--retrieval-mode` parameter:

```bash
dj-agents --retrieval-mode vector
```

For more parameter descriptions, see `dj-agents --help`

## MCP Agent

In addition to command-line tools, DataJuicer also natively supports MCP services, which is an important means to improve performance. MCP services can directly obtain operator information and execute data processing through native interfaces, making it easy to migrate and integrate without separate LLM queries and command-line calls.

### MCP Server Types

Data-Juicer provides two types of MCP:

**Recipe-Flow MCP (Data Recipe)**
- Provides two tools: `get_data_processing_ops` and `run_data_recipe`
- Retrieves by operator type, applicable modalities, and other tags, **no need to call LLM or vector models**
- Suitable for standardized, high-frequency scenarios with better performance

**Granular-Operators MCP (Fine-grained Operators)**
- Wraps each built-in operator as an independent tool, runs on call
- Returns all operators by default, but can control visible scope through environment variables
- Suitable for fine-grained control, building fully customized data processing pipelines

This means that in some scenarios, the Agent's call path can be *shorter, faster, and more direct* than manually writing YAML.

For detailed information, please refer to: [Data-Juicer MCP Service Documentation](https://datajuicer.github.io/data-juicer/en/main/docs/DJ_service.html#mcp-server)

> **Note**: The Data-Juicer MCP server is currently in early development, and features and tools may change with ongoing development.

### Configuration

Configure the service address in `configs/mcp_config.json`:

```json
{
    "mcpServers": {
        "DJ_recipe_flow": {
            "url": "http://127.0.0.1:8080/sse"
        }
    }
}
```

### Usage Methods

Enable MCP Agent to replace Data Processing Agent:

```bash
# Enable MCP Agent and Dev Agent
dj-agents --agents dj_mcp dj_dev

# Or use shorthand
dj-agents -a dj_mcp dj_dev

```
