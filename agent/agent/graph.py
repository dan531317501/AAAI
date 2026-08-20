"""ReAct 状态机：Thought -> Action -> Observation 循环。

graph 结构:

        ┌──────────────┐   有 tool_call    ┌──────────┐
 entry ─▶│   thought    │─────────────────▶│  action  │
        │  (LLM 推理)   │                  │(执行工具) │
        └──────┬───────┘                  └────┬─────┘
               │ 无 tool_call(最终答案)         │
               ▼                              ▼
              END                    ┌────────────────┐
                                     │  observation   │
                                     │ (记录工具结果)  │
                                     └───────┬────────┘
                                             │ 未达最大步数
                                             ▼
                                       回 thought 继续循环

- thought     : LLM 决定"想什么 + 做什么"（bind_tools，每次最多一个工具调用）。
- action      : 用 ToolNode 执行选中的工具。
- observation : 把工具结果写回 state，步数 +1，回到 thought。
- 步数用尽或 LLM 不再调用工具时，输出最终答案并结束。
"""
from typing import List, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from .state import ReActState

SYSTEM_PROMPT = """You are a helpful assistant that solves tasks step by step using the ReAct method.

Follow this loop strictly:
1. Thought: reason about what you know and what you still need.
2. Action: if you need information or need to change something, call exactly ONE tool.
3. Observation: the tool result will be shown to you in the next turn.

Repeat Thought -> Action -> Observation until you can answer the user's question.
When you have enough information, output the final answer as a normal message WITHOUT any tool calls.

Rules:
- You have access to tools: bash, read, write, and any registered MCP tools.
- Call at most one tool per turn.
- If a tool returns an error, read it and adjust your next action.
- Always end with a final answer written in the language the user used.
"""


def build_react_graph(
    llm: BaseChatModel,
    tools: List[BaseTool],
    max_steps: int = 5,
):
    """构建并编译 ReAct 状态机。"""
    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    def _history(state: ReActState) -> List[BaseMessage]:
        return [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]

    # ---- 节点 1: thought ----
    def thought(state: ReActState) -> dict:
        if state.get("step_count", 0) >= state.get("max_steps", max_steps):
            # 达到步数上限：强制输出最终答案（不绑定工具）
            response = llm.invoke(
                _history(state)
                + [
                    HumanMessage(
                        content=(
                            "You have reached the step limit. Summarize what you "
                            "already know and give your best final answer now, "
                            "without calling any tools."
                        )
                    )
                ]
            )
            return {
                "messages": [response],
                "thought": "已达到最大步数，基于已有信息给出最终答案",
                "action": None,
            }

        response = llm_with_tools.invoke(_history(state))
        if response.tool_calls:
            return {
                "messages": [response],
                "thought": response.content or "(调用工具)",
                "action": response.tool_calls[0],
            }
        # 没有工具调用 => 最终答案
        return {
            "messages": [response],
            "thought": response.content or "",
            "action": None,
        }

    def route_after_thought(state: ReActState) -> Literal["action", "__end__"]:
        return "action" if state.get("action") else "__end__"

    # ---- 节点 3: observation ----
    def observation(state: ReActState) -> dict:
        last = state["messages"][-1]
        if isinstance(last, ToolMessage):
            content = last.content
            if isinstance(content, list):  # 部分模型返回 content block 列表
                content = " ".join(str(block.get("text", block)) for block in content)
            obs = str(content)
        else:
            obs = str(last.content)
        return {
            "observation": obs,
            "step_count": state.get("step_count", 0) + 1,
        }

    # ---- 组装 graph ----
    graph = StateGraph(ReActState)
    graph.add_node("thought", thought)
    graph.add_node("action", tool_node)  # 节点 2: action
    graph.add_node("observation", observation)

    graph.set_entry_point("thought")
    graph.add_conditional_edges(
        "thought",
        route_after_thought,
        {"action": "action", "__end__": END},
    )
    graph.add_edge("action", "observation")
    graph.add_edge("observation", "thought")  # 回到 thought 继续循环

    return graph.compile()
