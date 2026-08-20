# react-agent — 简单版 LangGraph ReAct Agent

一个基于 [LangGraph](https://github.com/langchain-ai/langgraph) 的最小可运行 Agent 项目：

- ✅ 可配置 LLM Key 和 API URL（任意 OpenAI 兼容端点，如 OpenAI / DeepSeek / Qwen / Moonshot）
- ✅ 定义了一套 ReAct 流程：**Thought → Action → Observation** 循环
- ✅ 注册内置工具：`bash`、`read`、`write`
- ✅ 支持注册 MCP 工具（stdio / HTTP）

## 项目结构

```
agent/
├── pyproject.toml            # 依赖与入口 (react-agent 命令)
├── .env.example              # LLM 配置模板
├── mcp_servers.json          # MCP 服务器配置
├── agent/                    # 包
│   ├── config.py             # 配置加载 (LLM Key / API URL / 模型 / 步数)
│   ├── llm.py                # 构建 ChatOpenAI（支持自定义 base_url）
│   ├── callbacks.py          # 流式输出回调（逐 token 打印思考/回答）
│   ├── state.py              # ReActState 状态定义
│   ├── graph.py              # ReAct 状态机: thought -> action -> observation
│   ├── main.py               # CLI 入口（交互式 / 单次提问）
│   └── tools/
│       ├── builtin.py        # 内置工具: bash / read / write
│       └── mcp_tools.py      # MCP 工具注册 (langchain-mcp-adapters)
└── scripts/
    └── smoke_test.py         # 离线冒烟测试（假 LLM，无需 API Key）
```

## 快速开始

```bash
cd agent

# 方式一：uv（推荐）
uv sync

# 方式二：pip
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## 配置 LLM

```bash
cp .env.example .env
# 编辑 .env：
#   LLM_API_KEY=sk-xxx
#   LLM_API_URL=https://api.openai.com/v1
#   LLM_MODEL=gpt-4o-mini
#   MAX_STEPS=5
```

| 环境变量 | 说明 | 默认值 |
| --- | --- | --- |
| `LLM_API_KEY` | LLM API Key | 空 |
| `LLM_API_URL` | OpenAI 兼容 API 地址（以 `/v1` 结尾） | `https://api.openai.com/v1` |
| `LLM_MODEL` | 模型名 | `gpt-4o-mini` |
| `MAX_STEPS` | ReAct 循环最大步数 | `5` |

## 运行

```bash
# 交互式对话（exit / quit / Ctrl-D 退出）
uv run react-agent

# 单次提问
uv run react-agent "当前目录下有哪些文件？"
```

示例输出（LLM 输出逐 token 实时打印）：

```
🧭 第 1 轮 | 你: 当前目录下有哪些文件？
  💬 我需要列出当前目录的文件 ✓
  ⚡ Action: bash({'command': 'ls -la'})
  👀 Observation: total 0
  drwxr-xr-x  2 user  staff  64 ...
  💬 当前目录下有一个文件 foo.txt ✓
```

## 流式输出

- LLM 输出（Thought 文本 / 最终答案）通过 `agent/callbacks.py` 的
  `StreamingConsoleHandler` 逐 token 实时打印，无需等待整轮结束。
- 设置 `STREAM_CHAR_DELAY`（秒）> 0 可开启逐字打字机效果；0 为按 token 即时输出。
- 思考内容（reasoning）兼容提取 `additional_kwargs["reasoning_content"]`
  与 Responses API 的 reasoning/summary 块。
- ⚠️ 注意：标准 `ChatOpenAI` 按 OpenAI 官方协议解析，**不提取** DeepSeek 等
  第三方端点的 `reasoning_content` 字段。若用 DeepSeek 推理模型并想看思考过程，
  建议改用 `langchain-deepseek` 包的 `ChatDeepSeek`（把 `llm.py` 里的
  `ChatOpenAI` 换成 `ChatDeepSeek`，其余参数一致，回调已兼容）。

## ReAct 流程

LangGraph 状态机定义在 `agent/graph.py`，三个节点循环：

```
entry ─▶ thought ──(有工具调用)──▶ action ──▶ observation ──▶ 回 thought
            │                                              ▲
            └──(无工具调用=最终答案)──▶ END ─────────────────┘
```

| 节点 | 职责 |
| --- | --- |
| `thought` | LLM 绑定工具后推理：决定"想什么 + 做什么"；不调用工具即输出最终答案 |
| `action` | 用 `ToolNode` 执行选中的工具（每轮最多 1 个） |
| `observation` | 记录工具结果、步数 +1，回到 `thought`；步数用尽时强制输出最终答案 |

每次循环的状态（`agent/state.py`）都会记录 `thought / action / observation`，便于调试与展示。

## 内置工具

| 工具 | 说明 |
| --- | --- |
| `bash` | 执行 shell 命令（bash -c，60s 超时），返回 stdout/stderr |
| `read` | 读取 UTF-8 文本文件 |
| `write` | 创建/覆盖 UTF-8 文本文件 |

## 注册 MCP 工具

编辑项目根目录的 `mcp_servers.json`：

```json
{
  "mcpServers": {
    "math": {
      "command": "python",
      "args": ["/path/to/mcp_math_server.py"]
    },
    "weather": {
      "url": "http://localhost:8000/mcp",
      "transport": "streamable_http"
    }
  }
}
```

启动时 Agent 会通过 `MultiServerMCPClient` 拉取所有 MCP 工具，并与内置工具一起注册：

```
已注册工具 (5): bash, read, write, add, get_weather
```

## 验证（无需 API Key）

```bash
uv run python scripts/smoke_test.py
# ✅ 冒烟测试通过：ReAct 流程 Thought -> Action -> Observation 正常
```
