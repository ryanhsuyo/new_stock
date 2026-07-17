from datetime import date
import sys
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
_SCRIPTS = _BACKEND / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def test_update_workflow_blocks_when_market_data_is_stale(monkeypatch):
    import app.services.update_workflow_service as svc
    from app.services.workflow_outputs import DAILY_UPDATE_OUTPUTS

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    monkeypatch.setattr(svc, "date", FakeDate)
    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-29",
        "raw_ohlcv_as_of": "2026-05-29",
        "outputs_lag_raw_data": False,
        "is_stale": True,
        "stale_days": 9,
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "generated_at": "2026-06-07",
        "data_as_of": "2026-05-29",
        "snapshot_is_stale": False,
        "can_use_trade_outputs": True,
    })

    report = svc.get_update_workflow_status()

    assert report["overall_status"] == "blocked"
    assert report["can_use_trade_outputs"] is False
    assert report["current_step"] == "update_market_data"
    assert report["next_action"]["command"] == "python3 scripts/daily_update.py --months 1"
    assert report["next_action"]["copy_command"].splitlines()[-1] == "python3 scripts/daily_update.py --months 1"
    assert report["next_action"]["expected_outputs"] == DAILY_UPDATE_OUTPUTS
    assert report["steps"][0]["status"] == "blocked"


def test_update_workflow_requires_signals_when_outputs_lag_raw_data(monkeypatch):
    import app.services.update_workflow_service as svc

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    monkeypatch.setattr(svc, "date", FakeDate)
    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-06-06",
        "raw_ohlcv_as_of": "2026-06-07",
        "outputs_lag_raw_data": True,
        "raw_data_warning": "ohlcv.csv 已更新到 2026-06-07，交易輸出仍停在 2026-06-06。",
        "is_stale": False,
        "stale_days": 1,
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "generated_at": "2026-06-07",
        "data_as_of": "2026-06-06",
        "snapshot_is_stale": False,
        "can_use_trade_outputs": True,
    })

    report = svc.get_update_workflow_status()

    assert report["overall_status"] == "blocked"
    assert report["can_use_trade_outputs"] is False
    assert report["current_step"] == "regenerate_signals"
    assert report["next_action"]["command"] == "python3 scripts/run_signals.py"
    assert report["steps"][1]["status"] == "blocked"


def test_update_workflow_warns_when_daily_check_snapshot_is_stale(monkeypatch):
    import app.services.update_workflow_service as svc

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    monkeypatch.setattr(svc, "date", FakeDate)
    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-06-07",
        "raw_ohlcv_as_of": "2026-06-07",
        "outputs_lag_raw_data": False,
        "is_stale": False,
        "stale_days": 0,
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "generated_at": "2026-06-06",
        "data_as_of": "2026-06-07",
        "snapshot_is_stale": True,
        "snapshot_stale_reason": "Daily Check 快照產生於 2026-06-06，今天是 2026-06-07。",
        "snapshot_refresh_command": "python3 scripts/daily_check.py --write-report",
        "can_use_trade_outputs": True,
    })

    report = svc.get_update_workflow_status()

    assert report["overall_status"] == "action_required"
    assert report["can_use_trade_outputs"] is True
    assert report["current_step"] == "refresh_daily_check"
    assert report["next_action"]["command"] == "python3 scripts/daily_check.py --write-report"
    assert report["steps"][2]["status"] == "warning"


def test_update_workflow_blocks_when_fresh_daily_check_blocks_trade_outputs(monkeypatch):
    import app.services.update_workflow_service as svc
    from app.services.workflow_outputs import SIGNAL_OUTPUTS

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    monkeypatch.setattr(svc, "date", FakeDate)
    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-06-07",
        "raw_ohlcv_as_of": "2026-06-07",
        "outputs_lag_raw_data": False,
        "is_stale": False,
        "stale_days": 0,
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "generated_at": "2026-06-07",
        "data_as_of": "2026-06-07",
        "snapshot_is_stale": False,
        "can_use_trade_outputs": False,
        "top_actions": [
            {
                "key": "outputs",
                "status": "block",
                "title": "交易輸出日期不同步",
                "message": "summary、daily_brief 或 universe_report 的資料日不一致。",
                "next_action": "python3 scripts/run_signals.py",
                "action_payload": {
                    "kind": "command",
                    "command": "python3 scripts/run_signals.py",
                    "copy_command": "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/run_signals.py",
                },
            }
        ],
    })

    report = svc.get_update_workflow_status()

    assert report["overall_status"] == "blocked"
    assert report["can_use_trade_outputs"] is False
    assert report["current_step"] == "resolve_daily_check_blocker"
    assert report["next_action"]["key"] == "outputs"
    assert report["next_action"]["command"] == "python3 scripts/run_signals.py"
    assert report["next_action"]["copy_command"].endswith(
        "backend\npython3 scripts/run_signals.py"
    )
    assert report["next_action"]["expected_outputs"] == SIGNAL_OUTPUTS
    assert report["steps"][2]["status"] == "blocked"


