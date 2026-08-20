"""离线冒烟测试：用假 LLM 验证 ReAct 流程（无需 API Key）。

验证: thought(工具调用) -> action(执行 read 工具) -> observation -> thought(最终答案)。
"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage

from agent.graph import build_react_graph
from agent.tools.builtin import BUILTIN_TOOLS


class FakeReActModel(FakeMessagesListChatModel):
    """假 LLM：bind_tools 直接透传，按预设回复序列依次返回。"""

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001
        return self


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "hello.txt"
        p.write_text("hello react", encoding="utf-8")

        fake_llm = FakeReActModel(
            responses=[
                AIMessage(
                    content="我需要读取文件内容",
                    tool_calls=[{"name": "read", "args": {"path": str(p)}, "id": "call-1"}],
                ),
                AIMessage(content="文件内容是: hello react"),
            ]
        )

        graph = build_react_graph(fake_llm, BUILTIN_TOOLS, max_steps=3)
        state = {
            "messages": [HumanMessage(content="读取文件并告诉我内容")],
            "thought": "",
            "action": None,
            "observation": "",
            "step_count": 0,
            "max_steps": 3,
        }
        result = await graph.ainvoke(state)

        assert result["step_count"] == 1, f"step_count={result['step_count']}"
        assert "hello react" in result["observation"], f"observation={result['observation']}"
        assert "hello react" in str(result["messages"][-1].content)

        print("✅ 冒烟测试通过：ReAct 流程 Thought -> Action -> Observation 正常")
        print(f"   thought     : 我需要读取文件内容")
        print(f"   action      : read(path={p})")
        print(f"   observation : {result['observation']}")
        print(f"   answer      : {result['messages'][-1].content}")


if __name__ == "__main__":
    asyncio.run(main())
