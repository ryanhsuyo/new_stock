import json


def test_build_signal_alerts_reports_no_previous_snapshot():
    from app.services.signal_alert_service import build_signal_alerts

    alerts = build_signal_alerts({
        "as_of": "2026-06-24",
        "previous_as_of": None,
        "generated_at": "2026-06-24T15:00:00",
        "rules_version": "rules-test",
        "rules_metadata": {
            "version": "rules-test",
            "strategy_profile": "two_strategy_daily_v1",
        },
        "status": "no_previous_snapshot",
        "items": [],
    })

    assert alerts["alert_count"] == 0
    assert alerts["rules_version"] == "rules-test"
    assert alerts["rules_metadata"]["strategy_profile"] == "two_strategy_daily_v1"
    assert alerts["severity_counts"] == {}
    assert alerts["alerts"] == []
    assert "尚無前一日" in alerts["message"]


def test_build_signal_alerts_filters_unchanged_items():
    from app.services.signal_alert_service import build_signal_alerts

    alerts = build_signal_alerts({
        "as_of": "2026-06-24",
        "previous_as_of": "2026-06-23",
        "generated_at": "2026-06-24T15:00:00",
        "status": "reviewed",
        "items": [
            {"code": "2330", "name": "台積電", "outcome": "unchanged", "reason": "未改變"},
        ],
    })

    assert alerts["alert_count"] == 0
    assert alerts["alerts"] == []
    assert alerts["message"] == "隔日訊號無需處理的新警示。"


def test_build_signal_alerts_maps_mixed_outcomes_to_severity():
    from app.services.signal_alert_service import build_signal_alerts

    alerts = build_signal_alerts({
        "as_of": "2026-06-24",
        "previous_as_of": "2026-06-23",
        "generated_at": "2026-06-24T15:00:00",
        "status": "reviewed",
        "items": [
            {
                "code": "2330",
                "name": "台積電",
                "outcome": "risk_triggered",
                "reason": "前一日計畫轉為風險",
                "previous_action": "enter",
                "current_action": "exit",
                "current_signal": "exit_warning",
            },
            {
                "code": "2303",
                "name": "聯電",
                "outcome": "risk_eased",
                "reason": "風險解除",
                "previous_action": "exit",
                "current_action": "hold",
            },
            {
                "code": "2408",
                "name": "南亞科",
                "outcome": "action_changed",
                "reason": "動作改變",
                "previous_action": "wait_pullback",
                "current_action": "hold",
            },
            {
                "code": "9999",
                "name": "缺資料",
                "outcome": "missing_current",
                "reason": "本日缺少資料",
                "previous_action": "hold",
            },
        ],
    })

    by_code = {item["code"]: item for item in alerts["alerts"]}
    assert alerts["alert_count"] == 4
    assert alerts["severity_counts"] == {"block": 1, "info": 1, "warn": 2}
    assert by_code["2330"]["severity"] == "block"
    assert by_code["2330"]["title"] == "持股/候選轉風險"
    assert by_code["2303"]["severity"] == "info"
    assert by_code["2408"]["severity"] == "warn"
    assert by_code["9999"]["title"] == "前日計畫缺少本日資料"


def test_write_and_load_signal_alerts_round_trip(tmp_path):
    from app.services.signal_alert_service import load_signal_alerts, write_signal_alerts

    review = {
        "as_of": "2026-06-24",
        "previous_as_of": "2026-06-23",
        "generated_at": "2026-06-24T15:00:00",
        "status": "reviewed",
        "items": [{"code": "2330", "name": "台積電", "outcome": "risk_triggered"}],
    }

    path = write_signal_alerts(review, tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    loaded = load_signal_alerts(tmp_path)

    assert path.name == "signal_alerts.json"
    assert data["alert_count"] == 1
    assert loaded == data
