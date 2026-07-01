import json
import subprocess
import sys
from datetime import date
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
_SCRIPTS = _BACKEND / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def test_daily_check_builds_summary_from_doctor_report():
    import daily_check

    report = {
        "overall_status": "warn",
        "exit_code": 1,
        "generated_at": "2026-06-02",
        "checks": [
            {
                "key": "outputs",
                "status": "ok",
                "title": "交易輸出同步",
                "message": "summary、daily_brief、universe_report 的資料日一致。",
                "details": {"last_data_as_of": "2026-05-29"},
                "next_action": "",
            },
            {
                "key": "fundamentals",
                "status": "warn",
                "title": "基本面避雷覆蓋",
                "message": "0/74 檔可進行基本面避雷評分。",
                "details": {},
                "next_action": "先填 ROE、現金流、負債、成長與估值欄位。",
                "action_payload": {
                    "kind": "copy_text",
                    "copy_text": "基本面避雷優先補資料清單\n1. 台積電 2330",
                },
            },
            {
                "key": "decision_journal",
                "status": "warn",
                "title": "候選股復盤紀錄",
                "message": "可行動 43 檔，尚未復盤 43 檔。",
                "details": {"missing_codes": ["2330", "2454"]},
                "next_action": "依 universe_report_review_todo.md 補決策日誌。",
            },
        ],
    }

    summary = daily_check.build_daily_summary(report, limit=2)

    assert summary["overall_status"] == "warn"
    assert summary["generated_at"] == "2026-06-02"
    assert summary["source_report_generated_at"] == "2026-06-02"
    assert summary["data_as_of"] == "2026-05-29"
    assert summary["can_use_trade_outputs"] is True
    assert len(summary["top_actions"]) == 2
    assert summary["top_actions"][0]["key"] == "fundamentals"
    assert summary["top_actions"][0]["action_type"] == "fundamentals"
    assert summary["top_actions"][0]["action_payload"]["kind"] == "copy_text"
    assert "台積電 2330" in summary["top_actions"][0]["action_payload"]["copy_text"]
    assert summary["top_actions"][0]["action_payload"]["preview_items"] == ["台積電 2330"]
    assert summary["top_actions"][1]["details"]["missing_codes"] == ["2330", "2454"]
    assert summary["top_actions"][1]["action_type"] == "decision_journal"


def test_daily_check_surfaces_official_coverage_audit_without_generating_reports(monkeypatch):
    import daily_check

    monkeypatch.setattr(daily_check, "get_official_fundamentals_coverage_audit", lambda: {
        "target_count": 2,
        "coverage_pct": 37.5,
        "available_cell_count": 6,
        "missing_report_files": ["backend/out/official_fundamentals_dividend.csv"],
        "blocked_formal_fields": ["roe_5y_avg", "eps_growth_5y_cagr"],
        "next_action_label": "先產生缺少的官方 report-only CSV。",
    })
    report = {
        "overall_status": "warn",
        "exit_code": 1,
        "generated_at": "2026-06-29",
        "checks": [],
    }

    summary = daily_check.build_daily_summary(report, limit=3, include_official_coverage=True)

    action = next(item for item in summary["top_actions"] if item["key"] == "official_fundamentals_coverage")
    assert action["action_type"] == "fundamentals"
    assert action["status"] == "warn"
    assert "37.5%" in action["message"]
    assert action["details"]["target_count"] == 2
    assert action["details"]["missing_report_files"] == ["backend/out/official_fundamentals_dividend.csv"]
    assert action["action_payload"] == {
        "kind": "api",
        "method": "GET",
        "endpoint": "/api/system/fundamentals-official/coverage-audit",
        "confirm_message": "只讀取官方基本面覆蓋率稽核，不會產生報告或寫入正式基本面資料。",
    }


