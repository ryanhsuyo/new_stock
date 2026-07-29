from datetime import date, timedelta

from app.services import us_analysis_service as analysis
from app.services import us_strategy_service as trend
from app.services import us_wbottom_service as wbottom


def _rows(start: date, count: int, base: float) -> list[dict]:
    return [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "open": base + index,
            "high": base + index + 1,
            "low": base + index - 1,
            "close": base + index,
            "volume": 1000,
        }
        for index in range(count)
    ]


def test_fixed_asof_daily_outputs_ignore_future_rows(monkeypatch):
    historical = _rows(date(2026, 1, 1), 80, 100)
    cutoff = historical[-1]["date"]
    future = _rows(date(2026, 4, 1), 12, 1000)
    market = {
        "SPY": historical + future,
        "QQQ": historical + future,
        "AAA": historical + future,
    }
    leaders = [
        {"code": "SPY", "name": "SPY", "category": "ETF / Benchmark"},
        {"code": "QQQ", "name": "QQQ", "category": "ETF / Benchmark"},
        {"code": "AAA", "name": "AAA", "category": "Technology"},
    ]
    monkeypatch.setattr(analysis, "load_us_ohlcv", lambda: market)
    monkeypatch.setattr(analysis, "load_us_leaders", lambda: leaders)
    monkeypatch.setattr(wbottom, "load_us_ohlcv", lambda: market)
    monkeypatch.setattr(wbottom, "load_us_leaders", lambda: leaders)

    trend_with_future = trend.get_us_trend_follow(as_of=cutoff)
    wbottom_with_future = wbottom.get_us_wbottom(as_of=cutoff)

    market = {code: rows[:80] for code, rows in market.items()}
    trend_without_future = trend.get_us_trend_follow(as_of=cutoff)
    wbottom_without_future = wbottom.get_us_wbottom(as_of=cutoff)

    assert trend_with_future == trend_without_future
    assert wbottom_with_future == wbottom_without_future
    assert trend_with_future["as_of"] == cutoff
    assert wbottom_with_future["as_of"] == cutoff
    assert all(
        item["data_as_of"] == cutoff
        for item in trend_with_future["candidates"] + trend_with_future["excluded"]
    )
    assert future[0]["date"] > cutoff