def test_update_workflow_blocks_when_data_coverage_is_too_low(monkeypatch):
    import app.services.update_workflow_service as svc

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 23)

    monkeypatch.setattr(svc, "date", FakeDate)
    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-06-22",
        "raw_ohlcv_as_of": "2026-06-22",
        "outputs_lag_raw_data": False,
        "is_stale": False,
        "stale_days": 1,
        "batch_id": "batch-low",
        "coverage_report_path": "/tmp/backend/out/data_coverage_report.json",
        "data_coverage_pct": 50.0,
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "generated_at": "2026-06-23",
        "data_as_of": "2026-06-22",
        "snapshot_is_stale": False,
        "can_use_trade_outputs": True,
    })

    report = svc.get_update_workflow_status()

    assert report["overall_status"] == "blocked"
    assert report["current_step"] == "improve_data_coverage"
    assert report["next_action"]["command"] == "python3 scripts/daily_update.py --months 1"
    assert report["checks"]["batch_id"] == "batch-low"
    assert report["checks"]["data_coverage_pct"] == 50.0
    assert report["checks"]["coverage_report_path"].endswith("data_coverage_report.json")


def test_update_workflow_reuses_daily_check_command_payload(monkeypatch):
    import daily_check
    import app.services.update_workflow_service as svc

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    daily_summary = daily_check.build_daily_summary(
        {
            "overall_status": "block",
            "exit_code": 2,
            "generated_at": "2026-06-07",
            "checks": [
                {
                    "key": "outputs",
                    "status": "block",
                    "title": "交易輸出日期不同步",
                    "message": "summary、daily_brief 或 universe_report 的資料日不一致。",
                    "details": {"last_data_as_of": "2026-06-07"},
                    "next_action": "python3 scripts/run_signals.py",
                    "action_payload": {
                        "kind": "command",
                        "command": "python3 scripts/run_signals.py",
                        "copy_command": "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/run_signals.py",
                    },
                },
            ],
        },
        limit=1,
        universe=[],
    )

    monkeypatch.setattr(svc, "date", FakeDate)
    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-06-07",
        "raw_ohlcv_as_of": "2026-06-07",
        "outputs_lag_raw_data": False,
        "is_stale": False,
        "stale_days": 0,
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        **daily_summary,
        "snapshot_is_stale": False,
    })

    report = svc.get_update_workflow_status()

    daily_payload = daily_summary["top_actions"][0]["action_payload"]
    assert report["overall_status"] == "blocked"
    assert report["next_action"]["command"] == daily_payload["command"]
    assert report["next_action"]["copy_command"] == daily_payload["copy_command"]
    assert report["next_action"]["expected_outputs"] == daily_payload["expected_outputs"]


def test_update_workflow_preserves_daily_check_action_payload(monkeypatch):
    import app.services.update_workflow_service as svc

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    monkeypatch.setattr(svc, "date", FakeDate)
    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-06-07",
        "raw_ohlcv_as_of": "2026-06-07",
        "outputs_lag_raw_data": False,
        "is_stale": False,
        "stale_days": 0,
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "generated_at": "2026-06-07",
        "data_as_of": "2026-06-07",
        "snapshot_is_stale": False,
        "can_use_trade_outputs": False,
        "top_actions": [
            {
                "key": "manual_market_note",
                "status": "block",
                "title": "更新人工盤後筆記",
                "message": "人工筆記阻塞今日交易輸出。",
                "next_action": "POST /api/stocks/market-notes",
                "action_payload": {
                    "kind": "api",
                    "method": "POST",
                    "endpoint": "/api/stocks/market-notes",
                    "confirm_message": "只更新盤後筆記，不改交易紀錄。",
                },
            }
        ],
    })

    report = svc.get_update_workflow_status()

    assert report["overall_status"] == "blocked"
    assert report["next_action"]["key"] == "manual_market_note"
    assert report["next_action"]["action_payload"] == {
        "kind": "api",
        "method": "POST",
        "endpoint": "/api/stocks/market-notes",
        "confirm_message": "只更新盤後筆記，不改交易紀錄。",
    }


