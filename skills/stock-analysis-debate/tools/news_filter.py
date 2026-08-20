"""新闻去重/去噪/分层保留的纯函数。"""
import re
from datetime import datetime, timedelta


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
    # 去掉所有空白字符（含全角空格）
    s = re.sub(r"\s+", "", s)
    return s


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


def render_news_evidence(articles: list, news_start: str, curr_date: str) -> tuple[str, dict]:
    """将最终新闻列表序列化为带稳定证据编号和内容层级的文本。

    当前采集链路不包含社交媒体帖子或平台情绪指标，因此在产物中显式标记
    social posts 由独立文件 stocktwits.txt / reddit.txt 提供，news.txt 只做新闻叙事。
    """
    lines = [
        f"## News ({news_start} to {curr_date})\n",
        "Evidence Scope: company news feed",
        "Social Data Available: separate (stocktwits.txt, reddit.txt)",
        (
            "Social Data Note: this file contains news items only; first-party "
            "social-media posts and platform sentiment metrics live in "
            "stocktwits.txt and reddit.txt.\n"
        ),
    ]
    summary_count = 0
    title_only_count = 0

    for index, art in enumerate(articles, start=1):
        evidence_id = f"N{index:03d}"
        summary = str(art.get("summary") or "").strip()
        content_level = "summary" if summary else "title_only"
        if summary:
            summary_count += 1
        else:
            title_only_count += 1

        lines.append(f"### [{evidence_id}] {art.get('title', '')}")
        lines.append(f"  Date: {art.get('date', '')}")
        if art.get("provider"):
            lines.append(f"  Source: {art.get('provider')}")
        if art.get("link"):
            lines.append(f"  Link: {art.get('link')}")
        lines.append(f"  Content Level: {content_level}")
        if summary:
            lines.append(f"  Summary: {summary}")
        lines.append("")

    stats = {
        "summary": summary_count,
        "title_only": title_only_count,
        "social_data_available": "separate (stocktwits.txt, reddit.txt)",
    }
    return "\n".join(lines), stats


def filter_by_date_window(
    articles: list,
    curr_date: str,
    *,
    lookback_days: int = 60,
) -> tuple[list, int, int]:
    """Keep only dated articles inside the inclusive current-research window.

    Returns ``(kept, out_of_window_count, missing_or_unparseable_count)``.
    A date-less item cannot be used as a current catalyst and is therefore
    excluded instead of being treated as recent by default.
    """
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - timedelta(days=lookback_days)
    end_dt = curr_dt + timedelta(days=1)
    kept = []
    out_of_window = 0
    missing_date = 0
    for article in articles:
        raw_date = article.get("published_at") or article.get("date", "")
        parsed = None
        if raw_date:
            text = str(raw_date).strip()
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if parsed.tzinfo is not None:
                    parsed = parsed.replace(tzinfo=None)
            except ValueError:
                parsed = _parse_article_date(text)
        if parsed is None:
            missing_date += 1
            continue
        if parsed < start_dt or parsed >= end_dt:
            out_of_window += 1
            continue
        normalized = dict(article)
        normalized["published_at"] = parsed.isoformat()
        normalized["date"] = parsed.strftime("%Y-%m-%d %H:%M")
        kept.append(normalized)
    kept.sort(key=lambda item: item.get("published_at", ""), reverse=True)
    return kept, out_of_window, missing_date


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


# 8-60天窗口保留用的高信号词（命中其一即保留）
# 中文 + 英文双语关键词，确保港股 yfinance 英文标题也能被保留
_CN_HIGH_SIGNAL_KEYWORDS = [
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

_EN_HIGH_SIGNAL_KEYWORDS = [
    # 公司名/代码（英文财经媒体中提到公司名本身就是强信号）
    "meituan", "3690",
    # 财务/业绩
    "earnings", "revenue", "profit", "margin", "EBITDA",
    # 并购/交易
    "acquisition", "merger", "buyout", "takeover", "deal",
    # 评级/目标价
    "upgrade", "downgrade", "target price", "rating", "initiates",
    "overweight", "underweight", "outperform", "underperform",
    # 竞争/补贴
    "price war", "subsidy", "discount",
    # 合作/战略
    "partnership", "strategic", "alliance",
    # 监管/处罚
    "regulatory", "fine", "investigation", "probe", "crackdown",
    # 回购/分红/持股
    "buyback", "repurchase", "dividend", "stake", "holding",
    # 分拆/上市
    "spin-off", "split", "IPO", "listing",
    # 增长/衰退
    "growth", "decline", "loss", "impairment", "write-down",
    # 展望/预警
    "guidance", "outlook", "forecast", "warns",
    # 管理层变动
    "board", "CEO", "CFO", "management", "reshuffle",
    # 价格变动（常见英文财经标题用词）
    "surge", "jump", "soar", "rally", "climb",
    "fall", "fell", "slide", "plunge", "tumble", "sink",
    "sell-off", "selloff", "rout",
    "rebound", "recovery", "bounce",
    # 估值
    "cheap", "expensive", "undervalued", "overvalued", "pricey",
    # 风险/压力
    "concern", "worry", "risk", "pressure", "struggle",
    # 科技/AI相关（中概股常见催化剂）
    "AI", "artificial intelligence", "tech", "technology",
    "autonomous", "drone", "robot",
]


def is_high_signal(title: str) -> bool:
    """标题命中高信号词则返回 True（用于8-60天窗口粗筛）。
    支持中文和英文双语关键词，不区分大小写匹配英文。
    """
    if not title:
        return False
    for kw in _CN_HIGH_SIGNAL_KEYWORDS:
        if kw in title:
            return True
    title_lower = title.lower()
    for kw in _EN_HIGH_SIGNAL_KEYWORDS:
        if kw.lower() in title_lower:
            return True
    return False


def _parse_article_date(date_str: str) -> datetime:
    """解析 'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD'，失败返回 None。"""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def split_recent_and_history(articles: list, curr_date: str,
                             recent_days: int = 7, lookback_days: int = 60):
    """按日期分层：recent_days 内全留(recent)，recent+1~lookback 天只留高信号(history)，
    超出 lookback 的丢弃。返回 (recent_list, history_list)。
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
