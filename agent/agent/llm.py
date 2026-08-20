"""构建 LLM 客户端（OpenAI 兼容端点，支持任意 base_url）。"""
from langchain_openai import ChatOpenAI

from .config import Settings


def build_llm(settings: Settings) -> ChatOpenAI:
    """根据配置构建 ChatOpenAI 实例。"""
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key or "sk-placeholder",
        base_url=settings.llm_api_url,
        temperature=0,
        streaming=True,
    )