def test_daily_check_guides_when_official_coverage_priority_csv_is_missing(monkeypatch):
    import daily_check

    monkeypatch.setattr(
        daily_check,
        "get_official_fundamentals_coverage_audit",
        lambda: (_ for _ in ()).throw(FileNotFoundError("尚無 fundamentals_priority_fill.csv")),
    )
    report = {
        "overall_status": "warn",
        "exit_code": 1,
        "generated_at": "2026-06-29",
        "checks": [],
    }

    summary = daily_check.build_daily_summary(report, limit=3, include_official_coverage=True)

    action = next(item for item in summary["top_actions"] if item["key"] == "official_fundamentals_coverage")
    assert action["action_type"] == "fundamentals"
    assert action["status"] == "warn"
    assert "fundamentals_priority_fill.csv" in action["message"]
    assert action["action_payload"]["kind"] == "api"
    assert action["action_payload"]["method"] == "GET"
    assert action["action_payload"]["endpoint"] == "/api/system/fundamentals-official/coverage-audit"


def test_daily_check_explains_warn_with_usable_trade_outputs():
    import daily_check

    report = {
        "overall_status": "warn",
        "exit_code": 1,
        "generated_at": "2026-06-27",
        "checks": [
            {
                "key": "outputs",
                "status": "ok",
                "title": "交易輸出同步",
                "message": "summary、daily_brief、universe_report 的資料日一致。",
                "details": {"last_data_as_of": "2026-06-26"},
                "next_action": "",
            },
            {
                "key": "fundamentals",
                "status": "warn",
                "title": "基本面避雷覆蓋",
                "message": "0/76 檔可進行基本面避雷評分。",
                "details": {},
                "next_action": "先填 ROE、現金流、負債、成長與估值欄位。",
            },
        ],
    }

    summary = daily_check.build_daily_summary(report, limit=3)

    assert summary["overall_status"] == "warn"
    assert summary["can_use_trade_outputs"] is True
    assert summary["blocked_by"] == []
    assert "基本面" in summary["status_reason"]
    assert "不足" in summary["status_reason"]
    assert "交易輸出仍可回顧" in summary["trade_outputs_note"]
    assert "基本面避雷" in summary["trade_outputs_note"]
    assert "保守" in summary["trade_outputs_note"]


def test_daily_check_preserves_fundamentals_workflow_details():
    import daily_check

    report = {
        "overall_status": "warn",
        "exit_code": 1,
        "generated_at": "2026-06-28",
        "checks": [
            {
                "key": "fundamentals",
                "status": "warn",
                "title": "基本面避雷覆蓋",
                "message": "0/76 檔可進行基本面避雷評分。",
                "details": {
                    "workflow_stage": "fill_priority_csv",
                    "workflow_headline": "開始填基本面避雷優先補資料 CSV",
                    "workflow_primary_action": {
                        "label": "填寫 CSV",
                        "kind": "file",
                        "command": "backend/out/fundamentals_priority_fill.csv",
                    },
                    "workflow_checklist": [
                        {"key": "download_priority_csv", "label": "產生優先 CSV", "status": "done"},
                        {"key": "fill_required_fields", "label": "補齊 11 欄", "status": "todo"},
                    ],
                },
                "next_action": "先填優先 20 檔",
            },
        ],
    }

    summary = daily_check.build_daily_summary(report, limit=3)
    details = summary["top_actions"][0]["details"]

    assert summary["top_actions"][0]["key"] == "fundamentals"
    assert details["workflow_stage"] == "fill_priority_csv"
    assert details["workflow_headline"] == "開始填基本面避雷優先補資料 CSV"
    assert details["workflow_primary_action"]["label"] == "填寫 CSV"
    assert details["workflow_checklist"][1]["key"] == "fill_required_fields"


def test_daily_check_prioritizes_blockers_before_warnings():
    import daily_check

    report = {
        "overall_status": "block",
        "exit_code": 2,
        "generated_at": "2026-06-02",
        "checks": [
            {"key": "fundamentals", "status": "warn", "title": "基本面避雷", "message": "warn", "details": {}, "next_action": "補資料"},
            {"key": "outputs", "status": "block", "title": "輸出不同步", "message": "block", "details": {}, "next_action": "重算訊號"},
        ],
    }

    summary = daily_check.build_daily_summary(report, limit=3)

    assert summary["can_use_trade_outputs"] is False
    assert [item["key"] for item in summary["top_actions"]] == ["outputs", "fundamentals"]


