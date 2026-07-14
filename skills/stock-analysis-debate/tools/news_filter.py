"""新闻去重/去噪/分层保留的纯函数。"""
import re


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
