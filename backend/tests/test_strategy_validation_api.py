import json

from app.services.strategy_validation_service import load_strategy_validation_report


def _sample_report() -> dict:
    return {
        "config": {"start": "2026-05-01", "end": "2026-07-15"},
        "limitations": ["paper replay"],
        "results": {
            "combined": {
                "final_equity_after_estimated_liquidation_cost": 1_100_000,
                "trades": [{"code": "2330", "side": "buy"}],
                "open_positions": [{"code": "2330", "shares": 10}],
            }
        },
    }


def test_load_strategy_validation_report_enriches_stock_links(tmp_path):
    out = tmp_path / "out"
    data = tmp_path / "data"
    out.mkdir()
    data.mkdir()
    (out / "tw_portfolio_replay_2026-05-01_2026-07-15.json").write_text(
        json.dumps(_sample_report()), encoding="utf-8"
    )
    (data / "stock_names.json").write_text(json.dumps({"2330": "台積電"}), encoding="utf-8")
    (data / "stock_markets.json").write_text(json.dumps({"2330": "TWSE"}), encoding="utf-8")

    report = load_strategy_validation_report(out, data)

    assert report is not None
    assert report["results"]["combined"]["mode_label"] == "兩策略合併"
    trade = report["results"]["combined"]["trades"][0]
    assert trade["name"] == "台積電"
    assert trade["tradingview_url"].endswith("TWSE%3A2330")
    assert trade["analysis_hash"] == "#/research/2330"


def test_strategy_validation_endpoint_returns_404_when_report_missing(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "load_strategy_validation_report", lambda: None)
    response = client.get("/api/system/strategy-validation")
    assert response.status_code == 404


def test_strategy_validation_endpoint_returns_report(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "load_strategy_validation_report", _sample_report)
    response = client.get("/api/system/strategy-validation")
    assert response.status_code == 200
    assert response.json()["results"]["combined"]["trades"][0]["code"] == "2330"


def test_generate_strategy_validation_endpoint_passes_date_range(client, monkeypatch):
    import app.routers.system as router

    seen = {}
    def fake_run(start, end):
        seen["range"] = (start, end)
        return _sample_report()

    monkeypatch.setattr(router, "run_strategy_validation", fake_run)
    response = client.post("/api/system/strategy-validation?start=2026-06-01&end=2026-06-30")

    assert response.status_code == 200
    assert seen["range"] == ("2026-06-01", "2026-06-30")


def test_generate_strategy_validation_endpoint_returns_readable_date_error(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "run_strategy_validation", lambda start, end: (_ for _ in ()).throw(ValueError("開始日期不可晚於結束日期")))
    response = client.post("/api/system/strategy-validation?start=2026-07-01&end=2026-06-01")

    assert response.status_code == 422
    assert response.json()["detail"] == "開始日期不可晚於結束日期"


def test_run_strategy_validation_rejects_bad_ranges_before_reading_data():
    from app.services.strategy_validation_service import run_strategy_validation

    for start, end, message in [
        ("2026/06/01", "2026-06-30", "日期格式必須是 YYYY-MM-DD"),
        ("2026-07-01", "2026-06-01", "開始日期不可晚於結束日期"),
    ]:
        try:
            run_strategy_validation(start, end)
        except ValueError as exc:
            assert str(exc) == message
        else:
            raise AssertionError("expected ValueError")
