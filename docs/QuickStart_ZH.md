# 快速开始

## 系统要求

- Python 3.10+
- 有效的 DashScope API 密钥
- 可选：Data-Juicer 源码（用于自定义算子开发）

## 安装

```bash
# 安装 uv（如果还没有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 使用 uv 安装
uv pip install -e .
```

> **自定义算子开发提示**：
> 
> 为了获得更好的自定义算子开发体验，您还应该从源码下载并安装 Data-Juicer：
> 
> 1. 克隆代码仓库：
>    ```bash
>    git clone https://github.com/datajuicer/data-juicer.git
>    ```
> 
> 2. 以可编辑模式安装：
>    ```bash
>    uv pip install -e /path/to/data-juicer
>    ```
>    或
>    ```bash
>    pip install -e /path/to/data-juicer
>    ```
> 
> 可编辑模式安装对于确保 Agent 可以实时访问算子更新非常重要。

## 配置

1. **设置 API 密钥**

```bash
export DASHSCOPE_API_KEY="your-dashscope-key"
```

2. **可选：配置 Data-Juicer 路径（用于自定义算子开发）**

```bash
export DATA_JUICER_PATH="your-data-juicer-path"
```

> **提示**：也可以在运行时通过对话设置，例如：
> - "帮我设置 DataJuicer 路径：/path/to/data-juicer"
> - "帮我更新 DataJuicer 路径：/path/to/data-juicer"

## 使用

通过 `-u` 或 `--use-studio` 参数选择运行方式：

```bash
# 使用 AgentScope Studio 的交互式界面（请先安装并启动 AgentScope Studio）
dj-agents --use-studio

# 或直接使用命令行模式（默认）
dj-agents
```

注：

AgentScope Studio 通过 npm 安装：

```bash
npm install -g @agentscope/studio
```

使用以下命令启动 Studio：

```bash
as_studio
```
