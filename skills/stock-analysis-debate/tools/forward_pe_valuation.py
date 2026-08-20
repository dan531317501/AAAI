"""Deterministic next-fiscal-year Forward P/E target-price calculations.

The module deliberately has no network access.  The orchestration layer must
first write a ``valuation_consensus`` artifact containing the web evidence and
peer observations.  This module validates that artifact and performs only the
numeric filtering, percentile, and multiplication steps.
"""

from __future__ import annotations

from datetime import date, datetime
import math
from typing import Any


FORECAST_PERIOD = "next_fiscal_year"
MIN_VALID_PEERS = 3
DEFAULT_MAX_AGE_DAYS = 60
PERCENTILES = {
    "bear": ("P25", 0.25),
    "base": ("P50", 0.50),
    "bull": ("P75", 0.75),
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _source_date(record: dict[str, Any]) -> date | None:
    for field in ("updated_at", "published_at", "as_of_date", "retrieved_at"):
        parsed = _date(record.get(field))
        if parsed is not None:
            return parsed
    return None


def _is_known_share_basis(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return bool(text) and text not in {
        "unknown", "unverified", "n/a", "na", "none", "null",
    }


def _unit_label(currency: str, share_basis: str) -> str:
    """Render a single currency/share unit without duplicating its currency."""
    normalized_basis = share_basis.strip()
    if normalized_basis.upper().startswith(f"{currency.upper()}/"):
        return normalized_basis
    return f"{currency}/{normalized_basis}"


def _source_fields_ready(record: dict[str, Any], *, require_period: bool = True) -> list[str]:
    reasons: list[str] = []
    if not str(record.get("source_name") or "").strip():
        reasons.append("source_name_missing")
    source_url = str(record.get("source_url") or "").strip()
    if not source_url.startswith(("http://", "https://")):
        reasons.append("source_url_missing")
    if not str(record.get("basis") or "").strip():
        reasons.append("source_basis_missing")
    if require_period and not str(record.get("forecast_period") or "").strip():
        reasons.append("forecast_period_missing")
    if _source_date(record) is None:
        reasons.append("source_date_missing")
    return reasons


def _web_value_ready(record: dict[str, Any]) -> bool:
    candidates = [
        record.get("target_pe"),
        record.get("reasonable_pe"),
        record.get("median_pe"),
        record.get("pe_median"),
        record.get("range_low"),
        record.get("range_high"),
    ]
    pe_range = record.get("pe_range")
    if isinstance(pe_range, dict):
        candidates.extend(pe_range.values())
    return any(value is not None and _number(value) is not None and _number(value) > 0
               for value in candidates)


def validate_valuation_consensus(
    payload: dict[str, Any] | None,
    analysis_date: str,
    *,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> dict[str, Any]:
    """Validate web consensus and peer evidence without calculating a target."""
    reasons: list[str] = []
    normalized: dict[str, Any] = {
        "status": "unavailable",
        "analysis_date": analysis_date,
        "max_age_days": max_age_days,
        "web_consensus": [],
        "peers": [],
        "excluded_peers": [],
    }
    if not isinstance(payload, dict):
        return {**normalized, "blocking_reasons": ["valuation_consensus_missing"]}

    analysis_day = _date(analysis_date)
    if analysis_day is None:
        return {**normalized, "blocking_reasons": ["analysis_date_invalid"]}
    if str(payload.get("status") or "available").lower() not in {"available", "verified"}:
        reasons.append("valuation_consensus_not_available")

    instrument = payload.get("instrument") or payload.get("target_instrument") or {}
    if not isinstance(instrument, dict):
        instrument = {}
    target_currency = str(
        instrument.get("currency") or payload.get("currency") or ""
    ).strip().upper()
    target_share_basis = str(
        instrument.get("share_basis") or payload.get("share_basis") or ""
    ).strip()
    if not target_currency:
        reasons.append("target_currency_missing")
    if not _is_known_share_basis(target_share_basis):
        reasons.append("share_basis_unverified")
    instrument_reasons = _source_fields_ready(instrument, require_period=False)
    if instrument_reasons:
        reasons.extend(f"instrument_{reason}" for reason in instrument_reasons)

    def fresh(record: dict[str, Any], prefix: str) -> bool:
        record_date = _source_date(record)
        if record_date is None:
            reasons.append(f"{prefix}_source_date_missing")
            return False
        age = (analysis_day - record_date).days
        record["source_age_days"] = age
        if age < 0:
            reasons.append(f"{prefix}_source_date_in_future")
            return False
        if age > max_age_days:
            reasons.append(f"{prefix}_source_stale_over_{max_age_days}_days")
            return False
        return True

    valid_web: list[dict[str, Any]] = []
    for index, raw in enumerate(payload.get("web_consensus", [])):
        if not isinstance(raw, dict):
            reasons.append(f"web_consensus_{index}_invalid_record")
            continue
        record = dict(raw)
        record_reasons = _source_fields_ready(record)
        if record_reasons:
            reasons.extend(f"web_consensus_{index}_{reason}" for reason in record_reasons)
            continue
        if not _web_value_ready(record):
            reasons.append(f"web_consensus_{index}_pe_value_missing")
            continue
        if str(record.get("scope") or "").strip().lower() not in {"stock", "industry"}:
            reasons.append(f"web_consensus_{index}_scope_missing_or_invalid")
            continue
        if record.get("forecast_period") != FORECAST_PERIOD:
            reasons.append(f"web_consensus_{index}_forecast_period_mismatch")
            continue
        if not str(record.get("currency") or "").strip().upper():
            reasons.append(f"web_consensus_{index}_currency_missing")
            continue
        if not _is_known_share_basis(record.get("share_basis")):
            reasons.append(f"web_consensus_{index}_share_basis_unverified")
            continue
        if fresh(record, f"web_consensus_{index}"):
            valid_web.append(record)

    valid_peers: list[dict[str, Any]] = []
    for index, raw in enumerate(payload.get("peers", [])):
        if not isinstance(raw, dict):
            normalized["excluded_peers"].append({
                "index": index,
                "reason": "invalid_record",
            })
            continue
        record = dict(raw)
        peer_reasons = _source_fields_ready(record)
        pe = _number(record.get("forward_pe"))
        currency = str(record.get("currency") or "").strip().upper()
        share_basis = str(record.get("share_basis") or "").strip()
        if pe is None or pe <= 0:
            peer_reasons.append("forward_pe_not_positive")
        if not currency:
            peer_reasons.append("currency_missing")
        if not _is_known_share_basis(share_basis):
            peer_reasons.append("share_basis_unverified")
        if record.get("forecast_period") != FORECAST_PERIOD:
            peer_reasons.append("forecast_period_mismatch")
        if peer_reasons or not fresh(record, f"peer_{index}"):
            normalized["excluded_peers"].append({
                "symbol": record.get("symbol"),
                "reason": ";".join(dict.fromkeys(peer_reasons)) or "stale_or_invalid_date",
            })
            continue
        record["forward_pe"] = pe
        record["currency"] = currency
        valid_peers.append(record)

    if not valid_web:
        reasons.append("web_consensus_evidence_missing")
    if len(valid_peers) < MIN_VALID_PEERS:
        reasons.append(f"valid_peer_count_below_{MIN_VALID_PEERS}")

    normalized.update({
        "status": "verified" if not reasons else "partial",
        "instrument": {
            **instrument,
            "currency": target_currency or None,
            "share_basis": target_share_basis or None,
        },
        "web_consensus": valid_web,
        "peers": valid_peers,
        "peer_count": len(valid_peers),
        "web_consensus_count": len(valid_web),
        "blocking_reasons": list(dict.fromkeys(reasons)),
    })
    return normalized


def _linear_quantile(values: list[float], quantile: float) -> float:
    """Return a deterministic linear-interpolation sample quantile."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("quantile requires at least one value")
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def calculate_forward_pe_scenarios(
    forward_eps: dict[str, Any],
    peers: list[dict[str, Any]],
    evidence: dict[str, Any],
    analysis_date: str,
) -> dict[str, Any]:
    """Calculate Bear/Base/Bull targets from already validated peer evidence."""
    blocking_reasons = list(evidence.get("blocking_reasons", []))
    eps = _number(forward_eps.get("value"))
    currency = str(forward_eps.get("currency") or "").strip().upper()
    share_basis = str(forward_eps.get("share_basis") or "").strip()
    period = str(forward_eps.get("forecast_period") or "").strip()
    instrument = evidence.get("instrument") or {}
    evidence_currency = str(instrument.get("currency") or "").strip().upper()
    if evidence_currency and currency and evidence_currency != currency:
        blocking_reasons.append("forward_eps_currency_mismatch_target")
    evidence_share_basis = str(instrument.get("share_basis") or "").strip()
    if evidence_share_basis and share_basis and evidence_share_basis != share_basis:
        blocking_reasons.append("forward_eps_share_basis_mismatch_target")
    if eps is None or eps <= 0:
        blocking_reasons.append("forward_eps_not_positive")
    if period != FORECAST_PERIOD:
        blocking_reasons.append("forward_eps_forecast_period_mismatch")
    eps_date = _source_date(forward_eps)
    if eps_date is None:
        blocking_reasons.append("forward_eps_source_date_missing")
    else:
        eps_age = (_date(analysis_date) - eps_date).days if _date(analysis_date) else None
        if eps_age is not None:
            if eps_age < 0:
                blocking_reasons.append("forward_eps_source_date_in_future")
            elif eps_age > DEFAULT_MAX_AGE_DAYS:
                blocking_reasons.append(
                    f"forward_eps_source_stale_over_{DEFAULT_MAX_AGE_DAYS}_days"
                )
    if not currency:
        blocking_reasons.append("forward_eps_currency_missing")
    if not _is_known_share_basis(share_basis):
        blocking_reasons.append("forward_eps_share_basis_unverified")

    values = [
        _number(peer.get("forward_pe"))
        for peer in peers
        if _number(peer.get("forward_pe")) is not None
        and _number(peer.get("forward_pe")) > 0
    ]
    if len(values) < MIN_VALID_PEERS:
        blocking_reasons.append(f"valid_peer_count_below_{MIN_VALID_PEERS}")
    blocking_reasons = list(dict.fromkeys(blocking_reasons))
    result: dict[str, Any] = {
        "status": "unavailable" if blocking_reasons else "verified",
        "analysis_date": analysis_date,
        "forecast_period": period or FORECAST_PERIOD,
        "forward_eps": forward_eps,
        "peer_count": len(values),
        "peer_forward_pe_values": sorted(values),
        "blocking_reasons": blocking_reasons,
        "scenarios": {},
        "report_lines": {
            "forward_eps": "Not Rated",
            "target_pe": "Not Rated",
            "price_target": "Not Rated",
        },
    }
    if blocking_reasons:
        return result

    scenarios: dict[str, Any] = {}
    for scenario, (label, quantile) in PERCENTILES.items():
        target_pe = _linear_quantile(values, quantile)
        price_target = eps * target_pe
        scenarios[scenario] = {
            "label": label,
            "percentile": quantile,
            "target_pe": target_pe,
            "forward_eps": eps,
            "price_target": price_target,
            "currency": currency,
            "share_basis": share_basis,
            "formula": f"{eps:.6g} × {target_pe:.6g} = {price_target:.6g}",
        }
    result.update({
        "status": "verified",
        "currency": currency,
        "share_basis": share_basis,
        "scenarios": scenarios,
        "report_lines": {
            "forward_eps": f"{eps:.2f} {_unit_label(currency, share_basis)}",
            "target_pe": " / ".join(
                f"{scenarios[name]['target_pe']:.1f}x"
                for name in ("bear", "base", "bull")
            ),
            "price_target": (
                " / ".join(
                    f"{scenarios[name]['price_target']:.2f}"
                    for name in ("bear", "base", "bull")
                )
                + f" {_unit_label(currency, share_basis)}"
            ),
        },
    })
    return result


def build_forward_pe_valuation(
    forward_eps: dict[str, Any] | None,
    valuation_consensus: dict[str, Any] | None,
    analysis_date: str,
    *,
    analysis_mode: str = "current_research",
) -> dict[str, Any]:
    """Build the complete fail-closed Forward P/E valuation artifact."""
    evidence = validate_valuation_consensus(
        valuation_consensus,
        analysis_date,
    )
    if analysis_mode == "historical_replay":
        evidence["blocking_reasons"].append(
            "historical_replay_non_point_in_time_valuation_inputs"
        )
    evidence["blocking_reasons"] = list(dict.fromkeys(evidence["blocking_reasons"]))

    base: dict[str, Any] = {
        "schema_version": "1.0",
        "method": "forward_eps_x_peer_forward_pe_percentiles",
        "analysis_date": analysis_date,
        "analysis_mode": analysis_mode,
        "forecast_period": FORECAST_PERIOD,
        "valuation_evidence": evidence,
        "status": "unavailable",
        "gate": {
            "allowed": False,
            "blocking_reasons": list(evidence["blocking_reasons"]),
        },
        "scenarios": {},
        "report_lines": {
            "forward_eps": "Not Rated",
            "target_pe": "Not Rated",
            "price_target": "Not Rated",
        },
    }
    if not isinstance(forward_eps, dict):
        base["gate"]["blocking_reasons"].append("forward_eps_missing")
        base["gate"]["blocking_reasons"] = list(dict.fromkeys(base["gate"]["blocking_reasons"]))
        return base

    normalized_eps = dict(forward_eps)
    normalized_eps.setdefault("forecast_period", FORECAST_PERIOD)
    instrument = evidence.get("instrument") or {}
    normalized_eps.setdefault("currency", instrument.get("currency"))
    normalized_eps.setdefault("share_basis", instrument.get("share_basis"))
    result = calculate_forward_pe_scenarios(
        normalized_eps,
        evidence.get("peers", []),
        evidence,
        analysis_date,
    )
    base.update({
        "forward_eps": normalized_eps,
        "peer_count": result.get("peer_count", 0),
        "peer_forward_pe_values": result.get("peer_forward_pe_values", []),
        "scenarios": result.get("scenarios", {}),
        "report_lines": result.get("report_lines", {}),
    })
    reasons = list(dict.fromkeys(result.get("blocking_reasons", [])))
    base["gate"] = {
        "allowed": result.get("status") == "verified",
        "blocking_reasons": reasons,
        "required_inputs": [
            "forward_eps.next_fiscal_year",
            "valuation_consensus.web_consensus",
            "valuation_consensus.peers",
            "target_instrument.share_basis",
        ],
    }
    base["status"] = "verified" if base["gate"]["allowed"] else "partial"
    base["currency"] = result.get("currency")
    base["share_basis"] = result.get("share_basis")
    return base
