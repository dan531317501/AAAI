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
