# 股票分析 Skill 优化（新闻去噪 + 多业务分部视角）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 stock-analysis-debate skill 对 HK/US 多业务公司产出有分部视角的分析，并显著降低新闻噪声。

**Architecture:** 数据层（fetch_data.py + 新模块）负责新浪翻页抓全、标题去重、黑名单去噪、长桥分部数据抓取；prepare_segments.py 把长桥JSON转CSV；分析层 News Analyst 加打分标注，新增条件触发的 Segment Analyst。CN 市场不走业务线分析。可测的纯函数抽到独立模块（news_filter.py、longbridge_fetcher.py）便于 TDD。

**Tech Stack:** Python 3.13、yfinance、stockstats、pandas、requests、pytest、PyYAML

**Spec:** `docs/superpowers/specs/2026-07-14-stock-news-segment-design.md`

---

## 文件结构

| 文件 | 责任 | 类型 |
|------|------|------|
| `skills/stock-analysis-debate/tools/news_filter.py` | 新闻去重/去噪/分层保留的纯函数（可单测） | 新建 |
| `skills/stock-analysis-debate/tools/longbridge_fetcher.py` | 长桥 counter_id 生成 + API1/API2 抓取 + JSON解析（可单测） | 新建 |
| `skills/stock-analysis-debate/tools/prepare_segments.py` | 长桥JSON→紧凑CSV（可单测） | 新建 |
| `skills/stock-analysis-debate/tools/fetch_data.py` | 主抓取流程，调用上述模块；新浪翻页；写各文件 | 修改 |
| `skills/stock-analysis-debate/tools/requirements.txt` | 加 requests、PyYAML、pytest | 修改 |
| `skills/stock-analysis-debate/tools/tests/test_news_filter.py` | news_filter 单测 | 新建 |
| `skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py` | longbridge_fetcher 单测 | 新建 |
| `skills/stock-analysis-debate/tools/tests/test_prepare_segments.py` | prepare_segments 单测 | 新建 |
| `skills/stock-analysis-debate/prompts/news_analyst.md` | 加打分(0-3)+业务线标注+近似去重+高分事件表 | 修改 |
| `skills/stock-analysis-debate/prompts/segment_analyst.md` | 分部拐点分析+股价综合方向 | 新建 |
| `skills/stock-analysis-debate/prompts/fundamentals_analyst.md` | 微调：引用Segment Analyst结论 | 修改 |
| `skills/stock-analysis-debate/SKILL.md` | 增Phase 1.5；Phase 2条件触发第5 analyst；context增segment | 修改 |

**测试运行约定**：所有测试从 repo 根目录运行，PYTHONPATH 含 tools 目录：
`cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/ -v`

---

## Task 1: 搭建测试骨架与依赖

**Files:**
- Modify: `skills/stock-analysis-debate/tools/requirements.txt`
- Create: `skills/stock-analysis-debate/tools/tests/__init__.py`
- Create: `skills/stock-analysis-debate/tools/tests/conftest.py`

- [ ] **Step 1: 更新 requirements.txt**

写入 `skills/stock-analysis-debate/tools/requirements.txt`：

```
yfinance>=0.2.40
stockstats>=0.6.2
pandas>=2.0.0
requests>=2.31.0
PyYAML>=6.0
pytest>=8.0.0
```

- [ ] **Step 2: 创建测试包**

写入 `skills/stock-analysis-debate/tools/tests/__init__.py`（空文件）。

写入 `skills/stock-analysis-debate/tools/tests/conftest.py`：

```python
import sys
import os

# 让 tests 能 import tools 目录下的模块
TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.abspath(TOOLS_DIR))
```

- [ ] **Step 3: 安装依赖并验证 pytest 可跑**

Run: `cd /Users/zhangqi.huang/aaai && pip install -r skills/stock-analysis-debate/tools/requirements.txt && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/ -v`
Expected: `no tests ran`（无测试但框架正常），退出码 5

- [ ] **Step 4: Commit**

```bash
git add skills/stock-analysis-debate/tools/requirements.txt skills/stock-analysis-debate/tools/tests/
git commit -m "test: 搭建stock-analysis-debate测试骨架与依赖"
```

---

## Task 2: news_filter.py — 标题归一化与完全去重

**Files:**
- Create: `skills/stock-analysis-debate/tools/news_filter.py`
- Test: `skills/stock-analysis-debate/tools/tests/test_news_filter.py`

**设计**：数据层只做"标题归一化后完全相同"的去重。归一化 = 去掉首尾空白、统一全角/半角标点为半角、去掉所有空白字符后比较。保留最早一条（按日期+时间排序最前的）。

- [ ] **Step 1: 写失败测试 — 归一化**

写入 `skills/stock-analysis-debate/tools/tests/test_news_filter.py`：

```python
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
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_news_filter.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'news_filter'`

- [ ] **Step 3: 实现 normalize_title**

写入 `skills/stock-analysis-debate/tools/news_filter.py`：

```python
"""新闻去重/去噪/分层保留的纯函数。"""
import re
import unicodedata


# 全角→半角标点映射（常见财经标题用到的）
_FULLWIDTH_PUNCT = {
    "！": "!", "？": "?", "，": ",", "。": ".",
    "：": ":", "；": ";", "（": "(", "）": ")",
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "【": "[", "】": "]", "《": "<", "》": ">",
    "、": ",",
}


def normalize_title(title: str) -> str:
    """标题归一化：去首尾空白、去内部所有空白、全角标点转半角。"""
    if not title:
        return ""
    s = title.strip()
    # 全角标点转半角
    for full, half in _FULLWIDTH_PUNCT.items():
        s = s.replace(full, half)
    # 去掉所有空白字符（含全角空格 　）
    s = re.sub(r"\s+", "", s)
    return s
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_news_filter.py -v`
Expected: 4 passed

- [ ] **Step 5: 写失败测试 — 完全去重**

追加到 `skills/stock-analysis-debate/tools/tests/test_news_filter.py`：

```python
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
```

- [ ] **Step 6: 跑测试验证失败**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_news_filter.py -v`
Expected: FAIL，`ImportError: cannot import name 'dedup_by_title'`

- [ ] **Step 7: 实现 dedup_by_title**

追加到 `skills/stock-analysis-debate/tools/news_filter.py`：

```python
def dedup_by_title(articles: list) -> list:
    """标题归一化后完全相同的去重，保留最早一条（按 date 字符串升序）。

    articles: 每条 dict 含 title、date（字符串）、link、summary。
    返回去重后的列表，保持原相对顺序（同组内取最早的）。
    """
    seen = {}  # normalized_title -> 最早 article
    for art in articles:
        key = normalize_title(art.get("title", ""))
        if not key:
            continue
        if key not in seen:
            seen[key] = art
        else:
            # 保留 date 更早的
            if art.get("date", "") < seen[key].get("date", ""):
                seen[key] = art
    # 保持输入顺序输出
    return [art for art in articles if normalize_title(art.get("title", "")) in seen
            and seen[normalize_title(art.get("title", ""))] is art]
```

- [ ] **Step 8: 跑测试验证通过**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_news_filter.py -v`
Expected: 8 passed

- [ ] **Step 9: Commit**

```bash
git add skills/stock-analysis-debate/tools/news_filter.py skills/stock-analysis-debate/tools/tests/test_news_filter.py
git commit -m "feat(news_filter): 标题归一化与完全去重"
```

---

## Task 3: news_filter.py — 黑名单去噪

**Files:**
- Modify: `skills/stock-analysis-debate/tools/news_filter.py`
- Test: `skills/stock-analysis-debate/tools/tests/test_news_filter.py`

**设计**：两类黑名单。来源黑名单（provider 命中即剔）；关键词黑名单（标题命中任一即剔）。关键词黑名单只放"明显与公司股价无关"的，保守过滤（高召回优先）。

- [ ] **Step 1: 写失败测试 — 关键词黑名单**

追加到 `skills/stock-analysis-debate/tools/tests/test_news_filter.py`：

```python
from news_filter import is_noise, filter_noise


def test_is_noise_geopolitics_unrelated():
    # 地缘冲突无关项
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
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_news_filter.py -v`
Expected: FAIL，`ImportError: cannot import name 'is_noise'`

- [ ] **Step 3: 实现黑名单**

追加到 `skills/stock-analysis-debate/tools/news_filter.py`：

