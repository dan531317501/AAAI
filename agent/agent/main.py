"""ReAct Agent CLI。

用法:
    react-agent                     # 交互式对话
    react-agent "帮我看看当前目录"    # 单次提问
    python -m agent.main "问题"      # 等价方式
"""
import asyncio
import sys

from langchain_core.messages import HumanMessage

from .callbacks import StreamingConsoleHandler
from .config import Settings
from .graph import build_react_graph
from .llm import build_llm
from .state import ReActState
from .tools import BUILTIN_TOOLS, load_mcp_tools

BANNER = r"""
  ____           _              _
 |  _ \ ___ __ _| |_      __ _ / _| __ _  __ _
 | |_) / _ \/ _` | __|    / _` | |_ / _` |/ _` |
 |  _ <  __/ (_| | |_ _  | (_| |  _| (_| | (_| |
 |_| \_\___|\__,_|\__( )  \__,_|_|  \__,_|\__, |
                     |/                   |___/
        LangGraph ReAct Agent (Thought -> Action -> Observation)
"""


def _fmt(text: str, limit: int = 300) -> str:
    text = str(text).strip()
    return text if len(text) <= limit else text[:limit] + "..."


async def run_question(graph, question: str, step_no: int, settings: Settings) -> None:
    """运行一次提问：LLM 输出由回调逐 token 流式打印，节点层打印 Action/Observation。"""
    state: ReActState = {
        "messages": [HumanMessage(content=question)],
        "thought": "",
        "action": None,
        "observation": "",
        "step_count": 0,
        "max_steps": settings.max_steps,
    }

    print(f"\n🧭 第 {step_no} 轮 | 你: {question}")
    handler = StreamingConsoleHandler(char_delay=settings.stream_char_delay)
    prev_action, prev_obs = None, ""

    async for value in graph.astream(
        state,
        stream_mode="values",
        config={"callbacks": [handler]},  # 回调随 config 传播到 thought 节点内的 LLM 调用
    ):
        action = value.get("action")
        obs = value.get("observation", "")
        if action != prev_action:
            if action:
                print(f"  ⚡ Action: {action['name']}({action['args']})")
            prev_action = action
        if obs and obs != prev_obs:
            print(f"  👀 Observation: {_fmt(obs, 500)}")
            prev_obs = obs

    print()  # 轮次结束空行分隔


async def async_main() -> None:
    settings = Settings.from_env()
    print(BANNER)
    print(f"  LLM      : {settings.llm_model} @ {settings.llm_api_url}")
    print(f"  最大步数 : {settings.max_steps}")
    if not settings.llm_api_key:
        print("  ⚠️  未检测到 LLM_API_KEY（请复制 .env.example 为 .env 并填写）\n")

    llm = build_llm(settings)
    tools = list(BUILTIN_TOOLS) + await load_mcp_tools(settings.mcp_servers_path)
    print(f"  已注册工具 ({len(tools)}): {', '.join(t.name for t in tools)}\n")

    graph = build_react_graph(llm, tools, settings.max_steps)

    question = " ".join(sys.argv[1:]).strip()
    if question:
        await run_question(graph, question, 1, settings)
        return

    step_no = 1
    while True:
        try:
            question = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见 👋")
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit", "退出"}:
            print("再见 👋")
            break
        await run_question(graph, question, step_no, settings)
        step_no += 1


def run() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    run()
