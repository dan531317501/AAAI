"""LLM 流式输出回调：把生成内容逐 token 打印到控制台。

通过 config={"callbacks": [handler]} 传入 graph，LangGraph 会把回调
传播到 thought 节点内的每次 LLM 调用。

说明:
- LLM 流式输出的最小单位是 token，不是字符；设置 char_delay > 0 时
  会对每个 token 拆字符 + 延时，模拟打字机效果。
- 思考内容(reasoning)的提取做了兼容兜底:
  * additional_kwargs["reasoning_content"]  —— DeepSeek 等 provider 专用包
    (langchain-deepseek 的 ChatDeepSeek) 会放这里;
  * additional_kwargs["reasoning"/"reasoning_details"] 块 —— Responses API
    的 thinking/summary 块。
  注意: 标准 ChatOpenAI 只按 OpenAI 官方协议解析, 不提取第三方端点
  (如 DeepSeek) 的 reasoning_content 字段, 见 langchain_openai 文档警告。
"""
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler


def _extract_reasoning(chunk: Any) -> str:
    """从流式 chunk 里提取思考内容（拿不到时返回空串）。"""
    if chunk is None:
        return ""
    additional = getattr(chunk, "additional_kwargs", {}) or {}
    if isinstance(additional.get("reasoning_content"), str):
        return additional["reasoning_content"]
    blocks = additional.get("reasoning") or additional.get("reasoning_details")
    if isinstance(blocks, list):
        parts = []
        for block in blocks:
            if isinstance(block, dict):
                parts.append(str(block.get("summary") or block.get("text") or ""))
        return "".join(parts)
    return ""


class StreamingConsoleHandler(BaseCallbackHandler):
    """把 LLM 输出（思考/回答）逐 token 打印到控制台。

    char_delay: 每个字符的打印延时（秒），0 表示按 token 即时输出；
                大于 0 时模拟逐字打字机效果。
    """

    def __init__(
        self,
        char_delay: float = 0.0,
        answer_prefix: str = "  💬 ",
        thinking_prefix: str = "  🧠 Thinking: ",
    ) -> None:
        super().__init__()
        self.char_delay = char_delay
        self.answer_prefix = answer_prefix
        self.thinking_prefix = thinking_prefix
        self._thinking_open = False
        self._answer_open = False

    def _emit(self, text: str) -> None:
        if self.char_delay > 0:
            for ch in text:
                print(ch, end="", flush=True)
                time.sleep(self.char_delay)
        else:
            print(text, end="", flush=True)

    def on_llm_new_token(self, token: str, *, chunk: Any = None, **kwargs: Any) -> None:
        reasoning = _extract_reasoning(chunk)
        if reasoning:
            if not self._thinking_open:
                if self._answer_open:
                    print()  # 结束上一段回答行
                    self._answer_open = False
                print(self.thinking_prefix, end="", flush=True)
                self._thinking_open = True
            self._emit(reasoning)
        elif token:
            if not self._answer_open:
                if self._thinking_open:
                    print()  # 思考结束，另起一行打印回答
                    self._thinking_open = False
                print(self.answer_prefix, end="", flush=True)
                self._answer_open = True
            self._emit(token)

    def on_llm_end(self, *args: Any, **kwargs: Any) -> None:
        if self._thinking_open or self._answer_open:
            print(" ✓")
            self._thinking_open = False
            self._answer_open = False