```python
# 明显与公司股价无关的关键词。保守：只放确定性的噪声。
_NOISE_KEYWORDS = [
    # 地缘冲突（与个股无关的纯地缘新闻）
    "霍尔木兹", "哈梅内伊", "葬礼",
    # 励志/鸡汤/自媒体人格化
    "周文强", "人人都想成为", "国旗冉冉升起", "繁星点点",
    # 民族共同体/党建/研修类无关
    "中华民族共同体", "工商联组织", "赴浙大",
    # 地名/港口等无关
    "阿联酋港务", "迪拜拟建新港口",
]

# 来源黑名单：明显非财经来源（情感、社会类自媒体）
_NOISE_PROVIDERS = ["某情感号", "某社会号"]


def is_noise(title: str) -> bool:
    """标题命中噪声关键词则返回 True。保守过滤。"""
    if not title:
        return False
    for kw in _NOISE_KEYWORDS:
        if kw in title:
            return True
    return False


def _is_noise_provider(provider: str) -> bool:
    if not provider:
        return False
    for p in _NOISE_PROVIDERS:
        if p in provider:
            return True
    return False


def filter_noise(articles: list) -> list:
    """剔除命中关键词黑名单或来源黑名单的新闻。"""
    return [
        art for art in articles
        if not is_noise(art.get("title", ""))
        and not _is_noise_provider(art.get("provider", ""))
    ]
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_news_filter.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add skills/stock-analysis-debate/tools/news_filter.py skills/stock-analysis-debate/tools/tests/test_news_filter.py
git commit -m "feat(news_filter): 关键词与来源黑名单去噪"
```

---

## Task 4: news_filter.py — 7天全量 + 8-30天关键词粗筛分层

**Files:**
- Modify: `skills/stock-analysis-debate/tools/news_filter.py`
- Test: `skills/stock-analysis-debate/tools/tests/test_news_filter.py`

**设计**：分层保留。7天内全留；8-30天只留标题命中高信号词的。日期用每条新闻的 date 字段（格式 "YYYY-MM-DD HH:MM"）与基准日比较。

- [ ] **Step 1: 写失败测试 — 高信号词判定**

追加到 `skills/stock-analysis-debate/tools/tests/test_news_filter.py`：

```python
from news_filter import is_high_signal


def test_high_signal_earnings():
    assert is_high_signal("阿里巴巴发布财报 云业务同比增长30%") is True


def test_high_signal_price_war():
    assert is_high_signal("阿里与美团打价格战 补贴升级") is True


def test_high_signal_rating():
    assert is_high_signal("国信证券维持阿里巴巴优于大市评级") is True


def test_high_signal_generic_news_is_false():
    assert is_high_signal("阿里参加某行业论坛") is False
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_news_filter.py::test_high_signal_earnings -v`
Expected: FAIL，`ImportError: cannot import name 'is_high_signal'`

- [ ] **Step 3: 实现 is_high_signal**

追加到 `skills/stock-analysis-debate/tools/news_filter.py`：

```python
# 8-30天窗口保留用的高信号词（命中其一即保留）
_HIGH_SIGNAL_KEYWORDS = [
    "财报", "业绩", "营收", "净利润", "毛利率",
    "并购", "收购", "重组", "并入",
    "评级", "上调", "下调", "维持", "目标价",
    "价格战", "补贴", "百亿补贴",
    "合作", "战略合作", "官宣",
    "监管", "处罚", "立案", "约谈",
    "回购", "增持", "减持", "增发",
    "分部", "分拆", "独立", "拆分",
    "同比增长", "同比下滑", "同比下跌", "亏损", "盈利",
    "领投", "融资",
]


def is_high_signal(title: str) -> bool:
    """标题命中高信号词则返回 True（用于8-30天窗口粗筛）。"""
    if not title:
        return False
    for kw in _HIGH_SIGNAL_KEYWORDS:
        if kw in title:
            return True
    return False
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_news_filter.py -v -k high_signal`
Expected: 4 passed

- [ ] **Step 5: 写失败测试 — 分层保留**

追加到 `skills/stock-analysis-debate/tools/tests/test_news_filter.py`：

```python
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
    # 超过30天的直接丢弃（既不在recent也不在history）
    articles = [
        {"title": "阿里云财报同比增长30%", "date": "2026-06-10 09:00", "provider": ""},
    ]
    recent, history = split_recent_and_history(articles, "2026-07-14", recent_days=7, lookback_days=30)
    assert len(recent) == 0
    assert len(history) == 0
```

- [ ] **Step 6: 跑测试验证失败**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_news_filter.py -v -k split`
Expected: FAIL，`ImportError: cannot import name 'split_recent_and_history'`

- [ ] **Step 7: 实现 split_recent_and_history**

追加到 `skills/stock-analysis-debate/tools/news_filter.py`：

```python
from datetime import datetime, timedelta


def _parse_article_date(date_str: str) -> datetime:
    """解析 'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD'，失败返回 None。"""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def split_recent_and_history(articles: list, curr_date: str,
                             recent_days: int = 7, lookback_days: int = 30):
    """按日期分层：recent_days 内全留(recent)，recent+1~lookback 天只留高信号(history)，
    超出 lookback 的丢弃。

    返回 (recent_list, history_list)。
    """
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    recent_cutoff = curr_dt - timedelta(days=recent_days)
    history_cutoff = curr_dt - timedelta(days=lookback_days)

    recent, history = [], []
    for art in articles:
        d = _parse_article_date(art.get("date", ""))
        if d is None:
            # 无法解析日期，保守归入 recent 不丢
            recent.append(art)
            continue
        if d < history_cutoff:
            continue  # 超出 lookback 丢弃
        if d >= recent_cutoff:
            recent.append(art)
        else:
            if is_high_signal(art.get("title", "")):
                history.append(art)
    return recent, history
```

- [ ] **Step 8: 跑测试验证通过**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_news_filter.py -v -k split`
Expected: 4 passed

- [ ] **Step 9: 跑全量 news_filter 测试**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_news_filter.py -v`
Expected: 全部 passed

- [ ] **Step 10: Commit**

```bash
git add skills/stock-analysis-debate/tools/news_filter.py skills/stock-analysis-debate/tools/tests/test_news_filter.py
git commit -m "feat(news_filter): 7天全量+8-30天高信号粗筛分层"
```

---

## Task 5: longbridge_fetcher.py — counter_id 生成

**Files:**
- Create: `skills/stock-analysis-debate/tools/longbridge_fetcher.py`
- Test: `skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py`

**设计**：counter_id 规则：HK 去前导零 `ST/HK/{code}`；US `ST/US/{ticker}`。URL 编码 `/` 为 `%2F`。

- [ ] **Step 1: 写失败测试 — counter_id**

写入 `skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py`：

```python
from longbridge_fetcher import build_counter_id


def test_counter_id_hk_strips_leading_zeros():
    assert build_counter_id("09988.HK") == "ST/HK/89988"
    assert build_counter_id("00700.HK") == "ST/HK/700"


def test_counter_id_us():
    assert build_counter_id("AAPL") == "ST/US/AAPL"
    assert build_counter_id("MSFT") == "ST/US/MSFT"


def test_counter_id_cn_returns_none():
    # CN 不走长桥，返回 None 表示不支持
    assert build_counter_id("600519.SH") is None
    assert build_counter_id("000858.SZ") is None
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'longbridge_fetcher'`

- [ ] **Step 3: 实现 build_counter_id**

写入 `skills/stock-analysis-debate/tools/longbridge_fetcher.py`：

```python
"""长桥证券分部数据抓取：counter_id 生成 + API1/API2 调用 + JSON解析。"""
from urllib.parse import quote


