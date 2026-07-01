def test_pm_worklist_prioritizes_data_repair_before_followup_work(monkeypatch):
    import app.services.pm_worklist_service as svc

    monkeypatch.setattr(svc, "get_update_workflow_status", lambda: {
        "overall_status": "ready",
        "headline": "每日更新流程完成，可以使用最新交易輸出。",
        "can_use_trade_outputs": True,
        "current_step": "ready",
        "next_action": None,
        "checks": {},
    })
    monkeypatch.setattr(svc, "get_universe", lambda: [
        {"code": "2330", "name": "台積電", "data_status": "ok", "row_count": 243},
        {"code": "9999", "name": "缺資料", "data_status": "no_data", "row_count": 0},
    ])
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "workflow_summary": {
            "stage": "fill_priority_csv",
            "headline": "開始填基本面避雷優先補資料 CSV",
            "detail": "補資料 CSV 已產生，但尚未填入基本面欄位。",
            "coverage_label": "0/74 完整",
            "primary_action": {"label": "填寫 CSV", "command": "/backend/out/fundamentals_priority_fill.csv", "kind": "file"},
            "fill_targets_copy_text": "\n".join([
                "基本面避雷優先補資料清單",
                "1. 南亞科 2408 - 目前推薦/觀察名單，缺 2 欄",
                "   - 5 年平均 ROE (roe_5y_avg，範例 28.5)",
                "   - 本益比 (pe，範例 22.5)",
            ]),
            "focus_targets": [{
                "code": "2408",
                "name": "南亞科",
                "missing_count": 2,
                "missing_fields": ["roe_5y_avg", "pe"],
                "missing_field_labels": ["5 年平均 ROE", "本益比"],
                "priority_reason": "目前推薦/觀察名單",
            }],
        }
    })
    monkeypatch.setattr(svc, "build_universe_report_review_workflow_summary", lambda limit=10: {
        "stage": "review_candidates",
        "headline": "補候選股復盤紀錄",
        "detail": "有 43 檔尚未復盤。",
        "progress_label": "0/43 已復盤",
        "missing_count": 43,
        "primary_action": {"label": "批次記錄前 10 檔", "command": "POST /api/decision-journal/from-universe-report", "kind": "api"},
        "top_items": [{"code": "1301", "name": "台塑"}],
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "overall_status": "warn",
        "top_actions": [
            {"key": "fundamentals", "status": "warn", "title": "基本面避雷覆蓋", "message": "0/74", "next_action": "補資料"},
        ],
    })

    worklist = svc.get_pm_worklist()

    assert worklist["overall_status"] == "action_required"
    assert worklist["headline"] == "今日 PM 工作佇列：3 件待處理"
    assert worklist["primary_action"]["key"] == "data_repair"
    assert worklist["primary_action"]["title"] == "先修復追蹤股日線資料"
    assert worklist["primary_action"]["action_payload"]["copy_command"].endswith(
        "python3 scripts/daily_update.py --months 12"
    )
    assert [item["key"] for item in worklist["items"][:3]] == [
        "data_repair",
        "fundamentals",
        "universe_report_review",
    ]
    assert worklist["items"][0]["severity"] == "danger"
    assert worklist["items"][0]["metric"] == "1 檔需修復"
    assert worklist["items"][0]["action_payload"]["kind"] == "command"
    assert worklist["items"][0]["action_payload"]["command"] == "python3 scripts/daily_update.py --months 12"
    assert worklist["items"][0]["action_payload"]["copy_command"].endswith(
        "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/daily_update.py --months 12"
    )
    assert "backend/out/daily_check.json" in worklist["items"][0]["action_payload"]["expected_outputs"]
    assert worklist["items"][1]["focus_codes"] == ["2408"]
    assert worklist["items"][1]["action_payload"]["kind"] == "copy_text"
    assert "南亞科 2408" in worklist["items"][1]["action_payload"]["copy_text"]
    assert worklist["items"][1]["action_payload"]["preview_items"] == ["南亞科 2408"]
    assert "5 年平均 ROE" in worklist["items"][1]["action_payload"]["copy_text"]
    assert "本益比" in worklist["items"][1]["action_payload"]["copy_text"]
    assert worklist["items"][1]["action_payload"]["write_template_command"] == (
        "python3 scripts/prepare_fundamentals_priority_import.py --write-template"
    )
    assert worklist["items"][1]["action_payload"]["prepare_import_command"] == (
        "python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv"
    )
    assert worklist["items"][1]["action_payload"]["prepare_import_apply_command"] == (
        "python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv --apply"
    )
    assert "backend/out/fundamentals_priority_import_template.csv" in worklist["items"][1]["action_payload"]["expected_outputs"]
    assert "backend/out/fundamentals_priority_fill.csv" in worklist["items"][1]["action_payload"]["expected_outputs"]
    assert worklist["items"][2]["metric"] == "0/43 已復盤"
    assert worklist["items"][2]["action_payload"] == {
        "kind": "api",
        "method": "POST",
        "endpoint": "/api/decision-journal/from-universe-report",
        "date": None,
        "limit": 10,
        "confirm_message": "將從候選股報表批次建立前 10 筆復盤紀錄。這只會寫入決策日誌，不會修改交易紀錄、持倉或現金。是否繼續？",
    }


