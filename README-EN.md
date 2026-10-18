# MyAgent

A learning-oriented personal agent for understanding **Tool / MCP / Skill**, powered by local Ollama `qwen3.5:9b`.

Inspired by [deepseek-harness](https://github.com/deepseek-ai/deepseek-harness): one Tool registry, an agent loop, and an MCP bridge that registers remote tools as `mcp__server__tool` — without Cordis or a Web UI.

See [README.md](README.md) for the full Chinese guide (concepts, layout, and three demos).

```bash
./scripts/start.sh --ollama-only
conda activate my-agent
pip install -e .
myagent -v chat "compute (12 * 34) + 5"
myagent tools
myagent skills
```
