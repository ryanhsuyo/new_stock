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


def test_generate_strategy_validation_endpoint_triggers_background(client, monkeypatch):
    # POST 只觸發背景執行（全窗口回放需數分鐘，不得同步佔住請求）
    import app.routers.system as router

    seen = {}
    def fake_trigger(start, end):
        seen["range"] = (start, end)
        return {"status": "running", "started_at": "2026-07-17T22:00:00+08:00",
                "finished_at": None, "error": None, "start": start, "end": end}

    monkeypatch.setattr(router, "trigger_background_validation", fake_trigger)
    response = client.post("/api/system/strategy-validation?start=2026-06-01&end=2026-06-30")

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert seen["range"] == ("2026-06-01", "2026-06-30")


def test_generate_strategy_validation_endpoint_returns_readable_date_error(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "trigger_background_validation", lambda start, end: (_ for _ in ()).throw(ValueError("開始日期不可晚於結束日期")))
    response = client.post("/api/system/strategy-validation?start=2026-07-01&end=2026-06-01")

    assert response.status_code == 422
    assert response.json()["detail"] == "開始日期不可晚於結束日期"


def test_generate_strategy_validation_endpoint_returns_409_when_busy(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "trigger_background_validation", lambda start, end: (_ for _ in ()).throw(RuntimeError("策略驗收回放已在執行中")))
    response = client.post("/api/system/strategy-validation?start=2026-06-01&end=2026-06-30")

    assert response.status_code == 409


def test_strategy_validation_status_endpoint(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "load_validation_status", lambda: {"status": "success", "started_at": "x", "finished_at": "y", "error": None, "start": "2026-06-01", "end": "2026-06-30"})
    response = client.get("/api/system/strategy-validation/status")

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_trigger_background_validation_validates_dates_before_starting_thread():
    from app.services.strategy_validation_service import trigger_background_validation

    for start, end, message in [
        ("2026/06/01", "2026-06-30", "日期格式必須是 YYYY-MM-DD"),
        ("2026-07-01", "2026-06-01", "開始日期不可晚於結束日期"),
    ]:
        try:
            trigger_background_validation(start, end)
        except ValueError as exc:
            assert str(exc) == message
        else:
            raise AssertionError("expected ValueError")


def test_trigger_background_validation_busy_lock(monkeypatch):
    from app.services import strategy_validation_service as svc

    assert svc._VALIDATION_LOCK.acquire(blocking=False)
    try:
        try:
            svc.trigger_background_validation("2026-06-01", "2026-06-30")
        except RuntimeError as exc:
            assert "已在執行中" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")
    finally:
        svc._VALIDATION_LOCK.release()


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


def test_entry_guardrails_are_conservative_and_fail_closed():
    from app.services.strategy_validation_service import ENTRY_GUARDRAIL_PROFILES

    assert ENTRY_GUARDRAIL_PROFILES["combined"]["normal"] == {
        "max_position_pct": 15, "max_exposure_pct": 60, "max_new_positions": 3,
    }
    assert ENTRY_GUARDRAIL_PROFILES["steady_momentum"]["normal"] == {
        "max_position_pct": 15, "max_exposure_pct": 60, "max_new_positions": 3,
    }
    for profile in ENTRY_GUARDRAIL_PROFILES.values():
        assert profile["watch"]["max_exposure_pct"] < profile["normal"]["max_exposure_pct"]
        assert profile["defensive"]["max_new_positions"] == 0
        assert profile["extreme"]["max_new_positions"] == 0
        assert profile["unknown"]["max_new_positions"] == 0