def build_counter_id(ticker: str) -> str:
    """根据 ticker 生成长桥 counter_id。CN 返回 None（不支持）。

    HK: ST/HK/{code去前导零}  例如 09988.HK -> ST/HK/89988
    US: ST/US/{ticker}        例如 AAPL -> ST/US/AAPL
    CN: None（长桥无A股分部数据）
    """
    upper = ticker.upper()
    if ".HK" in upper:
        code = upper.split(".")[0].lstrip("0")
        return f"ST/HK/{code}"
    if ".SH" in upper or ".SS" in upper or ".SZ" in upper:
        return None
    if upper.replace(".", "").isdigit() and len(upper.split(".")[0]) == 6:
        return None
    # 否则按 US 处理
    return f"ST/US/{upper}"
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add skills/stock-analysis-debate/tools/longbridge_fetcher.py skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py
git commit -m "feat(longbridge): counter_id生成（HK去前导零/US/CN返回None）"
```

---

## Task 6: longbridge_fetcher.py — API1/API2 抓取与解析

**Files:**
- Modify: `skills/stock-analysis-debate/tools/longbridge_fetcher.py`
- Test: `skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py`

**设计**：两个 API。API1 business-historical（季度分部历史，参数 report=qf cate=business）。API2 revenue-sankey（财年桑基，参数 report=annual）。抓取用 requests，带 User-Agent。解析返回精简结构。网络调用与解析分离：抓取函数返回原始 dict，解析函数纯函数可单测（用 mock JSON）。

- [ ] **Step 1: 写失败测试 — 解析 API1**

追加到 `skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py`：

```python
from longbridge_fetcher import parse_business_historical


# 模拟长桥 API1 返回（精简）
_API1_SAMPLE = {
    "code": 0, "message": "success",
    "data": {
        "historical": [
            {
                "total": "32154000000", "currency": "CNY", "date": "20160630",
                "report_txt": "2017.Q1", "yoy": "",
                "business": [
                    {"name": "商业", "percent": "84.72", "value": "27241000000", "yoy": ""},
                    {"name": "云智能集团", "percent": "3.87", "value": "1243000000", "yoy": "20.11"},
                ],
            },
            {
                "total": "34292000000", "currency": "CNY", "date": "20160930",
                "report_txt": "2017.Q2", "yoy": "6.64",
                "business": [
                    {"name": "云智能集团", "percent": "4.35", "value": "1493000000", "yoy": "20.11"},
                ],
            },
        ]
    },
}


def test_parse_api1_returns_quarterly_segments():
    result = parse_business_historical(_API1_SAMPLE)
    assert len(result) == 2  # 两个季度
    q1 = result[0]
    assert q1["report_period"] == "2017.Q1"
    assert q1["total_revenue"] == "32154000000"
    assert q1["currency"] == "CNY"
    assert len(q1["segments"]) == 2
    seg = q1["segments"][1]
    assert seg["segment"] == "云智能集团"
    assert seg["revenue"] == "1243000000"
    assert seg["percent"] == "3.87"
    assert seg["yoy"] == "20.11"


def test_parse_api1_empty_returns_empty():
    assert parse_business_historical({"data": {"historical": []}}) == []


def test_parse_api1_null_safe():
    assert parse_business_historical({}) == []
    assert parse_business_historical(None) == []
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py -v -k parse_api1`
Expected: FAIL，`ImportError: cannot import name 'parse_business_historical'`

- [ ] **Step 3: 实现 parse_business_historical**

追加到 `skills/stock-analysis-debate/tools/longbridge_fetcher.py`：

```python
def parse_business_historical(resp: dict) -> list:
    """解析长桥 API1 返回，输出按季度的分部列表。

    返回 [{"report_period","date","total_revenue","currency","segments":[{segment,revenue,percent,yoy}]}]。
    """
    if not resp or not isinstance(resp, dict):
        return []
    historical = resp.get("data", {}).get("historical", [])
    if not historical:
        return []
    out = []
    for item in historical:
        segs = []
        for b in item.get("business", []):
            segs.append({
                "segment": b.get("name", ""),
                "revenue": b.get("value", ""),
                "percent": b.get("percent", ""),
                "yoy": b.get("yoy", ""),
            })
        out.append({
            "report_period": item.get("report_txt", ""),
            "date": item.get("date", ""),
            "total_revenue": item.get("total", ""),
            "currency": item.get("currency", ""),
            "segments": segs,
        })
    return out
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py -v -k parse_api1`
Expected: 3 passed

- [ ] **Step 5: 写失败测试 — 解析 API2**

追加到 `skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py`：

```python
from longbridge_fetcher import parse_revenue_sankey


_API2_SAMPLE = {
    "code": 0, "message": "success",
    "data": {
        "list": [
            {
                "fiscal_year": 2019, "report": "2019 财年三季报", "currency": "HKD",
                "nodes": [
                    {"key": "bus_116796", "name": "商业", "value": "117277656183", "yoy": "10", "level": 1},
                    {"key": "bus_133364", "name": "云智能集团", "value": "7538895063", "yoy": "30", "level": 1},
                    {"key": "total_rev", "name": "营业收入", "value": "133738698422", "yoy": "", "level": 2},
                ],
            },
        ]
    },
}


def test_parse_api2_returns_fiscal_year_segments():
    result = parse_revenue_sankey(_API2_SAMPLE)
    assert len(result) == 1
    fy = result[0]
    assert fy["fiscal_year"] == 2019
    assert fy["currency"] == "HKD"
    # level==1 的才是业务分部节点
    assert len(fy["segments"]) == 2
    names = [s["segment"] for s in fy["segments"]]
    assert "商业" in names and "云智能集团" in names


def test_parse_api2_empty():
    assert parse_revenue_sankey({"data": {"list": []}}) == []
    assert parse_revenue_sankey(None) == []
```

- [ ] **Step 6: 跑测试验证失败**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py -v -k parse_api2`
Expected: FAIL，`ImportError: cannot import name 'parse_revenue_sankey'`

- [ ] **Step 7: 实现 parse_revenue_sankey**

追加到 `skills/stock-analysis-debate/tools/longbridge_fetcher.py`：

```python
def parse_revenue_sankey(resp: dict) -> list:
    """解析长桥 API2 返回，输出按财年的分部列表（仅 level==1 的业务节点）。"""
    if not resp or not isinstance(resp, dict):
        return []
    items = resp.get("data", {}).get("list", [])
    if not items:
        return []
    out = []
    for item in items:
        segs = []
        for n in item.get("nodes", []):
            if n.get("level") == 1:
                segs.append({
                    "segment": n.get("name", ""),
                    "revenue": n.get("value", ""),
                    "yoy": n.get("yoy", ""),
                })
        out.append({
            "fiscal_year": item.get("fiscal_year"),
            "report": item.get("report", ""),
            "currency": item.get("currency", ""),
            "segments": segs,
        })
    return out
```

- [ ] **Step 8: 跑测试验证通过**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py -v`
Expected: 全部 passed

- [ ] **Step 9: 实现抓取函数（网络层，不单测，靠集成验证）**

追加到 `skills/stock-analysis-debate/tools/longbridge_fetcher.py`：

```python
import json
import requests

_API1_URL = "https://mr.lbkrs.com/api/forward/v2/stock-info/business-historical"
_API2_URL = "https://mr.lbkrs.com/api/forward/v3/stock-info/revenue-sankey"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
             "Accept": "application/json"}


def _encode_counter_id(counter_id: str) -> str:
    """counter_id 含 /，需 URL 编码为 %2F。"""
    return quote(counter_id, safe="")


def fetch_business_historical(ticker: str) -> dict:
    """抓取长桥 API1（季度分部历史）。失败返回 {}。"""
    cid = build_counter_id(ticker)
    if cid is None:
        return {}
    url = f"{_API1_URL}?counter_id={_encode_counter_id(cid)}&report=qf&cate=business"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [longbridge API1] error: {e}", flush=True)
        return {}


def fetch_revenue_sankey(ticker: str) -> dict:
    """抓取长桥 API2（财年桑基）。失败返回 {}。"""
    cid = build_counter_id(ticker)
    if cid is None:
        return {}
    url = f"{_API2_URL}?counter_id={_encode_counter_id(cid)}&report=annual"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [longbridge API2] error: {e}", flush=True)
        return {}
```

- [ ] **Step 10: 集成验证（真实API）**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -c "from longbridge_fetcher import fetch_business_historical, parse_business_historical; r=fetch_business_historical('09988.HK'); print('quarters:', len(parse_business_historical(r)))"`
Expected: 打印 `quarters: N`（N>0，证明真实API可抓且解析正确）

- [ ] **Step 11: Commit**

```bash
git add skills/stock-analysis-debate/tools/longbridge_fetcher.py skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py
git commit -m "feat(longbridge): API1/API2抓取与解析（季度分部+财年桑基）"
```

---

## Task 7: prepare_segments.py — 长桥JSON→CSV