def test_update_workflow_converts_daily_check_file_blocker_to_safe_copy_command(monkeypatch):
    import app.services.update_workflow_service as svc

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    monkeypatch.setattr(svc, "date", FakeDate)
    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-06-07",
        "raw_ohlcv_as_of": "2026-06-07",
        "outputs_lag_raw_data": False,
        "is_stale": False,
        "stale_days": 0,
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "generated_at": "2026-06-07",
        "data_as_of": "2026-06-07",
        "snapshot_is_stale": False,
        "can_use_trade_outputs": False,
        "top_actions": [
            {
                "key": "signal_alerts",
                "status": "block",
                "title": "隔日訊號警示",
                "message": "偵測到 4 筆 block 警示。",
                "next_action": "查看 backend/out/signal_alerts.json 並先處理 block / warn 項目。",
                "action_payload": {
                    "kind": "file",
                    "file_path": "backend/out/signal_alerts.json",
                    "preview_items": ["2330 台積電：隔日動作變更"],
                },
            }
        ],
    })

    report = svc.get_update_workflow_status()

    assert report["overall_status"] == "blocked"
    assert report["next_action"]["key"] == "signal_alerts"
    assert report["next_action"]["command"] == "cat backend/out/signal_alerts.json"
    assert report["next_action"]["copy_command"].endswith(
        "backend\ncat backend/out/signal_alerts.json"
    )
    assert report["next_action"]["action_payload"]["kind"] == "file"
    assert report["next_action"]["action_payload"]["file_path"] == "backend/out/signal_alerts.json"


def test_update_workflow_headline_summarizes_signal_alert_blocker(monkeypatch):
    import app.services.update_workflow_service as svc

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    monkeypatch.setattr(svc, "date", FakeDate)
    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-06-07",
        "raw_ohlcv_as_of": "2026-06-07",
        "outputs_lag_raw_data": False,
        "is_stale": False,
        "stale_days": 0,
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "generated_at": "2026-06-07",
        "data_as_of": "2026-06-07",
        "snapshot_is_stale": False,
        "can_use_trade_outputs": False,
        "top_actions": [
            {
                "key": "signal_alerts",
                "status": "block",
                "title": "訊號快照變化警示",
                "message": "偵測到 26 筆訊號快照變化警示。",
                "details": {
                    "alert_count": 26,
                    "block_count": 10,
                    "warn_count": 15,
                    "info_count": 1,
                },
                "action_payload": {
                    "kind": "file",
                    "file_path": "backend/out/signal_alerts.json",
                    "preview_items": ["2301 光寶科：持股/候選轉風險｜先復盤風險"],
                },
            }
        ],
    })

    report = svc.get_update_workflow_status()

    assert report["overall_status"] == "blocked"
    assert report["current_step"] == "resolve_daily_check_blocker"
    assert "訊號快照變化警示" in report["headline"]
    assert "26 筆" in report["headline"]
    assert "10 block" in report["headline"]
    assert "15 warn" in report["headline"]
    assert report["next_action"]["action_payload"]["preview_items"] == [
        "2301 光寶科：持股/候選轉風險｜先復盤風險"
    ]


def test_update_workflow_exposes_schedule_health_in_checks(monkeypatch):
    import app.services.update_workflow_service as svc

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-06-07",
        "raw_ohlcv_as_of": "2026-06-07",
        "outputs_lag_raw_data": False,
        "is_stale": False,
        "stale_days": 0,
        "schedule_health_status": "overdue",
        "schedule_is_overdue": True,
        "schedule_health_message": "自最近一次完成後已錯過 1 個平日更新。",
        "manual_update_action": {
            "action_type": "copy_command",
            "command": "python3 scripts/daily_update.py --months 1",
            "copy_command": "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/daily_update.py --months 1",
            "expected_outputs": ["backend/out/update_status.json"],
        },
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "generated_at": "2026-06-07",
        "data_as_of": "2026-06-07",
        "snapshot_is_stale": False,
        "can_use_trade_outputs": True,
    })

    report = svc.get_update_workflow_status()

    assert report["checks"]["schedule_health_status"] == "overdue"
    assert report["checks"]["schedule_is_overdue"] is True
    assert "錯過 1 個平日更新" in report["checks"]["schedule_health_message"]
    assert report["checks"]["manual_update_action"]["command"] == "python3 scripts/daily_update.py --months 1"


