from output_layout import resolve_ticker_paths


def test_ticker_data_dir_places_date_directly_under_data_root(tmp_path):
    ticker_data_dir = tmp_path / "reposrts" / "AAPL" / "data"

    ticker_root, day_dir = resolve_ticker_paths(
        "AAPL",
        "2026-08-04",
        base_output_dir=str(tmp_path / "legacy"),
        ticker_data_dir=str(ticker_data_dir),
    )

    assert ticker_root == str(ticker_data_dir)
    assert day_dir == str(ticker_data_dir / "2026-08-04")


def test_legacy_output_dir_still_appends_normalized_ticker_and_date(tmp_path):
    ticker_root, day_dir = resolve_ticker_paths(
        "600519.SH",
        "2026-08-04",
        base_output_dir=str(tmp_path / "data"),
    )

    assert ticker_root == str(tmp_path / "data" / "600519_SH")
    assert day_dir == str(tmp_path / "data" / "600519_SH" / "2026-08-04")
