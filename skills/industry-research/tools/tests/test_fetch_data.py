"""Tests for the data fetching engine."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_data import (
    build_search_queries,
    deduplicate_news,
    classify_confidence,
    DataQualityReport,
    FetchMetadata,
)
from utils import load_yaml


class TestBuildSearchQueries:
    """Test query construction from chain.yaml nodes."""

    def test_builds_query_per_key_factor(self):
        chain = {
            "nodes": [
                {"id": "bat", "name": "电池", "key_factors": ["锂价", "产能"]},
            ]
        }
        queries = build_search_queries(chain, "新能源汽车")
        assert len(queries) >= 2  # At least one per key_factor
        assert any("锂价" in q for q in queries)
        assert any("新能源汽车" in q for q in queries)

    def test_includes_supports(self):
        chain = {
            "nodes": [{"id": "x", "name": "X", "key_factors": ["y"], "layer": 0}],
            "supports": [
                {"id": "pol", "name": "政策", "key_factors": ["补贴"], "affects": ["x"]}
            ],
        }
        queries = build_search_queries(chain, "测试行业")
        assert any("补贴" in q for q in queries)

    def test_returns_empty_for_empty_chain(self):
        chain = {"nodes": [], "supports": []}
        queries = build_search_queries(chain, "X")
        assert queries == []


class TestDeduplicateNews:
    """Test news deduplication."""

    def test_removes_exact_duplicates(self):
        items = [
            {"title": "Same", "url": "http://a.com/1", "date": "2026-01-01"},
            {"title": "Same", "url": "http://a.com/1", "date": "2026-01-01"},
            {"title": "Different", "url": "http://a.com/2", "date": "2026-01-02"},
        ]
        result = deduplicate_news(items)
        assert len(result) == 2

    def test_removes_similar_titles(self):
        items = [
            {"title": "碳酸锂价格跌破10万元", "url": "http://a.com/1", "date": "2026-01-01"},
            {"title": "碳酸锂价格跌破10万元关口", "url": "http://b.com/2", "date": "2026-01-01"},
        ]
        result = deduplicate_news(items)
        # Titles are very similar, should be deduplicated to 1
        assert len(result) <= 2

    def test_keeps_different_articles(self):
        items = [
            {"title": "电池产能扩张加速", "url": "http://a.com/1", "date": "2026-01-01"},
            {"title": "整车销量创新高", "url": "http://a.com/2", "date": "2026-01-02"},
        ]
        result = deduplicate_news(items)
        assert len(result) == 2


class TestClassifyConfidence:
    """Test source confidence classification."""

    def test_official_source_high(self):
        assert classify_confidence("https://www.miit.gov.cn/policy/123") == "高"

    def test_reputable_media_medium(self):
        assert classify_confidence("https://www.cls.cn/detail/123") in ("高", "中")

    def test_unknown_source_low(self):
        assert classify_confidence("https://some-random-blog.com/post") == "低"

    def test_gov_cn_is_high(self):
        assert classify_confidence("https://stats.gov.cn/report") == "高"


class TestDataQualityReport:
    """Test data quality report generation."""

    def test_generates_report(self):
        report = DataQualityReport.generate(
            total_sources=10,
            success_count=8,
            broken_sources=["http://dead.link/1", "http://dead.link/2"],
            news_count=150,
            data_date="2026-07-24",
        )
        assert report["total_sources"] == 10
        assert report["success_rate"] == 0.8
        assert report["data_fresh"] is True
        assert len(report["broken_sources"]) == 2


class TestFetchMetadata:
    """Test metadata structure."""

    def test_metadata_structure(self):
        meta = FetchMetadata.create(
            industry="测试行业",
            date="2026-07-24",
            sources_used=10,
            success=9,
            failed=1,
            news_collected=100,
            duration_seconds=45.5,
        )
        assert meta["industry"] == "测试行业"
        assert meta["date"] == "2026-07-24"
        assert meta["sources_total"] == 10
        assert meta["sources_success"] == 9
        assert meta["sources_failed"] == 1
        assert "timestamp" in meta
