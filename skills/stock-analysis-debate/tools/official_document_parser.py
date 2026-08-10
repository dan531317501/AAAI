"""Deterministically extract canonical financial facts from official documents.

Official exchange disclosures are often PDFs or HTML pages rather than XBRL.
This module extracts text and conservative table rows without using an LLM.
Anything that cannot be tied to a metric, unit, and reporting period is left
out so the caller can apply a lower-priority API fallback.
"""

from __future__ import annotations

from datetime import date, datetime
from html.parser import HTMLParser
from io import BytesIO
import calendar
import math
import re
from typing import Any, Callable

import requests

from provider_runtime import retry_call


DOCUMENT_HEADERS = {
    "User-Agent": "Mozilla/5.0 stock-analysis-debate/1.0",
    "Accept": "application/pdf,text/html,application/xhtml+xml",
}


CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "net_income_attributable_to_parent": (
        "profit for the year attributable to owners of the company",
        "profit for the year attributable to owners",
        "profit for the period attributable to owners of the company",
        "profit for the period attributable to owners",
        "profit attributable to owners of the company",
        "profit attributable to owners",
        "归属于母公司所有者的净利润",
        "归属于上市公司股东的净利润",
    ),
    "operating_cash_flow": (
        "net cash generated from operating activities",
        "net cash provided by operating activities",
        "total cash from operating activities",
        "经营活动产生的现金流量净额",
    ),
    "diluted_eps": (
        "diluted earnings per share",
        "diluted eps",
        "稀释每股收益",
    ),
    "basic_eps": (
        "basic earnings per share",
        "basic eps",
        "基本每股收益",
    ),
    "stockholders_equity": (
        "equity attributable to owners of the company",
        "equity attributable to owners",
        "stockholders' equity",
        "stockholders equity",
        "归属于母公司所有者权益",
        "归属于上市公司股东的净资产",
    ),
    "total_assets": (
        "total assets",
        "资产总额",
        "资产合计",
    ),
    "cash_and_equivalents": (
        "cash and cash equivalents",
        "cash and equivalents",
        "cash and short-term investments",
        "货币资金",
        "现金及现金等价物",
    ),
    "capital_expenditure": (
        "payments to acquire property, plant and equipment",
        "capital expenditure",
        "capital expenditures",
        "购建固定资产、无形资产和其他长期资产支付的现金",
    ),
    "cost_of_revenue": (
        "cost of revenue",
        "cost of goods and services sold",
        "cost of goods sold",
        "营业成本",
    ),
    "gross_profit": (
        "gross profit",
        "毛利",
    ),
    "operating_income": (
        "operating income",
        "operating income loss",
        "profit from operating activities",
        "营业利润",
    ),
    "pretax_income": (
        "profit before tax",
        "income before income taxes",
        "profit before taxation",
        "利润总额",
    ),
    "income_tax_expense": (
        "income tax expense",
        "income tax expense benefit",
        "所得税费用",
    ),
    "revenue": (
        "revenue",
        "revenues",
        "operating revenue",
        "total revenue",
        "营业收入",
        "营业总收入",
        "收入",
    ),
    "net_income": (
        "profit for the year",
        "profit for the period",
        "net income",
        "net profit",
        "净利润",
    ),
    "debt_current": (
        "current debt",
        "short-term debt",
        "current borrowings",
        "短期借款",
    ),
    "debt_noncurrent": (
        "long-term debt",
        "long term debt",
        "non-current borrowings",
        "长期借款",
    ),
}


_ALIASES_BY_LENGTH = sorted(
    (
        (alias.casefold(), metric)
        for metric, aliases in CANONICAL_ALIASES.items()
        for alias in aliases
    ),
    key=lambda item: len(item[0]),
    reverse=True,
)
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z])\(?[-+−]?\s*(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?\s*%?"
)
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})\b")


class _HTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._buffer: list[str] = []

    def _flush(self) -> None:
        value = re.sub(r"\s+", " ", "".join(self._buffer)).strip()
        if value:
            self.lines.append(value)
        self._buffer = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4"}:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"p", "div", "tr", "li", "h1", "h2", "h3", "h4"}:
            self._flush()

    def handle_data(self, data: str) -> None:
        self._buffer.append(data)

    def text(self) -> str:
        self._flush()
        return "\n".join(self.lines)


def _normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00a0", " ")).strip()