**Files:**
- Create: `skills/stock-analysis-debate/tools/prepare_segments.py`
- Test: `skills/stock-analysis-debate/tools/tests/test_prepare_segments.py`

**设计**：输入 parse_business_historical 的输出（季度分部列表），取最近 N 个季度（默认8），输出紧凑CSV：`segment,report_period,total_revenue,revenue,percent,yoy`。纯函数 `to_csv` 可单测；CLI 入口读 JSON 文件、调 to_csv、写 CSV 文件。

- [ ] **Step 1: 写失败测试 — to_csv**

写入 `skills/stock-analysis-debate/tools/tests/test_prepare_segments.py`：

```python
from prepare_segments import to_csv


def _quarters():
    return [
        {
            "report_period": "2025.Q4", "date": "20250331",
            "total_revenue": "32154000000", "currency": "CNY",
            "segments": [
                {"segment": "商业", "revenue": "27241000000", "percent": "84.72", "yoy": ""},
                {"segment": "云智能集团", "revenue": "1243000000", "percent": "3.87", "yoy": "20.11"},
            ],
        },
        {
            "report_period": "2025.Q3", "date": "20241231",
            "total_revenue": "30000000000", "currency": "CNY",
            "segments": [
                {"segment": "云智能集团", "revenue": "1100000000", "percent": "3.67", "yoy": "15.00"},
            ],
        },
    ]


def test_to_csv_header_and_rows():
    csv = to_csv(_quarters(), recent_n=8)
    lines = csv.strip().split("\n")
    assert lines[0] == "segment,report_period,total_revenue,revenue,percent,yoy"
    # 3行数据（Q4 2个分部 + Q3 1个分部）
    assert len(lines) == 4
    # 检查一行内容
    row = "云智能集团,2025.Q4,32154000000,1243000000,3.87,20.11"
    assert row in csv


def test_to_csv_truncates_to_recent_n():
    # recent_n=1 只取最近1个季度
    csv = to_csv(_quarters(), recent_n=1)
    lines = csv.strip().split("\n")
    # header + 2个分部（最近季度Q4有2个分部）
    assert len(lines) == 3
    assert "2025.Q4" in csv
    assert "2025.Q3" not in csv


def test_to_csv_empty_input():
    assert to_csv([], recent_n=8).strip() == "segment,report_period,total_revenue,revenue,percent,yoy"
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_prepare_segments.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'prepare_segments'`

- [ ] **Step 3: 实现 to_csv**

写入 `skills/stock-analysis-debate/tools/prepare_segments.py`：

```python
"""把长桥分部数据（解析后的季度列表）转成紧凑CSV，喂LLM省token。"""
import csv
import io
import json
import os
import argparse


def to_csv(quarters: list, recent_n: int = 8) -> str:
    """quarters: parse_business_historical 的输出。取最近 recent_n 个季度。

    输出 CSV：segment,report_period,total_revenue,revenue,percent,yoy
    （每行一个分部×季度）。quarters 按 date 降序后取前 recent_n。
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["segment", "report_period", "total_revenue", "revenue", "percent", "yoy"])

    # 按 date 降序取最近 recent_n
    sorted_q = sorted(quarters, key=lambda q: q.get("date", ""), reverse=True)
    for q in sorted_q[:recent_n]:
        period = q.get("report_period", "")
        total = q.get("total_revenue", "")
        for seg in q.get("segments", []):
            writer.writerow([
                seg.get("segment", ""),
                period,
                total,
                seg.get("revenue", ""),
                seg.get("percent", ""),
                seg.get("yoy", ""),
            ])
    return buf.getvalue()
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_prepare_segments.py -v`
Expected: 3 passed

- [ ] **Step 5: 写 CLI 入口**

追加到 `skills/stock-analysis-debate/tools/prepare_segments.py`：

```python
def main():
    import sys
    import argparse
    parser = argparse.ArgumentParser(description="长桥分部JSON转CSV")
    parser.add_argument("ticker", help="Ticker (e.g. 09988.HK, AAPL)")
    parser.add_argument("date", help="Analysis date YYYY-MM-DD")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--recent-n", type=int, default=8)
    args = parser.parse_args()

    output_dir = args.output_dir or os.path.join(os.path.dirname(__file__), "..", "data")
    day_dir = os.path.join(output_dir, args.ticker.upper().replace(".", "_"), args.date)
    json_path = os.path.join(day_dir, "segments_financials.json")

    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found", flush=True)
        return 1

    with open(json_path) as f:
        data = json.load(f)

    # data 存 {"business_historical": [...], "revenue_sankey": [...]}（fetch_data 写入格式）
    quarters = data.get("business_historical", [])
    csv_text = to_csv(quarters, recent_n=args.recent_n)

    csv_path = os.path.join(day_dir, "segments_financials.csv")
    with open(csv_path, "w") as f:
        f.write(csv_text)
    print(f"Segments CSV written to {csv_path}", flush=True)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

注：本步 main 是基础版（仅CSV）。Task 11 会扩展为含 `--gen-yaml` 的完整版并整体替换此 main。

- [ ] **Step 6: Commit**

```bash
git add skills/stock-analysis-debate/tools/prepare_segments.py skills/stock-analysis-debate/tools/tests/test_prepare_segments.py
git commit -m "feat(prepare_segments): 长桥分部JSON转紧凑CSV"
```

---

## Task 8: segments.yaml 清单生成（从长桥CSV推导）

**Files:**
- Modify: `skills/stock-analysis-debate/tools/longbridge_fetcher.py`
- Test: `skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py`

**设计**：从 parse_business_historical 的最近季度提取分部名，生成 segments.yaml 结构。multi_segment 判断：分部数>1 且"所有其他/其他"占比<90%。aliases 由固定规则补充常见简称（避免 LLM 依赖，可单测）。

- [ ] **Step 1: 写失败测试 — 分部清单推导**

追加到 `skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py`：

```python
from longbridge_fetcher import derive_segments_yaml


def test_derive_multi_segment_true():
    quarters = [
        {"date": "20250331", "report_period": "2025.Q4", "total_revenue": "32154000000",
         "segments": [
             {"segment": "商业", "revenue": "27241000000", "percent": "84.72", "yoy": ""},
             {"segment": "云智能集团", "revenue": "1243000000", "percent": "3.87", "yoy": "20"},
         ]},
    ]
    out = derive_segments_yaml(quarters)
    assert out["multi_segment"] is True
    assert out["data_source"] == "longbridge"
    names = [s["name"] for s in out["segments"]]
    assert "商业" in names and "云智能集团" in names


def test_derive_single_other_dominant_is_not_multi():
    # 只有"所有其他"且占比95% -> multi_segment False
    quarters = [
        {"date": "20250331", "report_period": "2025.Q4", "total_revenue": "1000",
         "segments": [{"segment": "所有其他", "revenue": "950", "percent": "95", "yoy": ""}]},
    ]
    out = derive_segments_yaml(quarters)
    assert out["multi_segment"] is False


def test_derive_aliases_for_known_segment():
    quarters = [
        {"date": "20250331", "report_period": "2025.Q4", "total_revenue": "1000",
         "segments": [{"segment": "云智能集团", "revenue": "100", "percent": "10", "yoy": ""}]},
    ]
    out = derive_segments_yaml(quarters)
    seg = [s for s in out["segments"] if s["name"] == "云智能集团"][0]
    assert "阿里云" in seg["aliases"]


def test_derive_empty_returns_none():
    assert derive_segments_yaml([]) is None
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py -v -k derive`
Expected: FAIL，`ImportError: cannot import name 'derive_segments_yaml'`

- [ ] **Step 3: 实现 derive_segments_yaml**

追加到 `skills/stock-analysis-debate/tools/longbridge_fetcher.py`：

```python
# 常见分部名 -> 别名（用于新闻业务线匹配）
_SEGMENT_ALIASES = {
    "云智能集团": ["阿里云", "云计算", "通义", "飞天", "AI"],
    "商业": ["淘宝", "天猫", "电商", "88VIP", "淘天"],
    "本地生活集团": ["饿了么", "高德", "本地生活", "外卖"],
    "菜鸟集团": ["菜鸟", "物流", "跨境物流"],
    "国际数字商业集团": ["国际电商", "速卖通", "Lazada", "国际商业"],
    "大文娱集团": ["优酷", "阿里影业", "大文娱", "灵犀互娱"],
    "游戏": ["腾讯游戏", "王者荣耀", "和平精英"],
    "金融科技": ["微信支付", "财付通", "金融科技"],
}