def test_pm_worklist_returns_clear_state_when_no_work(monkeypatch):
    import app.services.pm_worklist_service as svc

    monkeypatch.setattr(svc, "get_update_workflow_status", lambda: {
        "overall_status": "ready",
        "headline": "每日更新流程完成，可以使用最新交易輸出。",
        "can_use_trade_outputs": True,
        "current_step": "ready",
        "next_action": None,
        "checks": {},
    })
    monkeypatch.setattr(svc, "get_universe", lambda: [])
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "workflow_summary": {
            "stage": "complete",
            "headline": "基本面避雷資料已完成",
            "detail": "ok",
            "coverage_label": "74/74 完整",
            "primary_action": {"label": "查看", "command": "", "kind": "link"},
            "focus_targets": [],
        }
    })
    monkeypatch.setattr(svc, "build_universe_report_review_workflow_summary", lambda limit=10: {
        "stage": "complete",
        "headline": "候選股復盤已完成",
        "detail": "ok",
        "progress_label": "43/43 已復盤",
        "missing_count": 0,
        "primary_action": {"label": "查看紀錄", "command": "GET /api/decision-journal", "kind": "link"},
        "top_items": [],
    })
    monkeypatch.setattr(
        svc,
        "get_daily_check_report",
        lambda: {"overall_status": "ok", "top_actions": []},
    )

    worklist = svc.get_pm_worklist()

    assert worklist["overall_status"] == "clear"
    assert worklist["headline"] == "今日 PM 工作佇列已清空"
    assert worklist["primary_action"] is None
    assert worklist["items"] == []


def test_pm_worklist_surfaces_official_coverage_when_daily_check_has_not_refreshed(monkeypatch):
    import app.services.pm_worklist_service as svc

    monkeypatch.setattr(svc, "get_update_workflow_status", lambda: {
        "overall_status": "ready",
        "headline": "每日更新流程完成，可以使用最新交易輸出。",
        "can_use_trade_outputs": True,
        "current_step": "ready",
        "next_action": None,
        "checks": {},
    })
    monkeypatch.setattr(svc, "get_universe", lambda: [])
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {"workflow_summary": {"stage": "complete"}})
    monkeypatch.setattr(svc, "build_universe_report_review_workflow_summary", lambda limit=10: {"stage": "complete"})
    monkeypatch.setattr(
        svc,
        "get_daily_check_report",
        lambda: {"overall_status": "ok", "top_actions": [], "snapshot_is_stale": True},
    )
    monkeypatch.setattr(svc, "get_official_fundamentals_coverage_audit", lambda: {
        "target_count": 2,
        "coverage_pct": 37.5,
        "available_cell_count": 6,
        "missing_report_files": ["backend/out/official_fundamentals_dividend.csv"],
        "blocked_formal_fields": ["roe_5y_avg"],
        "next_action_label": "先產生缺少的官方 report-only CSV。",
    })

    worklist = svc.get_pm_worklist()

    item = next(item for item in worklist["items"] if item["key"] == "official_fundamentals_coverage")
    assert item["severity"] == "warning"
    assert item["action_type"] == "fundamentals"
    assert item["metric"] == "37.5% 覆蓋"
    assert "official_fundamentals_dividend.csv" in item["detail"]
    assert item["action_payload"] == {
        "kind": "api",
        "method": "GET",
        "endpoint": "/api/system/fundamentals-official/coverage-audit",
        "confirm_message": "只讀取官方基本面覆蓋率稽核，不會產生報告或寫入正式基本面資料。",
    }


