"""长桥证券数据抓取：K 线、分部数据及其 JSON 解析。"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math
import re
import unicodedata
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from provider_runtime import retry_call


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


def build_kline_counter_id(ticker: str, market: str = None) -> str:
    """根据 ticker 生成长桥 K 线接口的 counter_id。

    HK: ST/HK/{code去前导零}
    US: ST/US/{ticker}
    CN: ST/SH|SZ/{code}
    """
    upper = ticker.upper()
    code = upper.split(".")[0]

    if market == "HK" or upper.endswith(".HK") or (
        market is None and code.isdigit() and len(code) <= 5
    ):
        return f"ST/HK/{code.lstrip('0') or '0'}"
    if upper.endswith((".SH", ".SS")):
        return f"ST/SH/{code}"
    if upper.endswith(".SZ"):
        return f"ST/SZ/{code}"
    if upper.endswith(".BJ"):
        return None

    if market == "CN" or (code.isdigit() and len(code) == 6):
        if code.startswith(("5", "6", "9")) and not code.startswith("92"):
            exchange = "SH"
        elif code.startswith(("0", "3")):
            exchange = "SZ"
        else:
            return None
        return f"ST/{exchange}/{code}"

    return f"ST/US/{upper}"


def _normalize_kline_volume(item: dict, market: str | None) -> float | None:
    """Normalize Longbridge fallback volume to shares when its unit is known.

    The current CN range-kline endpoint has returned lots in ``amount`` while
    HK/US rows and yfinance use shares.  CN turnover provides a runtime sanity
    check: turnover / (amount * close) is approximately 100 for lots and 1
    for shares.  Ambiguous rows are left unavailable instead of contaminating
    volume-weighted indicators.
    """
    raw_amount = item.get("amount")
    if raw_amount in (None, ""):
        return None
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(amount) or amount < 0:
        return None
    if market != "CN" or amount == 0:
        return amount

    turnover_raw = item.get("balance")
    if turnover_raw in (None, ""):
        turnover_raw = item.get("turnover")
    try:
        close = float(item["close"])
        turnover = float(turnover_raw)
    except (KeyError, TypeError, ValueError):
        return None
    if (
        not math.isfinite(close)
        or close <= 0
        or not math.isfinite(turnover)
        or turnover < 0
    ):
        return None

    implied_multiplier = turnover / (amount * close)
    if 0.5 <= implied_multiplier <= 2:
        return amount
    if 50 <= implied_multiplier <= 200:
        return amount * 100
    return None


def parse_range_klines(resp: dict, market: str = None) -> list:
    """解析长桥日 K，返回按日期升序排列的 OHLCV 记录。"""
    if not isinstance(resp, dict) or resp.get("code") != 0:
        return []

    market_tz = {
        "CN": ZoneInfo("Asia/Shanghai"),
        "HK": ZoneInfo("Asia/Hong_Kong"),
        "US": ZoneInfo("America/New_York"),
    }.get(market, timezone.utc)
    records = {}
    for item in resp.get("data", {}).get("klines", []):
        try:
            date = datetime.fromtimestamp(
                int(item["timestamp"]), tz=timezone.utc
            ).astimezone(
                market_tz
            ).date().isoformat()
            records[date] = {
                "Date": date,
                "Open": float(item["open"]),
                "High": float(item["high"]),
                "Low": float(item["low"]),
                "Close": float(item["close"]),
                "Volume": _normalize_kline_volume(item, market),
            }
        except (KeyError, TypeError, ValueError, OverflowError):
            continue

    return [records[date] for date in sorted(records)]


def _parse_sankey_period(period: str):
    """把 QN YYYY 转成 (year, quarter)；格式不合法时返回 None。"""
    match = re.fullmatch(r"\s*Q([1-4])\s+(\d{4})\s*", str(period), re.IGNORECASE)
    if not match:
        return None
    return int(match.group(2)), int(match.group(1))


def _previous_quarter(year: int, quarter: int) -> tuple:
    if quarter == 1:
        return year - 1, 4
    return year, quarter - 1


def _growth_percent(current, base) -> str:
    """按百分比计算增长率；基期非正或数值无效时返回空字符串。"""
    try:
        current_value = Decimal(str(current))
        base_value = Decimal(str(base))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    if not current_value.is_finite() or not base_value.is_finite() or base_value <= 0:
        return ""
    growth = (current_value / base_value - Decimal("1")) * Decimal("100")
    text = format(growth.quantize(Decimal("0.000001")), "f").rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _decimal_value(value):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _normalized_segment_name(name: str) -> str:
    text = unicodedata.normalize("NFKC", str(name or "")).casefold()
    return re.sub(r"[\s_\-–—]+", "", text)


_INTERSEGMENT_ELIMINATION_NAMES = {
    _normalized_segment_name(name)
    for name in (
        "部门间冲销",
        "部门间冲消",
        "部门间抵销",
        "部门间抵消",
        "分部间冲销",
        "分部间冲消",
        "分部间抵销",
        "分部间抵消",
        "Intersegment elimination",
        "Intersegment eliminations",
        "Inter-segment elimination",
        "Inter-segment eliminations",
        "抵消",
        "抵销",
        "冲消",
        "冲销",
        "Elimination",
        "Eliminations",
    )
}
_OTHER_SEGMENT_NAMES = {
    _normalized_segment_name(name)
    for name in ("所有其他", "其他", "未分摊", "All Other", "All Others", "Unallocated")
}


def classify_segment_row(name: str) -> str:
    """区分真实业务分部、其他汇总项和部门间抵销项。"""
    normalized = _normalized_segment_name(name)
    if normalized in _INTERSEGMENT_ELIMINATION_NAMES:
        return "intersegment_elimination"
    if normalized in _OTHER_SEGMENT_NAMES:
        return "other"
    return "business_segment"


_SANKEY_NODE_TYPES = {
    "total_rev": "revenue_total",
    "gp": "gross_profit",
    "cost_rev": "cost_of_revenue",
    "oper_inc": "operating_profit",
    "oper_fee": "operating_expense",
    "sga": "selling_general_and_administrative_expense",
    "rd_exp": "research_and_development_expense",
}


def classify_sankey_node(node: dict) -> str:
    """按桑基节点的会计语义分类。"""
    if classify_segment_row(node.get("name", "")) == "intersegment_elimination":
        return "intersegment_elimination"
    try:
        level = int(node.get("level"))
    except (TypeError, ValueError):
        level = None
    if level == 1:
        return classify_segment_row(node.get("name", ""))
    return _SANKEY_NODE_TYPES.get(node.get("key"), "financial_node")


def _sankey_growth_value(node: dict):
    if node.get("key") == "total_rev":
        return node.get("show_value", "")
    return node.get("value", "")


def normalize_revenue_sankey(periods: list) -> None:
    """为桑基节点补齐分类、构成、增长率、勾稽及缺失分部检测。"""
    values = {}
    for item in periods:
        period = _parse_sankey_period(item.get("period", ""))
        nodes = [
            node for node in item.get("nodes", [])
            if isinstance(node, dict)
        ]
        item["nodes"] = nodes
        item.pop("segments", None)

        total_node = next(
            (node for node in nodes if node.get("key") == "total_rev"),
            None,
        )
        gross = _decimal_value(total_node.get("value", "") if total_node else "")
        consolidated = _decimal_value(
            total_node.get("show_value", "") if total_node else ""
        )
        elimination_values = []
        level_one_values = []
        level_one_valid = True
        for node in nodes:
            if "longbridge_yoy_raw" not in node:
                node["longbridge_yoy_raw"] = node.get("yoy", "")
            node["row_type"] = classify_sankey_node(node)
            node["gross_segment_mix_percent"] = ""

            value = _decimal_value(node.get("value", ""))
            if node["row_type"] == "intersegment_elimination" and value is not None:
                elimination_values.append(-abs(value))
            if str(node.get("level")) == "1":
                if value is None:
                    level_one_valid = False
                else:
                    level_one_values.append(value)
            if period is not None and node.get("key"):
                values[(*period, str(node["key"]))] = _sankey_growth_value(node)

        eliminations = (
            sum(elimination_values, Decimal("0"))
            if elimination_values
            else (
                consolidated - gross
                if gross is not None and consolidated is not None
                else None
            )
        )
        item["gross_segment_revenue_before_elimination"] = (
            _decimal_text(gross) if gross is not None else ""
        )
        item["consolidated_revenue"] = (
            _decimal_text(consolidated) if consolidated is not None else ""
        )
        item["intersegment_eliminations"] = (
            _decimal_text(eliminations) if eliminations is not None else ""
        )

        if gross is None or consolidated is None or eliminations is None:
            item["reconciliation_delta"] = ""
            item["reconciliation_status"] = "unavailable"
        else:
            delta = gross + eliminations - consolidated
            item["reconciliation_delta"] = _decimal_text(delta)
            item["reconciliation_status"] = (
                "ok" if abs(delta) <= Decimal("1") else "mismatch"
            )

        if gross is None or not nodes or not level_one_valid:
            item["segment_completeness_delta"] = ""
            item["missing_segment_revenue"] = ""
            item["segment_completeness_status"] = "unavailable"
        else:
            level_one_sum = sum(level_one_values, Decimal("0"))
            completeness_delta = level_one_sum - gross
            item["segment_completeness_delta"] = _decimal_text(completeness_delta)
            if abs(completeness_delta) <= Decimal("1"):
                item["segment_completeness_status"] = "ok"
                item["missing_segment_revenue"] = "0"
            elif completeness_delta < 0:
                item["segment_completeness_status"] = "missing"
                item["missing_segment_revenue"] = _decimal_text(-completeness_delta)
            else:
                item["segment_completeness_status"] = "inconsistent"
                item["missing_segment_revenue"] = ""

        for node in nodes:
            value = _decimal_value(node.get("value", ""))
            if (
                str(node.get("level")) == "1"
                and gross is not None
                and gross > 0
                and value is not None
            ):
                mix = value / gross * Decimal("100")
                node["gross_segment_mix_percent"] = _decimal_text(
                    mix.quantize(Decimal("0.000001"))
                )

    for item in periods:
        period = _parse_sankey_period(item.get("period", ""))
        if period is None:
            continue
        year, quarter = period
        previous_year, previous_quarter = _previous_quarter(year, quarter)
        for node in item.get("nodes", []):
            key = str(node.get("key", ""))
            current = _sankey_growth_value(node)
            node["qoq"] = _growth_percent(
                current,
                values.get((previous_year, previous_quarter, key), ""),
            )
            node["yoy"] = _growth_percent(
                current,
                values.get((year - 1, quarter, key), ""),
            )


def parse_revenue_sankey(resp: dict) -> list:
    """无损保留长桥桑基节点，并补充可直接分析的派生字段。"""
    if not resp or not isinstance(resp, dict):
        return []
    items = resp.get("data", {}).get("list", [])
    if not items:
        return []
    out = []
    for item in items:
        nodes = [
            dict(node)
            for node in item.get("nodes", [])
            if isinstance(node, dict)
        ]
        parsed = dict(item)
        parsed["nodes"] = nodes
        out.append(parsed)
    normalize_revenue_sankey(out)
    return out


REVENUE_SANKEY_ENDPOINT = (
    "https://mr.lbkrs.com/api/forward/v3/stock-info/revenue-sankey"
)
_KLINE_URL = "https://mr.lbkrs.com/api/forward/v1/quote/range_kline"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
             "Accept": "application/json"}
_KLINE_HEADERS = {"x-app-id": "longbridge"}


def _encode_counter_id(counter_id: str) -> str:
    """counter_id 含 /，需 URL 编码为 %2F。"""
    return quote(counter_id, safe="")


def get_revenue_sankey_metadata(ticker: str = None) -> dict:
    """返回可写入桑基 JSON 的来源与派生字段语义。"""
    metadata = {
        "provider": "Longbridge",
        "payload_type": "parsed",
        "currency_semantics": {
            "status": "translated_only",
            "meaning": (
                "period.currency is the provider presentation currency; the API "
                "does not expose original reporting currency or conversion rate"
            ),
            "prohibited_uses": [
                "official_operating_growth",
                "cross_currency_valuation",
            ],
        },
        "request_url_templates": {
            "revenue_sankey": (
                f"{REVENUE_SANKEY_ENDPOINT}"
                "?counter_id={counter_id}&report=qf"
            ),
        },
        "quarterly_growth_semantics": {
            "qoq": "locally calculated against the previous fiscal quarter",
            "yoy": "locally calculated against the same fiscal quarter one year earlier",
            "longbridge_yoy_raw": (
                "original nodes[].yoy value; retained for audit"
            ),
        },
        "quarterly_accounting_semantics": {
            "consolidated_revenue": (
                "reported group revenue after intersegment eliminations"
            ),
            "gross_segment_revenue_before_elimination": (
                "total_rev.value before intersegment eliminations"
            ),
            "intersegment_eliminations": (
                "sum of intersegment elimination rows; normally negative"
            ),
            "gross_segment_mix_percent": (
                "segment revenue divided by gross segment revenue before eliminations"
            ),
            "reconciliation": (
                "gross segment revenue plus intersegment eliminations must equal "
                "consolidated revenue"
            ),
        },
        "revenue_sankey_semantics": {
            "nodes": "all original Longbridge node fields retained with derived fields",
            "gross_segment_revenue_before_elimination": (
                "total_rev.value before intersegment eliminations"
            ),
            "consolidated_revenue": (
                "total_rev.show_value after intersegment eliminations"
            ),
            "intersegment_eliminations": (
                "elimination nodes represented as a negative accounting effect"
            ),
            "gross_segment_mix_percent": (
                "level-1 node value divided by total_rev.value"
            ),
            "segment_completeness_status": (
                "comparison of summed level-1 node values with total_rev.value"
            ),
        },
    }
    counter_id = build_counter_id(ticker) if ticker else None
    if counter_id:
        encoded_counter_id = _encode_counter_id(counter_id)
        metadata["counter_id"] = counter_id
        metadata["request_urls"] = {
            "revenue_sankey": (
                f"{REVENUE_SANKEY_ENDPOINT}"
                f"?counter_id={encoded_counter_id}&report=qf"
            ),
        }
    return metadata


def fetch_revenue_sankey(ticker: str) -> dict:
    """抓取长桥 API2（季度/财年桑基历史）。失败返回 {}。"""
    cid = build_counter_id(ticker)
    if cid is None:
        return {}
    url = (
        f"{REVENUE_SANKEY_ENDPOINT}"
        f"?counter_id={_encode_counter_id(cid)}&report=qf"
    )
    try:
        def call():
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.json()

        return retry_call(
            call,
            provider="Longbridge",
            operation=f"{ticker}.revenue_sankey",
            validator=lambda value: isinstance(value, dict),
        )
    except Exception as e:
        print(f"  [longbridge API2] error: {e}", flush=True)
        return {}


def fetch_range_klines(ticker: str, market: str = None) -> dict:
    """抓取长桥日 K 数据。失败返回 {}。"""
    counter_id = build_kline_counter_id(ticker, market)
    if counter_id is None:
        return {}
    params = {
        "counter_id": counter_id,
        "adjust_type": 1,
        "new_version_kline": "true",
        "include_turnover_rate": "false",
        "kline_session": 0,
        "time_range": 3,
    }
    try:
        def call():
            resp = requests.get(
                _KLINE_URL,
                params=params,
                headers=_KLINE_HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()

        return retry_call(
            call,
            provider="Longbridge",
            operation=f"{ticker}.range_klines",
            validator=lambda value: isinstance(value, dict),
        )
    except Exception as e:
        print(f"  [longbridge K line] error: {e}", flush=True)
        return {}


# 常见分部名 -> 别名（用于新闻业务线匹配）。同时收录长桥返回的中英文名。
_SEGMENT_ALIASES = {
    # 阿里
    "云智能集团": ["阿里云", "云计算", "通义", "飞天", "AI"],
    "商业": ["淘宝", "天猫", "电商", "88VIP", "淘天"],
    "Alibaba China E-commerce Group": ["淘宝", "天猫", "电商", "88VIP", "淘天", "中国电商"],
    "本地生活集团": ["饿了么", "高德", "本地生活", "外卖"],
    "菜鸟集团": ["菜鸟", "物流", "跨境物流"],
    "国际数字商业集团": ["国际电商", "速卖通", "Lazada", "国际商业"],
    "阿里国际数字商业集团（AIDC）": ["国际电商", "速卖通", "Lazada", "AIDC", "国际商业"],
    "大文娱集团": ["优酷", "阿里影业", "大文娱", "灵犀互娱"],
    # 腾讯
    "游戏": ["腾讯游戏", "王者荣耀", "和平精英"],
    "金融科技": ["微信支付", "财付通", "金融科技"],
}


def derive_segments_yaml(periods: list) -> dict:
    """从最新桑基期间的 Level-1 节点生成 segments.yaml。"""
    if not periods:
        return None
    latest = max(
        periods,
        key=lambda item: _parse_sankey_period(item.get("period", "")) or (0, 0),
    )
    nodes = [
        node for node in latest.get("nodes", [])
        if isinstance(node, dict) and str(node.get("level")) == "1"
    ]
    if not nodes:
        return None

    real_segs = [
        node for node in nodes
        if classify_sankey_node(node) == "business_segment"
    ]
    other = [
        node for node in nodes
        if classify_sankey_node(node) == "other"
    ]
    other_pct = 0.0
    if other:
        try:
            other_pct = sum(
                float(node.get("gross_segment_mix_percent", "0") or "0")
                for node in other
            )
        except ValueError:
            other_pct = 0.0

    multi = len(real_segs) > 1 and other_pct < 90.0

    seg_list = []
    for node in real_segs:
        name = node.get("name", "")
        seg_list.append({
            "name": name,
            "aliases": _SEGMENT_ALIASES.get(name, []),
            "brief": "",
        })

    basis = f"长桥分部数据：{len(real_segs)}个业务分部"
    if other:
        basis += f"，其他汇总项抵销前占比{other_pct:.2f}%"
    completeness = latest.get("segment_completeness_status", "unavailable")
    basis += f"，Level-1完整性={completeness}"
    if completeness == "missing":
        basis += f"（缺口{latest.get('missing_segment_revenue', '')}）"
    return {
        "multi_segment": multi,
        "judgment_basis": basis,
        "data_source": "longbridge",
        "segments": seg_list,
    }
