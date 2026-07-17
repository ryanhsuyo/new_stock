from app.services.us_strategy_validation_service import _validate_range


def test_validate_us_strategy_range_snaps_to_available_trading_days():
    assert _validate_range("2026-06-13", "2026-06-17", ["2026-06-12", "2026-06-15", "2026-06-16", "2026-06-18"]) == ("2026-06-15", "2026-06-16")


def test_validate_us_strategy_range_rejects_invalid_input():
    for start, end, expected in [("2026/06/01", "2026-06-30", "日期格式必須是 YYYY-MM-DD"), ("2026-07-01", "2026-06-01", "開始日期不可晚於結束日期"), ("2020-01-01", "2020-01-02", "所選區間沒有可用的美股交易資料")]:
        try:
            _validate_range(start, end, ["2026-06-15"])
        except ValueError as exc:
            assert str(exc) == expected
        else:
            raise AssertionError("expected ValueError")


def test_us_strategy_validation_endpoint(client, monkeypatch):
    import app.routers.markets as router
    monkeypatch.setattr(router, "run_us_strategy_validation", lambda start, end: {"region": "US", "start_date": start, "end_date": end, "results": {}})
    response = client.post("/api/markets/us/strategy-validation?start=2026-06-01&end=2026-06-30")
    assert response.status_code == 200
    assert response.json()["region"] == "US"


def test_us_strategy_validation_endpoint_returns_date_error(client, monkeypatch):
    import app.routers.markets as router
    monkeypatch.setattr(router, "run_us_strategy_validation", lambda start, end: (_ for _ in ()).throw(ValueError("bad range")))
    response = client.post("/api/markets/us/strategy-validation?start=x&end=y")
    assert response.status_code == 422
    assert response.json()["detail"] == "bad range"