def test_pm_worklist_guides_when_official_coverage_priority_csv_is_missing(monkeypatch):
    import app.services.pm_worklist_service as svc

    monkeypatch.setattr(svc, "get_update_workflow_status", lambda: {
        "overall_status": "ready",
        "headline": "每日更新流程完成，可以使用最新交易輸出。",
        "can_use_trade_outputs": True,
        "current_step": "ready",
        "next_action": None,
        "checks": {},
    })
    monkeypatch.setattr(svc, "get_universe", lambda: [])
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {"workflow_summary": {"stage": "complete"}})
    monkeypatch.setattr(svc, "build_universe_report_review_workflow_summary", lambda limit=10: {"stage": "complete"})
    monkeypatch.setattr(
        svc,
        "get_daily_check_report",
        lambda: {"overall_status": "ok", "top_actions": [], "snapshot_is_stale": True},
    )
    monkeypatch.setattr(
        svc,
        "get_official_fundamentals_coverage_audit",
        lambda: (_ for _ in ()).throw(FileNotFoundError("尚無 fundamentals_priority_fill.csv")),
    )

    worklist = svc.get_pm_worklist()

    item = next(item for item in worklist["items"] if item["key"] == "official_fundamentals_coverage")
    assert item["severity"] == "warning"
    assert "fundamentals_priority_fill.csv" in item["detail"]
    assert item["action_payload"]["method"] == "GET"
    assert item["action_payload"]["endpoint"] == "/api/system/fundamentals-official/coverage-audit"


def test_pm_worklist_puts_update_workflow_blocker_first(monkeypatch):
    import app.services.pm_worklist_service as svc

    monkeypatch.setattr(svc, "get_update_workflow_status", lambda: {
        "overall_status": "blocked",
        "headline": "資料日線需要更新，交易輸出暫停使用。",
        "can_use_trade_outputs": False,
        "current_step": "update_market_data",
        "next_action": {
            "key": "update_market_data",
            "title": "先更新日線與訊號資料",
            "detail": "資料已過期或尚未建立，請先跑每日更新流程。",
            "command": "python3 scripts/daily_update.py --months 1",
            "copy_command": "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/daily_update.py --months 1",
            "action_type": "copy_command",
            "expected_outputs": [
                "backend/data/ohlcv.csv",
                "backend/out/update_status.json",
                "backend/out/data_coverage_report.json",
                "backend/out/summary.json",
                "backend/out/universe_report.csv",
                "backend/out/daily_brief.json",
                "backend/out/daily_check.json",
            ],
        },
        "checks": {"data_as_of": "2026-05-29"},
    })
    monkeypatch.setattr(svc, "get_universe", lambda: [
        {"code": "9999", "name": "缺資料", "data_status": "no_data", "row_count": 0},
    ])
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {"workflow_summary": {"stage": "complete"}})
    monkeypatch.setattr(svc, "build_universe_report_review_workflow_summary", lambda limit=10: {"stage": "complete"})
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {"overall_status": "ok", "top_actions": []})

    worklist = svc.get_pm_worklist()

    assert worklist["overall_status"] == "action_required"
    assert worklist["primary_action"]["key"] == "update_workflow"
    assert worklist["primary_action"]["severity"] == "danger"
    assert worklist["items"][0]["key"] == "update_workflow"
    assert worklist["items"][0]["severity"] == "danger"
    assert worklist["items"][0]["action_type"] == "update_workflow"
    assert worklist["items"][0]["action_payload"] == {
        "kind": "command",
        "command": "python3 scripts/daily_update.py --months 1",
        "copy_command": "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/daily_update.py --months 1",
        "current_step": "update_market_data",
        "expected_outputs": [
            "backend/data/ohlcv.csv",
            "backend/out/update_status.json",
            "backend/out/data_coverage_report.json",
            "backend/out/summary.json",
            "backend/out/universe_report.csv",
            "backend/out/daily_brief.json",
            "backend/out/daily_check.json",
        ],
    }
    assert worklist["items"][0]["command"] == "python3 scripts/daily_update.py --months 1"