def derive_segments_yaml(quarters: list) -> dict:
    """从最近季度提取分部名，生成 segments.yaml 结构。无数据返回 None。"""
    if not quarters:
        return None
    # 取最近一个季度（date 最大）
    latest = max(quarters, key=lambda q: q.get("date", ""))
    segs = latest.get("segments", [])
    if not segs:
        return None

    # 排除"所有其他/其他"做 multi_segment 判断
    real_segs = [s for s in segs if s.get("segment", "") not in ("所有其他", "其他")]
    other = [s for s in segs if s.get("segment", "") in ("所有其他", "其他")]
    other_pct = 0.0
    if other:
        try:
            other_pct = float(other[0].get("percent", "0") or "0")
        except ValueError:
            other_pct = 0.0

    multi = len(real_segs) > 1 and other_pct < 90.0

    seg_list = []
    for s in real_segs + other:  # "其他"也保留进清单，但不计入 multi 判断
        name = s.get("segment", "")
        seg_list.append({
            "name": name,
            "aliases": _SEGMENT_ALIASES.get(name, []),
            "brief": "",
        })

    basis = f"长桥分部数据：{len(real_segs)}个业务分部"
    if other:
        basis += f"，所有其他占比{other_pct}%"
    return {
        "multi_segment": multi,
        "judgment_basis": basis,
        "data_source": "longbridge",
        "segments": seg_list,
    }
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py -v`
Expected: 全部 passed

- [ ] **Step 5: Commit**

```bash
git add skills/stock-analysis-debate/tools/longbridge_fetcher.py skills/stock-analysis-debate/tools/tests/test_longbridge_fetcher.py
git commit -m "feat(longbridge): 从分部数据推导segments.yaml结构"
```

---

## Task 9: fetch_data.py — 新浪翻页抓取 + 集成 news_filter

**Files:**
- Modify: `skills/stock-analysis-debate/tools/fetch_data.py`（`fetch_cn_news`、`fetch_hk_news` 函数 + main 调用）

**设计**：新浪翻页循环 `Page=1..N`，正则提取每页新闻。全部页汇总后，依次跑 `filter_noise` → `split_recent_and_history`（7天全量+8-30天高信号）→ `dedup_by_title`，再写 `news.txt` 和 `news_meta.txt`。CN/HK 都走这条流水（US 仍走 yfinance get_news，但同样过 news_filter 流水）。

- [ ] **Step 1: 改造 fetch_hk_news 增加翻页**

修改 `skills/stock-analysis-debate/tools/fetch_data.py` 的 `fetch_hk_news`，在抓取后返回结构化 list（而非直接拼字符串）。新增 `fetch_hk_news_raw(ticker, start_date, end_date)` 返回 `list[dict]`（每条含 title/date/provider/link），原 `fetch_hk_news` 改为调用 raw 后用 news_filter 处理再拼字符串。

写入新的 `fetch_hk_news_raw`（替换原 `fetch_hk_news` 内的抓取逻辑）：

```python
def _sina_fetch_all_pages(prefix: str, start_dt, end_dt, max_pages: int = 20) -> list:
    """翻页抓取新浪 vCB_AllNewsStock，返回原始 article list。

    prefix: 如 hk00700 / sh600519
    终止：抓到日期早于 start_dt，或连续两页无新增，或达 max_pages。
    """
    import re
    import requests
    all_items = []
    empty_streak = 0
    for page in range(1, max_pages + 1):
        url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{prefix}.phtml/Page={page}.phtml"
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.encoding = "gb2312"
        except Exception as e:
            print(f"  [sina page {page}] error: {e}", flush=True)
            break

        items = re.findall(
            r"(\d{4}-\d{2}-\d{2})&nbsp;(\d{2}:\d{2})(?:&nbsp;|\s)*<a[^>]*href='([^']*)'[^>]*>([^<]+)</a>",
            resp.text,
        )
        if not items:
            empty_streak += 1
            if empty_streak >= 2:
                break
            continue
        empty_streak = 0

        page_new = 0
        oldest_this_page = None
        for date_str, time_str, link, title in items:
            title = title.strip()
            if len(title) < 8:
                continue
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            if oldest_this_page is None or d < oldest_this_page:
                oldest_this_page = d
            all_items.append({
                "title": title,
                "date": f"{date_str} {time_str}",
                "provider": "Sina Finance",
                "link": link,
                "summary": "",
            })
            page_new += 1

        # 本页最早日期已早于窗口起始，可停
        if oldest_this_page and oldest_this_page < start_dt:
            break
    return all_items


def fetch_hk_news_raw(ticker: str, start_date: str, end_date: str) -> list:
    """抓取 HK 新浪新闻原始列表（未过滤）。"""
    code = ticker.split(".")[0]
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    prefix = f"hk{code}"
    return _sina_fetch_all_pages(prefix, start_dt, end_dt)
```

- [ ] **Step 2: 同样改造 fetch_cn_news_raw**

在 `fetch_data.py` 中新增 `fetch_cn_news_raw`（基于原 `fetch_cn_news` 的 Sina 部分 + 东方财富公告，返回结构化 list）。Eastmoney 公告也并入同一 list（provider 标 "Eastmoney"）：

```python
def fetch_cn_news_raw(ticker: str, start_date: str, end_date: str) -> list:
    """抓取 CN 新浪市场新闻 + 东方财富公告，返回原始 list。"""
    import re
    import requests
    code = ticker.split(".")[0]
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    items = []

    # Sina 市场新闻（翻页）
    first_digit = code[0]
    prefix = f"sh{code}" if first_digit == "6" else f"sz{code}"
    items.extend(_sina_fetch_all_pages(prefix, start_dt, end_dt))

    # Eastmoney 官方公告（单页20条）
    try:
        url_em = "https://np-anotice-stock.eastmoney.com/api/security/ann"
        params = {"page_size": 20, "page_index": 1, "ann_type": "A",
                  "client_source": "web", "stock_list": code}
        resp_em = requests.get(url_em, params=params, timeout=15)
        resp_em.raise_for_status()
        for item in resp_em.json().get("data", {}).get("list", []):
            nd = item.get("notice_date", "")
            title = item.get("title", "No title")
            try:
                nd_dt = datetime.strptime(nd.split(" ")[0], "%Y-%m-%d")
                if not (start_dt <= nd_dt <= end_dt + timedelta(days=1)):
                    continue
            except (ValueError, AttributeError):
                pass
            items.append({
                "title": title,
                "date": nd,
                "provider": "Eastmoney",
                "link": f"https://data.eastmoney.com/notices/detail/{code}/{item.get('art_code','')}.html",
                "summary": "",
            })
    except Exception as e:
        print(f"  [eastmoney] error: {e}", flush=True)
    return items
```

- [ ] **Step 3: 新增统一过滤+写文件函数**

在 `fetch_data.py` 中新增：

```python
from news_filter import filter_noise, split_recent_and_history, dedup_by_title


def process_and_write_news(raw_items: list, curr_date: str, news_start: str,
                           out_path: str, meta_path: str, lookback_days: int = 30) -> int:
    """对原始新闻跑 filter_noise -> split -> dedup，写 news.txt + news_meta.txt。
    返回最终保留条数。"""
    raw_count = len(raw_items)
    after_noise = filter_noise(raw_items)
    noise_count = raw_count - len(after_noise)
    recent, history = split_recent_and_history(after_noise, curr_date,
                                               recent_days=7, lookback_days=lookback_days)
    combined = recent + history
    after_dedup = dedup_by_title(combined)
    dedup_count = len(combined) - len(after_dedup)

    # 写 news.txt
    lines = [f"## News ({news_start} to {curr_date})\n"]
    for art in after_dedup:
        lines.append(f"**{art.get('title','')}**")
        lines.append(f"  Date: {art.get('date','')}")
        if art.get("provider"):
            lines.append(f"  Source: {art.get('provider')}")
        if art.get("link"):
            lines.append(f"  Link: {art.get('link')}")
        lines.append("")
    with open(out_path, "w") as f:
        f.write("\n".join(lines))

    # 写 news_meta.txt
    meta = [
        f"# News Processing Audit ({news_start} to {curr_date})\n",
        f"raw_fetched: {raw_count}",
        f"after_noise_filter: {len(after_noise)} (removed {noise_count})",
        f"recent_7d_kept: {len(recent)}",
        f"history_8_30d_kept: {len(history)}",
        f"after_dedup: {len(after_dedup)} (removed {dedup_count})",
        f"final_kept: {len(after_dedup)}",
    ]
    with open(meta_path, "w") as f:
        f.write("\n".join(meta))
    return len(after_dedup)
