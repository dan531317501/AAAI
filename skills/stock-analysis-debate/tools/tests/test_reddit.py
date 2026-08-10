import pytest

from reddit import (
    parse_atom,
    render_posts,
    _strip_html,
    fetch_reddit_posts,
    _fetch_subreddit_rss,
)


ATOM_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>{title}</title>
    <published>{published}</published>
    <content type="html"><![CDATA[<div class="md"><p>before</p><!-- SC_OFF --><div class="md"><p>{selftext}</p></div><!-- SC_ON --><p>after</p></div>]]></content>
  </entry>
</feed>
"""


def test_parse_atom_extracts_title_selftext_and_timestamp():
    xml_text = ATOM_TEMPLATE.format(
        title="Is this the bottom?",
        published="2026-08-02T15:30:00Z",
        selftext="Buying the dip tomorrow",
    )
    posts = parse_atom(xml_text, limit=5)

    assert len(posts) == 1
    post = posts[0]
    assert post["title"] == "Is this the bottom?"
    assert post["selftext"] == "Buying the dip tomorrow"
    assert post["source"] == "rss"
    assert post["score"] is None
    assert post["num_comments"] is None
    assert isinstance(post["created_utc"], float)


def test_parse_atom_returns_empty_on_malformed_xml():
    assert parse_atom("<not-xml", 5) == []


def test_strip_html_removes_markup_and_unescapes():
    text = _strip_html("<!-- SC_OFF --><div>Hello &amp; goodbye</div><!-- SC_ON -->")
    assert text == "Hello & goodbye"


def test_render_posts_marks_rss_without_fabricating_scores():
    posts = [{
        "title": "Thoughts on earnings?",
        "score": None,
        "num_comments": None,
        "created_utc": 1783036800,  # 2026-07-03
        "selftext": "Quarter looked solid",
        "source": "rss",
    }]
    text = render_posts(posts, "stocks", "AAPL")

    assert "r/stocks — 1 recent posts mentioning AAPL" in text
    assert "(via RSS feed; scores/comments unavailable)" in text
    assert "[2026-07-03] Thoughts on earnings?" in text
    assert "body excerpt: Quarter looked solid" in text
    assert "↑" not in text  # no fake score metrics


def test_render_posts_placeholder_for_empty_subreddit():
    text = render_posts([], "stocks", "AAPL")

    assert "r/stocks: <no posts found mentioning AAPL in the past 7 days>" in text


def test_fetch_reddit_posts_aggregates_subreddits(monkeypatch):
    calls = []

    def fake_fetch(ticker, sub, limit, timeout):
        calls.append(sub)
        return [{"title": f"post in {sub}", "score": None, "num_comments": None,
                 "created_utc": None, "selftext": "", "source": "rss"}]

    monkeypatch.setattr("reddit._fetch_subreddit_rss", fake_fetch)
    text = fetch_reddit_posts("AAPL", subreddits=("wsb", "stocks"), limit_per_sub=3)

    assert calls == ["wsb", "stocks"]
    assert "r/wsb" in text
    assert "r/stocks" in text


def test_fetch_reddit_posts_global_placeholder_when_all_empty(monkeypatch):
    monkeypatch.setattr(
        "reddit._fetch_subreddit_rss",
        lambda ticker, sub, limit, timeout: [],
    )
    text = fetch_reddit_posts("ZZZZ", subreddits=("wsb", "stocks"))

    assert "no Reddit posts found mentioning ZZZZ" in text
    assert "r/wsb" in text


def test_fetch_subreddit_rss_returns_empty_on_http_error(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise ConnectionError("blocked")

    monkeypatch.setattr("reddit.urlopen", fake_urlopen)
    assert _fetch_subreddit_rss("AAPL", "stocks", 5, 10.0) == []
