"""
Phase 1: 产业链发现与建模工具。

职责:
- init_chain(): 创建骨架 chain.yaml
- validate_chain(): Schema 验证
- load_chain() / save_chain(): 读写 chain.yaml

注意: chain.yaml 的实际内容（nodes, edges, supports）由 LLM 在 SKILL.md
编排流程中生成并写入，本脚本只负责结构验证和骨架初始化。
"""

from datetime import date
from pathlib import Path
from typing import Any


class ChainValidationError(Exception):
    """Raised when chain.yaml fails validation."""
    pass


def validate_chain(chain: dict) -> list[str]:
    """Validate chain.yaml structure. Returns list of error messages (empty = valid)."""
    errors = []

    # Top-level keys
    for key in ["industry", "nodes", "edges", "supports"]:
        if key not in chain or not chain[key] if key != "supports" else False:
            if key != "supports":
                errors.append(f"Missing required top-level key: '{key}'")

    if "supports" not in chain:
        errors.append("Missing top-level key: 'supports'")

    if "nodes" not in chain or not isinstance(chain.get("nodes"), list):
        errors.append("'nodes' must be a non-empty list")
        return errors

    # Validate nodes
    node_ids = set()
    for i, node in enumerate(chain["nodes"]):
        prefix = f"nodes[{i}]"
        if "id" not in node:
            errors.append(f"{prefix}: missing 'id'")
        else:
            nid = node["id"]
            if nid in node_ids:
                errors.append(f"{prefix}: duplicate node id '{nid}'")
            node_ids.add(nid)

        if "name" not in node:
            errors.append(f"{prefix}: missing 'name'")

        kf = node.get("key_factors", [])
        if not isinstance(kf, list) or len(kf) == 0:
            errors.append(f"{prefix}: 'key_factors' must be a non-empty list")

        layer = node.get("layer")
        if not isinstance(layer, int):
            errors.append(f"{prefix}: 'layer' must be an integer, got {type(layer).__name__}")

    # Validate edges: from/to must reference existing nodes
    if isinstance(chain.get("edges"), list):
        for i, edge in enumerate(chain["edges"]):
            prefix = f"edges[{i}]"
            for direction in ["from", "to"]:
                ref = edge.get(direction, "")
                if ref and ref not in node_ids:
                    errors.append(f"{prefix}: '{direction}' references unknown node '{ref}'")
                elif not ref:
                    errors.append(f"{prefix}: missing '{direction}'")

    # Validate supports: affects must reference existing nodes
    if isinstance(chain.get("supports"), list):
        for i, sup in enumerate(chain["supports"]):
            prefix = f"supports[{i}]"
            if "id" not in sup:
                errors.append(f"{prefix}: missing 'id'")
            affects = sup.get("affects", [])
            for ref in affects:
                if ref not in node_ids:
                    errors.append(f"{prefix}: 'affects' references unknown node '{ref}'")

    return errors


def validate_or_raise(chain: dict):
    """Validate and raise ChainValidationError if invalid."""
    errors = validate_chain(chain)
    if errors:
        raise ChainValidationError("\n".join(errors))


def init_chain(industry: str, output_path: Path):
    """Create a skeleton chain.yaml. Does NOT overwrite existing files."""
    if output_path.exists():
        return  # Don't overwrite

    skeleton = {
        "industry": industry,
        "description": f"{industry}产业链（待完善）",
        "discovery_date": str(date.today()),
        "nodes": [],
        "edges": [],
        "supports": [],
        "meta": {
            "version": 1,
            "last_updated": str(date.today()),
        },
    }
    save_chain(skeleton, output_path)


def load_chain(path: Path) -> dict:
    """Load chain.yaml from path."""
    import yaml
    if not path.exists():
        raise FileNotFoundError(f"chain.yaml not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        raise ValueError(f"Empty or invalid YAML: {path}")
    return data


def save_chain(chain: dict, path: Path):
    """Save chain dict to path as YAML."""
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(chain, f, allow_unicode=True, sort_keys=False,
                       default_flow_style=False)
