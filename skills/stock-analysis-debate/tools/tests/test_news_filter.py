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