def test_daily_check_adds_signal_alert_action_before_warnings():
    import daily_check

    report = {
        "overall_status": "warn",
        "exit_code": 1,
        "generated_at": "2026-06-24",
        "checks": [
            {"key": "fundamentals", "status": "warn", "title": "基本面避雷", "message": "warn", "details": {}, "next_action": "補資料"},
        ],
    }
    alerts = {
        "as_of": "2026-06-24",
        "previous_as_of": "2026-06-23",
        "alert_count": 1,
        "severity_counts": {"block": 1},
        "message": "偵測到 1 筆隔日訊號變化警示。",
        "alerts": [
            {"code": "2330", "name": "台積電", "title": "持股/候選轉風險"},
        ],
    }

    summary = daily_check.build_daily_summary(report, limit=3, signal_alerts=alerts)

    assert summary["can_use_trade_outputs"] is False
    assert "不可作為今天判斷依據" in summary["trade_outputs_note"]
    assert summary["signal_alerts"]["alert_count"] == 1
    assert [item["key"] for item in summary["top_actions"]] == ["signal_alerts", "fundamentals"]
    action = summary["top_actions"][0]
    assert action["action_type"] == "signal_alerts"
    assert action["status"] == "block"
    assert action["action_payload"]["kind"] == "file"
    assert action["action_payload"]["file_path"] == "backend/out/signal_alerts.json"
    assert action["action_payload"]["copy_command"].endswith("backend\ncat backend/out/signal_alerts.json")
    assert action["action_payload"]["expected_outputs"] == ["backend/out/signal_alerts.json"]
    assert action["action_payload"]["preview_items"] == ["2330 台積電：持股/候選轉風險"]


def test_daily_check_keeps_zero_signal_alerts_out_of_top_actions():
    import daily_check

    report = {
        "overall_status": "ok",
        "exit_code": 0,
        "generated_at": "2026-06-24",
        "checks": [],
    }
    alerts = {
        "as_of": "2026-06-24",
        "previous_as_of": "2026-06-23",
        "alert_count": 0,
        "severity_counts": {},
        "message": "隔日訊號無需處理的新警示。",
        "alerts": [],
    }

    summary = daily_check.build_daily_summary(report, limit=3, signal_alerts=alerts)

    assert summary["signal_alerts"]["alert_count"] == 0
    assert summary["top_actions"] == []


def test_daily_check_adds_today_scan_summary_and_action_when_outputs_are_usable():
    import daily_check

    report = {
        "overall_status": "ok",
        "exit_code": 0,
        "generated_at": "2026-06-25",
        "checks": [
            {
                "key": "outputs",
                "status": "ok",
                "title": "交易輸出同步",
                "message": "ok",
                "details": {"last_data_as_of": "2026-06-25"},
                "next_action": "",
            }
        ],
    }
    today_scan = {
        "as_of": "2026-06-25",
        "formal_entries": [{"code": "2337", "name": "旺宏"}, {"code": "6274", "name": "台燿"}],
        "old_wang_candidates": [{"code": "2303", "name": "聯電"}],
        "steady_momentum_candidates": [{"code": "2337", "name": "旺宏"}],
        "risk_items": [{"code": "2603", "name": "長榮"}],
        "data_freshness": {
            "expected_as_of": "2026-06-25",
            "row_count": 4,
            "fresh_count": 3,
            "stale_count": 1,
            "missing_date_count": 0,
            "top_stale_items": [{"code": "5425", "name": "台半", "data_as_of": "2026-06-24"}],
        },
        "notes": ["老王大盤濾網目前封鎖追價。"],
    }

    summary = daily_check.build_daily_summary(report, limit=3, today_scan=today_scan)

    assert summary["today_scan"]["as_of"] == "2026-06-25"
    assert summary["today_scan"]["formal_entry_count"] == 2
    assert summary["today_scan"]["old_wang_count"] == 1
    assert summary["today_scan"]["steady_momentum_count"] == 1
    assert summary["today_scan"]["risk_count"] == 1
    assert [item["key"] for item in summary["top_actions"]] == ["data_freshness", "today_scan"]
    freshness_action = summary["top_actions"][0]
    assert freshness_action["action_type"] == "data_freshness"
    assert freshness_action["status"] == "warn"
    assert freshness_action["title"] == "追蹤股票資料日落後"
    assert freshness_action["message"] == "有 1 檔股票資料日落後，目標資料日為 2026-06-25。"
    assert freshness_action["next_action"] == "python3 scripts/daily_update.py --months 1"
    assert freshness_action["details"]["stale_count"] == 1
    assert freshness_action["action_payload"]["kind"] == "command"
    assert freshness_action["action_payload"]["command"] == "python3 scripts/daily_update.py --months 1"
    assert "cd " in freshness_action["action_payload"]["copy_command"]
    assert "backend/out/daily_check.json" in freshness_action["action_payload"]["expected_outputs"]
    assert freshness_action["action_payload"]["preview_items"] == ["5425 台半 仍停在 2026-06-24"]
    action = summary["top_actions"][1]
    assert action["action_type"] == "today_scan"
    assert action["status"] == "warn"
    assert action["message"] == "可小試 2 檔、老王觀察 1 檔、穩健動能 1 檔、風險處理 1 檔。"
    assert action["details"]["data_freshness"]["stale_count"] == 1
    assert action["action_payload"]["file_path"] == "backend/out/today_scan.json"
    assert action["action_payload"]["preview_items"] == [
        "可小試：2337 旺宏, 6274 台燿",
        "風險：2603 長榮",
        "資料日落後：5425 台半 仍停在 2026-06-24",
    ]


