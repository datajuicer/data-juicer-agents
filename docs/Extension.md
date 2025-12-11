# Customization and Extension

## Custom Prompts

All Agent system prompts are defined in the `prompts.py` file.

## Model Replacement

You can specify different models for different Agents in `main.py`. For example:
- Main Agent uses `qwen-max` for complex reasoning
- Development Agent uses `qwen3-coder-480b-a35b-instruct` to optimize code generation quality

At the same time, Formatter and Memory can also be replaced. This design allows the system to be both out-of-the-box and adaptable to enterprise-level requirements.

## Extending New Agents

DataJuicer Agents is an open framework. The core is the `agents2toolkit` function—it can automatically wrap any Agent as a tool callable by the Router.

Simply add your Agent instance to the `agents` list, and the Router will dynamically generate corresponding tools at runtime and automatically route based on task semantics.

This means you can quickly build domain-specific data agents based on this framework.

*Extensibility is an important design principle*.
