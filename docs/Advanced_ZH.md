# 高级功能

## 算子检索

算子检索是 Agent 能否精准工作的核心。DJ 智能体实现了一个智能算子检索工具，通过独立的 LLM 查询环节从 Data-Juicer 的近200个算子中快速找到最相关的算子。这是数据处理智能体和代码开发智能体能够准确运行的关键组件。

我们没有采用单一方案，而是提供了三种模式，通过 `-r` 参数灵活选择：

### 检索模式

**LLM 检索 (默认)**
- 使用 Qwen-Turbo 从语义层面理解用户需求，适合复杂、模糊的描述
- 提供详细的匹配理由和相关性评分
- Token 消耗较高，但匹配精度最高

**向量检索 (vector)**
- 基于 DashScope 文本嵌入 + FAISS 相似度搜索
- 速度快，适合批量任务或快速原型
- 无需调用 LLM，成本更低

**自动模式 (auto)**
- 优先尝试 LLM 检索，失败时自动降级到向量检索

### 使用

通过 `-r` 或 `--retrieval-mode` 参数指定检索模式：

```bash
dj-agents --retrieval-mode vector
```

更多参数说明见 `dj-agents --help`

## MCP 智能体

除了命令行，DataJuicer 还原生支持 MCP 服务，这是提升性能的重要手段。MCP 服务可直接通过原生接口获取算子信息、执行数据处理，易于迁移和集成，无需单独的 LLM 查询和命令行调用。

### MCP 服务器类型

Data-Juicer 提供两类 MCP：

**Recipe-Flow MCP（数据菜谱）**
- 提供 `get_data_processing_ops` 和 `run_data_recipe` 两个工具
- 通过算子类型、适用模态等标签进行检索，**无需调用 LLM 或向量模型**
- 适合标准化、高频场景，性能更优

**Granular-Operators MCP（细粒度算子）**
- 将每个内置算子包装为独立工具，调用即运行
- 默认返回所有算子，但可通过环境变量控制可见范围
- 适合精细化控制，构建完全定制化的数据处理管道

这意味着，在某些场景下，Agent 的调用路径可以比手动写 YAML *更短、更快、更直接*。

详细信息请参考：[Data-Juicer MCP 服务文档](https://datajuicer.github.io/data-juicer/zh_CN/main/docs/DJ_service_ZH.html#mcp)

> **注意**：Data-Juicer MCP 服务器目前处于早期开发阶段，功能和工具可能会随着持续开发而变化。

### 配置

在 `configs/mcp_config.json` 中配置服务地址：

```json
{
    "mcpServers": {
        "DJ_recipe_flow": {
            "url": "http://127.0.0.1:8080/sse"
        }
    }
}
```

### 使用方法

启用 MCP 智能体替代数据处理智能体：

```bash
# 启用 MCP 智能体和开发智能体
dj-agents --agents dj_mcp dj_dev

# 或使用简写
dj-agents -a dj_mcp dj_dev

```
