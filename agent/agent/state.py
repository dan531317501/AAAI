"""ReAct 循环的状态定义。

messages          累积的对话消息（用户 / AI / 工具结果）
thought           当前轮次的思考
action            当前轮次的工具调用（None 表示直接给出最终答案）
observation       当前轮次的工具执行结果
step_count        已执行的动作步数
max_steps         动作步数上限
"""
from typing import Annotated, List, Optional, TypedDict

from langchain_core.messages import BaseMessage, ToolCall
from langgraph.graph.message import add_messages


class ReActState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    thought: str
    action: Optional[ToolCall]
    observation: str
    step_count: int
    max_steps: int