def test_pm_worklist_keeps_daily_check_action_payload_when_not_duplicated(monkeypatch):
    import app.services.pm_worklist_service as svc

    monkeypatch.setattr(svc, "get_update_workflow_status", lambda: {
        "overall_status": "ready",
        "headline": "每日更新流程完成，可以使用最新交易輸出。",
        "can_use_trade_outputs": True,
        "current_step": "ready",
        "next_action": None,
        "checks": {},
    })
    monkeypatch.setattr(svc, "get_universe", lambda: [])
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {"workflow_summary": {"stage": "complete"}})
    monkeypatch.setattr(svc, "build_universe_report_review_workflow_summary", lambda limit=10: {"stage": "complete"})
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "overall_status": "warn",
        "top_actions": [
            {
                "key": "manual_market_note",
                "status": "warn",
                "title": "更新人工盤後筆記",
                "message": "筆記已過期。",
                "next_action": "POST /api/stocks/market-notes",
                "action_payload": {
                    "kind": "api",
                    "method": "POST",
                    "endpoint": "/api/stocks/market-notes",
                    "confirm_message": "只更新盤後筆記，不改正式訊號。",
                },
            },
            {
                "key": "fundamentals_priority",
                "status": "warn",
                "title": "補一批基本面資料",
                "message": "先補前兩檔。",
                "next_action": "補資料",
                "action_payload": {
                    "kind": "copy_text",
                    "copy_text": "基本面避雷優先補資料清單\n1. 聯發科 2454 - 缺 11 欄\n2. 台光電 2383 - 缺 10 欄",
                    "preview_items": ["聯發科 2454", "台光電 2383"],
                    "file_path": "/backend/out/fundamentals_priority_fill.csv",
                },
            },
        ],
    })

    worklist = svc.get_pm_worklist()

    assert [item["key"] for item in worklist["items"]] == [
        "daily_check_manual_market_note",
        "daily_check_fundamentals_priority",
    ]
    assert worklist["primary_action"]["key"] == "daily_check_manual_market_note"
    assert worklist["primary_action"]["action_payload"]["endpoint"] == "/api/stocks/market-notes"
    assert worklist["items"][0]["action_payload"] == {
        "kind": "api",
        "method": "POST",
        "endpoint": "/api/stocks/market-notes",
        "confirm_message": "只更新盤後筆記，不改正式訊號。",
    }
    assert worklist["items"][1]["action_payload"]["preview_items"] == ["聯發科 2454", "台光電 2383"]
    assert worklist["items"][1]["action_payload"]["file_path"] == "/backend/out/fundamentals_priority_fill.csv"


