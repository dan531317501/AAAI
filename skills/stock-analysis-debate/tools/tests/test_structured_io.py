import json

import pytest
from toon_format import decode
from toon_format.types import DecodeOptions

import structured_io
from structured_io import (
    json_to_toon,
    read_structured_file,
    resolve_structured_path,
    structured_path,
    write_structured_file,
)


def _stock_payload():
    return {
        "ticker": "01810.HK",
        "currency": {"quote": "HKD", "financial": "CNY"},
        "metrics": [
            {"metric_id": "revenue", "value": 88_888.5, "status": "verified"},
            {"metric_id": "profit", "value": None, "status": "unavailable"},
        ],
        "notes": ["含中文", "comma, colon: and newline\nkept"],
        "allowed": True,
    }


def test_json_to_toon_round_trips_nested_stock_data():
    payload = _stock_payload()

    toon_text = json_to_toon(json.dumps(payload, ensure_ascii=False))

    assert decode(toon_text, DecodeOptions(strict=True)) == payload
    assert "ticker: 01810.HK" in toon_text


def test_default_write_uses_toon_and_removes_stale_json(tmp_path):
    logical_path = tmp_path / "validated_metrics.json"
    logical_path.write_text('{"stale": true}', encoding="utf-8")

    actual_path = write_structured_file(logical_path, _stock_payload())

    assert actual_path == tmp_path / "validated_metrics.toon"
    assert actual_path.is_file()
    assert not logical_path.exists()
    assert read_structured_file(logical_path) == _stock_payload()


def test_switching_variable_to_json_writes_json_and_removes_stale_toon(
    tmp_path,
    monkeypatch,
):
    logical_path = tmp_path / "summary.json"
    stale_toon = logical_path.with_suffix(".toon")
    stale_toon.write_text("stale: true", encoding="utf-8")
    monkeypatch.setattr(structured_io, "STRUCTURED_OUTPUT_FORMAT", "json")

    actual_path = write_structured_file(logical_path, _stock_payload())

    assert actual_path == logical_path
    assert json.loads(actual_path.read_text(encoding="utf-8")) == _stock_payload()
    assert not stale_toon.exists()


def test_reader_prefers_configured_format_but_falls_back_to_history(tmp_path):
    logical_path = tmp_path / "data_quality.json"
    json_path = write_structured_file(
        logical_path,
        {"source": "json"},
        output_format="json",
        remove_alternate=False,
    )
    toon_path = write_structured_file(
        logical_path,
        {"source": "toon"},
        output_format="toon",
        remove_alternate=False,
    )

    assert resolve_structured_path(logical_path) == toon_path
    assert read_structured_file(logical_path) == {"source": "toon"}
    toon_path.unlink()
    assert resolve_structured_path(logical_path) == json_path
    assert read_structured_file(logical_path) == {"source": "json"}


def test_structured_path_rejects_unknown_format():
    with pytest.raises(ValueError, match="unsupported structured output format"):
        structured_path("summary.json", output_format="yaml")


def test_non_finite_number_is_rejected_without_replacing_existing_file(tmp_path):
    logical_path = tmp_path / "summary.json"
    existing = logical_path.with_suffix(".toon")
    existing.write_text("status: existing", encoding="utf-8")

    with pytest.raises(ValueError, match="Out of range float values"):
        write_structured_file(logical_path, {"value": float("nan")})

    assert existing.read_text(encoding="utf-8") == "status: existing"


def test_toon_round_trip_mismatch_fails_closed(monkeypatch):
    def fake_encode(_value):
        return "ignored"

    def fake_decode(_text, _options):
        return {"value": "changed"}

    class FakeDecodeOptions:
        def __init__(self, strict):
            self.strict = strict

    monkeypatch.setattr(
        structured_io,
        "_toon_codec",
        lambda: (fake_encode, fake_decode, FakeDecodeOptions),
    )

    with pytest.raises(ValueError, match="round-trip validation failed"):
        json_to_toon({"value": "original"})