def test_daily_check_prioritizes_data_freshness_before_fundamentals_warning():
    import daily_check

    report = {
        "overall_status": "warn",
        "exit_code": 1,
        "generated_at": "2026-06-25",
        "checks": [
            {
                "key": "outputs",
                "status": "ok",
                "title": "交易輸出同步",
                "message": "ok",
                "details": {"last_data_as_of": "2026-06-25"},
                "next_action": "",
            },
            {
                "key": "fundamentals",
                "status": "warn",
                "title": "基本面避雷覆蓋",
                "message": "0/76 檔可進行基本面避雷評分。",
                "details": {},
                "next_action": "補基本面避雷資料。",
            },
        ],
    }
    today_scan = {
        "as_of": "2026-06-25",
        "formal_entries": [],
        "old_wang_candidates": [],
        "steady_momentum_candidates": [],
        "risk_items": [],
        "data_freshness": {
            "expected_as_of": "2026-06-25",
            "row_count": 2,
            "fresh_count": 1,
            "stale_count": 1,
            "missing_date_count": 0,
            "top_stale_items": [{"code": "2492", "name": "華新科", "data_as_of": "2026-06-24"}],
        },
    }

    summary = daily_check.build_daily_summary(report, limit=2, today_scan=today_scan)

    assert [item["key"] for item in summary["top_actions"]] == ["data_freshness", "fundamentals"]
    assert [item["action_type"] for item in summary["top_actions"]] == ["data_freshness", "fundamentals"]
    assert "華新科" in summary["top_actions"][0]["action_payload"]["preview_items"][0]


def test_daily_check_suppresses_today_scan_action_when_outputs_are_blocked():
    import daily_check

    report = {
        "overall_status": "block",
        "exit_code": 2,
        "generated_at": "2026-06-25",
        "checks": [
            {
                "key": "outputs",
                "status": "block",
                "title": "輸出不同步",
                "message": "block",
                "details": {"last_data_as_of": "2026-06-25"},
                "next_action": "python3 scripts/run_signals.py",
            }
        ],
    }

    summary = daily_check.build_daily_summary(
        report,
        limit=3,
        today_scan={"as_of": "2026-06-25", "formal_entries": [{"code": "2337", "name": "旺宏"}]},
    )

    assert summary["can_use_trade_outputs"] is False
    assert summary["today_scan"]["formal_entry_count"] == 1
    assert "today_scan" not in [item["key"] for item in summary["top_actions"]]