def canonical_metric_for_label(label: str) -> str | None:
    candidate = re.sub(r"[:：]\s*", " ", _normalise_text(label)).casefold()
    if "net of non-recurring" in candidate or "扣除非经常性损益" in candidate:
        return None
    if "earnings per share" in candidate:
        if re.search(r"\bdiluted\b", candidate):
            return "diluted_eps"
        if re.search(r"\bbasic\b", candidate):
            return "basic_eps"
    for alias, metric in _ALIASES_BY_LENGTH:
        if alias in candidate:
            if metric == "operating_income" and "other operating income" in candidate:
                continue
            if metric == "capital_expenditure" and not re.match(
                r"^(?:[^a-z0-9]*)(?:payments to acquire property, plant and equipment|capital expenditures?)\b",
                candidate,
            ):
                continue
            if metric == "revenue" and any(
                marker in candidate for marker in (
                    "deferred revenue", "unearned revenue", "to increase", "guidance",
                    "expected revenue",
                )
            ):
                continue
            return metric
    return None


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for parser in (lambda: datetime.fromisoformat(text.replace("Z", "+00:00")).date(),
                   lambda: datetime.strptime(text[:10], "%Y-%m-%d").date(),
                   lambda: datetime.strptime(text[:10], "%d/%m/%Y").date()):
        try:
            return parser()
        except ValueError:
            continue
    return None


def _infer_report_year(text: str, analysis_date: str) -> int:
    years = [int(value) for value in _YEAR_RE.findall(text)]
    analysis_year = _parse_date(analysis_date).year if _parse_date(analysis_date) else 2100
    valid = [year for year in years if 2000 <= year <= analysis_year]
    return max(valid) if valid else analysis_year


def _unit_context(text: str, financial_currency: str | None) -> tuple[str | None, str, float, str | None]:
    compact = _normalise_text(text).replace("’", "'").replace("′", "'")
    currency_patterns = (
        (r"(?:US\$|USD)", "USD"),
        (r"(?:HK\$|HKD)", "HKD"),
        (r"(?:RMB|CNY|人民币)", "CNY"),
        (r"(?:EUR|€)", "EUR"),
    )
    currency = next(
        (code for pattern, code in currency_patterns if re.search(pattern, compact, re.I)),
        (financial_currency.upper() if financial_currency else None),
    )
    scale = 1.0
    raw_scale = None
    declared_scale = re.search(
        r"(?:amounts|figures)?\s+in\s+(?:us\$|usd|hk\$|hkd|rmb|cny|eur|€)\s*"
        r"(?P<scale>thousands?|millions?|billions?|'000|’000|千元|千)\b",
        compact,
        re.I,
    )
    scale_text = declared_scale.group("scale") if declared_scale else compact
    if re.search(r"(?:million|mn|millions|百万|百万元)", scale_text, re.I):
        scale, raw_scale = 1_000_000.0, "million"
    elif re.search(r"(?:billion|bn|billions|十亿)", scale_text, re.I):
        scale, raw_scale = 1_000_000_000.0, "billion"
    elif re.search(r"(?:thousand|thousands|'000|’000|千元|千)", scale_text, re.I):
        scale, raw_scale = 1_000.0, "thousand"
    unit = currency or "provider_native"
    raw_unit = f"{currency} {raw_scale}" if raw_scale else None
    return currency, unit, scale, raw_unit


def _number_tokens(text: str) -> list[tuple[float, bool, str]]:
    result: list[tuple[float, bool, str]] = []
    for match in _NUMBER_RE.finditer(text):
        raw = match.group(0).strip()
        cleaned = raw.replace(",", "").replace(" ", "").replace("−", "-")
        is_percent = cleaned.endswith("%")
        cleaned = cleaned.rstrip("%").strip("()")
        try:
            value = float(cleaned)
        except ValueError:
            continue
        if not math.isfinite(value) or 1900 <= abs(value) <= 2100:
            continue
        if raw.startswith("(") and raw.endswith(")"):
            value = -value
        result.append((int(value) if value.is_integer() else value, is_percent, raw))
    return result


