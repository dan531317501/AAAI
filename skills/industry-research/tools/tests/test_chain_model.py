"""Tests for chain.yaml model validation."""

import tempfile
from pathlib import Path

import pytest

# Import from the tools directory
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_chain import validate_chain, init_chain, load_chain, ChainValidationError


VALID_CHAIN = {
    "industry": "测试行业",
    "description": "用于测试的示例产业链",
    "nodes": [
        {"id": "raw_a", "name": "原料A", "key_factors": ["价格", "产能"], "layer": -2},
        {"id": "comp_b", "name": "部件B", "key_factors": ["良率"], "layer": -1},
        {"id": "prod_c", "name": "产品C", "key_factors": ["销量", "价格"], "layer": 0},
        {"id": "consumer", "name": "消费者", "key_factors": ["需求", "偏好"], "layer": 1},
    ],
    "edges": [
        {"from": "raw_a", "to": "comp_b", "type": "upstream", "mechanism": "原料→部件"},
        {"from": "comp_b", "to": "prod_c", "type": "upstream", "mechanism": "部件→产品"},
        {"from": "prod_c", "to": "consumer", "type": "downstream", "mechanism": "产品→消费者"},
    ],
    "supports": [
        {"id": "policy", "name": "政策", "affects": ["prod_c"], "key_factors": ["补贴"]},
    ],
}


class TestValidateChain:
    """Test chain.yaml schema validation."""

    def test_valid_chain_passes(self):
        errors = validate_chain(VALID_CHAIN)
        assert len(errors) == 0

    def test_missing_industry_name(self):
        chain = {k: v for k, v in VALID_CHAIN.items() if k != "industry"}
        errors = validate_chain(chain)
        assert any("industry" in e.lower() for e in errors)

    def test_missing_nodes(self):
        chain = {k: v for k, v in VALID_CHAIN.items() if k != "nodes"}
        errors = validate_chain(chain)
        assert any("nodes" in e.lower() for e in errors)

    def test_node_missing_id(self):
        chain = dict(VALID_CHAIN)
        chain["nodes"] = [{"name": "无ID节点", "key_factors": ["x"], "layer": 0}]
        errors = validate_chain(chain)
        assert any("id" in e.lower() for e in errors)

    def test_edge_references_invalid_node(self):
        chain = dict(VALID_CHAIN)
        chain["edges"] = [{"from": "nonexistent", "to": "prod_c", "type": "upstream", "mechanism": "x"}]
        errors = validate_chain(chain)
        assert any("nonexistent" in e for e in errors)

    def test_support_references_invalid_node(self):
        chain = dict(VALID_CHAIN)
        chain["supports"] = [{"id": "x", "name": "X", "affects": ["ghost_node"], "key_factors": ["y"]}]
        errors = validate_chain(chain)
        assert any("ghost_node" in e for e in errors)

    def test_empty_key_factors(self):
        chain = dict(VALID_CHAIN)
        chain["nodes"][0]["key_factors"] = []
        errors = validate_chain(chain)
        assert any("key_factors" in e.lower() for e in errors)

    def test_layer_is_not_integer(self):
        chain = dict(VALID_CHAIN)
        chain["nodes"][0]["layer"] = "upstream"
        errors = validate_chain(chain)
        assert any("layer" in e.lower() for e in errors)

    def test_duplicate_node_ids(self):
        chain = dict(VALID_CHAIN)
        chain["nodes"].append({"id": "raw_a", "name": "重复", "key_factors": ["x"], "layer": 0})
        errors = validate_chain(chain)
        assert any("duplicate" in e.lower() or "重复" in e for e in errors)


class TestInitChain:
    """Test chain initialization."""

    def test_init_creates_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.yaml"
            init_chain("测试行业", path)
            assert path.exists()
            chain = load_chain(path)
            assert chain["industry"] == "测试行业"
            assert "nodes" in chain
            assert "edges" in chain
            assert "supports" in chain
            assert "meta" in chain

    def test_init_does_not_overwrite_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.yaml"
            init_chain("行业A", path)
            init_chain("行业B", path)  # Should keep the first
            chain = load_chain(path)
            assert chain["industry"] == "行业A"


class TestLoadSave:
    """Test load/save round-trip."""

    def test_save_and_load_chain(self):
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.yaml"
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from fetch_chain import save_chain
            save_chain(VALID_CHAIN, path)
            loaded = load_chain(path)
            assert loaded["industry"] == VALID_CHAIN["industry"]
            assert len(loaded["nodes"]) == len(VALID_CHAIN["nodes"])
            assert len(loaded["edges"]) == len(VALID_CHAIN["edges"])
