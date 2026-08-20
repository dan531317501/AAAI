"""通过 langchain-mcp-adapters 注册 MCP 工具。

在项目根目录的 mcp_servers.json 中配置 MCP 服务器：

- stdio 方式（本地进程）:
  {
    "mcpServers": {
      "math": {"command": "python", "args": ["/path/to/mcp_math_server.py"]}
    }
  }

- HTTP 方式（远程服务）:
  {
    "mcpServers": {
      "weather": {"url": "http://localhost:8000/mcp", "transport": "streamable_http"}
    }
  }

加载成功后，MCP 暴露的工具会与内置工具一起注册到 Agent。
"""
import json
from pathlib import Path
from typing import List, Optional

from langchain_core.tools import BaseTool


async def load_mcp_tools(servers_path: Optional[Path] = None) -> List[BaseTool]:
    """读取 mcp_servers.json 并返回其中注册的全部 MCP 工具（无配置时返回空列表）。"""
    servers_path = Path(servers_path) if servers_path else None
    if servers_path is None or not servers_path.exists():
        return []

    config = json.loads(servers_path.read_text(encoding="utf-8"))
    servers = config.get("mcpServers", {}) or {}
    if not servers:
        return []

    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(servers)
    tools = await client.get_tools()
    return list(tools)