```

- [ ] **Step 4: 改 main() 的新闻分支调用新流水**

修改 `fetch_data.py` main() 中 `[3/8] Fetching company news` 段，替换为：

```python
    # 3. News (route by market, 翻页+过滤流水)
    print("  [3/8] Fetching company news...")
    news_path = os.path.join(ticker_dir, "news.txt")
    meta_path = os.path.join(ticker_dir, "news_meta.txt")
    if market == "CN":
        raw = fetch_cn_news_raw(ticker, news_start, curr_date)
    elif market == "HK":
        raw = fetch_hk_news_raw(ticker, news_start, curr_date)
    else:
        # US: 用 yfinance get_news，转成同结构 list
        raw = _yf_news_to_list(yf_ticker, news_start, curr_date)
    process_and_write_news(raw, curr_date, news_start, news_path, meta_path,
                           lookback_days=NEWS_LOOKBACK_DAYS)
    results["files"]["news"] = news_path
```

并新增 US 转换辅助 `_yf_news_to_list`（基于原 `fetch_news` 的解析逻辑，返回 list[dict]）：

```python
def _yf_news_to_list(ticker: str, start_date: str, end_date: str) -> list:
    symbol = normalize_ticker(ticker)
    out = []
    try:
        stock = yf.Ticker(symbol)
        news = retry(lambda: stock.get_news(count=60))
        if not news:
            return out
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        for article in news:
            content = article.get("content", article)
            title = content.get("title", "")
            pub_date_str = content.get("pubDate", "")
            provider = content.get("provider", {}).get("displayName", "")
            url_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
            link = url_obj.get("url", "")
            date_field = ""
            if pub_date_str:
                try:
                    pd = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    if not (start_dt <= pd <= end_dt + timedelta(days=1)):
                        continue
                    date_field = pd.strftime("%Y-%m-%d %H:%M")
                except (ValueError, AttributeError):
                    date_field = pub_date_str
            out.append({"title": title, "date": date_field, "provider": provider,
                        "link": link, "summary": content.get("summary", "")})
    except Exception as e:
        print(f"  [yf news] error: {e}", flush=True)
    return out
```

- [ ] **Step 5: 集成验证 — HK 翻页抓全**

Run: `python skills/stock-analysis-debate/tools/fetch_data.py 09988.HK 2026-07-14 --output-dir skills/stock-analysis-debate/tools/data`
Expected: 完成；检查 `cat skills/stock-analysis-debate/tools/data/09988_HK/2026-07-14/news_meta.txt` 应显示 `raw_fetched` 显著大于40（翻页生效），`final_kept` 远小于 raw（去噪去重生效）。检查 `news.txt` 不再含"周文强/霍尔木兹/国旗"等噪声。

- [ ] **Step 6: Commit**

```bash
git add skills/stock-analysis-debate/tools/fetch_data.py
git commit -m "feat(fetch_data): 新浪翻页抓全+news_filter去噪去重分层流水"
```

---

## Task 10: fetch_data.py — 长桥分部抓取 + segments flag

**Files:**
- Modify: `skills/stock-analysis-debate/tools/fetch_data.py`

**设计**：main() 中市场为 HK/US 时，调 longbridge_fetcher 抓 API1+API2，解析后存 `segments_financials.json`（含两个字段）。检查 ticker 级 `segments.yaml` 是否存在，不存在写 `segments_missing.flag`；长桥抓取失败写 `segments_fetch_failed.flag`。CN 跳过。

- [ ] **Step 1: 新增长桥抓取段**

在 `fetch_data.py` 顶部 import：

```python
from longbridge_fetcher import (build_counter_id, fetch_business_historical,
                                fetch_revenue_sankey, parse_business_historical,
                                parse_revenue_sankey)
```

在 main() 的 insider 抓取之后、写 summary 之前，新增 `[10] Segments` 段：

```python
    # 10. Segments (仅 HK/US)
    print("  [10] Fetching business segments...")
    if market in ("HK", "US"):
        seg_path = os.path.join(ticker_dir, "segments_financials.json")
        bh_raw = fetch_business_historical(ticker)
        bh_parsed = parse_business_historical(bh_raw)
        rs_raw = fetch_revenue_sankey(ticker)
        rs_parsed = parse_revenue_sankey(rs_raw)
        seg_data = {"business_historical": bh_parsed, "revenue_sankey": rs_parsed}
        with open(seg_path, "w") as f:
            json.dump(seg_data, f, ensure_ascii=False, indent=2)
        results["files"]["segments_financials"] = seg_path

        # 检查 ticker 级 segments.yaml
        ticker_root = os.path.join(output_dir, ticker.replace(".", "_"))
        yaml_path = os.path.join(ticker_root, "segments.yaml")
        if not os.path.exists(yaml_path):
            if not bh_parsed and not rs_parsed:
                # 长桥无数据/失败
                open(os.path.join(ticker_dir, "segments_fetch_failed.flag"), "w").close()
                print("    longbridge returned no segment data -> segments_fetch_failed.flag", flush=True)
            else:
                open(os.path.join(ticker_dir, "segments_missing.flag"), "w").close()
                print("    segments.yaml missing -> segments_missing.flag", flush=True)
    else:
        print("  [10] Skipped (CN market, no segment analysis)", flush=True)
```

- [ ] **Step 2: 集成验证 — HK 长桥抓取**

Run: `cd /Users/zhangqi.huang/aaai && python skills/stock-analysis-debate/tools/fetch_data.py 09988.HK 2026-07-14 --output-dir skills/stock-analysis-debate/tools/data`
Expected: 终端打印 `[10] Fetching business segments...`；`ls skills/stock-analysis-debate/tools/data/09988_HK/2026-07-14/` 含 `segments_financials.json`（非空，含 business_historical 数组）；由于首次运行无 `segments.yaml`，应生成 `segments_missing.flag`。
验证 JSON 有数据：`python -c "import json; d=json.load(open('skills/stock-analysis-debate/tools/data/09988_HK/2026-07-14/segments_financials.json')); print(len(d['business_historical']))"`
Expected: 打印 N>0

- [ ] **Step 3: Commit**

```bash
git add skills/stock-analysis-debate/tools/fetch_data.py
git commit -m "feat(fetch_data): 长桥分部抓取(HK/US)+segments flag"
```

---

## Task 11: Phase 1.5 清单生成脚本逻辑

**Files:**
- Modify: `skills/stock-analysis-debate/tools/prepare_segments.py`（扩展 main 支持 `--gen-yaml`）
- Test: `skills/stock-analysis-debate/tools/tests/test_prepare_segments.py`

**设计**：prepare_segments.py 加 `--gen-yaml` 模式：读当日 `segments_financials.json`，跑 `derive_segments_yaml`，写 ticker 级 `segments.yaml`（用 PyYAML dump），并跑 `to_csv` 写 `segments_financials.csv`。清理 `segments_missing.flag`。

- [ ] **Step 1: 写失败测试 — gen_yaml_from_data**

追加到 `skills/stock-analysis-debate/tools/tests/test_prepare_segments.py`：

```python
from prepare_segments import gen_yaml_from_data


def test_gen_yaml_multi_segment():
    bh = [{"date": "20250331", "report_period": "2025.Q4", "total_revenue": "1000",
           "segments": [
               {"segment": "商业", "revenue": "900", "percent": "90", "yoy": ""},
               {"segment": "云智能集团", "revenue": "100", "percent": "10", "yoy": "20"},
           ]}]
    data = {"business_historical": bh, "revenue_sankey": []}
    out = gen_yaml_from_data(data)
    assert out["multi_segment"] is True
    assert out["data_source"] == "longbridge"
    assert any(s["name"] == "云智能集团" for s in out["segments"])


def test_gen_yaml_empty_returns_none():
    assert gen_yaml_from_data({"business_historical": [], "revenue_sankey": []}) is None
    assert gen_yaml_from_data({}) is None
