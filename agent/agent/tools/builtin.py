"""内置工具：bash / read / write。"""
import subprocess
from pathlib import Path

from langchain_core.tools import tool


@tool
def bash(command: str) -> str:
    """Execute a shell command (bash -c) and return stdout/stderr.
Use for listing files, running scripts, querying the system, etc."""
    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        return f"[error] command timed out after 60s: {exc}"
    out = (result.stdout or "") + (result.stderr or "")
    if not out.strip():
        return f"(no output, exit code {result.returncode})"
    return out.strip()


@tool("read")
def read_file(path: str) -> str:
    """Read a UTF-8 text file and return its content. Provide the file path."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"[error] file not found: {path}"
    return p.read_text(encoding="utf-8", errors="replace")


@tool("write")
def write_file(path: str, content: str) -> str:
    """Create or overwrite a UTF-8 text file with the given content.
Provide the file path and the full content."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} chars to {path}"


BUILTIN_TOOLS = [bash, read_file, write_file]
