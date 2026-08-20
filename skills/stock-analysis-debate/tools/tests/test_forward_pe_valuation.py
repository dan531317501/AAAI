import pytest

from forward_pe_valuation import (
    build_forward_pe_valuation,
    calculate_forward_pe_scenarios,
    validate_valuation_consensus,
)


def _payload():
    return {
        "schema_version": "1.0",
        "status": "available",
        "instrument": {
            "currency": "USD",
            "share_basis": "USD/ADR",
            "source_name": "SEC F-6",
            "source_url": "https://www.sec.gov/example",
            "as_of_date": "2026-08-10",
            "basis": "The ADS ratio is explicitly stated in the deposit agreement.",
        },
        "web_consensus": [
            {
                "scope": "industry",
                "target_pe": 7.0,
                "forecast_period": "next_fiscal_year",
                "currency": "USD",
                "share_basis": "USD/industry_peer",
                "source_name": "Example Research",
                "source_url": "https://example.com/industry-pe",
                "published_at": "2026-08-01",
                "basis": "The industry note reports a next-fiscal-year Forward P/E midpoint.",
            }
        ],
        "peers": [
            {
                "symbol": "PEER1",
                "forward_pe": 4.0,
                "forecast_period": "next_fiscal_year",
                "currency": "USD",
                "share_basis": "USD/common_share",
                "source_name": "Peer data provider",
                "source_url": "https://example.com/peer1",
                "as_of_date": "2026-08-11",
                "basis": "Provider's next-fiscal-year Forward P/E field.",
            },
            {
                "symbol": "PEER2",
                "forward_pe": 6.0,
                "forecast_period": "next_fiscal_year",
                "currency": "KRW",
                "share_basis": "KRW/common_share",
                "source_name": "Peer data provider",
                "source_url": "https://example.com/peer2",
                "as_of_date": "2026-08-11",
                "basis": "Provider's next-fiscal-year Forward P/E field.",
            },
            {
                "symbol": "PEER3",
                "forward_pe": 8.0,
                "forecast_period": "next_fiscal_year",
                "currency": "USD",
                "share_basis": "USD/common_share",
                "source_name": "Peer data provider",
                "source_url": "https://example.com/peer3",
                "as_of_date": "2026-08-11",
                "basis": "Provider's next-fiscal-year Forward P/E field.",
            },
            {
                "symbol": "PEER4",
                "forward_pe": 10.0,
                "forecast_period": "next_fiscal_year",
                "currency": "USD",
                "share_basis": "USD/common_share",
                "source_name": "Peer data provider",
                "source_url": "https://example.com/peer4",
                "as_of_date": "2026-08-11",
                "basis": "Provider's next-fiscal-year Forward P/E field.",
            },
        ],
    }


def _eps():
    return {
        "value": 32.14059,
        "currency": "USD",
        "share_basis": "USD/ADR",
        "forecast_period": "next_fiscal_year",
        "provider_period": "+1y",
        "analyst_count": 5,
        "source_name": "yfinance",
        "source_field": "earnings_estimate.+1y.avg",
        "retrieved_at": "2026-08-11T12:00:00+00:00",
    }


def test_validates_web_consensus_and_keeps_peer_currency_as_native_ratio_basis():
    evidence = validate_valuation_consensus(_payload(), "2026-08-12")

    assert evidence["status"] == "verified"
    assert evidence["peer_count"] == 4
    assert evidence["web_consensus_count"] == 1
    assert evidence["blocking_reasons"] == []
    assert {peer["currency"] for peer in evidence["peers"]} == {"USD", "KRW"}


def test_calculates_linear_p25_p50_p75_and_three_price_targets():
    evidence = validate_valuation_consensus(_payload(), "2026-08-12")
    result = calculate_forward_pe_scenarios(
        _eps(), evidence["peers"], evidence, "2026-08-12"
    )

    assert result["status"] == "verified"
    assert result["scenarios"]["bear"]["target_pe"] == pytest.approx(5.5)
    assert result["scenarios"]["base"]["target_pe"] == pytest.approx(7.0)
    assert result["scenarios"]["bull"]["target_pe"] == pytest.approx(8.5)
    assert result["scenarios"]["base"]["price_target"] == pytest.approx(224.98413)
    assert result["scenarios"]["base"]["share_basis"] == "USD/ADR"


def test_build_result_has_report_ready_scenario_fields():
    result = build_forward_pe_valuation(_eps(), _payload(), "2026-08-12")

    assert result["status"] == "verified"
    assert result["gate"]["allowed"] is True
    assert result["method"] == "forward_eps_x_peer_forward_pe_percentiles"
    assert set(result["scenarios"]) == {"bear", "base", "bull"}
    assert result["scenarios"]["bear"]["formula"].startswith("32.1406")
    assert result["report_lines"] == {
        "forward_eps": "32.14 USD/ADR",
        "target_pe": "5.5x / 7.0x / 8.5x",
        "price_target": "176.77 / 224.98 / 273.20 USD/ADR",
    }


@pytest.mark.parametrize(
    "mutator,reason",
    [
        (lambda payload: payload["web_consensus"][0].update({"published_at": "2026-01-01"}),
         "web_consensus_0_source_stale_over_60_days"),
        (lambda payload: (
            payload["peers"][0].update({"forecast_period": "NTM"}),
            payload["peers"][1].update({"forecast_period": "NTM"}),
        ),
         "valid_peer_count_below_3"),
        (lambda payload: (payload["peers"].pop(), payload["peers"].pop()),
         "valid_peer_count_below_3"),
        (lambda payload: payload["instrument"].update({"share_basis": "unknown"}),
         "share_basis_unverified"),
    ],
)
def test_invalid_or_stale_evidence_closes_target_gate(mutator, reason):
    payload = _payload()
    mutator(payload)
    result = build_forward_pe_valuation(_eps(), payload, "2026-08-12")

    assert result["gate"]["allowed"] is False
    assert reason in result["gate"]["blocking_reasons"]
    assert result["scenarios"] == {}


def test_one_invalid_peer_is_excluded_when_three_valid_peers_remain():
    payload = _payload()
    payload["peers"][0]["forecast_period"] = "NTM"

    result = build_forward_pe_valuation(_eps(), payload, "2026-08-12")

    assert result["gate"]["allowed"] is True
    assert result["peer_count"] == 3
    assert result["valuation_evidence"]["excluded_peers"][0]["symbol"] == "PEER1"


def test_historical_replay_never_uses_current_web_snapshot():
    result = build_forward_pe_valuation(
        _eps(), _payload(), "2026-08-12", analysis_mode="historical_replay"
    )

    assert result["gate"]["allowed"] is False
    assert "historical_replay_non_point_in_time_valuation_inputs" in result["gate"]["blocking_reasons"]