def test_daily_check_includes_data_repair_queue_from_universe():
    import daily_check
    from app.services.workflow_outputs import DAILY_UPDATE_OUTPUTS

    report = {
        "overall_status": "warn",
        "exit_code": 1,
        "generated_at": "2026-06-02",
        "checks": [
            {
                "key": "outputs",
                "status": "ok",
                "title": "交易輸出同步",
                "message": "ok",
                "details": {"last_data_as_of": "2026-05-29"},
                "next_action": "",
            },
        ],
    }
    universe = [
        {"code": "2330", "name": "台積電", "data_status": "ok", "row_count": 243, "last_data_as_of": "2026-05-29"},
        {"code": "9999", "name": "測試股", "data_status": "no_data", "row_count": 0, "last_data_as_of": None},
        {"code": "8888", "name": "短資料", "data_status": "insufficient", "row_count": 12, "last_data_as_of": "2026-05-10"},
    ]

    summary = daily_check.build_daily_summary(report, limit=3, universe=universe)

    repair = summary["data_repair"]
    assert repair["total_count"] == 2
    assert repair["no_data_count"] == 1
    assert repair["insufficient_count"] == 1
    assert repair["command"] == "python3 scripts/daily_update.py --months 12"
    assert [item["code"] for item in repair["top_items"]] == ["9999", "8888"]
    data_repair_action = next(action for action in summary["top_actions"] if action["key"] == "data_repair")
    assert data_repair_action["action_type"] == "data_repair"
    assert data_repair_action["action_payload"]["command"] == "python3 scripts/daily_update.py --months 12"
    assert data_repair_action["action_payload"]["copy_command"].endswith(
        "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/daily_update.py --months 12"
    )
    assert data_repair_action["action_payload"]["expected_outputs"] == DAILY_UPDATE_OUTPUTS


def test_daily_check_blocks_trade_outputs_when_data_coverage_blocks():
    import daily_check

    summary = daily_check.build_daily_summary(
        {
            "overall_status": "block",
            "exit_code": 2,
            "generated_at": "2026-06-23",
            "checks": [
                {
                    "key": "outputs",
                    "status": "ok",
                    "title": "交易輸出同步",
                    "message": "ok",
                    "details": {"last_data_as_of": "2026-06-22"},
                    "next_action": "",
                },
                {
                    "key": "data_coverage",
                    "status": "block",
                    "title": "資料覆蓋率不足",
                    "message": "coverage=50.0%",
                    "details": {"coverage_pct": 50.0},
                    "next_action": "python3 scripts/daily_update.py --months 1",
                    "action_payload": {
                        "kind": "command",
                        "command": "python3 scripts/daily_update.py --months 1",
                    },
                },
            ],
        },
        limit=1,
        universe=[],
    )

    assert summary["can_use_trade_outputs"] is False
    assert summary["top_actions"][0]["key"] == "data_coverage"
    assert "backend/out/data_coverage_report.json" in summary["top_actions"][0]["action_payload"]["expected_outputs"]


def test_daily_check_command_actions_include_expected_outputs():
    import daily_check
    from app.services.workflow_outputs import SIGNAL_OUTPUTS

    report = {
        "overall_status": "block",
        "exit_code": 2,
        "generated_at": "2026-06-02",
        "checks": [
            {
                "key": "outputs",
                "status": "block",
                "title": "交易輸出日期不同步",
                "message": "summary、daily_brief 或 universe_report 的資料日不一致。",
                "details": {"last_data_as_of": "2026-05-29"},
                "next_action": "python3 scripts/run_signals.py",
                "action_payload": {
                    "kind": "command",
                    "command": "python3 scripts/run_signals.py",
                    "copy_command": "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/run_signals.py",
                },
            },
        ],
    }

    summary = daily_check.build_daily_summary(report, limit=1, universe=[])
    payload = summary["top_actions"][0]["action_payload"]

    assert payload["expected_outputs"] == SIGNAL_OUTPUTS


