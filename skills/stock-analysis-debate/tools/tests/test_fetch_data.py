import pandas as pd

import fetch_data


def test_fetch_financial_stmt_keeps_only_the_rolling_one_year_window(monkeypatch):
    statement = pd.DataFrame(
        [[100, 90, 80, 70]],
        index=["Total Revenue"],
        columns=pd.to_datetime(
            ["2026-06-30", "2025-08-04", "2025-08-03", "2024-12-31"]
        ),
    )

    class FakeTicker:
        quarterly_income_stmt = statement

    monkeypatch.setattr(fetch_data.yf, "Ticker", lambda symbol: FakeTicker())
    monkeypatch.setattr(fetch_data, "retry", lambda callback: callback())

    result = fetch_data.fetch_financial_stmt(
        "AAPL", "income_stmt", "quarterly", "2026-08-04", market="US"
    )

    assert "2025-08-04" in result
    assert "2025-08-03" not in result
    assert "2024-12-31" not in result
