# MyAgent

从零理解 **Tool / MCP / Skill** 的学习型个人 Agent。模型默认使用本地 Ollama 的 `qwen3.5:9b`。

架构刻意对齐 [deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) 的核心思想：**统一 Tool 注册表 + Agent 循环 + MCP 桥把外部能力注册进同一张表**，但不引入 Cordis / Web UI，方便把原理跑通。

## 三者关系

| 概念 | 本项目里是什么 | 解决什么问题 |
|------|----------------|--------------|
| **Tool** | `ToolSpec`（JSON Schema + `execute`） | 模型「能调用什么」 |
| **MCP** | stdio 客户端把远端工具注册为 `mcp__server__tool` | 把别人的能力变成本地 Tool，无需改 Loop |
| **Skill** | `skills/*/SKILL.md`（提示 + 可选 tools 白名单） | 教模型「何时用什么」 |

一句话：**Skill 管提示与可见工具集；Tool 是可执行能力；MCP 是把外部 Tool 灌进 Registry 的协议桥。**

```text
User → AgentLoop → Ollama(qwen3.5)
              ↓
         ToolRegistry
         ├── builtin (calculator / now / read_file / list_dir)
         └── MCP bridge → mcp/demo_server.py (add / echo)
              ↑
         SkillLoader (注入 system + 可选 allowlist)
```

## 快速开始

### 1. 准备模型

```bash
./scripts/start.sh --ollama-only
# 或
./scripts/ollama_qwen3.5.sh
```

确保 `.env`（可参考 `.env.example`）中有：

```bash
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:9b
```

### 2. 安装（conda 环境 `my-agent`）

```bash
conda activate my-agent
pip install -e .
```

### 3. 跑通三条路径

**Tool（内置计算器）**

```bash
myagent -v chat "算一下 (12 * 34) + 5"
```

verbose 下应看到 `calculator` 被调用，再返回答案。

**MCP（demo server）**

默认在 `config/default.yaml` 启用了 `demo`：

```bash
myagent tools
# 应看到 mcp__demo__add、mcp__demo__echo
myagent -v chat "用 MCP 的 add 把 19 和 23 加起来"
```

**Skill（hello-math）**

```bash
myagent skills
myagent -v chat "帮我验算 99*99"
# verbose 中应出现 skills: hello-math
```

一键启动（激活 conda `my-agent` → 检查/拉起 Ollama 与 `qwen3.5:9b` → 进入对话）：

```bash
./scripts/start.sh
./scripts/start.sh -v                 # verbose：看 tool / skill 调用
./scripts/start.sh "算一下 1+1"       # 单次提问
./scripts/start.sh -- tools           # 透传其它子命令
```

已在环境中时也可直接：`myagent chat`。REPL 内可用 `/tools` `/skills` `/clear` `/quit`。

## 代码地图

| 路径 | 职责 |
|------|------|
| `src/myagent/tools/` | Tool 契约、Registry、内置工具 |
| `src/myagent/llm/ollama.py` | Ollama `/api/chat` + tools |
| `src/myagent/agent/loop.py` | 多轮 tool loop（对应 harness 的 agent-loop） |
| `src/myagent/mcp/client.py` | MCP stdio 桥（对应 dsh-mcp-client） |
| `mcp/demo_server.py` | 最小 MCP server |
| `src/myagent/skills/loader.py` | 解析 / 匹配 `SKILL.md` |
| `skills/hello-math/SKILL.md` | 示例 Skill |
| `config/default.yaml` | 模型、轮次、MCP servers |

## 怎么扩展

1. **加内置 Tool**：在 `tools/builtin.py` 用 `@define_tool` 写函数，并 `registry.register`。
2. **加 MCP**：在 `config/default.yaml` 的 `mcp.servers` 增加一条 stdio 配置；重启后工具名自动变成 `mcp__名字__工具`。
3. **加 Skill**：新建 `skills/你的技能/SKILL.md`（YAML frontmatter + 正文）。`tools:` 可限制本 skill 激活时暴露的内置工具（MCP 工具仍保留，便于学习）。

## 设计取舍（学习版）

- 用官方 `mcp` Python SDK，不手写 JSON-RPC。
- Skill 匹配是关键词/描述重叠，不是向量检索。
- 不做子 Agent、权限 UI、HMR；这些是 harness 生产能力，原理理解后再加。

## 参考

- [deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) — everything is a plugin / `mcp__server__tool`
- [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling)
- [Model Context Protocol](https://modelcontextprotocol.io/)
