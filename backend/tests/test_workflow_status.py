"""
workflow_status 測試

PM 視角：Dashboard 不只顯示檔案狀態，也要能告訴使用者目前卡在哪、
下一步該先做什麼。
"""


def test_workflow_status_prioritizes_stale_data(client, monkeypatch):
    import app.services.workflow_service as svc
    from app.services.workflow_outputs import DAILY_UPDATE_OUTPUTS

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-19",
        "is_stale": True,
        "stale_days": 3,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "idle",
        "run_error": None,
        "manual_note_status": None,
        "out_files": {
            "summary_json": {"exists": True, "parse_error": None},
            "universe_report_csv": {"exists": True},
            "daily_brief_json": {"exists": True, "update_required": False, "parse_error": None},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 10,
        "complete_count": 10,
        "coverage_pct": 100.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    body = client.get("/api/system/workflow-status").json()

    assert body["overall_status"] == "blocked"
    assert body["can_trade_today"] is False
    assert body["next_actions"][0]["key"] == "update_data"
    assert body["next_actions"][0]["action_type"] == "update_data"
    assert body["next_actions"][0]["success_check"] == "確認 data_as_of 更新到最新交易日，且 summary.json / universe_report.csv / daily_brief.json 都已重新產生。"
    assert body["next_actions"][0]["expected_outputs"] == DAILY_UPDATE_OUTPUTS
    assert body["next_actions"][0]["action_payload"] == {
        "kind": "command",
        "command": "python3 scripts/daily_update.py --months 1",
        "copy_command": body["next_actions"][0]["copy_command"],
        "expected_outputs": body["next_actions"][0]["expected_outputs"],
    }
    assert body["decision_guardrails"]["can_use_trade_outputs"] is False
    assert "daily_brief" in body["decision_guardrails"]["blocked_outputs"]
    assert "universe_report" in body["decision_guardrails"]["blocked_outputs"]
    assert "technical_signals" in body["decision_guardrails"]["blocked_outputs"]
    assert "資料最新日 2026-05-19" in body["decision_guardrails"]["message"]
    assert body["decision_guardrails"]["required_action_expected_outputs"] == DAILY_UPDATE_OUTPUTS
    assert body["decision_guardrails"]["action_payload"] == {
        "kind": "command",
        "command": "python3 scripts/daily_update.py --months 1",
        "copy_command": body["decision_guardrails"]["required_action_copy_command"],
        "expected_outputs": body["decision_guardrails"]["required_action_expected_outputs"],
    }
    assert body["readiness_review"]["overall_label"] == "需先處理阻塞"
    assert body["readiness_review"]["top_blocker_key"] == "data"
    assert body["readiness_review"]["sections"][0] == {
        "key": "data",
        "label": "資料日",
        "status": "blocked",
        "message": "資料最新日 2026-05-19，已落後 3 天。",
        "next_action_key": "update_data",
    }


def test_workflow_status_treats_stalled_update_as_blocker(client, monkeypatch):
    import app.services.workflow_service as svc

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "stalled",
        "last_run_started_at": "2026-06-25T00:00:00",
        "last_data_as_of": "2026-06-24",
        "is_stale": False,
        "stale_days": 1,
        "last_error_summary": "資料更新執行超過 2 小時，可能已中斷",
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "idle",
        "run_error": None,
        "manual_note_status": None,
        "out_files": {
            "summary_json": {"exists": True, "parse_error": None},
            "universe_report_csv": {"exists": True},
            "daily_brief_json": {"exists": True, "update_required": False, "parse_error": None},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 10,
        "complete_count": 10,
        "coverage_pct": 100.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    body = client.get("/api/system/workflow-status").json()

    assert body["overall_status"] == "blocked"
    assert body["can_trade_today"] is False
    assert body["next_actions"][0]["key"] == "restart_stalled_update"
    assert body["next_actions"][0]["title"] == "資料更新可能卡住，重新啟動"
    assert body["next_actions"][0]["severity"] == "danger"


def test_workflow_status_flags_missing_reports(client, monkeypatch):
    import app.services.workflow_service as svc
    from app.services.workflow_outputs import SIGNAL_OUTPUTS

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-22",
        "is_stale": False,
        "stale_days": 0,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "idle",
        "run_error": None,
        "manual_note_status": None,
        "out_files": {
            "summary_json": {"exists": False},
            "universe_report_csv": {"exists": False},
            "daily_brief_json": {"exists": False},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 10,
        "complete_count": 10,
        "coverage_pct": 100.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    body = client.get("/api/system/workflow-status").json()

    assert body["overall_status"] == "blocked"
    assert body["next_actions"][0]["key"] == "run_signals"
    assert body["next_actions"][0]["action_type"] == "run_signals"
    assert body["next_actions"][0]["success_check"] == "確認 summary.json、universe_report.csv、daily_brief.json 都存在且可解析。"
    assert body["next_actions"][0]["expected_outputs"] == SIGNAL_OUTPUTS
    assert body["readiness_review"]["top_blocker_key"] == "reports"
    assert body["readiness_review"]["sections"][1]["status"] == "blocked"
    assert body["readiness_review"]["sections"][1]["next_action_key"] == "run_signals"


def test_workflow_status_blocks_when_output_dates_lag_data(client, monkeypatch):
    import app.services.workflow_service as svc
    from app.services.workflow_outputs import SIGNAL_OUTPUTS

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-29",
        "is_stale": False,
        "stale_days": 0,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "idle",
        "run_error": None,
        "manual_note_status": None,
        "out_files": {
            "summary_json": {"exists": True, "parse_error": None, "as_of": "2026-05-28"},
            "universe_report_csv": {"exists": True, "as_of": "2026-05-28"},
            "daily_brief_json": {"exists": True, "update_required": False, "parse_error": None, "as_of": "2026-05-29"},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 10,
        "complete_count": 10,
        "coverage_pct": 100.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    body = client.get("/api/system/workflow-status").json()

    assert body["overall_status"] == "blocked"
    assert body["can_trade_today"] is False
    assert body["next_actions"][0]["key"] == "refresh_outputs"
    assert body["next_actions"][0]["command"] == "python3 scripts/run_signals.py"
    assert body["next_actions"][0]["copy_command"].endswith(
        "backend\npython3 scripts/run_signals.py"
    )
    assert body["decision_guardrails"]["can_use_trade_outputs"] is False
    assert body["decision_guardrails"]["required_action_copy_command"].endswith(
        "backend\npython3 scripts/run_signals.py"
    )
    assert body["decision_guardrails"]["required_action_expected_outputs"] == SIGNAL_OUTPUTS
    assert body["decision_guardrails"]["action_payload"] == {
        "kind": "command",
        "command": "python3 scripts/run_signals.py",
        "copy_command": body["decision_guardrails"]["required_action_copy_command"],
        "expected_outputs": body["decision_guardrails"]["required_action_expected_outputs"],
    }
    assert "日期與資料日不一致" in body["decision_guardrails"]["message"]
    assert body["readiness_review"]["top_blocker_key"] == "output_freshness"
    assert body["checks"]["output_freshness"]["status"] == "blocked"
    assert body["checks"]["output_freshness"]["expected_as_of"] == "2026-05-29"


def test_workflow_status_blocks_when_raw_ohlcv_is_newer_than_outputs(client, monkeypatch):
    import app.services.workflow_service as svc

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-28",
        "raw_ohlcv_as_of": "2026-05-29",
        "outputs_lag_raw_data": True,
        "raw_data_warning": "ohlcv.csv 已更新到 2026-05-29，但交易輸出仍停在 2026-05-28；請重新產生訊號與報表。",
        "is_stale": False,
        "stale_days": 0,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "idle",
        "run_error": None,
        "manual_note_status": None,
        "out_files": {
            "summary_json": {"exists": True, "parse_error": None, "as_of": "2026-05-28"},
            "universe_report_csv": {"exists": True, "as_of": "2026-05-28"},
            "daily_brief_json": {"exists": True, "update_required": False, "parse_error": None, "as_of": "2026-05-28"},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 10,
        "complete_count": 10,
        "coverage_pct": 100.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    body = client.get("/api/system/workflow-status").json()

    assert body["overall_status"] == "blocked"
    assert body["can_trade_today"] is False
    assert body["next_actions"][0]["key"] == "run_signals_for_raw_data"
    assert body["next_actions"][0]["copy_command"].endswith(
        "backend\npython3 scripts/run_signals.py"
    )
    assert body["decision_guardrails"]["can_use_trade_outputs"] is False
    assert "ohlcv.csv 已更新到 2026-05-29" in body["decision_guardrails"]["message"]
    assert body["readiness_review"]["top_blocker_key"] == "raw_outputs"


def test_workflow_status_blocks_when_universe_report_parse_fails(client, monkeypatch):
    import app.services.workflow_service as svc

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-29",
        "is_stale": False,
        "stale_days": 0,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "idle",
        "run_error": None,
        "manual_note_status": None,
        "out_files": {
            "summary_json": {"exists": True, "parse_error": None, "as_of": "2026-05-29"},
            "universe_report_csv": {"exists": True, "parse_error": "CSV 欄位解析失敗", "as_of": None},
            "daily_brief_json": {"exists": True, "update_required": False, "parse_error": None, "as_of": "2026-05-29"},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 10,
        "complete_count": 10,
        "coverage_pct": 100.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    body = client.get("/api/system/workflow-status").json()

    assert body["overall_status"] == "blocked"
    assert body["can_trade_today"] is False
    assert body["next_actions"][0]["key"] == "fix_universe_report_csv"
    assert body["decision_guardrails"]["can_use_trade_outputs"] is False
    assert body["decision_guardrails"]["required_action"] == "python3 scripts/run_signals.py"
    assert body["decision_guardrails"]["required_action_copy_command"].endswith(
        "backend\npython3 scripts/run_signals.py"
    )
    assert body["checks"]["signals"]["reports_ready"] is False


def test_workflow_status_ready_with_fundamentals_warning(client, monkeypatch):
    import app.services.workflow_service as svc

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-22",
        "is_stale": False,
        "stale_days": 0,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "success",
        "run_error": None,
        "manual_note_status": {"update_required": False},
        "out_files": {
            "summary_json": {"exists": True, "parse_error": None},
            "universe_report_csv": {"exists": True},
            "daily_brief_json": {"exists": True, "update_required": False, "parse_error": None},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 20,
        "complete_count": 8,
        "coverage_pct": 40.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    body = client.get("/api/system/workflow-status").json()

    assert body["overall_status"] == "warning"
    assert body["can_trade_today"] is True
    assert any(action["key"] == "fill_fundamentals" for action in body["next_actions"])
    assert body["decision_guardrails"]["can_use_trade_outputs"] is True
    assert body["decision_guardrails"]["blocked_outputs"] == []


def test_workflow_status_promotes_ready_fundamentals_merge_action(client, monkeypatch):
    import app.services.workflow_service as svc

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-22",
        "is_stale": False,
        "stale_days": 0,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "success",
        "run_error": None,
        "manual_note_status": {"update_required": False},
        "out_files": {
            "summary_json": {"exists": True, "parse_error": None},
            "universe_report_csv": {"exists": True},
            "daily_brief_json": {"exists": True, "update_required": False, "parse_error": None},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 20,
        "complete_count": 8,
        "coverage_pct": 40.0,
        "priority_fill_readiness": {
            "status": "ready_to_merge",
            "can_merge": True,
            "complete_code_count": 2,
            "suggested_action": "先按預覽合併，確認更新檔數與欄位數後再合併匯入。",
        },
        "priority_fill_guide": {
            "next_action_label": "可先預覽合併 2 檔",
        },
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    body = client.get("/api/system/workflow-status").json()

    action = next(item for item in body["next_actions"] if item["key"] == "merge_fundamentals")
    assert action["title"] == "合併基本面避雷補資料"
    assert "2 檔" in action["detail"]
    assert action["command"] == "POST /api/system/fundamentals-priority-fill/merge"
    assert action["action_payload"] == {
        "kind": "api",
        "method": "POST",
        "endpoint": "/api/system/fundamentals-priority-fill/merge",
    }
    assert body["checks"]["fundamentals"]["priority_fill_status"] == "ready_to_merge"


def test_workflow_status_prioritizes_invalid_fundamentals_priority_csv(client, monkeypatch):
    import app.services.workflow_service as svc

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-22",
        "is_stale": False,
        "stale_days": 0,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "success",
        "run_error": None,
        "manual_note_status": {"update_required": False},
        "out_files": {
            "summary_json": {"exists": True, "parse_error": None},
            "universe_report_csv": {"exists": True},
            "daily_brief_json": {"exists": True, "update_required": False, "parse_error": None},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 20,
        "complete_count": 8,
        "coverage_pct": 40.0,
        "priority_fill_readiness": {
            "status": "invalid",
            "can_merge": False,
            "suggested_action": "先修正 CSV 內的錯誤值、空白代號或重複代號，再重新預覽。",
        },
        "priority_csv_validation": {
            "valid": False,
            "errors": [{
                "row_number": 3,
                "code": "2408",
                "field": "roe_5y_avg",
                "value": "abc",
                "message": "必須是數字",
            }],
            "warnings": [],
        },
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    body = client.get("/api/system/workflow-status").json()

    action = next(item for item in body["next_actions"] if item["key"] == "fix_fundamentals_csv")
    assert action["severity"] == "danger"
    assert "第 3 列" in action["detail"]
    assert "2408" in action["detail"]
    assert body["checks"]["fundamentals"]["priority_fill_error_count"] == 1


def test_workflow_status_includes_close_checklist(client, monkeypatch):
    import app.services.workflow_service as svc

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-22",
        "is_stale": False,
        "stale_days": 0,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "success",
        "run_error": None,
        "manual_note_status": {"update_required": False},
        "out_files": {
            "summary_json": {"exists": True, "parse_error": None},
            "universe_report_csv": {"exists": True},
            "daily_brief_json": {"exists": True, "update_required": False, "parse_error": None},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 20,
        "complete_count": 20,
        "coverage_pct": 100.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    body = client.get("/api/system/workflow-status").json()
    checklist = body["close_checklist"]

    assert [item["key"] for item in checklist] == [
        "update_data",
        "market_note",
        "run_signals",
        "daily_brief",
        "universe_report",
        "portfolio_risk",
    ]
    assert all(item["status"] == "done" for item in checklist)
    assert checklist[-1]["action_type"] == "portfolio"


def test_workflow_status_close_checklist_marks_blocked_steps(client, monkeypatch):
    import app.services.workflow_service as svc

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-19",
        "is_stale": True,
        "stale_days": 3,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "idle",
        "run_error": None,
        "manual_note_status": {"update_required": True},
        "out_files": {
            "summary_json": {"exists": False},
            "universe_report_csv": {"exists": False},
            "daily_brief_json": {"exists": False},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 20,
        "complete_count": 20,
        "coverage_pct": 100.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    body = client.get("/api/system/workflow-status").json()
    by_key = {item["key"]: item for item in body["close_checklist"]}

    assert by_key["update_data"]["status"] == "todo"
    assert by_key["market_note"]["status"] == "todo"
    assert by_key["run_signals"]["status"] == "todo"
    assert by_key["daily_brief"]["status"] == "blocked"
    assert by_key["universe_report"]["status"] == "blocked"
    assert by_key["portfolio_risk"]["status"] == "blocked"


def test_workflow_status_builds_portfolio_tasks_from_held_report_rows(client, monkeypatch):
    import app.services.workflow_service as svc

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-22",
        "is_stale": False,
        "stale_days": 0,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "success",
        "run_error": None,
        "manual_note_status": {"update_required": False},
        "out_files": {
            "summary_json": {"exists": True, "parse_error": None},
            "universe_report_csv": {"exists": True},
            "daily_brief_json": {"exists": True, "update_required": False, "parse_error": None},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 20,
        "complete_count": 20,
        "coverage_pct": 100.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [
        {
            "code": "2337",
            "name": "旺宏",
            "holding_shares": 1000,
            "holding_position_pct": 18.2,
            "daily_action": "exit",
            "daily_action_label": "出場處理",
            "daily_action_reason": "跌破 MA10",
            "daily_key_price": "MA10 175",
            "daily_invalidation": "重新站回 MA20",
            "daily_priority": 100,
        },
        {
            "code": "2408",
            "name": "南亞科",
            "holding_shares": 500,
            "holding_position_pct": 12.5,
            "daily_action": "hold",
            "daily_action_label": "續抱",
            "daily_action_reason": "守住缺口",
            "daily_key_price": "缺口 330",
            "daily_invalidation": "跌破缺口",
            "daily_priority": 70,
        },
        {
            "code": "2330",
            "name": "台積電",
            "holding_shares": 0,
            "daily_action": "enter",
            "daily_priority": 90,
        },
    ])

    body = client.get("/api/system/workflow-status").json()
    tasks = body["portfolio_tasks"]

    assert [task["code"] for task in tasks] == ["2337", "2408"]
    assert tasks[0]["severity"] == "danger"
    assert tasks[0]["action"] == "exit"
    assert tasks[0]["key_price"] == "MA10 175"
    assert tasks[1]["severity"] == "success"


def test_workflow_status_exposes_pm_metrics(client, monkeypatch):
    import app.services.workflow_service as svc

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-22",
        "is_stale": False,
        "stale_days": 0,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "success",
        "run_error": None,
        "manual_note_status": {"update_required": True, "stale_reason": "筆記過期"},
        "out_files": {
            "summary_json": {"exists": True, "parse_error": None},
            "universe_report_csv": {"exists": True},
            "daily_brief_json": {"exists": True, "update_required": False, "parse_error": None},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 20,
        "complete_count": 18,
        "coverage_pct": 90.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [
        {
            "code": "2337",
            "name": "旺宏",
            "holding_shares": 1000,
            "daily_action": "reduce",
            "daily_action_label": "減碼觀察",
            "daily_priority": 95,
        },
        {
            "code": "2408",
            "name": "南亞科",
            "holding_shares": 500,
            "daily_action": "hold",
            "daily_action_label": "續抱",
            "daily_priority": 70,
        },
    ])

    body = client.get("/api/system/workflow-status").json()
    metrics = body["workflow_metrics"]

    assert metrics["blocker_count"] == 0
    assert metrics["warning_count"] == 2
    assert metrics["todo_step_count"] == 1
    assert metrics["done_step_count"] == 5
    assert metrics["portfolio_task_count"] == 2
    assert metrics["portfolio_danger_count"] == 1


def test_workflow_status_tracks_decision_journal_coverage_for_portfolio_tasks(client, monkeypatch):
    import app.services.workflow_service as svc
    from app.models.decision_journal import DecisionJournalEntry

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-22",
        "is_stale": False,
        "stale_days": 0,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "success",
        "run_error": None,
        "manual_note_status": {"update_required": False},
        "out_files": {
            "summary_json": {"exists": True, "parse_error": None},
            "universe_report_csv": {"exists": True},
            "daily_brief_json": {"exists": True, "update_required": False, "parse_error": None},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 20,
        "complete_count": 20,
        "coverage_pct": 100.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [
        {
            "code": "2337",
            "name": "旺宏",
            "holding_shares": 1000,
            "daily_action": "reduce",
            "daily_action_label": "減碼觀察",
            "daily_priority": 95,
        },
        {
            "code": "2408",
            "name": "南亞科",
            "holding_shares": 500,
            "daily_action": "hold",
            "daily_action_label": "續抱",
            "daily_priority": 70,
        },
    ])
    monkeypatch.setattr(svc, "load_decision_journal", lambda: [
        DecisionJournalEntry(
            id="j1",
            date="2026-05-22",
            code="2337",
            name="旺宏",
            decision="reduce",
            reason="跌破短均，先減碼。",
            created_at="2026-05-22T15:30:00",
        ),
        DecisionJournalEntry(
            id="old",
            date="2026-05-21",
            code="2408",
            name="南亞科",
            decision="hold",
            reason="昨日續抱。",
            created_at="2026-05-21T15:30:00",
        ),
    ])

    body = client.get("/api/system/workflow-status").json()
    metrics = body["workflow_metrics"]

    assert metrics["decision_journal_today_count"] == 1
    assert metrics["portfolio_tasks_without_journal_count"] == 1
    assert body["checks"]["decision_journal"]["missing_portfolio_codes"] == ["2408"]
    task_by_code = {task["code"]: task for task in body["portfolio_tasks"]}
    assert task_by_code["2337"]["journal_recorded"] is True
    assert task_by_code["2408"]["journal_recorded"] is False
    assert any(action["key"] == "record_decisions" for action in body["next_actions"])


def test_workflow_status_tracks_universe_report_journal_coverage(client, monkeypatch):
    import app.services.workflow_service as svc
    from app.models.decision_journal import DecisionJournalEntry

    monkeypatch.setattr(svc, "get_data_status", lambda: {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-27",
        "is_stale": False,
        "stale_days": 0,
        "last_error_summary": None,
    })
    monkeypatch.setattr(svc, "get_signals_status", lambda: {
        "run_status": "success",
        "run_error": None,
        "manual_note_status": {"update_required": False},
        "out_files": {
            "summary_json": {"exists": True, "as_of": "2026-05-27", "parse_error": None},
            "universe_report_csv": {"exists": True, "as_of": "2026-05-27", "parse_error": None},
            "daily_brief_json": {"exists": True, "as_of": "2026-05-27", "update_required": False, "parse_error": None},
        },
    })
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "total_codes": 20,
        "complete_count": 20,
        "coverage_pct": 100.0,
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [
        {
            "code": "2344",
            "name": "華邦電",
            "holding_shares": 0,
            "daily_action": "enter",
            "daily_action_label": "可小試",
            "daily_priority": 90,
        },
        {
            "code": "2408",
            "name": "南亞科",
            "holding_shares": 0,
            "daily_action": "wait_pullback",
            "daily_action_label": "等回測",
            "daily_action_reason": "守住月線後等回測。",
            "daily_key_price": "MA10 302.5",
            "daily_invalidation": "跌破 MA20",
            "daily_priority": 82,
        },
        {
            "code": "2337",
            "name": "旺宏",
            "holding_shares": 0,
            "daily_action": "exit",
            "daily_action_label": "出場處理",
            "daily_action_reason": "跌破關鍵支撐。",
            "daily_key_price": "停損 29.5",
            "daily_invalidation": "重新站回 MA20",
            "daily_priority": 40,
        },
        {
            "code": "2330",
            "name": "台積電",
            "holding_shares": 0,
            "daily_action": "long_watch",
            "daily_action_label": "長期觀察",
            "daily_priority": 55,
        },
    ])
    monkeypatch.setattr(svc, "load_decision_journal", lambda: [
        DecisionJournalEntry(
            id="j1",
            date="2026-05-27",
            code="2344",
            name="華邦電",
            decision="buy",
            reason="候選股報表可小試。",
            source="universe_report",
            created_at="2026-05-27T15:30:00",
        ),
        DecisionJournalEntry(
            id="manual",
            date="2026-05-27",
            code="2408",
            name="南亞科",
            decision="watch",
            reason="手動筆記，不算報表紀錄。",
            source="manual",
            created_at="2026-05-27T15:31:00",
        ),
    ])

    body = client.get("/api/system/workflow-status").json()
    metrics = body["workflow_metrics"]
    coverage = body["checks"]["universe_report_journal"]

    assert metrics["universe_actionable_count"] == 3
    assert metrics["universe_actionable_without_journal_count"] == 2
    assert coverage["recorded_actionable_codes"] == ["2344"]
    assert coverage["missing_actionable_codes"] == ["2337", "2408"]
    assert coverage["missing_actionable_items"][0]["code"] == "2337"
    assert coverage["missing_actionable_items"][0]["label"] == "出場處理"
    assert coverage["missing_actionable_items"][1]["code"] == "2408"
    assert coverage["missing_actionable_items"][1]["key_price"] == "MA10 302.5"
    assert coverage["today_universe_report_count"] == 1
    assert any(action["key"] == "record_report_decisions" for action in body["next_actions"])