def test_daily_check_prints_action_payload_details(capsys):
    import daily_check

    summary = {
        "overall_status": "warn",
        "data_as_of": "2026-05-29",
        "can_use_trade_outputs": True,
        "data_repair": {"total_count": 0},
        "top_actions": [
            {
                "key": "fundamentals",
                "status": "warn",
                "title": "基本面避雷覆蓋",
                "message": "0/74 檔可評分。",
                "next_action": "先填優先欄位。",
                "action_payload": {
                    "kind": "copy_text",
                    "copy_text": "基本面避雷優先補資料清單\n1. 台積電 2330 - 缺 11 欄\n2. 聯電 2303 - 缺 11 欄",
                    "file_path": "/tmp/backend/out/fundamentals_priority_fill.csv",
                    "write_template_command": "python3 scripts/prepare_fundamentals_priority_import.py --write-template",
                    "prepare_import_command": "python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv",
                    "prepare_import_apply_command": "python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv --apply",
                },
            },
            {
                "key": "decision_journal",
                "status": "warn",
                "title": "候選股復盤紀錄",
                "message": "尚未復盤。",
                "details": {"missing_codes": ["2330", "2454"]},
                "next_action": "依草稿補決策日誌。",
                "action_payload": {
                    "kind": "file",
                    "file_path": "/tmp/backend/out/universe_report_review_todo.md",
                    "confirm_message": "不會修改交易紀錄、持倉或現金。",
                },
            },
            {
                "key": "outputs",
                "status": "block",
                "title": "交易輸出缺檔",
                "message": "缺少輸出檔。",
                "next_action": "python3 scripts/daily_update.py --months 1",
                "action_payload": {
                    "kind": "command",
                    "command": "python3 scripts/daily_update.py --months 1",
                    "copy_command": "cd /tmp/backend\npython3 scripts/daily_update.py --months 1",
                    "expected_outputs": ["backend/out/summary.json", "backend/out/daily_check.json"],
                },
            },
        ],
    }

    daily_check.print_daily_summary(summary)
    out = capsys.readouterr().out

    assert "優先補基本面：台積電 2330, 聯電 2303" in out
    assert "產生模板：python3 scripts/prepare_fundamentals_priority_import.py --write-template" in out
    assert "匯入預覽：python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv" in out
    assert "正式寫入：python3 scripts/prepare_fundamentals_priority_import.py /path/to/source.csv --apply" in out
    assert "缺少復盤代碼：2330, 2454" in out
    assert "目標檔案：/tmp/backend/out/fundamentals_priority_fill.csv" in out
    assert "查看檔案：/tmp/backend/out/universe_report_review_todo.md" in out
    assert "提醒：不會修改交易紀錄、持倉或現金。" in out
    assert "跑完檢查：" in out
    assert "backend/out/daily_check.json" in out


def test_daily_check_json_cli_outputs_machine_readable_summary(monkeypatch, capsys, tmp_path):
    import daily_check

    monkeypatch.setattr(daily_check, "build_doctor_report", lambda backend: {
        "overall_status": "ok",
        "exit_code": 0,
        "generated_at": "2026-06-02",
        "checks": [
            {
                "key": "outputs",
                "status": "ok",
                "title": "交易輸出同步",
                "message": "ok",
                "details": {"summary_as_of": "2026-05-29"},
                "next_action": "",
            }
        ],
    })
    monkeypatch.setattr(daily_check, "load_universe_for_daily_check", lambda: [])

    code = daily_check.run_daily_check(daily_check.parse_args(["--backend", str(tmp_path), "--json"]))

    assert code == 0
    body = json.loads(capsys.readouterr().out)
    assert body["overall_status"] == "ok"
    assert body["generated_at"] == "2026-06-02"
    assert body["data_as_of"] == "2026-05-29"