def _period_candidates(context: str, full_text: str, analysis_date: str) -> list[dict[str, Any]]:
    compact = _normalise_text(context).casefold()
    full_context = f"{context} {full_text}"
    year = _infer_report_year(full_context, analysis_date)

    def quarter_period(quarter: int, period_year: int) -> dict[str, Any]:
        month = 1 + (quarter - 1) * 3
        end_month = month + 2
        return {
            "period_start": f"{period_year}-{month:02d}-01",
            "period_end": f"{period_year}-{end_month:02d}-{calendar.monthrange(period_year, end_month)[1]:02d}",
            "period_type": "quarter",
            "fiscal_year": period_year,
            "fiscal_period": f"Q{quarter}",
        }

    def short_year(value: str) -> int:
        number = int(value)
        return 2000 + number if len(value) == 2 else number

    explicit_quarters: list[dict[str, Any]] = []
    for match in re.finditer(r"\b([1-4])\s*q\s*(\d{2,4})\b", compact, re.I):
        explicit_quarters.append(quarter_period(int(match.group(1)), short_year(match.group(2))))
    for match in re.finditer(r"\bq\s*([1-4])\s+(\d{4})\b", compact, re.I):
        explicit_quarters.append(quarter_period(int(match.group(1)), int(match.group(2))))
    unique_quarters: list[dict[str, Any]] = []
    seen_quarters: set[tuple[str, str]] = set()
    for period in explicit_quarters:
        key = (period["period_end"], period["period_type"])
        if key not in seen_quarters:
            seen_quarters.add(key)
            unique_quarters.append(period)
    if unique_quarters:
        return unique_quarters

    month_numbers = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    dates: list[date] = []
    for match in re.finditer(
        r"\b(january|february|march|april|may|june|july|august|september|"
        r"october|november|december)\s+(\d{1,2}),?\s+(\d{4})\b",
        full_context.casefold(),
    ):
        candidate = date(
            int(match.group(3)), month_numbers[match.group(1)], int(match.group(2))
        )
        if candidate not in dates:
            dates.append(candidate)
    date_context = full_context.casefold()
    if len(dates) >= 2 and "as of" in date_context:
        return [
            {
                "period_start": None,
                "period_end": item.isoformat(),
                "period_type": "instant",
                "fiscal_year": item.year,
                "fiscal_period": f"Q{((item.month - 1) // 3) + 1}",
            }
            for item in dates
        ]
    if len(dates) >= 2 and "three months ended" in date_context:
        return [quarter_period(((item.month - 1) // 3) + 1, item.year) for item in dates]

    quarter_names = (
        ("first quarter", 1), ("q1", 1), ("第一季度", 1),
        ("second quarter", 2), ("q2", 2), ("第二季度", 2),
        ("third quarter", 3), ("q3", 3), ("第三季度", 3),
        ("fourth quarter", 4), ("q4", 4), ("第四季度", 4),
    )
    quarter_hits = [number for marker, number in quarter_names if marker in compact]
    if quarter_hits:
        unique_hits = list(dict.fromkeys(quarter_hits))
        if "by quarter" in compact:
            unique_hits = [1, 2, 3, 4]
        return [quarter_period(quarter, year) for quarter in unique_hits]
    years = list(dict.fromkeys(int(value) for value in _YEAR_RE.findall(context)))
    if len(years) >= 2 and any(marker in compact for marker in ("year ended", "as of", "年度", "年末")):
        return [
            {
                "period_start": f"{item}-01-01",
                "period_end": f"{item}-12-31",
                "period_type": "annual",
                "fiscal_year": item,
                "fiscal_period": "FY",
            }
            for item in years
        ]
    if len(years) >= 2:
        return [
            {
                "period_start": f"{item}-01-01",
                "period_end": f"{item}-12-31",
                "period_type": "annual",
                "fiscal_year": item,
                "fiscal_period": "FY",
            }
            for item in years
        ]
    return []


def _select_values(tokens: list[tuple[float, bool, str]], expected: int, context: str) -> list[float]:
    values = [value for value, is_percent, _ in tokens if not is_percent]
    if len(values) > expected and ("as compared" in context.casefold() or "%" in context):
        filtered = [value for value in values if abs(float(value)) > 100]
        if len(filtered) >= expected:
            values = filtered
        else:
            # Comparison percentages are usually inserted between the first
            # and last financial columns. Remove the largest small interior
            # value first so EPS rows such as 0.09, 0.06, 50.0, 0.11 align.
            while len(values) > expected:
                interior = [
                    (index, abs(float(value)))
                    for index, value in enumerate(values[1:-1], start=1)
                    if abs(float(value)) <= 100
                ]
                if not interior:
                    break
                remove_index = max(interior, key=lambda item: item[1])[0]
                values.pop(remove_index)
    return values[:expected]


def _logical_rows(lines: list[str]) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        clean = _normalise_text(line)
        if not clean:
            continue
        label = clean
        if (
            "profit for the period attributable" in clean.casefold()
            and index + 1 < len(lines)
        ):
            label = f"{clean} {lines[index + 1]}"
        elif (
            index > 0
            and clean.casefold().startswith(("basic ", "diluted "))
            and any(
                "earnings per share" in lines[previous].casefold()
                for previous in range(max(0, index - 2), index)
            )
        ):
            label = f"earnings per share {clean}"
        if canonical_metric_for_label(label) is None:
            continue
        rows.append((label, index))
    return rows


def _parse_text_pages(
    pages: list[dict[str, Any]],
    *,
    analysis_date: str,
    financial_currency: str | None,
    source: str,
    provider: str,
    source_url: str,
    extraction_method: str,
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for page in pages:
        text = str(page.get("text") or "")
        lines = [_normalise_text(line) for line in text.splitlines() if _normalise_text(line)]
        if not lines:
            continue
        page_currency, page_unit, page_scale, page_raw_unit = _unit_context(
            text, financial_currency
        )
        for label, index in _logical_rows(lines):
            context_lines = lines[max(0, index - 12): min(len(lines), index + 6)]
            context = " ".join(context_lines)
            periods = _period_candidates(context, text, analysis_date)
            if not periods:
                continue
            row_lines = lines[index:min(len(lines), index + 5)]
            if _number_tokens(lines[index]):
                row_lines = [lines[index]]
            row_text = " ".join(row_lines)
            tokens = _number_tokens(row_text)
            values = _select_values(tokens, len(periods), context)
            if not values:
                continue
            metric = canonical_metric_for_label(label)
            if metric is None:
                continue
            row_currency, row_unit, row_scale, row_raw_unit = _unit_context(
                row_text, financial_currency
            )
            currency, unit, scale, raw_unit = (
                row_currency,
                row_unit,
                row_scale,
                row_raw_unit,
            )
            if raw_unit is None:
                currency, unit, scale, raw_unit = _unit_context(
                    context, financial_currency
                )
            if raw_unit is None and page_raw_unit is not None:
                currency, unit, scale, raw_unit = (
                    page_currency,
                    page_unit,
                    page_scale,
                    page_raw_unit,
                )
            if metric in {"basic_eps", "diluted_eps"}:
                scale = 1.0
                unit = f"{currency}/share" if currency else "provider_native/share"
                raw_unit = unit
            for period, value in zip(periods, values):
                normalized_value = value * scale
                key = (metric, period["period_end"], period["period_type"], normalized_value)
                if key in seen:
                    continue
                seen.add(key)
                facts.append({
                    "metric": metric,
                    "value": int(normalized_value) if float(normalized_value).is_integer() else normalized_value,
                    "unit": unit,
                    "currency": currency,
                    "period_start": period["period_start"],
                    "period_end": period["period_end"],
                    "period_type": period["period_type"],
                    "filed_at": _parse_date(page.get("filed_at")) .isoformat() if _parse_date(page.get("filed_at")) else None,
                    "fiscal_year": period.get("fiscal_year"),
                    "fiscal_period": period.get("fiscal_period"),
                    "source": source,
                    "provider": provider,
                    "source_url": source_url,
                    "source_page": page.get("page_number"),
                    "source_excerpt": row_text[:500],
                    "extraction_method": extraction_method,
                    "raw_tag": label,
                    "raw_unit": raw_unit or unit,
                    "scale": scale,
                    "official": True,
                })
    return facts


def _pdf_pages(payload: bytes) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("pypdf is required for official PDF extraction") from error
    reader = PdfReader(BytesIO(payload))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"page_number": index, "text": text})
    return pages


def _html_pages(payload: bytes) -> list[dict[str, Any]]:
    parser = _HTMLTextParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    return [{"page_number": 1, "text": parser.text()}]


def extract_document_text(payload: bytes, content_type: str | None, source_url: str) -> list[dict[str, Any]]:
    content = (content_type or "").casefold()
    is_pdf = payload.startswith(b"%PDF") or "pdf" in content or source_url.casefold().split("?", 1)[0].endswith(".pdf")
    if is_pdf:
        try:
            return _pdf_pages(payload)
        except Exception as error:
            raise ValueError(f"official PDF could not be parsed: {error}") from error
    is_html = "html" in content or "xhtml" in content or source_url.casefold().split("?", 1)[0].endswith((".htm", ".html"))
    if is_html:
        return _html_pages(payload)
    raise ValueError(f"unsupported official document content type: {content_type or 'unknown'}")


def parse_document_payload(
    payload: bytes,
    content_type: str | None,
    record: dict[str, Any],
    analysis_date: str,
    financial_currency: str | None,
) -> dict[str, Any]:
    source_url = str(record.get("url") or record.get("source_url") or "")
    pages = extract_document_text(payload, content_type, source_url)
    is_pdf = payload.startswith(b"%PDF") or "pdf" in (content_type or "").casefold() or source_url.casefold().split("?", 1)[0].endswith(".pdf")
    extraction_method = "pdf_text_regex" if is_pdf else "html_text_regex"
    full_text = "\n".join(str(page.get("text") or "") for page in pages)
    if len(re.sub(r"\s+", "", full_text)) < 80:
        raise ValueError("official document has no usable text layer")
    source = str(record.get("source") or "OFFICIAL_DISCLOSURE")
    provider = str(record.get("provider") or "official_disclosure")
    facts = _parse_text_pages(
        pages,
        analysis_date=analysis_date,
        financial_currency=financial_currency,
        source=source,
        provider=provider,
        source_url=source_url,
        extraction_method=extraction_method,
    )
    return {
        "status": "available" if facts else "partial",
        "content_type": content_type,
        "page_count": len(pages),
        "facts": facts,
        "extraction_method": extraction_method,
    }


def download_document(record: dict[str, Any], provider: str) -> tuple[bytes, str | None]:
    source_url = str(record.get("url") or record.get("source_url") or "")
    if not source_url:
        raise ValueError("official document URL is missing")

    def fetch() -> requests.Response:
        response = requests.get(source_url, headers=DOCUMENT_HEADERS, timeout=30)
        response.raise_for_status()
        return response

    response = retry_call(
        fetch,
        provider=provider,
        operation="official_document_download",
        validator=lambda value: bool(value.content),
    )
    return response.content, response.headers.get("Content-Type")


def parse_official_documents(
    records: list[dict[str, Any]],
    analysis_date: str,
    financial_currency: str | None,
    *,
    downloader: Callable[[dict[str, Any], str], tuple[bytes, str | None]] = download_document,
    provider: str = "official_disclosure",
) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    fact_indexes: dict[tuple[Any, ...], int] = {}
    documents: list[dict[str, Any]] = []

    def fact_quality(fact: dict[str, Any]) -> int:
        raw_unit = str(fact.get("raw_unit") or "").casefold()
        score = 0
        if "thousand" in raw_unit or "'000" in raw_unit or "千" in raw_unit:
            score += 3
        if "million" in raw_unit or "billion" in raw_unit:
            score -= 1
        if fact.get("source_page") and int(fact["source_page"]) >= 4:
            score += 1
        return score

    for record in records:
        if not isinstance(record, dict):
            continue
        source_url = record.get("url") or record.get("source_url")
        document_audit = {
            "source_url": source_url,
            "title": record.get("title"),
            "filed_at": record.get("filed_at"),
            "status": "unavailable",
            "fact_count": 0,
        }
        try:
            payload, content_type = downloader(record, provider)
            parsed = parse_document_payload(
                payload,
                content_type,
                record,
                analysis_date,
                financial_currency,
            )
            document_audit.update({
                "status": parsed["status"],
                "content_type": parsed.get("content_type"),
                "page_count": parsed.get("page_count"),
                "extraction_method": parsed.get("extraction_method"),
                "fact_count": len(parsed.get("facts", [])),
            })
            for fact in parsed.get("facts", []):
                key = (fact.get("metric"), fact.get("period_end"), fact.get("period_type"))
                existing_index = fact_indexes.get(key)
                if existing_index is None:
                    fact_indexes[key] = len(facts)
                    facts.append(fact)
                    continue
                if fact_quality(fact) > fact_quality(facts[existing_index]):
                    facts[existing_index] = fact
        except Exception as error:
            document_audit.update({
                "status": "unavailable",
                "error": f"{type(error).__name__}: {error}",
            })
        documents.append(document_audit)
    return {"facts": facts, "documents": documents}
