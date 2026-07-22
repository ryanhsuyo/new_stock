import app.services.pre_market_risk_service as svc


def _rows(previous: float, latest: float, latest_date: str = "2026-07-16") -> list[dict]:
    return [
        {"date": "2026-07-15", "close": str(previous)},
        {"date": latest_date, "close": str(latest)},
    ]


def _fresh() -> dict:
    return {
        "region": "US", "source": "fixture", "source_configured": True,
        "last_updated": "2026-07-16", "stale": False,
        "days_since_last": 0, "expected_trading_day": "2026-07-16",
    }


def test_extreme_risk_requires_multiple_explainable_signals(monkeypatch):
    monkeypatch.setattr(svc, "load_us_ohlcv", lambda: {
        "QQQ": _rows(100, 96), "TSM": _rows(100, 95), "SPY": _rows(100, 97),
    })
    monkeypatch.setattr(svc, "load_market_notes", lambda: [])
    monkeypatch.setattr(svc, "get_us_data_freshness", _fresh)

    report = svc.get_pre_market_risk_report()

    assert report["level"] == "extreme"
    assert report["can_open_new_positions"] is False
    assert report["max_exposure_pct"] == 30
    assert report["score"] == 11
    assert all(item["reason"] for item in report["signals"])


def test_stale_data_never_reports_normal(monkeypatch):
    monkeypatch.setattr(svc, "load_us_ohlcv", lambda: {
        "QQQ": _rows(100, 101), "TSM": _rows(100, 101), "SPY": _rows(100, 101),
    })
    monkeypatch.setattr(svc, "load_market_notes", lambda: [])
    stale = _fresh() | {"stale": True, "days_since_last": 3}
    monkeypatch.setattr(svc, "get_us_data_freshness", lambda: stale)

    report = svc.get_pre_market_risk_report()

    assert report["level"] == "unknown"
    assert report["can_open_new_positions"] is False
    assert report["max_exposure_pct"] is None


def test_recent_manual_event_adds_risk_without_becoming_a_trade(monkeypatch):
    monkeypatch.setattr(svc, "load_us_ohlcv", lambda: {
        "QQQ": _rows(100, 99), "TSM": _rows(100, 99), "SPY": _rows(100, 99),
    })
    monkeypatch.setattr(svc, "load_market_notes", lambda: [{
        "date": "2026-07-16", "title": "權值股法說", "headline": "留意利多出盡",
        "risk_level": "high", "source": "manual",
    }])
    monkeypatch.setattr(svc, "get_us_data_freshness", _fresh)

    report = svc.get_pre_market_risk_report()

    assert report["level"] == "defensive"
    assert report["latest_event"]["points"] == 4
    assert "trade" not in report


def test_old_manual_event_is_visible_but_not_scored(monkeypatch):
    monkeypatch.setattr(svc, "load_us_ohlcv", lambda: {
        "QQQ": _rows(100, 101), "TSM": _rows(100, 101), "SPY": _rows(100, 101),
    })
    monkeypatch.setattr(svc, "load_market_notes", lambda: [{
        "date": "2026-05-01", "title": "舊事件", "headline": "不可沿用",
        "risk_level": "high", "source": "manual",
    }])
    monkeypatch.setattr(svc, "get_us_data_freshness", _fresh)

    report = svc.get_pre_market_risk_report()

    assert report["score"] == 0
    assert report["latest_event"]["is_stale"] is True
    assert report["latest_event"]["points"] == 0


def test_pre_market_risk_api(client, monkeypatch):
    monkeypatch.setattr("app.routers.system.get_pre_market_risk_report", lambda: {
        "generated_at": "2026-07-17T00:00:00+00:00", "level": "watch",
        "level_label": "警戒", "score": 2, "headline": "fixture", "data_as_of": "2026-07-16",
        "data_freshness": {}, "can_open_new_positions": True, "max_exposure_pct": 70,
        "signals": [], "latest_event": None, "guidance": {}, "official_sources": [], "limitations": [],
    })
    response = client.get("/api/system/pre-market-risk")
    assert response.status_code == 200
    assert response.json()["level"] == "watch"


def test_historical_risk_uses_only_us_bars_before_tw_fill_date():
    rows = {
        "QQQ": [_rows(100, 96)[0], _rows(100, 96)[1], {"date": "2026-07-17", "close": "120"}],
        "TSM": [_rows(100, 95)[0], _rows(100, 95)[1], {"date": "2026-07-17", "close": "120"}],
        "SPY": [_rows(100, 97)[0], _rows(100, 97)[1], {"date": "2026-07-17", "close": "120"}],
    }

    report = svc.assess_historical_pre_market_risk("2026-07-17", rows)

    assert report["level"] == "extreme"
    assert report["data_as_of"] == "2026-07-16"
    assert report["score"] == 11


def test_historical_risk_fails_closed_when_bars_are_too_old():
    rows = {
        "QQQ": _rows(100, 101, "2026-07-10"),
        "TSM": _rows(100, 101, "2026-07-10"),
        "SPY": _rows(100, 101, "2026-07-10"),
    }

    report = svc.assess_historical_pre_market_risk("2026-07-17", rows)

    assert report["level"] == "unknown"
