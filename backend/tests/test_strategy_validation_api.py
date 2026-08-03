import json
import os

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
    assert report["available_report_count"] == 1
    assert report["results"]["combined"]["mode_label"] == "兩策略合併"
    trade = report["results"]["combined"]["trades"][0]
    assert trade["name"] == "台積電"
    assert trade["tradingview_url"].endswith("TWSE%3A2330")
    assert trade["analysis_hash"] == "#/research/2330"


def test_load_strategy_validation_report_uses_newest_file_mtime(tmp_path):
    out = tmp_path / "out"
    data = tmp_path / "data"
    out.mkdir()
    data.mkdir()
    data.joinpath("stock_names.json").write_text("{}", encoding="utf-8")
    data.joinpath("stock_markets.json").write_text("{}", encoding="utf-8")

    lexically_later = out / "tw_portfolio_replay_2026-07-08_2026-07-15.json"
    actually_newer = out / "tw_portfolio_replay_2026-07-01_2026-07-29.json"
    lexically_later.write_text(json.dumps(_sample_report()), encoding="utf-8")
    newer_report = _sample_report()
    newer_report["config"] = {"start": "2026-07-01", "end": "2026-07-29"}
    actually_newer.write_text(json.dumps(newer_report), encoding="utf-8")
    os.utime(lexically_later, (1_000, 1_000))
    os.utime(actually_newer, (2_000, 2_000))

    report = load_strategy_validation_report(out, data)

    assert report is not None
    assert report["config"] == {"start": "2026-07-01", "end": "2026-07-29"}
    assert report["available_report_count"] == 2


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


def test_planned_stop_uses_stop_level_when_intraday_low_crosses():
    from app.services.strategy_validation_service import _planned_stop_fill

    fill = _planned_stop_fill(
        {"open": 105.0, "high": 106.0, "low": 94.0, "close": 96.0},
        100.0,
    )

    assert fill == 99.9


def test_planned_stop_uses_gap_open_when_open_is_below_stop():
    from app.services.strategy_validation_service import _planned_stop_fill

    fill = _planned_stop_fill(
        {"open": 92.0, "high": 95.0, "low": 90.0, "close": 94.0},
        100.0,
    )

    assert fill == 91.908


def test_planned_stop_does_not_trigger_above_stop():
    from app.services.strategy_validation_service import _planned_stop_fill

    assert _planned_stop_fill(
        {"open": 105.0, "high": 106.0, "low": 101.0, "close": 102.0},
        100.0,
    ) is None


def test_same_day_stop_reentry_is_audited_without_arbitrary_cooldown():
    from app.services.strategy_validation_service import _same_day_stop_reentry_audit

    audit = _same_day_stop_reentry_audit(
        "2408", "2026-07-14", "2026-07-15", {"2408"}
    )

    assert audit == {
        "code": "2408",
        "signal_date": "2026-07-14",
        "fill_date": "2026-07-15",
        "reason_code": "same_day_stop_reentry",
        "reason": "計畫停損當日訊號已失效，不立即排入隔日重買",
    }
    assert _same_day_stop_reentry_audit(
        "2615", "2026-07-14", "2026-07-15", {"2408"}
    ) is None


def test_stop_reentry_audit_reports_exact_session_gap_and_risk_levels():
    from app.services.strategy_validation_service import _build_stop_reentry_audit

    trades = [
        {"code": "2301", "side": "sell", "fill_date": "2026-07-02", "reason_code": "planned_stop"},
        {"code": "3017", "side": "buy", "fill_date": "2026-07-03"},
        {"code": "2301", "side": "buy", "fill_date": "2026-07-07", "strategy": "old_wang"},
    ]
    days = ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-06", "2026-07-07"]
    risks = [
        {"date": "2026-07-02", "level": "defensive"},
        {"date": "2026-07-07", "level": "normal"},
    ]

    assert _build_stop_reentry_audit(trades, days, risks) == [{
        "code": "2301",
        "stop_date": "2026-07-02",
        "reentry_date": "2026-07-07",
        "sessions_until_reentry": 3,
        "stop_risk_level": "defensive",
        "reentry_risk_level": "normal",
        "strategy": "old_wang",
    }]


def test_entry_risk_recovers_through_watch_for_one_session():
    from app.services.strategy_validation_service import _effective_entry_risk_level

    assert _effective_entry_risk_level("normal", "defensive") == "watch"
    assert _effective_entry_risk_level("normal", "extreme") == "watch"
    assert _effective_entry_risk_level("normal", "unknown") == "watch"
    assert _effective_entry_risk_level("normal", "watch") == "normal"
    assert _effective_entry_risk_level("normal", "normal") == "normal"
    assert _effective_entry_risk_level("defensive", "normal") == "defensive"


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