```

- [ ] **Step 2: 跑测试验证失败**

Run: `PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_prepare_segments.py -v -k gen_yaml`
Expected: FAIL，`ImportError: cannot import name 'gen_yaml_from_data'`

- [ ] **Step 3: 实现 gen_yaml_from_data**

在 `skills/stock-analysis-debate/tools/prepare_segments.py` 顶部加 import：

```python
from longbridge_fetcher import derive_segments_yaml
```

追加函数：

```python
def gen_yaml_from_data(data: dict) -> dict:
    """从 segments_financials.json 内容推导 segments.yaml 结构。无数据返回 None。"""
    if not data:
        return None
    bh = data.get("business_historical", [])
    if not bh:
        return None
    return derive_segments_yaml(bh)
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/test_prepare_segments.py -v`
Expected: 全部 passed

- [ ] **Step 5: 扩展 main 支持 --gen-yaml**

修改 `skills/stock-analysis-debate/tools/prepare_segments.py` 的 main，增加 `--gen-yaml` 参数分支。替换整个 main 为：

```python
def main():
    import sys
    parser = argparse.ArgumentParser(description="长桥分部数据预处理")
    parser.add_argument("ticker", help="Ticker (e.g. 09988.HK, AAPL)")
    parser.add_argument("date", help="Analysis date YYYY-MM-DD")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--recent-n", type=int, default=8)
    parser.add_argument("--gen-yaml", action="store_true",
                        help="同时生成 ticker 级 segments.yaml")
    args = parser.parse_args()

    output_dir = args.output_dir or os.path.join(os.path.dirname(__file__), "..", "data")
    ticker = args.ticker.upper()
    day_dir = os.path.join(output_dir, ticker.replace(".", "_"), args.date)
    json_path = os.path.join(day_dir, "segments_financials.json")

    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found", flush=True)
        return 1

    with open(json_path) as f:
        data = json.load(f)

    quarters = data.get("business_historical", [])
    csv_text = to_csv(quarters, recent_n=args.recent_n)
    csv_path = os.path.join(day_dir, "segments_financials.csv")
    with open(csv_path, "w") as f:
        f.write(csv_text)
    print(f"Segments CSV written to {csv_path}", flush=True)

    if args.gen_yaml:
        import yaml
        yaml_struct = gen_yaml_from_data(data)
        if yaml_struct is None:
            print("No segment data to derive yaml", flush=True)
            return 1
        ticker_root = os.path.join(output_dir, ticker.replace(".", "_"))
        yaml_path = os.path.join(ticker_root, "segments.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_struct, f, allow_unicode=True, sort_keys=False)
        print(f"segments.yaml written to {yaml_path}", flush=True)
        # 清理 missing flag
        flag = os.path.join(day_dir, "segments_missing.flag")
        if os.path.exists(flag):
            os.remove(flag)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 6: 集成验证 — 生成阿里清单**

Run: `cd /Users/zhangqi.huang/aaai && python skills/stock-analysis-debate/tools/prepare_segments.py 09988.HK 2026-07-14 --output-dir skills/stock-analysis-debate/tools/data --gen-yaml`
Expected: 打印 CSV 和 yaml 写入路径。`cat skills/stock-analysis-debate/tools/data/09988_HK/segments.yaml` 应显示 `multi_segment: true` + 分部列表（商业/云智能集团等）。`cat skills/stock-analysis-debate/tools/data/09988_HK/2026-07-14/segments_financials.csv` 应有表头+数据行。`segments_missing.flag` 应已被删除。

- [ ] **Step 7: Commit**

```bash
git add skills/stock-analysis-debate/tools/prepare_segments.py skills/stock-analysis-debate/tools/tests/test_prepare_segments.py
git commit -m "feat(prepare_segments): --gen-yaml生成segments.yaml并产出CSV"
```

---

## Task 12: 改造 news_analyst.md prompt

**Files:**
- Modify: `skills/stock-analysis-debate/prompts/news_analyst.md`

**设计**：原 prompt 是通用研究指令。改为两段式：先打分标注每条新闻（影响力0-3 + 业务线标签），再做近似去重，最后写报告含高分事件表和业务线命中表。

- [ ] **Step 1: 重写 news_analyst.md**

写入 `skills/stock-analysis-debate/prompts/news_analyst.md`（覆盖全文）：

```markdown
You are a news analyst. You will be given `news.txt` (already de-duplicated and de-noised at the data layer, but may still contain near-duplicates from media rewrites). If a `segments.yaml` business-segment list is provided, use it for tagging.

## Task

### Step 1: Score and tag every news item
For each news item in `news.txt`, assign:
- **Impact score (0-3)**:
  - 0 = noise (unrelated to the company / macro filler / inspirational content)
  - 1 = marginally related
  - 2 = relevant but routine
  - 3 = high-signal catalyst (price war, rating change, major segment shift, M&A, regulatory action, capital flow, earnings)
- **Segment tag**: which business segment (from segments.yaml `name`/`aliases`) the news relates to. Use "N/A" if none.

### Step 2: Near-duplicate removal
Identify media rewrites / same-event-different-headlines. Within each near-duplicate group, keep only the highest-scored item for the report. (The data layer only removed exact-title duplicates; you handle semantic near-duplicates here.)

### Step 3: Write the report
Write a comprehensive report of the current news state relevant for trading. Provide specific, actionable insights with supporting evidence. Then append TWO Markdown tables:

**Table A — High-signal events (score ≥ 2):**
| Date | Title | Score | Segment | Direction |

**Table B — Segment hit summary:**
| Segment | # high-signal items | Net direction (pos/neg/neutral) |

Direction = whether the news is positive/negative/neutral for that segment's growth and thus the stock price. Include market-specific notes: A-share (涨跌停/停牌/分红送转/ST), HK (配股/回购/Stock Connect 南向资金).
```

- [ ] **Step 2: Commit**

```bash
git add skills/stock-analysis-debate/prompts/news_analyst.md
git commit -m "feat(prompt): news_analyst加打分标注+业务线命中+近似去重"
```

---

## Task 13: 新建 segment_analyst.md prompt

**Files:**
- Create: `skills/stock-analysis-debate/prompts/segment_analyst.md`

- [ ] **Step 1: 写 segment_analyst.md**

写入 `skills/stock-analysis-debate/prompts/segment_analyst.md`：

```markdown
You are a business-segment analyst for a multi-segment company. You receive `segments_financials.csv` (quarterly segment revenue / % / YoY from Longbridge) and the News Analyst's segment-hit summary.

## Task

1. **Identify inflection points**: For each segment, compare the latest quarter's YoY growth vs prior quarters. Flag segments showing acceleration (growth up) or deceleration (growth down / losses widening).
2. **Direction for stock price**: For each flagged inflection, judge whether it is positive, negative, or neutral for the GROUP stock price, considering segment weight (% of revenue).
3. **Net driver**: State which segment is the primary growth/decline driver for the group this period.
4. **Evidence**: Anchor every claim to specific quarter data + corresponding news items.

Append a Markdown table:

| Segment | Latest YoY | Prior YoY | Inflection | Rev % | Stock-price impact |

End with: `PRIMARY DRIVER: <segment> — <positive/negative> <one-line reason>`
```

- [ ] **Step 2: Commit**

```bash
git add skills/stock-analysis-debate/prompts/segment_analyst.md
git commit -m "feat(prompt): 新增segment_analyst分部拐点分析"
```

---

## Task 14: 微调 fundamentals_analyst.md

**Files:**
- Modify: `skills/stock-analysis-debate/prompts/fundamentals_analyst.md`

**设计**：在原 prompt 末尾加一句，引用 Segment Analyst 结论（若存在）。

- [ ] **Step 1: 追加引用说明**

在 `skills/stock-analysis-debate/prompts/fundamentals_analyst.md` 末尾追加：

```markdown

If a Segment Analyst report is provided in context, incorporate its segment-level inflection conclusions (which segment drives growth/decline, and the group-level direction) into your fundamentals assessment rather than treating the company as a single consolidated block.
```

- [ ] **Step 2: Commit**

```bash
git add skills/stock-analysis-debate/prompts/fundamentals_analyst.md
git commit -m "feat(prompt): fundamentals_analyst引用segment结论"
```

---

## Task 15: SKILL.md 工作流改造

**Files:**
- Modify: `skills/stock-analysis-debate/SKILL.md`

**设计**：插入 Phase 1.5；Phase 2 增条件触发的 Segment Analyst；Phase 3-7 context 增 segment 报告；标注 CN 不走业务线。Critical Execution Rules 更新。

- [ ] **Step 1: 在 Workflow 列表插入 Phase 1.5**

在 `skills/stock-analysis-debate/SKILL.md` 的 Workflow 有序列表中，Phase 1 和 Phase 2 之间插入：

```markdown
1.5. **Phase 1.5: Segment Setup** (HK/US only) — Bash: `prepare_segments.py --gen-yaml`
   - Skipped for CN market. Skipped if `segments_fetch_failed.flag` exists.
   - Foreground, synchronous.
```

并把原 Phase 2 描述改为含条件第5 analyst：

```markdown
2. **Phase 2: Analyst Reports** — 4 or 5 Agent calls
   - Parallel: launch all in a SINGLE message, foreground.
   - 5th agent (Segment Analyst) runs ONLY for HK/US with `multi_segment: true` in `segments.yaml`.
```

- [ ] **Step 2: 新增 Phase 1.5 详细章节**

在 Phase 1 章节之后、"## Phase 2" 之前插入：

```markdown
## Phase 1.5: Segment Setup (HK/US only)

**Skip conditions**: CN market, OR `segments_fetch_failed.flag` exists in the date dir.

1. Check `skills/stock-analysis-debate/tools/data/{TICKER}/segments.yaml` (ticker-level, no date).
   - If exists: read it, then still run prepare_segments.py WITHOUT `--gen-yaml` to produce the day's `segments_financials.csv`:
     ```bash
     python skills/stock-analysis-debate/tools/prepare_segments.py {TICKER} {DATE} --output-dir skills/stock-analysis-debate/tools/data
     ```
   - If missing: run with `--gen-yaml` (generates both `segments.yaml` and the day's CSV):
     ```bash
     python skills/stock-analysis-debate/tools/prepare_segments.py {TICKER} {DATE} --output-dir skills/stock-analysis-debate/tools/data --gen-yaml
     ```
2. Read `segments.yaml`. Record `multi_segment` for Phase 2 branching.
3. Proceed immediately to Phase 2.
```

- [ ] **Step 3: Phase 2 章节增 Segment Analyst**

在 `skills/stock-analysis-debate/SKILL.md` 的 Phase 2 "### The 4 Analysts" 列表后追加：

```markdown
### Conditional 5th Analyst (HK/US + multi_segment only):

**Segment Analyst** — Prompt: `skills/stock-analysis-debate/prompts/segment_analyst.md` — Data: `segments_financials.csv`, News Analyst's segment-hit summary (from `phase2_analyst_reports.md`).

Launch Segment Analyst IN PARALLEL with the other 4 only when `segments.yaml` has `multi_segment: true`. Otherwise run 4 analysts as before.
```

- [ ] **Step 4: Phase 3-7 context 增 segment 报告**

在 `skills/stock-analysis-debate/SKILL.md` Phase 3 Step 3a 的 context 说明里追加一句（在 "Paste ALL 4 analyst reports verbatim" 之后）：

```markdown
- If a Segment Analyst report exists (Phase 2 produced 5 reports), paste it verbatim alongside the 4 analyst reports. Include instrument-segment context: "This is a N-segment group; primary driver: <segment>."
```

同样在 Phase 6 的 "Context shared across all 6 calls" 处追加：

```markdown
- If a Segment Analyst report exists, paste it verbatim with the 4 analyst reports.
```

- [ ] **Step 5: Critical Execution Rules 增补**

在 `skills/stock-analysis-debate/SKILL.md` 的 Critical Execution Rules 列表末尾追加：

```markdown
6. **CN market skips Phase 1.5 and Segment Analyst entirely.** No `segments.yaml`, no segment data. Run 4 analysts.
7. **If `segments_fetch_failed.flag` exists**, treat as CN: skip Phase 1.5 and Segment Analyst, run 4 analysts. Note the missing segment view in the final report.
```

- [ ] **Step 6: 更新 Phase 1 文件表**

在 `skills/stock-analysis-debate/SKILL.md` Phase 1 的文件表后追加（HK/US only）：

```markdown
| `segments_financials.json` | 长桥原始分部数据（季度+财年） | 长桥 API1+API2 |
| `segments_financials.csv` | 预处理紧凑分部CSV | prepare_segments.py (Phase 1.5) |
| `news_meta.txt` | 新闻抓取/去重/去噪审计 | fetch_data.py |
| `segments_missing.flag` | 清单缺失标记（触发Phase 1.5生成） | fetch_data.py |
| `segments_fetch_failed.flag` | 长桥抓取失败标记（降级） | fetch_data.py |
```

ticker 级：
```markdown
| `data/{TICKER}/segments.yaml` | 业务线清单（跨次复用） | prepare_segments.py --gen-yaml |
```

- [ ] **Step 7: 端到端验证 — 跑完整 fetch + prepare**

Run: `cd /Users/zhangqi.huang/aaai && rm -f skills/stock-analysis-debate/tools/data/09988_HK/segments.yaml && python skills/stock-analysis-debate/tools/fetch_data.py 09988.HK 2026-07-14 --output-dir skills/stock-analysis-debate/tools/data && python skills/stock-analysis-debate/tools/prepare_segments.py 09988.HK 2026-07-14 --output-dir skills/stock-analysis-debate/tools/data --gen-yaml`
Expected: fetch 生成 segments_financials.json + segments_missing.flag；prepare 生成 segments.yaml + segments_financials.csv 并删除 flag。`cat skills/stock-analysis-debate/tools/data/09988_HK/segments.yaml` 显示 `multi_segment: true`。

- [ ] **Step 8: Commit**

```bash
git add skills/stock-analysis-debate/SKILL.md
git commit -m "feat(skill): Phase 1.5 + 条件触发的Segment Analyst + CN跳过 + 降级"
```

---

## Task 16: README 同步 + 全量回归

**Files:**
- Modify: `README.md`（若 skill 有独立 README 则改之；否则在 repo README 增 skill 说明）

- [ ] **Step 1: 更新 README**

在 repo `README.md` 中 stock-analysis-debate 相关段落补充：新增新闻翻页去噪流水、长桥分部数据（HK/US）、Phase 1.5、Segment Analyst、CN 不走业务线。如 repo 无 README 则跳过此步并记录。

- [ ] **Step 2: 全量单测回归**

Run: `cd /Users/zhangqi.huang/aaai && PYTHONPATH=skills/stock-analysis-debate/tools python -m pytest skills/stock-analysis-debate/tools/tests/ -v`
Expected: 全部 passed

- [ ] **Step 3: 集成回归 — US 市场**

Run: `cd /Users/zhangqi.huang/aaai && python skills/stock-analysis-debate/tools/fetch_data.py AAPL 2026-07-14 --output-dir skills/stock-analysis-debate/tools/data && python skills/stock-analysis-debate/tools/prepare_segments.py AAPL 2026-07-14 --output-dir skills/stock-analysis-debate/tools/data --gen-yaml`
Expected: AAPL 生成完整数据含 segments；`segments.yaml` 含 AAPL 分部（如 美洲/欧洲/大中华/日本/其他 或服务/产品）。

- [ ] **Step 4: 集成回归 — CN 降级**

Run: `cd /Users/zhangqi.huang/aaai && python skills/stock-analysis-debate/tools/fetch_data.py 600519.SH 2026-07-14 --output-dir skills/stock-analysis-debate/tools/data`
Expected: 终端打印 `[10] Skipped (CN market...)`；该日期目录无 segments_financials.json、无 flag；新闻流水仍正常（新浪翻页+去噪）。

- [ ] **Step 5: Commit**

```bash
git add README.md skills/stock-analysis-debate/tools/data/
git commit -m "docs: 同步README + 全量回归验证"
```

---

## 完成标准

- `pytest skills/stock-analysis-debate/tools/tests/` 全绿。
- HK（09988）+ US（AAPL）端到端：fetch_data 产出 news.txt（翻页去噪）、segments_financials.json/csv、segments.yaml（multi_segment=true）。
- CN（600519）端到端：跳过分部，新闻流水正常。
- 失败降级：长桥不可用时生成 segments_fetch_failed.flag，不阻断分析。

---
