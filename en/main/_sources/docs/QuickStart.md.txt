# Quick Start

## System Requirements

- Python 3.10+
- Valid DashScope API key
- Optional: Data-Juicer source code (for custom operator development)

## Installation

```bash
# Install uv (if not already)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Installation using uv
uv pip install -e .
```

> **Note for Custom Operator Development**: 
> 
> For a better custom operator development experience, you should also download and install Data-Juicer from source:
> 
> 1. Clone the repository:
>    ```bash
>    git clone https://github.com/datajuicer/data-juicer.git
>    ```
> 
> 2. Install it in editable mode:
>    ```bash
>    uv pip install -e /path/to/data-juicer
>    ```
>    or
>    ```bash
>    pip install -e /path/to/data-juicer
>    ```
> 
> Editable mode installation is essential to ensure the agent can access real-time operator updates.

1. **Set API Key**

```bash
export DASHSCOPE_API_KEY="your-dashscope-key"
```

2. **Optional: Configure Data-Juicer Path (for custom operator development)**

```bash
export DATA_JUICER_PATH="your-data-juicer-path"
```

> **Tip**: You can also set this during runtime through conversation, for example:
> - "Help me set the DataJuicer path: /path/to/data-juicer"
> - "Help me update the DataJuicer path: /path/to/data-juicer"

## Usage

Choose the running mode using the `-u` or `--use-studio` parameter:

```bash
# Use AgentScope Studio's interactive interface (please install and start AgentScope Studio first)
dj-agents --use-studio

# Or use command line mode directly (default)
dj-agents
```

Note:

Install AgentScope Studio via npm:

```bash
npm install -g @agentscope/studio
```

Start Studio with the following command:

```bash
as_studio
```
