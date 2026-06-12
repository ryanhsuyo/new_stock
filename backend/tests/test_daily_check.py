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
                "key": "buffett",
                "status": "warn",
                "title": "巴菲特基本面覆蓋",
                "message": "0/74 檔可進行 Buffett 評分。",
                "details": {},
                "next_action": "先填 ROE、現金流、負債、成長與估值欄位。",
                "action_payload": {
                    "kind": "copy_text",
                    "copy_text": "巴菲特基本面優先補資料清單\n1. 台積電 2330",
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
    assert summary["top_actions"][0]["key"] == "buffett"
    assert summary["top_actions"][0]["action_payload"]["kind"] == "copy_text"
    assert "台積電 2330" in summary["top_actions"][0]["action_payload"]["copy_text"]
    assert summary["top_actions"][0]["action_payload"]["preview_items"] == ["台積電 2330"]
    assert summary["top_actions"][1]["details"]["missing_codes"] == ["2330", "2454"]


def test_daily_check_prioritizes_blockers_before_warnings():
    import daily_check

    report = {
        "overall_status": "block",
        "exit_code": 2,
        "generated_at": "2026-06-02",
        "checks": [
            {"key": "buffett", "status": "warn", "title": "Buffett", "message": "warn", "details": {}, "next_action": "補資料"},
            {"key": "outputs", "status": "block", "title": "輸出不同步", "message": "block", "details": {}, "next_action": "重算訊號"},
        ],
    }

    summary = daily_check.build_daily_summary(report, limit=3)

    assert summary["can_use_trade_outputs"] is False
    assert [item["key"] for item in summary["top_actions"]] == ["outputs", "buffett"]


def test_daily_check_includes_data_repair_queue_from_universe():
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
    assert data_repair_action["action_payload"]["command"] == "python3 scripts/daily_update.py --months 12"
    assert data_repair_action["action_payload"]["copy_command"].endswith(
        "cd /Users/ryan/Desktop/code/new_stock/backend\npython3 scripts/daily_update.py --months 12"
    )
    assert data_repair_action["action_payload"]["expected_outputs"] == [
        "backend/data/ohlcv.csv",
        "backend/out/update_status.json",
        "backend/out/summary.json",
        "backend/out/universe_report.csv",
        "backend/out/daily_brief.json",
        "backend/out/daily_check.json",
    ]


def test_daily_check_command_actions_include_expected_outputs():
    import daily_check

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

    assert payload["expected_outputs"] == [
        "backend/out/summary.json",
        "backend/out/universe_report.csv",
        "backend/out/daily_brief.json",
        "backend/out/daily_check.json",
    ]


def test_daily_check_prints_action_payload_details(capsys):
    import daily_check

    summary = {
        "overall_status": "warn",
        "data_as_of": "2026-05-29",
        "can_use_trade_outputs": True,
        "data_repair": {"total_count": 0},
        "top_actions": [
            {
                "key": "buffett",
                "status": "warn",
                "title": "巴菲特基本面覆蓋",
                "message": "0/74 檔可評分。",
                "next_action": "先填優先欄位。",
                "action_payload": {
                    "kind": "copy_text",
                    "copy_text": "巴菲特基本面優先補資料清單\n1. 台積電 2330 - 缺 11 欄\n2. 聯電 2303 - 缺 11 欄",
                    "file_path": "/tmp/backend/out/fundamentals_priority_fill.csv",
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
                "key": "buffett",
                "status": "warn",
                "title": "巴菲特基本面覆蓋",
                "message": "0/74",
                "details": {},
                "next_action": "補資料",
                "action_payload": {
                    "kind": "copy_text",
                    "copy_text": "巴菲特基本面優先補資料清單\n1. 聯發科 2454 - 缺 11 欄\n2. 台光電 2383 - 缺 11 欄",
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
    assert body["top_actions"][0]["key"] == "buffett"
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
