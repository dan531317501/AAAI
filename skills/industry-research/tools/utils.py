"""Shared utilities for industry-research tools."""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests


# --- Path helpers ---

def get_skill_root() -> Path:
    """Return the skill root directory (skills/industry-research/)."""
    return Path(__file__).resolve().parent.parent


def get_data_dir(industry: str) -> Path:
    """Return data/{industry}/ directory, creating if needed."""
    d = get_skill_root() / "data" / industry
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_report_dir(industry: str, date: str) -> Path:
    """Return data/{industry}/reports/{date}/ directory, creating if needed."""
    d = get_data_dir(industry) / "reports" / date
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_news_raw_dir(industry: str, date: str) -> Path:
    """Return data/{industry}/reports/{date}/news_raw/ directory."""
    d = get_report_dir(industry, date) / "news_raw"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- HTTP session with retry ---

def make_session(timeout: int = 30, max_retries: int = 3) -> requests.Session:
    """Create a requests.Session with retry and User-Agent."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retry = Retry(total=max_retries, backoff_factor=1.0,
                  status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "IndustryResearch/1.0 (research-bot@example.com)"
    })
    return session


def fetch_via_jina(url: str, timeout: int = 30) -> Optional[str]:
    """Fetch page content via Jina AI Reader proxy. Returns text or None."""
    jina_url = f"https://r.jina.ai/{url}"
    try:
        resp = requests.get(jina_url, timeout=timeout,
                            headers={"Accept": "text/markdown"})
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def fetch_direct(url: str, session: Optional[requests.Session] = None,
                 timeout: int = 30) -> Optional[str]:
    """Fetch URL directly. Returns text or None on failure."""
    s = session or make_session()
    try:
        resp = s.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def fetch_with_fallback(url: str, fallback_url: str = "",
                        session: Optional[requests.Session] = None,
                        timeout: int = 30) -> Optional[str]:
    """Try Jina proxy first, then direct fetch, then fallback URL."""
    result = fetch_via_jina(url, timeout)
    if result:
        return result
    result = fetch_direct(url, session, timeout)
    if result:
        return result
    if fallback_url:
        result = fetch_via_jina(fallback_url, timeout)
        if result:
            return result
        result = fetch_direct(fallback_url, session, timeout)
        if result:
            return result
    return None


# --- Content helpers ---

def content_hash(text: str) -> str:
    """SHA256 hash of text for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_raw_content(raw_dir: Path, source_id: str, url: str, content: str):
    """Save raw fetched content to news_raw/ for audit trail."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{source_id}_{content_hash(url)[:12]}.txt"
    filepath = raw_dir / filename
    filepath.write_text(content, encoding="utf-8")


# --- YAML helpers ---

def load_yaml(path: Path) -> dict:
    """Load a YAML file. Returns empty dict if not found."""
    import yaml
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: Path, data: dict):
    """Save data as YAML file."""
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False,
                       default_flow_style=False)


def load_json(path: Path) -> dict:
    """Load a JSON file. Returns empty dict if not found."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    """Save data as JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
