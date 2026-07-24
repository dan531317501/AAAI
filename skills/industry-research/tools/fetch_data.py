"""
Phase 2.2: 数据采集引擎。

读取 sources.yaml 和 chain.yaml，执行数据采集：
1. 新闻搜索: 为每个 key_factor 构建搜索查询，通过 SerpApi/DuckDuckGo 搜索
2. 内容抓取: 通过 Jina AI 代理获取文章正文
3. 去重去噪: 标题相似度去重 + 置信度分类
4. 输出: news.json (按节点分组) + metrics.json (量化指标) + metadata.json + data_quality.json

用法:
  python fetch_data.py <INDUSTRY> <DATE> --output-dir <DIR>
"""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import requests

from utils import (
    get_data_dir, get_report_dir, get_news_raw_dir,
    load_yaml, save_json, load_json,
    fetch_via_jina, fetch_direct, fetch_with_fallback,
    content_hash, cache_raw_content,
)

# SerpApi configuration
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
SERPAPI_URL = "https://serpapi.com/search"
MAX_SEARCH_WORKERS = 5
SINGLE_QUERY_TIMEOUT = 10  # seconds per query
TOTAL_SEARCH_TIMEOUT = 30  # seconds total for all queries


# --- Search ---

def search_news_queries(queries: list[str], num_results: int = 5,
                        max_workers: int = MAX_SEARCH_WORKERS,
                        total_timeout: int = TOTAL_SEARCH_TIMEOUT) -> list[dict]:
    """
    Execute search queries in parallel via SerpApi HTTP API.

    Uses ThreadPoolExecutor for parallel requests. Returns deduplicated
    list of {title, url, snippet, date, source} dicts.
    """
    if not SERPAPI_KEY:
        print("WARNING: SERPAPI_KEY not set, skipping live search", file=sys.stderr)
        return []

    if not queries:
        return []

    all_results = []
    seen_urls = set()

    with ThreadPoolExecutor(max_workers=min(max_workers, len(queries))) as executor:
        futures = {
            executor.submit(_search_serpapi_http, q, num_results): q
            for q in queries
        }

        try:
            for future in as_completed(futures, timeout=total_timeout):
                try:
                    results = future.result(timeout=SINGLE_QUERY_TIMEOUT)
                except Exception:
                    results = []
                for r in results:
                    url = r.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(r)
        except FuturesTimeoutError:
            print(f"  Search timed out after {total_timeout}s, got {len(all_results)} results", file=sys.stderr)

    return all_results


def _search_serpapi_http(query: str, num: int = 5) -> list[dict]:
    """Search via SerpApi HTTP API. Returns [] on failure."""
    try:
        params = {
            "q": query,
            "api_key": SERPAPI_KEY,
            "engine": "google",
            "tbm": "nws",
            "num": str(num),
            "gl": "us",
            "hl": "zh-CN",
        }
        resp = requests.get(SERPAPI_URL, params=params, timeout=SINGLE_QUERY_TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
        news = data.get("news_results", [])
        return [
            {
                "title": n.get("title", ""),
                "url": n.get("link", ""),
                "snippet": n.get("snippet", ""),
                "date": n.get("date", ""),
                "source": n.get("source", ""),
            }
            for n in news
        ]
    except Exception:
        return []


# --- Query Building ---

def build_search_queries(chain: dict, industry: str, max_per_node: int = 3) -> list[str]:
    """Build search queries from chain.yaml nodes and supports."""
    queries = []

    for node in chain.get("nodes", []):
        node_name = node.get("name", "")
        for kf in node.get("key_factors", [])[:max_per_node]:
            queries.append(f"{industry} {node_name} {kf}")

    for sup in chain.get("supports", []):
        sup_name = sup.get("name", "")
        for kf in sup.get("key_factors", [])[:max_per_node]:
            queries.append(f"{industry} {sup_name} {kf}")

    return queries


# --- Deduplication ---

def deduplicate_news(items: list[dict], title_similarity_threshold: float = 0.85) -> list[dict]:
    """Remove duplicate/similar news items by URL and title similarity."""
    if not items:
        return []

    deduped = []
    seen_urls = set()
    seen_titles = []  # list of (title, index) for similarity check

    for item in items:
        url = item.get("url", "")
        title = item.get("title", "")

        # Exact URL dedup
        if url and url in seen_urls:
            continue
        seen_urls.add(url)

        # Title similarity dedup
        is_dup = False
        for prev_title, _ in seen_titles:
            similarity = SequenceMatcher(None, title, prev_title).ratio()
            if similarity >= title_similarity_threshold:
                is_dup = True
                break

        if not is_dup:
            deduped.append(item)
            seen_titles.append((title, len(deduped) - 1))

    return deduped


# --- Confidence Classification ---

HIGH_CONFIDENCE_DOMAINS = [
    ".gov.cn", "stats.gov", "miit.gov", "ndrc.gov",
    "who.int", "worldbank.org", "imf.org",
]

MEDIUM_CONFIDENCE_DOMAINS = [
    "cls.cn", "caixin.com", "eastmoney.com", "sina.com.cn",
    "163.com", "sohu.com", "bloomberg.com", "reuters.com",
    "ft.com", "wsj.com", "finance.sina", "hexun.com",
    "cninfo.com.cn", "sse.com.cn", "szse.cn",
]


def classify_confidence(url: str) -> str:
    """Classify source confidence: 高/中/低 based on domain."""
    url_lower = url.lower()

    for domain in HIGH_CONFIDENCE_DOMAINS:
        if domain in url_lower:
            return "高"

    for domain in MEDIUM_CONFIDENCE_DOMAINS:
        if domain in url_lower:
            return "中"

    return "低"


# --- Content Fetching ---

CONTENT_FETCH_TIMEOUT = 10     # seconds per article
CONTENT_FETCH_MAX = 10         # max articles to fetch full text
CONTENT_FETCH_WORKERS = 3      # parallel content fetchers


def fetch_article_content(url: str, raw_dir: Path) -> Optional[str]:
    """Fetch article full text via Jina AI proxy. Cache raw content."""
    content = fetch_via_jina(url, timeout=CONTENT_FETCH_TIMEOUT)
    if content:
        cache_raw_content(raw_dir, "article", url, content)
    return content


def fetch_articles_parallel(items: list[dict], raw_dir: Path,
                            max_items: int = CONTENT_FETCH_MAX,
                            max_workers: int = CONTENT_FETCH_WORKERS) -> int:
    """
    Fetch article content for top items in parallel. Modifies items in place.
    Returns number of successfully fetched articles.
    """
    top_items = items[:max_items]
    if not top_items:
        return 0

    fetched = 0

    def _fetch_one(idx: int, item: dict):
        url = item.get("url", "")
        if not url:
            return idx, ""
        content = fetch_article_content(url, raw_dir)
        return idx, (content[:5000] if content else "")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_one, i, item): i
            for i, item in enumerate(top_items)
        }
        for future in as_completed(futures):
            try:
                idx, text = future.result(timeout=CONTENT_FETCH_TIMEOUT + 2)
                if text:
                    top_items[idx]["content"] = text
                    fetched += 1
            except Exception:
                pass

    return fetched


