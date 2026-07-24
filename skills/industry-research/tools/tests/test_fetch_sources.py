"""Tests for data source registration."""

import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_sources import (
    init_sources,
    validate_sources,
    add_source,
    mark_broken_source,
    SourceEntry,
)


VALID_SOURCE = {
    "id": "test_source",
    "name": "Test Source",
    "url": "https://example.com/data",
    "fallback_url": "https://example.com/backup",
    "frequency": "daily",
    "selector_type": "api",
    "parser": None,
}


class TestValidateSources:
    """Test sources.yaml validation."""

    def test_valid_source_passes(self):
        sources = {"sources": {"node_a": [VALID_SOURCE]}, "meta": {"last_verified": "2026-07-24", "broken_sources": []}}
        errors = validate_sources(sources)
        assert len(errors) == 0

    def test_missing_url(self):
        s = dict(VALID_SOURCE)
        del s["url"]
        sources = {"sources": {"n": [s]}, "meta": {"last_verified": "", "broken_sources": []}}
        errors = validate_sources(sources)
        assert any("url" in e.lower() for e in errors)

    def test_missing_id(self):
        s = dict(VALID_SOURCE)
        del s["id"]
        sources = {"sources": {"n": [s]}, "meta": {"last_verified": "", "broken_sources": []}}
        errors = validate_sources(sources)
        assert any("id" in e.lower() for e in errors)

    def test_missing_frequency(self):
        s = dict(VALID_SOURCE)
        del s["frequency"]
        sources = {"sources": {"n": [s]}, "meta": {"last_verified": "", "broken_sources": []}}
        errors = validate_sources(sources)
        assert any("frequency" in e.lower() for e in errors)

    def test_duplicate_source_id(self):
        sources = {"sources": {"n": [VALID_SOURCE, VALID_SOURCE]}, "meta": {"last_verified": "", "broken_sources": []}}
        errors = validate_sources(sources)
        assert any("duplicate" in e.lower() for e in errors)

    def test_invalid_frequency_value(self):
        s = dict(VALID_SOURCE)
        s["frequency"] = "hourly"
        sources = {"sources": {"n": [s]}, "meta": {"last_verified": "", "broken_sources": []}}
        errors = validate_sources(sources)
        assert any("hourly" in e for e in errors)


class TestInitSources:
    """Test sources initialization."""

    def test_creates_skeleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.yaml"
            init_sources(path)
            assert path.exists()
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)
            assert "sources" in data
            assert "meta" in data

    def test_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.yaml"
            init_sources(path)
            mtime1 = path.stat().st_mtime
            init_sources(path)
            mtime2 = path.stat().st_mtime
            assert mtime1 == mtime2


class TestAddSource:
    """Test adding a source to registry."""

    def test_adds_to_correct_node(self):
        sources = {"sources": {}, "meta": {"last_verified": "", "broken_sources": []}}
        updated = add_source(sources, "lithium", VALID_SOURCE)
        assert "lithium" in updated["sources"]
        assert updated["sources"]["lithium"][0]["id"] == "test_source"

    def test_appends_to_existing_node(self):
        sources = {"sources": {"lithium": [VALID_SOURCE]}, "meta": {"last_verified": "", "broken_sources": []}}
        new_source = dict(VALID_SOURCE)
        new_source["id"] = "test_source_2"
        updated = add_source(sources, "lithium", new_source)
        assert len(updated["sources"]["lithium"]) == 2


class TestMarkBroken:
    """Test marking broken sources."""

    def test_moves_to_broken_list(self):
        sources = {
            "sources": {"node_a": [VALID_SOURCE]},
            "meta": {"last_verified": "", "broken_sources": []},
        }
        updated = mark_broken_source(sources, "node_a", "test_source")
        assert len(updated["sources"]["node_a"]) == 0
        assert "test_source" in updated["meta"]["broken_sources"]

    def test_ignores_unknown_source(self):
        sources = {"sources": {}, "meta": {"last_verified": "", "broken_sources": []}}
        updated = mark_broken_source(sources, "ghost", "ghost_id")
        assert updated == sources  # No change
