"""
Phase 2.1: 数据源搜索与注册。

职责:
- init_sources(): 创建骨架 sources.yaml
- validate_sources(): Schema 验证
- add_source() / mark_broken_source(): 修改注册表
- search_for_sources(): 为 key_factor 搜索数据源（供 LLM 编排调用）

注意: 实际的数据源 URL 发现由 LLM + WebFetch 在 SKILL.md 编排中完成，
本脚本负责结构化存储和验证。
"""

from datetime import date
from pathlib import Path
from typing import Optional


VALID_FREQUENCIES = {"daily", "weekly", "monthly", "quarterly", "annual", "on_change"}
VALID_SELECTOR_TYPES = {"api", "css_selector", "rss", "json_endpoint"}


class SourceEntry:
    """Structured source entry."""

    def __init__(self, source_id: str, name: str, url: str,
                 fallback_url: str = "", frequency: str = "daily",
                 selector_type: str = "api", parser: Optional[str] = None):
        self.id = source_id
        self.name = name
        self.url = url
        self.fallback_url = fallback_url
        self.frequency = frequency
        self.selector_type = selector_type
        self.parser = parser

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "fallback_url": self.fallback_url,
            "frequency": self.frequency,
            "selector_type": self.selector_type,
            "parser": self.parser,
        }


def validate_sources(sources: dict) -> list[str]:
    """Validate sources.yaml structure. Returns list of error messages."""
    errors = []

    if "sources" not in sources:
        errors.append("Missing 'sources' key")
        return errors

    if "meta" not in sources:
        errors.append("Missing 'meta' key")
        return errors

    all_ids = set()

    for node_id, source_list in sources["sources"].items():
        for i, src in enumerate(source_list):
            prefix = f"sources.{node_id}[{i}]"

            if "id" not in src:
                errors.append(f"{prefix}: missing 'id'")
            else:
                if src["id"] in all_ids:
                    errors.append(f"{prefix}: duplicate source id '{src['id']}'")
                all_ids.add(src["id"])

            if "name" not in src:
                errors.append(f"{prefix}: missing 'name'")

            if "url" not in src or not src["url"]:
                errors.append(f"{prefix}: missing or empty 'url'")

            freq = src.get("frequency", "")
            if not freq:
                errors.append(f"{prefix}: missing 'frequency'")
            elif freq not in VALID_FREQUENCIES:
                errors.append(f"{prefix}: invalid frequency '{freq}', must be one of {VALID_FREQUENCIES}")

    return errors


def init_sources(output_path: Path):
    """Create a skeleton sources.yaml. Does NOT overwrite existing."""
    if output_path.exists():
        return

    skeleton = {
        "sources": {},
        "meta": {
            "last_verified": str(date.today()),
            "broken_sources": [],
        },
    }
    from utils import save_yaml
    save_yaml(output_path, skeleton)


def add_source(sources: dict, node_id: str, entry: dict) -> dict:
    """Add a source entry to the sources registry for a given node."""
    if node_id not in sources["sources"]:
        sources["sources"][node_id] = []
    sources["sources"][node_id].append(entry)
    return sources


def mark_broken_source(sources: dict, node_id: str, source_id: str) -> dict:
    """Remove a broken source from its node and add to broken_sources list."""
    if node_id in sources.get("sources", {}):
        node_sources = sources["sources"][node_id]
        sources["sources"][node_id] = [
            s for s in node_sources if s.get("id") != source_id
        ]
    if source_id not in sources["meta"].get("broken_sources", []):
        sources["meta"].setdefault("broken_sources", []).append(source_id)
    return sources


def search_for_sources(node_name: str, key_factor: str, industry: str) -> list[dict]:
    """
    Template function for searching data sources for a key_factor.

    This is a NO-OP function that returns an empty list. The actual search
    is performed by LLM + WebFetch in the SKILL.md workflow. This function
    exists to provide the interface contract.

    Returns a list of candidate source dicts with: title, url, description.
    """
    return []
