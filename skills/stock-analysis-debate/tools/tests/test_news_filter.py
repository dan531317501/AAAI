from news_filter import normalize_title


def test_normalize_title_strips_whitespace():
    assert normalize_title("  阿里云增长30%  ") == "阿里云增长30%"


def test_normalize_title_removes_inner_spaces():
    assert normalize_title("阿里 云 增长 30%") == "阿里云增长30%"


def test_normalize_title_unifies_fullwidth_punct():
    # 全角感叹号转半角
    assert normalize_title("利好！") == "利好!"


def test_normalize_title_empty_returns_empty():
    assert normalize_title("") == ""
    assert normalize_title("   ") == ""


from news_filter import dedup_by_title


def _article(title, date, link=""):
    return {"title": title, "date": date, "link": link, "summary": ""}


def test_dedup_keeps_first_when_exact_duplicate():
    articles = [
        _article("阿里云增长30%", "2026-07-14 09:00"),
        _article("阿里云增长30%", "2026-07-14 10:00"),  # 同标题，更晚
    ]
    result = dedup_by_title(articles)
    assert len(result) == 1
    assert result[0]["date"] == "2026-07-14 09:00"


def test_dedup_normalizes_before_compare():
    # 一个含空格一个不含，归一化后相同 -> 去重
    articles = [
        _article("阿里 云 增长", "2026-07-14 09:00"),
        _article("阿里云增长", "2026-07-14 08:00"),  # 更早，应保留这条
    ]
    result = dedup_by_title(articles)
    assert len(result) == 1
    assert result[0]["date"] == "2026-07-14 08:00"


def test_dedup_keeps_different_titles():
    articles = [
        _article("阿里云增长30%", "2026-07-14 09:00"),
        _article("阿里云增长40%", "2026-07-14 10:00"),
    ]
    result = dedup_by_title(articles)
    assert len(result) == 2


def test_dedup_empty_list():
    assert dedup_by_title([]) == []


from news_filter import render_news_evidence


def test_render_news_evidence_preserves_summary_and_marks_content_level():
    articles = [
        {
            "title": "公司发布季度业绩",
            "date": "2026-07-30 09:00",
            "provider": "Example News",
            "link": "https://example.com/earnings",
            "summary": "季度收入同比增长 20%。",
        },
        {
            "title": "分析师调整目标价",
            "date": "2026-07-30 10:00",
            "provider": "Example News",
            "link": "https://example.com/target",
            "summary": "",
        },
    ]

    text, stats = render_news_evidence(articles, "2026-07-01", "2026-07-31")

    assert "### [N001] 公司发布季度业绩" in text
    assert "Content Level: summary" in text
    assert "Summary: 季度收入同比增长 20%。" in text
    assert "### [N002] 分析师调整目标价" in text
    assert "Content Level: title_only" in text
    assert stats == {
        "summary": 1,
        "title_only": 1,
        "social_data_available": "separate (stocktwits.txt, reddit.txt)",
    }


def test_render_news_evidence_ids_follow_final_article_order():
    articles = [
        _article("第一条新闻", "2026-07-30 09:00"),
        _article("第二条新闻", "2026-07-30 10:00"),
    ]

    first_text, _ = render_news_evidence(articles, "2026-07-01", "2026-07-31")
    second_text, _ = render_news_evidence(articles, "2026-07-01", "2026-07-31")

    assert first_text == second_text
    assert first_text.index("[N001] 第一条新闻") < first_text.index("[N002] 第二条新闻")


def test_render_news_evidence_delegates_social_data_to_separate_files():
    text, stats = render_news_evidence([], "2026-07-01", "2026-07-31")

    assert "Social Data Available: separate (stocktwits.txt, reddit.txt)" in text
    assert "social-media posts and platform sentiment metrics live in" in text
    assert stats["social_data_available"] == "separate (stocktwits.txt, reddit.txt)"


from fetch_data import process_and_write_news


