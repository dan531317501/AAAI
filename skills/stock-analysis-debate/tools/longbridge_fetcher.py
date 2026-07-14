"""长桥证券分部数据抓取：counter_id 生成 + API1/API2 调用 + JSON解析。"""
import requests
from urllib.parse import quote


def build_counter_id(ticker: str) -> str:
    """根据 ticker 生成长桥 counter_id。CN 返回 None（不支持）。

    HK: ST/HK/{code去前导零}  例如 09988.HK -> ST/HK/9988
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
    latest = max(quarters, key=lambda q: q.get("date", ""))
    segs = latest.get("segments", [])
    if not segs:
        return None

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
    for s in real_segs + other:
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