def test_pm_worklist_maps_daily_check_data_freshness_as_data_health(monkeypatch):
    import app.services.pm_worklist_service as svc

    monkeypatch.setattr(svc, "get_update_workflow_status", lambda: {
        "overall_status": "ready",
        "headline": "每日更新流程完成，可以使用最新交易輸出。",
        "can_use_trade_outputs": True,
        "current_step": "ready",
        "next_action": None,
        "checks": {},
    })
    monkeypatch.setattr(svc, "get_universe", lambda: [])
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {
        "workflow_summary": {
            "stage": "fill_priority_csv",
            "headline": "補基本面",
            "detail": "補資料 CSV 已產生。",
            "coverage_label": "0/76 完整",
            "primary_action": {"label": "填寫 CSV", "command": "/backend/out/fundamentals_priority_fill.csv", "kind": "file"},
            "fill_targets_copy_text": "基本面避雷優先補資料清單\n1. 聯發科 2454 - 缺 11 欄",
            "focus_targets": [{"code": "2454", "name": "聯發科"}],
        }
    })
    monkeypatch.setattr(svc, "build_universe_report_review_workflow_summary", lambda limit=10: {"stage": "complete"})
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "overall_status": "warn",
        "top_actions": [
            {
                "key": "data_freshness",
                "status": "warn",
                "title": "追蹤股票資料日落後",
                "message": "有 9 檔股票資料日落後，目標資料日為 2026-06-30。",
                "next_action": "python3 scripts/daily_update.py --months 1",
                "details": {
                    "stale_count": 9,
                    "missing_date_count": 0,
                },
                "action_payload": {
                    "kind": "command",
                    "command": "python3 scripts/daily_update.py --months 1",
                    "copy_command": "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/daily_update.py --months 1",
                    "expected_outputs": ["backend/out/summary.json", "backend/out/daily_check.json"],
                    "preview_items": [
                        "2492 華新科 仍停在 2026-06-26",
                        "5425 台半 仍停在 2026-06-29",
                    ],
                },
            },
        ],
    })

    worklist = svc.get_pm_worklist()

    assert [item["key"] for item in worklist["items"][:2]] == ["data_freshness", "fundamentals"]
    freshness = worklist["items"][0]
    assert freshness["action_type"] == "data_freshness"
    assert freshness["source"] == "daily_check"
    assert freshness["priority"] > worklist["items"][1]["priority"]
    assert freshness["action_label"] == "複製更新指令"
    assert freshness["command"] == "python3 scripts/daily_update.py --months 1"
    assert freshness["metric"] == "9 檔資料日落後"
    assert freshness["focus_codes"] == ["2492", "5425"]
    assert freshness["action_payload"]["copy_command"].endswith("python3 scripts/daily_update.py --months 1")
    assert freshness["action_payload"]["preview_items"] == [
        "2492 華新科 仍停在 2026-06-26",
        "5425 台半 仍停在 2026-06-29",
    ]