def test_process_and_write_news_merges_evidence_and_audit_counts(tmp_path):
    raw_items = [
        {
            "title": "公司发布季度业绩",
            "date": "2026-07-30 09:00",
            "provider": "Example News",
            "link": "https://example.com/earnings",
            "summary": "季度收入同比增长 20%。",
        },
        {
            "title": "分析师调整目标价",
            "date": "2026-07-30 10:00",
            "provider": "Example News",
            "link": "https://example.com/target",
            "summary": "",
        },
    ]
    news_path = tmp_path / "news.txt"
    legacy_meta_path = tmp_path / "news_meta.txt"
    legacy_meta_path.write_text("stale audit")

    kept = process_and_write_news(
        raw_items,
        "2026-07-31",
        "2026-07-01",
        str(news_path),
        market="US",
    )

    news_text = news_path.read_text()
    assert kept == 2
    assert "[N001] 公司发布季度业绩" in news_text
    assert "Summary: 季度收入同比增长 20%。" in news_text
    assert "## News Processing Audit (2026-07-01 to 2026-07-31)" in news_text
    assert "content_level_summary: 1" in news_text
    assert "content_level_title_only: 1" in news_text
    assert "social_data_available: separate (stocktwits.txt, reddit.txt)" in news_text
    assert not legacy_meta_path.exists()


from news_filter import is_noise, filter_noise


def test_is_noise_geopolitics_unrelated():
    assert is_noise("霍尔木兹海峡局势升温") is True
    assert is_noise("哈梅内伊葬礼上不该出现的一幕") is True


def test_is_noise_chicken_soup():
    assert is_noise("周文强：人人都想成为马云") is True
    assert is_noise("国旗冉冉升起是我心中最美的风景") is True


def test_is_noise_keeps_real_signal():
    assert is_noise("阿里云同比增长30% 成增长引擎") is False
    assert is_noise("阿里巴巴领投爱诗科技C轮") is False
    assert is_noise("菜鸟供应链定位独立公司") is False


def test_filter_noise_removes_blacklisted():
    articles = [
        {"title": "阿里云增长30%", "date": "2026-07-14 09:00", "provider": ""},
        {"title": "周文强：人人都想成为马云", "date": "2026-07-14 10:00", "provider": ""},
        {"title": "霍尔木兹海峡新进展", "date": "2026-07-14 11:00", "provider": ""},
    ]
    result = filter_noise(articles)
    assert len(result) == 1
    assert result[0]["title"] == "阿里云增长30%"


def test_filter_noise_source_blacklist():
    articles = [
        {"title": "阿里云增长30%", "date": "2026-07-14 09:00", "provider": "某情感号"},
        {"title": "阿里云增长40%", "date": "2026-07-14 10:00", "provider": "新浪财经"},
    ]
    result = filter_noise(articles)
    assert len(result) == 1
    assert result[0]["provider"] == "新浪财经"


from news_filter import is_high_signal


def test_high_signal_earnings():
    assert is_high_signal("阿里巴巴发布财报 云业务同比增长30%") is True


def test_high_signal_price_war():
    assert is_high_signal("阿里与美团打价格战 补贴升级") is True


def test_high_signal_rating():
    assert is_high_signal("国信证券维持阿里巴巴优于大市评级") is True


def test_high_signal_generic_news_is_false():
    assert is_high_signal("阿里参加某行业论坛") is False


from news_filter import split_recent_and_history


def test_split_recent_keeps_all_within_7days():
    # 基准日 2026-07-14，7天内（含7-08起）全留
    articles = [
        {"title": "阿里参加论坛", "date": "2026-07-14 09:00", "provider": ""},
        {"title": "阿里参加沙龙", "date": "2026-07-08 09:00", "provider": ""},
    ]
    recent, history = split_recent_and_history(articles, "2026-07-14", recent_days=7)
    assert len(recent) == 2
    assert len(history) == 0


def test_split_history_keeps_only_high_signal():
    # 8-30天：高信号留，非高信号丢
    articles = [
        {"title": "阿里云财报同比增长30%", "date": "2026-07-01 09:00", "provider": ""},
        {"title": "阿里参加论坛", "date": "2026-07-01 10:00", "provider": ""},
    ]
    recent, history = split_recent_and_history(articles, "2026-07-14", recent_days=7)
    assert len(recent) == 0
    assert len(history) == 1
    assert "财报" in history[0]["title"]


def test_split_boundary_exactly_7_days():
    # 2026-07-07 距 2026-07-14 = 7天，算 recent（<=7）
    articles = [
        {"title": "边界新闻", "date": "2026-07-07 09:00", "provider": ""},
    ]
    recent, history = split_recent_and_history(articles, "2026-07-14", recent_days=7)
    assert len(recent) == 1


def test_split_beyond_30_days_dropped():
    # 超过30天的直接丢弃
    articles = [
        {"title": "阿里云财报同比增长30%", "date": "2026-06-10 09:00", "provider": ""},
    ]
    recent, history = split_recent_and_history(articles, "2026-07-14", recent_days=7, lookback_days=30)
    assert len(recent) == 0
    assert len(history) == 0