def test_update_workflow_surfaces_partial_data_freshness_warning(monkeypatch):
    import app.services.update_workflow_service as svc
    from app.services.workflow_outputs import DAILY_UPDATE_OUTPUTS

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-06-30",
        "raw_ohlcv_as_of": "2026-06-30",
        "outputs_lag_raw_data": False,
        "is_stale": False,
        "stale_days": 0,
        "schedule_health_status": "ok",
        "schedule_is_overdue": False,
        "schedule_health_message": "最近一次更新正常完成。",
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "generated_at": "2026-07-01",
        "data_as_of": "2026-06-30",
        "snapshot_is_stale": False,
        "can_use_trade_outputs": True,
        "top_actions": [
            {
                "key": "data_freshness",
                "status": "warn",
                "title": "追蹤股票資料日落後",
                "message": "有 9 檔股票資料日落後，目標資料日為 2026-06-30。",
                "next_action": "python3 scripts/daily_update.py --months 1",
                "details": {
                    "expected_as_of": "2026-06-30",
                    "stale_count": 9,
                    "missing_date_count": 0,
                    "top_stale_items": [
                        {"code": "2492", "name": "華新科", "data_as_of": "2026-06-26"},
                    ],
                },
                "action_payload": {
                    "kind": "command",
                    "command": "python3 scripts/daily_update.py --months 1",
                    "copy_command": "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/daily_update.py --months 1",
                    "expected_outputs": DAILY_UPDATE_OUTPUTS,
                    "preview_items": ["2492 華新科 仍停在 2026-06-26"],
                },
            }
        ],
    })

    report = svc.get_update_workflow_status()

    assert report["overall_status"] == "action_required"
    assert report["can_use_trade_outputs"] is True
    assert report["current_step"] == "repair_partial_data_freshness"
    assert report["next_action"]["key"] == "data_freshness"
    assert report["next_action"]["command"] == "python3 scripts/daily_update.py --months 1"
    assert report["next_action"]["expected_outputs"] == DAILY_UPDATE_OUTPUTS
    assert report["steps"][0]["status"] == "warning"
    assert report["checks"]["partial_stale_count"] == 9
    assert report["checks"]["partial_missing_date_count"] == 0
    assert report["checks"]["partial_data_freshness_items"][0]["code"] == "2492"


def test_update_workflow_api_returns_schema(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "get_update_workflow_status", lambda: {
        "generated_at": "2026-06-07",
        "overall_status": "ready",
        "headline": "每日更新流程完成，可以使用最新交易輸出。",
        "can_use_trade_outputs": True,
        "current_step": "ready",
        "next_action": None,
        "steps": [
            {
                "key": "update_market_data",
                "label": "更新資料",
                "status": "done",
                "message": "資料已同步。",
                "command": "python3 scripts/daily_update.py --months 1",
            },
        ],
        "checks": {"data_as_of": "2026-06-07"},
    })

    response = client.get("/api/system/update-workflow")

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "ready"
    assert body["steps"][0]["key"] == "update_market_data"


def test_update_workflow_api_keeps_next_action_payload(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "get_update_workflow_status", lambda: {
        "generated_at": "2026-06-07",
        "overall_status": "blocked",
        "headline": "Daily Check 判斷交易輸出不可使用，需先處理阻塞。",
        "can_use_trade_outputs": False,
        "current_step": "resolve_daily_check_blocker",
        "next_action": {
            "key": "manual_market_note",
            "title": "更新人工盤後筆記",
            "detail": "人工筆記阻塞今日交易輸出。",
            "action_type": "copy_command",
            "command": "POST /api/stocks/market-notes",
            "copy_command": None,
            "expected_outputs": [],
            "action_payload": {
                "kind": "api",
                "method": "POST",
                "endpoint": "/api/stocks/market-notes",
                "confirm_message": "只更新盤後筆記，不改交易紀錄。",
            },
        },
        "steps": [
            {
                "key": "refresh_daily_check",
                "label": "刷新 PM 摘要",
                "status": "blocked",
                "message": "Daily Check 快照已是今天。",
                "command": "python3 scripts/daily_check.py --write-report",
            },
        ],
        "checks": {"data_as_of": "2026-06-07"},
    })

    response = client.get("/api/system/update-workflow")

    assert response.status_code == 200
    body = response.json()
    assert body["next_action"]["action_payload"] == {
        "kind": "api",
        "method": "POST",
        "endpoint": "/api/stocks/market-notes",
        "confirm_message": "只更新盤後筆記，不改交易紀錄。",
    }