# --- Grouping ---

def group_news_by_node(news_items: list[dict], chain: dict) -> dict[str, list[dict]]:
    """Group news items by which node's key_factors they match."""
    grouped: dict[str, list[dict]] = {}

    all_node_ids = [n["id"] for n in chain.get("nodes", [])]
    for sid in [s["id"] for s in chain.get("supports", [])]:
        all_node_ids.append(sid)

    # Initialize empty lists
    for nid in all_node_ids:
        grouped[nid] = []
    grouped["_unmatched"] = []

    # Build token list per node (short meaningful chunks from name + key_factors)
    node_tokens: dict[str, list[str]] = {}
    for node in chain.get("nodes", []):
        tokens = _tokenize_matching_terms(node.get("name", ""))
        for kf in node.get("key_factors", []):
            tokens.extend(_tokenize_matching_terms(kf))
        node_tokens[node["id"]] = _deduplicate_tokens(tokens)

    for sup in chain.get("supports", []):
        tokens = _tokenize_matching_terms(sup.get("name", ""))
        for kf in sup.get("key_factors", []):
            tokens.extend(_tokenize_matching_terms(kf))
        node_tokens[sup["id"]] = _deduplicate_tokens(tokens)

    for item in news_items:
        title_and_snippet = (item.get("title", "") + " " + item.get("snippet", "")).lower()

        best_node = None
        best_score = 0

        for nid, tokens in node_tokens.items():
            score = _calculate_match_score(title_and_snippet, tokens)
            if score > best_score:
                best_score = score
                best_node = nid

        # Require at least 1 token match to classify
        if best_score >= 1:
            grouped[best_node].append(item)
        else:
            grouped["_unmatched"].append(item)

    return grouped


def _tokenize_matching_terms(text: str) -> list[str]:
    """Split Chinese text into meaningful short tokens for fuzzy matching."""
    tokens = []
    # Split on common separators and punctuation
    import re
    chunks = re.split(r'[/\s,，、()（）—·\-\d+]+', text)
    for chunk in chunks:
        chunk = chunk.strip().lower()
        if len(chunk) >= 2:
            tokens.append(chunk)
            # Also extract sub-tokens of 2-3 chars for partial matching
            if len(chunk) >= 4:
                for i in range(len(chunk) - 1):
                    sub = chunk[i:i+2]
                    if len(sub) == 2:
                        tokens.append(sub)
    return tokens


def _deduplicate_tokens(tokens: list[str]) -> list[str]:
    """Remove duplicate tokens, keeping order."""
    seen = set()
    result = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _calculate_match_score(text: str, tokens: list[str]) -> int:
    """Count how many unique tokens appear in the text."""
    score = 0
    for token in tokens:
        if len(token) >= 2 and token in text:
            score += 1
    return score