def test_pm_worklist_today_focus_surfaces_data_freshness_primary_action(monkeypatch):
    import app.services.pm_worklist_service as svc

    monkeypatch.setattr(svc, "get_update_workflow_status", lambda: {
        "overall_status": "ready",
        "headline": "每日更新流程完成，可以使用最新交易輸出。",
        "can_use_trade_outputs": True,
        "current_step": "ready",
        "next_action": None,
        "checks": {},
    })
    monkeypatch.setattr(svc, "get_universe", lambda: [])
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {"workflow_summary": {"stage": "complete"}})
    monkeypatch.setattr(svc, "build_universe_report_review_workflow_summary", lambda limit=10: {"stage": "complete", "top_items": []})
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "overall_status": "warn",
        "data_as_of": "2026-06-30",
        "top_actions": [
            {
                "key": "data_freshness",
                "status": "warn",
                "title": "追蹤股票資料日落後",
                "message": "有 2 檔股票資料日落後，目標資料日為 2026-06-30。",
                "next_action": "python3 scripts/daily_update.py --months 1",
                "action_payload": {
                    "kind": "command",
                    "command": "python3 scripts/daily_update.py --months 1",
                    "preview_items": [
                        "2492 華新科 仍停在 2026-06-26",
                        "5425 台半 仍停在 2026-06-29",
                    ],
                },
            },
        ],
    })
    monkeypatch.setattr(svc, "get_workflow_status", lambda: {
        "can_trade_today": True,
        "data_as_of": "2026-06-30",
        "portfolio_tasks": [],
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    worklist = svc.get_pm_worklist()
    focus = worklist["today_focus"]

    assert [item["code"] for item in focus[:2]] == ["2492", "5425"]
    assert all(item["category"] == "review_needed" for item in focus[:2])
    assert focus[0]["name"] == "華新科"
    assert focus[0]["label"] == "資料日落後"
    assert focus[0]["source"] == "daily_check"
    assert focus[0]["action_label"] == "複製更新指令"
    assert focus[0]["primary_metric"] == "2026-06-26"
    assert "先更新日線資料" in focus[0]["next_action"]


def test_pm_worklist_exposes_ready_today_focus_from_backend_contract(monkeypatch):
    import app.services.pm_worklist_service as svc

    monkeypatch.setattr(svc, "get_update_workflow_status", lambda: {
        "overall_status": "ready",
        "headline": "每日更新流程完成，可以使用最新交易輸出。",
        "can_use_trade_outputs": True,
        "current_step": "ready",
        "next_action": None,
        "checks": {},
    })
    monkeypatch.setattr(svc, "get_universe", lambda: [])
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {"workflow_summary": {"stage": "complete"}})
    monkeypatch.setattr(svc, "build_universe_report_review_workflow_summary", lambda limit=10: {
        "stage": "review_candidates",
        "headline": "補候選股復盤紀錄",
        "detail": "有 5 檔尚未復盤。",
        "progress_label": "0/5 已復盤",
        "missing_count": 5,
        "primary_action": {"label": "批次記錄前 5 檔", "command": "POST /api/decision-journal/from-universe-report", "kind": "api"},
        "as_of": "2026-06-10",
        "top_items": [{"code": "2454", "name": "聯發科", "daily_action_label": "可小試", "daily_action_reason": "等回測"}],
    })
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "overall_status": "ok",
        "data_as_of": "2026-06-10",
        "top_actions": [],
    })
    monkeypatch.setattr(svc, "get_workflow_status", lambda: {
        "can_trade_today": True,
        "data_as_of": "2026-06-10",
        "portfolio_tasks": [
            {
                "code": "2337",
                "name": "旺宏",
                "label": "出場處理",
                "reason": "跌破 MA10",
                "key_price": "MA10 175",
                "severity": "danger",
                "priority": 100,
            },
            {
                "code": "2408",
                "name": "南亞科",
                "label": "停利觀察",
                "reason": "接近壓力區",
                "severity": "warning",
                "priority": 90,
            },
        ],
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [
        {
            "code": "2344",
            "name": "華邦電",
            "holding_shares": 0,
            "daily_action": "enter",
            "daily_action_label": "可小試",
            "daily_action_reason": "站回 MA5，等量能確認",
            "daily_priority": 95,
            "entry_price_low": 120,
            "entry_price_high": 125,
        },
        {
            "code": "3006",
            "name": "晶豪科",
            "holding_shares": 0,
            "daily_action": "wait_pullback",
            "daily_action_label": "等回測",
            "daily_action_reason": "距 MA20 偏遠",
            "daily_priority": 80,
        },
    ])

    worklist = svc.get_pm_worklist()
    focus = worklist["today_focus"]

    assert [item["category"] for item in focus] == [
        "portfolio_risk",
        "portfolio_risk",
        "entry_candidate",
        "entry_candidate",
        "review_needed",
    ]
    assert focus[0]["code"] == "2337"
    assert focus[0]["source"] == "portfolio"
    assert focus[2]["code"] == "2344"
    assert focus[2]["source"] == "universe_report"
    assert focus[-1]["source"] == "pm_worklist"
    for item in focus:
        assert set(item) >= {
            "category",
            "code",
            "name",
            "label",
            "reason",
            "next_action",
            "severity",
            "source",
            "price_basis",
            "as_of",
            "short_reason",
            "detail_reason",
            "action_label",
            "primary_metric",
        }
        assert item["price_basis"] == "最新收盤價（非即時市價）"
        assert item["as_of"] == "2026-06-10"
    assert focus[0]["short_reason"] == "跌破 MA10"
    assert focus[0]["detail_reason"] == "跌破 MA10"
    assert focus[0]["action_label"] == "查看持股"
    assert focus[0]["primary_metric"] == "MA10 175"
    assert focus[2]["action_label"] == "查看進場計畫"
    assert focus[2]["primary_metric"] == "進場 120–125"


def test_pm_worklist_today_focus_blocks_trade_candidates_when_outputs_blocked(monkeypatch):
    import app.services.pm_worklist_service as svc

    monkeypatch.setattr(svc, "get_update_workflow_status", lambda: {
        "overall_status": "blocked",
        "headline": "資料過期，交易輸出暫停使用。",
        "can_use_trade_outputs": False,
        "current_step": "update_market_data",
        "next_action": {
            "title": "先更新日線與訊號資料",
            "detail": "資料已過期。",
            "command": "python3 scripts/daily_update.py --months 1",
            "expected_outputs": [],
        },
        "checks": {},
    })
    monkeypatch.setattr(svc, "get_universe", lambda: [])
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {"workflow_summary": {"stage": "complete"}})
    monkeypatch.setattr(svc, "build_universe_report_review_workflow_summary", lambda limit=10: {"stage": "complete", "top_items": []})
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "overall_status": "block",
        "data_as_of": "2026-06-10",
        "top_actions": [],
    })
    monkeypatch.setattr(svc, "get_workflow_status", lambda: {
        "can_trade_today": False,
        "data_as_of": "2026-06-10",
        "portfolio_tasks": [],
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [
        {
            "code": "2344",
            "name": "華邦電",
            "holding_shares": 0,
            "daily_action": "enter",
            "daily_action_label": "可小試",
            "daily_action_reason": "站回 MA5",
            "daily_priority": 95,
        }
    ])

    worklist = svc.get_pm_worklist()

    assert worklist["primary_action"]["key"] == "update_workflow"
    assert all(item["category"] != "entry_candidate" for item in worklist["today_focus"])
    assert worklist["today_focus"][0]["category"] == "review_needed"
    assert worklist["today_focus"][0]["label"] == "先解除交易輸出阻塞"
    assert "不要用候選股做進場判斷" in worklist["today_focus"][0]["reason"]


def test_pm_worklist_today_focus_has_empty_state_when_no_focus_items(monkeypatch):
    import app.services.pm_worklist_service as svc

    monkeypatch.setattr(svc, "get_update_workflow_status", lambda: {
        "overall_status": "ready",
        "headline": "每日更新流程完成，可以使用最新交易輸出。",
        "can_use_trade_outputs": True,
        "current_step": "ready",
        "next_action": None,
        "checks": {},
    })
    monkeypatch.setattr(svc, "get_universe", lambda: [])
    monkeypatch.setattr(svc, "get_fundamentals_status", lambda: {"workflow_summary": {"stage": "complete"}})
    monkeypatch.setattr(svc, "build_universe_report_review_workflow_summary", lambda limit=10: {"stage": "complete", "top_items": []})
    monkeypatch.setattr(svc, "get_daily_check_report", lambda: {
        "overall_status": "ok",
        "data_as_of": "2026-06-10",
        "top_actions": [],
    })
    monkeypatch.setattr(svc, "get_workflow_status", lambda: {
        "can_trade_today": True,
        "data_as_of": "2026-06-10",
        "portfolio_tasks": [],
    })
    monkeypatch.setattr(svc, "get_universe_report_json", lambda: [])

    worklist = svc.get_pm_worklist()

    assert worklist["today_focus"] == [{
        "category": "review_needed",
        "code": "",
        "name": "今日焦點已收斂",
        "label": "暫無持股風險或候選股",
        "reason": "目前沒有持股風險、可小試候選或待復盤項目。",
        "short_reason": "目前沒有持股風險、可小試候選或待復盤項目",
        "detail_reason": "目前沒有持股風險、可小試候選或待復盤項目。",
        "next_action": "維持觀察，若盤後資料更新再重新檢查 Dashboard。",
        "action_label": "維持觀察",
        "primary_metric": "",
        "severity": "info",
        "source": "pm_worklist",
        "price_basis": "最新收盤價（非即時市價）",
        "as_of": "2026-06-10",
    }]


def test_pm_worklist_endpoint(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "get_pm_worklist", lambda: {
        "generated_at": "2026-06-03T12:00:00",
        "overall_status": "action_required",
        "headline": "今日 PM 工作佇列：1 件待處理",
        "primary_action": {
            "key": "data_repair",
            "title": "先修復追蹤股日線資料",
            "detail": "x",
            "priority": 100,
            "severity": "danger",
            "status": "todo",
            "action_type": "data_repair",
            "action_label": "複製修復指令",
            "command": "python3 scripts/daily_update.py --months 12",
            "source": "universe",
            "metric": "1 檔需修復",
            "focus_codes": ["9999"],
            "action_payload": {
                "kind": "command",
                "command": "python3 scripts/daily_update.py --months 12",
                "copy_command": "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/daily_update.py --months 12",
                "expected_outputs": ["backend/out/summary.json", "backend/out/daily_check.json"],
            },
        },
        "today_focus": [{
            "category": "review_needed",
            "code": "9999",
            "name": "缺資料",
            "label": "資料修復",
            "reason": "缺日線資料。",
            "next_action": "先執行 daily_update 修復資料。",
            "severity": "danger",
            "source": "pm_worklist",
            "price_basis": "最新收盤價（非即時市價）",
            "as_of": "2026-06-03",
        }],
        "items": [{
            "key": "data_repair",
            "title": "先修復追蹤股日線資料",
            "detail": "x",
            "priority": 100,
            "severity": "danger",
            "status": "todo",
            "action_type": "data_repair",
            "action_label": "複製修復指令",
            "command": "python3 scripts/daily_update.py --months 12",
            "source": "universe",
            "metric": "1 檔需修復",
            "focus_codes": ["9999"],
            "action_payload": {
                "kind": "command",
                "command": "python3 scripts/daily_update.py --months 12",
                "copy_command": "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/daily_update.py --months 12",
                "expected_outputs": ["backend/out/summary.json", "backend/out/daily_check.json"],
            },
        }, {
            "key": "daily_check_fundamentals_priority",
            "title": "補一批基本面資料",
            "detail": "先補前兩檔。",
            "priority": 40,
            "severity": "warning",
            "status": "todo",
            "action_type": "daily_check",
            "action_label": "查看 Daily Check",
            "command": "補資料",
            "source": "daily_check",
            "metric": "warn",
            "focus_codes": [],
            "action_payload": {
                "kind": "copy_text",
                "copy_text": "基本面避雷優先補資料清單\n1. 聯發科 2454 - 缺 11 欄",
                "preview_items": ["聯發科 2454"],
                "file_path": "/backend/out/fundamentals_priority_fill.csv",
            },
        }, {
            "key": "daily_check_manual_market_note",
            "title": "更新人工盤後筆記",
            "detail": "筆記已過期。",
            "priority": 40,
            "severity": "warning",
            "status": "todo",
            "action_type": "daily_check",
            "action_label": "查看 Daily Check",
            "command": "POST /api/stocks/market-notes",
            "source": "daily_check",
            "metric": "warn",
            "focus_codes": [],
            "action_payload": {
                "kind": "api",
                "method": "POST",
                "endpoint": "/api/stocks/market-notes",
                "confirm_message": "只更新盤後筆記，不改正式訊號。",
            },
        }],
    })

    response = client.get("/api/system/pm-worklist")

    assert response.status_code == 200
    body = response.json()
    assert body["primary_action"]["key"] == "data_repair"
    assert body["primary_action"]["action_payload"]["expected_outputs"] == [
        "backend/out/summary.json",
        "backend/out/daily_check.json",
    ]
    assert body["today_focus"][0]["category"] == "review_needed"
    assert body["today_focus"][0]["price_basis"] == "最新收盤價（非即時市價）"
    assert body["items"][0]["key"] == "data_repair"
    assert body["items"][0]["action_payload"]["copy_command"].endswith("python3 scripts/daily_update.py --months 12")
    assert body["items"][0]["action_payload"]["expected_outputs"] == [
        "backend/out/summary.json",
        "backend/out/daily_check.json",
    ]
    assert body["items"][1]["action_payload"]["preview_items"] == ["聯發科 2454"]
    assert body["items"][1]["action_payload"]["file_path"] == "/backend/out/fundamentals_priority_fill.csv"
    assert body["items"][2]["action_payload"]["endpoint"] == "/api/stocks/market-notes"
    assert body["items"][2]["action_payload"]["confirm_message"] == "只更新盤後筆記，不改正式訊號。"