def test_daily_check_write_report_outputs_json_file(monkeypatch, tmp_path):
    import daily_check

    monkeypatch.setattr(daily_check, "build_doctor_report", lambda backend: {
        "overall_status": "warn",
        "exit_code": 1,
        "generated_at": "2026-06-02",
        "checks": [
            {
                "key": "outputs",
                "status": "ok",
                "title": "交易輸出同步",
                "message": "ok",
                "details": {"last_data_as_of": "2026-05-29"},
                "next_action": "",
            },
            {
                "key": "fundamentals",
                "status": "warn",
                "title": "基本面避雷覆蓋",
                "message": "0/74",
                "details": {},
                "next_action": "補資料",
                "action_payload": {
                    "kind": "copy_text",
                    "copy_text": "基本面避雷優先補資料清單\n1. 聯發科 2454 - 缺 11 欄\n2. 台光電 2383 - 缺 11 欄",
                },
            },
        ],
    })
    monkeypatch.setattr(daily_check, "load_universe_for_daily_check", lambda: [])

    code = daily_check.run_daily_check(daily_check.parse_args(["--backend", str(tmp_path), "--write-report"]))

    path = tmp_path / "out" / "daily_check.json"
    assert code == 1
    assert path.exists()
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["overall_status"] == "warn"
    assert body["generated_at"] == "2026-06-02"
    assert body["data_as_of"] == "2026-05-29"
    assert body["top_actions"][0]["key"] == "fundamentals"
    assert body["top_actions"][0]["action_payload"]["preview_items"] == ["聯發科 2454", "台光電 2383"]


def test_write_daily_summary_uses_atomic_write(monkeypatch, tmp_path):
    import daily_check

    calls = []

    def fake_atomic_write(path, text, *, encoding="utf-8"):
        calls.append((path, text, encoding))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding=encoding)

    monkeypatch.setattr(daily_check, "atomic_write_text", fake_atomic_write)

    path = daily_check.write_daily_summary({"overall_status": "ok"}, tmp_path)

    assert path == tmp_path / "out" / "daily_check.json"
    assert calls[0][0] == path
    assert calls[0][2] == "utf-8"
    assert json.loads(calls[0][1])["overall_status"] == "ok"


def test_daily_check_service_returns_none_for_invalid_report(monkeypatch, tmp_path):
    import app.services.daily_check_service as svc

    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(svc, "_OUT", out)
    (out / "daily_check.json").write_text("{broken", encoding="utf-8")

    assert svc.get_daily_check_report() is None


def test_daily_check_service_marks_old_snapshot_as_stale(monkeypatch, tmp_path):
    import app.services.daily_check_service as svc

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 5)

    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(svc, "_OUT", out)
    monkeypatch.setattr(svc, "date", FakeDate, raising=False)
    (out / "daily_check.json").write_text(
        json.dumps(
            {
                "overall_status": "ok",
                "exit_code": 0,
                "generated_at": "2026-06-04T18:00:00",
                "data_as_of": "2026-05-29",
                "can_use_trade_outputs": True,
                "top_actions": [],
            }
        ),
        encoding="utf-8",
    )

    report = svc.get_daily_check_report()

    assert report is not None
    assert report["snapshot_is_stale"] is True
    assert "2026-06-04" in report["snapshot_stale_reason"]
    assert "2026-06-05" in report["snapshot_stale_reason"]
    assert report["snapshot_refresh_command"] == "python3 scripts/daily_check.py --write-report"
    assert report["snapshot_refresh_copy_command"].endswith(
        "backend\npython3 scripts/daily_check.py --write-report"
    )
    assert report["snapshot_refresh_expected_outputs"] == ["backend/out/daily_check.json"]


def test_daily_check_service_keeps_current_snapshot_fresh(monkeypatch, tmp_path):
    import app.services.daily_check_service as svc

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 5)

    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(svc, "_OUT", out)
    monkeypatch.setattr(svc, "date", FakeDate, raising=False)
    (out / "daily_check.json").write_text(
        json.dumps(
            {
                "overall_status": "ok",
                "exit_code": 0,
                "generated_at": "2026-06-05",
                "data_as_of": "2026-05-29",
                "can_use_trade_outputs": True,
                "top_actions": [],
            }
        ),
        encoding="utf-8",
    )

    report = svc.get_daily_check_report()

    assert report is not None
    assert report["snapshot_is_stale"] is False
    assert report["snapshot_stale_reason"] == ""
    assert report["snapshot_refresh_command"] == "python3 scripts/daily_check.py --write-report"
    assert report["snapshot_refresh_copy_command"].endswith(
        "backend\npython3 scripts/daily_check.py --write-report"
    )
    assert report["snapshot_refresh_expected_outputs"] == ["backend/out/daily_check.json"]


def test_daily_check_help_exits_0():
    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "daily_check.py"), "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--limit" in result.stdout
    assert "--write-report" in result.stdout
