"""配置加载：LLM Key / API URL / 模型名 / 最大步数。

优先级: .env 文件 -> 环境变量 -> 默认值。
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    """Agent 运行配置。"""

    llm_api_key: str = "sk-cbf55f613bcb4ec8ad04d58a75730a03"
    llm_api_url: str = "https://api.deepseek.com"
    llm_model: str = "gpt-4o-mini"
    max_steps: int = 5
    stream_char_delay: float = 0.0
    mcp_servers_path: Path = field(default_factory=lambda: PROJECT_ROOT / "mcp_servers.json")

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> "Settings":
        """从 .env 文件与环境变量加载配置。"""
        load_dotenv(env_path or PROJECT_ROOT / ".env")
        return cls(
            llm_api_key=os.getenv("LLM_API_KEY", "sk-cbf55f613bcb4ec8ad04d58a75730a03"),
            llm_api_url=os.getenv("LLM_API_URL", "https://api.deepseek.com"),
            llm_model=os.getenv("LLM_MODEL", "deepseek-v4-flash"),
            max_steps=int(os.getenv("MAX_STEPS", "5")),
            stream_char_delay=float(os.getenv("STREAM_CHAR_DELAY", "0")),
        )