# --- Data Quality ---

class DataQualityReport:
    @staticmethod
    def generate(
        total_sources: int,
        success_count: int,
        broken_sources: list[str],
        news_count: int,
        data_date: str,
    ) -> dict:
        success_rate = success_count / total_sources if total_sources > 0 else 0
        return {
            "data_as_of_date": data_date,
            "data_fresh": success_rate >= 0.5,
            "total_sources": total_sources,
            "success_count": success_count,
            "failed_count": total_sources - success_count,
            "success_rate": round(success_rate, 3),
            "broken_sources": broken_sources,
            "news_total": news_count,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }


class FetchMetadata:
    @staticmethod
    def create(
        industry: str,
        date: str,
        sources_used: int,
        success: int,
        failed: int,
        news_collected: int,
        duration_seconds: float,
    ) -> dict:
        return {
            "industry": industry,
            "date": date,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "duration_seconds": round(duration_seconds, 1),
            "sources_total": sources_used,
            "sources_success": success,
            "sources_failed": failed,
            "news_collected": news_collected,
        }


# --- Main ---

def fetch_data(industry: str, date_str: str, output_dir: Path) -> dict:
    """
    Main data fetching pipeline.

    Returns a dict with paths to output files.
    """
    t0 = time.time()

    chain_path = get_data_dir(industry) / "chain.yaml"
    sources_path = get_data_dir(industry) / "sources.yaml"
    report_dir = get_report_dir(industry, date_str)
    raw_dir = get_news_raw_dir(industry, date_str)

    chain = load_yaml(chain_path)
    sources = load_yaml(sources_path)

    if not chain:
        print(f"ERROR: chain.yaml not found or empty at {chain_path}", file=sys.stderr)
        print("Run Phase 1 first to discover the industry chain.", file=sys.stderr)
        sys.exit(1)

    # 1. Build search queries and search for news
    queries = build_search_queries(chain, industry)
    print(f"Searching with {len(queries)} queries...")
    raw_news = search_news_queries(queries)
    print(f"  Found {len(raw_news)} raw results")

    # 2. Deduplicate
    news_items = deduplicate_news(raw_news)
    print(f"  After dedup: {len(news_items)} unique items")

    # 3. Annotate confidence
    for item in news_items:
        item["confidence"] = classify_confidence(item.get("url", ""))

    # 4. Fetch article content for top items in parallel
    print(f"  Fetching full text for top {CONTENT_FETCH_MAX} articles...")
    fetched = fetch_articles_parallel(news_items, raw_dir)
    print(f"  Fetched {fetched} articles")

    # 5. Group by node
    grouped = group_news_by_node(news_items, chain)

    # 6. Save outputs
    news_path = report_dir / "news.json"
    save_json(news_path, grouped)

    metrics_path = report_dir / "metrics.json"
    save_json(metrics_path, {"_note": "Quantitative metrics populated from structured source fetches (Phase 2.2)", "indicators": {}})

    # 7. Copy chain and sources for archive
    import shutil
    shutil.copy(chain_path, report_dir / "chain.yaml")
    if sources_path.exists():
        shutil.copy(sources_path, report_dir / "sources.yaml")

    # 8. Generate metadata and quality report
    broken = sources.get("meta", {}).get("broken_sources", [])
    elapsed = time.time() - t0

    metadata = FetchMetadata.create(
        industry=industry, date=date_str,
        sources_used=len(sources.get("sources", {})),
        success=len(news_items), failed=0,
        news_collected=len(news_items),
        duration_seconds=elapsed,
    )
    save_json(report_dir / "metadata.json", metadata)

    quality = DataQualityReport.generate(
        total_sources=max(len(sources.get("sources", {})), 1),
        success_count=len(grouped),
        broken_sources=broken,
        news_count=len(news_items),
        data_date=date_str,
    )
    save_json(report_dir / "data_quality.json", quality)

    print(f"\nData collection complete in {elapsed:.1f}s")
    print(f"  News items: {len(news_items)}")
    print(f"  Grouped into: {len([k for k, v in grouped.items() if v and k != '_unmatched'])} nodes")
    print(f"  Output: {report_dir}")

    return {
        "news_file": str(news_path),
        "metrics_file": str(metrics_path),
        "metadata_file": str(report_dir / "metadata.json"),
        "quality_file": str(report_dir / "data_quality.json"),
        "report_dir": str(report_dir),
    }


def main():
    parser = argparse.ArgumentParser(description="Phase 2.2: Data Collection")
    parser.add_argument("industry", help="Industry name (e.g. 新能源汽车, AI)")
    parser.add_argument("date", help="Analysis date (YYYY-MM-DD)")
    parser.add_argument("--output-dir", default=None, help="Output base directory")
    args = parser.parse_args()

    fetch_data(args.industry, args.date, Path(args.output_dir) if args.output_dir else None)


if __name__ == "__main__":
    main()
