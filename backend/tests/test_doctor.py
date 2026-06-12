import csv
import json
import subprocess
import sys
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
_SCRIPTS = _BACKEND / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_universe(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["code", "name", "data_ok", "daily_action", "buffett_data_ok", "data_as_of"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _minimal_backend(tmp_path: Path) -> Path:
    backend = tmp_path / "backend"
    _write_json(backend / "out" / "update_status.json", {
        "last_run_status": "success",
        "last_data_as_of": "2026-05-29",
        "last_error": None,
    })
    _write_json(backend / "out" / "summary.json", {
        "as_of": "2026-05-29",
        "generated_at": "2026-05-29T15:20:00",
        "universe_size": 2,
        "data_ok_count": 2,
        "data_missing_count": 0,
    })
    _write_json(backend / "out" / "daily_brief.json", {
        "as_of": "2026-05-29",
        "data_status": {"last_data_as_of": "2026-05-29"},
    })
    _write_universe(backend / "out" / "universe_report.csv", [
        {
            "code": "2330",
            "name": "台積電",
            "data_ok": "True",
            "daily_action": "enter",
            "buffett_data_ok": "False",
            "data_as_of": "2026-05-29",
        },
        {
            "code": "2454",
            "name": "聯發科",
            "data_ok": "True",
            "daily_action": "avoid",
            "buffett_data_ok": "False",
            "data_as_of": "2026-05-29",
        },
    ])
    _write_json(backend / "data" / "decision_journal.json", [])
    _write_json(backend / "data" / "trades.json", [])
    _write_json(backend / "data" / "fundamentals.json", {})
    return backend


def test_doctor_warns_for_buffett_and_unrecorded_actionable_items(tmp_path):
    import doctor

    backend = _minimal_backend(tmp_path)
    report = doctor.build_doctor_report(backend)
    by_key = {check["key"]: check for check in report["checks"]}

    assert report["overall_status"] == "warn"
    assert by_key["outputs"]["status"] == "ok"
    assert by_key["universe_report"]["details"]["actionable_count"] == 1
    assert by_key["buffett"]["status"] == "warn"
    assert by_key["buffett"]["details"]["complete_count"] == 0
    assert by_key["decision_journal"]["status"] == "warn"
    assert by_key["decision_journal"]["details"]["missing_actionable_count"] == 1
    assert by_key["decision_journal"]["details"]["review_todo_exists"] is False
    assert by_key["decision_journal"]["next_action"] == "python3 scripts/export_universe_review_todo.py"
    assert by_key["decision_journal"]["action_payload"]["kind"] == "command"
    assert by_key["decision_journal"]["action_payload"]["copy_command"] == (
        f"cd {backend}\npython3 scripts/export_universe_review_todo.py"
    )
    assert by_key["decision_journal"]["action_payload"]["expected_outputs"] == [
        "backend/out/universe_report_review_todo.md"
    ]


def test_doctor_prints_missing_actionable_codes(tmp_path, capsys):
    import doctor

    backend = _minimal_backend(tmp_path)

    report = doctor.build_doctor_report(backend)
    doctor.print_report(report)
    out = capsys.readouterr().out

    assert "缺少復盤代碼：2330" in out


def test_doctor_reports_existing_universe_review_todo_file(tmp_path):
    import doctor

    backend = _minimal_backend(tmp_path)
    todo_path = backend / "out" / "universe_report_review_todo.md"
    todo_path.write_text("# 候選股復盤待辦 - 2026-05-29\n", encoding="utf-8")

    report = doctor.build_doctor_report(backend)
    check = {item["key"]: item for item in report["checks"]}["decision_journal"]

    assert check["status"] == "warn"
    assert check["details"]["review_todo_exists"] is True
    assert check["details"]["review_todo_path"] == str(todo_path)
    assert str(todo_path) in check["next_action"]
    assert check["action_payload"] == {
        "kind": "file",
        "file_path": str(todo_path),
        "confirm_message": "依候選股復盤草稿補 source='universe_report' 的決策日誌；此動作不會修改交易紀錄、持倉或現金。",
    }


def test_doctor_surfaces_ready_to_merge_buffett_priority_csv(tmp_path):
    import doctor

    backend = _minimal_backend(tmp_path)
    _write_json(backend / "out" / "fundamentals_report.json", {
        "priority_fill_readiness": {
            "status": "ready_to_merge",
            "can_merge": True,
            "complete_code_count": 2,
            "filled_code_count": 3,
            "filled_field_count": 24,
            "suggested_action": "先按預覽合併，確認更新檔數與欄位數後再合併匯入。",
        },
        "priority_csv_validation": {
            "valid": True,
            "errors": [],
            "warnings": [],
        },
    })

    report = doctor.build_doctor_report(backend)
    buffett = {check["key"]: check for check in report["checks"]}["buffett"]

    assert buffett["status"] == "warn"
    assert buffett["details"]["priority_fill_status"] == "ready_to_merge"
    assert buffett["details"]["can_merge"] is True
    assert buffett["details"]["complete_code_count"] == 2
    assert "fundamentals-priority-fill/merge" in buffett["next_action"]


def test_doctor_uses_priority_csv_suggested_action_when_buffett_fill_is_empty(tmp_path):
    import doctor

    backend = _minimal_backend(tmp_path)
    _write_json(backend / "out" / "fundamentals_report.json", {
        "priority_fill_readiness": {
            "status": "empty",
            "can_merge": False,
            "complete_code_count": 0,
            "filled_code_count": 0,
            "filled_field_count": 0,
            "suggested_action": "先填優先 20 檔",
        },
        "priority_csv_validation": {
            "valid": True,
            "errors": [],
            "warnings": [],
        },
        "workflow_summary": {
            "fill_targets_copy_text": "巴菲特基本面優先補資料清單\n1. 台積電 2330 - 缺 11 欄",
        },
    })

    report = doctor.build_doctor_report(backend)
    buffett = {check["key"]: check for check in report["checks"]}["buffett"]

    assert buffett["status"] == "warn"
    assert buffett["details"]["priority_fill_status"] == "empty"
    assert buffett["next_action"] == "先填優先 20 檔"
    assert buffett["action_payload"]["kind"] == "copy_text"
    assert "台積電 2330" in buffett["action_payload"]["copy_text"]


def test_doctor_prints_copy_text_payload_target(tmp_path, capsys):
    import doctor

    backend = _minimal_backend(tmp_path)
    _write_json(backend / "out" / "fundamentals_report.json", {
        "priority_fill_readiness": {
            "status": "empty",
            "suggested_action": "先填優先 20 檔",
        },
        "priority_csv_validation": {"valid": True, "errors": [], "warnings": []},
        "workflow_summary": {
            "fill_targets_copy_text": "巴菲特基本面優先補資料清單\n1. 台積電 2330 - 缺 11 欄\n2. 聯電 2303 - 缺 11 欄",
        },
    })

    report = doctor.build_doctor_report(backend)
    doctor.print_report(report)
    out = capsys.readouterr().out

    assert "可複製清單：已準備文字內容" in out
    assert "優先補基本面：台積電 2330, 聯電 2303" in out
    assert str(backend / "out" / "fundamentals_priority_fill.csv") in out


def test_doctor_prints_copy_text_preview_without_dash(tmp_path, capsys):
    import doctor

    backend = _minimal_backend(tmp_path)
    _write_json(backend / "out" / "fundamentals_report.json", {
        "priority_fill_readiness": {
            "status": "empty",
            "suggested_action": "先填優先 20 檔",
        },
        "priority_csv_validation": {"valid": True, "errors": [], "warnings": []},
        "workflow_summary": {
            "fill_targets_copy_text": "巴菲特基本面優先補資料清單\n1. 台積電 2330\n2. 聯發科 2454",
        },
    })

    report = doctor.build_doctor_report(backend)
    doctor.print_report(report)
    out = capsys.readouterr().out

    assert "優先補基本面：台積電 2330, 聯發科 2454" in out


def test_doctor_prints_file_payload_target(tmp_path, capsys):
    import doctor

    backend = _minimal_backend(tmp_path)
    todo_path = backend / "out" / "universe_report_review_todo.md"
    todo_path.write_text("# 候選股復盤待辦 - 2026-05-29\n", encoding="utf-8")

    report = doctor.build_doctor_report(backend)
    doctor.print_report(report)
    out = capsys.readouterr().out

    assert "查看檔案：" in out
    assert str(todo_path) in out
    assert "此動作不會修改交易紀錄、持倉或現金" in out


def test_doctor_prints_api_payload_target(tmp_path, capsys):
    import doctor

    backend = _minimal_backend(tmp_path)
    _write_json(backend / "out" / "fundamentals_report.json", {
        "priority_fill_readiness": {
            "status": "ready_to_merge",
            "can_merge": True,
            "complete_code_count": 2,
            "filled_code_count": 2,
            "filled_field_count": 22,
            "suggested_action": "可先預覽合併 2 檔",
        },
        "priority_csv_validation": {"valid": True, "errors": [], "warnings": []},
    })

    report = doctor.build_doctor_report(backend)
    doctor.print_report(report)
    out = capsys.readouterr().out

    assert "API 動作：POST /api/system/fundamentals-priority-fill/merge" in out
    assert "先預覽巴菲特基本面補資料合併結果" in out


def test_doctor_falls_back_to_fresh_fundamentals_workflow_for_legacy_report(tmp_path, monkeypatch):
    import doctor

    backend = _minimal_backend(tmp_path)
    monkeypatch.setattr(doctor, "_BACKEND", backend)
    monkeypatch.setattr(doctor, "get_fundamentals_status", lambda: {
        "priority_fill_readiness": {
            "status": "empty",
            "can_merge": False,
            "complete_code_count": 0,
            "filled_code_count": 0,
            "filled_field_count": 0,
            "suggested_action": "先填優先 20 檔",
        },
        "priority_csv_validation": {"valid": True, "errors": [], "warnings": []},
        "workflow_summary": {
            "fill_targets_copy_text": "巴菲特基本面優先補資料清單\n1. 聯電 2303 - 缺 11 欄",
        },
    })
    _write_json(backend / "out" / "fundamentals_report.json", {
        "priority_fill_readiness": {
            "status": "empty",
            "can_merge": False,
            "complete_code_count": 0,
            "filled_code_count": 0,
            "filled_field_count": 0,
            "suggested_action": "先填優先 20 檔",
        },
        "priority_csv_validation": {"valid": True, "errors": [], "warnings": []},
    })

    report = doctor.build_doctor_report(backend)
    buffett = {check["key"]: check for check in report["checks"]}["buffett"]

    assert buffett["action_payload"]["kind"] == "copy_text"
    assert "聯電 2303" in buffett["action_payload"]["copy_text"]


def test_doctor_blocks_invalid_buffett_priority_csv_with_first_issue(tmp_path):
    import doctor

    backend = _minimal_backend(tmp_path)
    _write_json(backend / "out" / "fundamentals_report.json", {
        "priority_fill_readiness": {
            "status": "invalid",
            "can_merge": False,
            "filled_code_count": 1,
            "filled_field_count": 1,
            "complete_code_count": 0,
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

    report = doctor.build_doctor_report(backend)
    buffett = {check["key"]: check for check in report["checks"]}["buffett"]

    assert report["overall_status"] == "block"
    assert buffett["status"] == "block"
    assert buffett["details"]["priority_fill_status"] == "invalid"
    assert buffett["details"]["priority_fill_error_count"] == 1
    assert "第 3 列" in buffett["details"]["first_priority_issue"]
    assert "2408" in buffett["details"]["first_priority_issue"]


def test_doctor_prints_first_buffett_priority_issue(tmp_path, capsys):
    import doctor

    backend = _minimal_backend(tmp_path)
    _write_json(backend / "out" / "fundamentals_report.json", {
        "priority_fill_readiness": {
            "status": "invalid",
            "suggested_action": "先修正 priority CSV。",
        },
        "priority_csv_validation": {
            "valid": False,
            "errors": [{
                "row_number": 5,
                "code": "2330",
                "field": "pe",
                "value": "xx",
                "message": "必須是數字",
            }],
            "warnings": [],
        },
    })

    report = doctor.build_doctor_report(backend)
    doctor.print_report(report)
    out = capsys.readouterr().out

    assert "第一筆問題" in out
    assert "第 5 列" in out
    assert "2330" in out


def test_doctor_blocks_when_outputs_are_out_of_sync(tmp_path):
    import doctor

    backend = _minimal_backend(tmp_path)
    _write_json(backend / "out" / "daily_brief.json", {
        "as_of": "2026-05-28",
        "data_status": {"last_data_as_of": "2026-05-28"},
    })

    report = doctor.build_doctor_report(backend)
    by_key = {check["key"]: check for check in report["checks"]}

    assert report["overall_status"] == "block"
    assert report["exit_code"] == 2
    assert by_key["outputs"]["status"] == "block"
    assert by_key["outputs"]["next_action"] == "python3 scripts/run_signals.py"
    assert by_key["outputs"]["action_payload"]["copy_command"] == (
        f"cd {backend}\npython3 scripts/run_signals.py"
    )
    assert by_key["outputs"]["action_payload"]["expected_outputs"] == [
        "backend/out/summary.json",
        "backend/out/universe_report.csv",
        "backend/out/daily_brief.json",
        "backend/out/daily_check.json",
    ]


def test_doctor_prints_expected_outputs_for_command_actions(tmp_path, capsys):
    import doctor

    backend = tmp_path / "backend"
    backend.mkdir()

    report = doctor.build_doctor_report(backend)
    doctor.print_report(report)
    out = capsys.readouterr().out

    assert "跑完檢查：" in out
    assert "backend/data/ohlcv.csv" in out
    assert "backend/out/daily_check.json" in out


def test_doctor_uses_daily_update_for_missing_outputs(tmp_path):
    import doctor

    backend = tmp_path / "backend"
    backend.mkdir()

    report = doctor.build_doctor_report(backend)
    outputs = {check["key"]: check for check in report["checks"]}["outputs"]

    assert outputs["status"] == "block"
    assert outputs["next_action"] == "python3 scripts/daily_update.py --months 1"
    assert outputs["action_payload"]["copy_command"] == (
        f"cd {backend}\npython3 scripts/daily_update.py --months 1"
    )
    assert outputs["action_payload"]["expected_outputs"] == [
        "backend/data/ohlcv.csv",
        "backend/out/update_status.json",
        "backend/out/summary.json",
        "backend/out/universe_report.csv",
        "backend/out/daily_brief.json",
        "backend/out/daily_check.json",
    ]


def test_doctor_uses_daily_update_when_update_status_is_not_success(tmp_path):
    import doctor

    backend = _minimal_backend(tmp_path)
    _write_json(backend / "out" / "update_status.json", {
        "last_run_status": "failed",
        "last_data_as_of": "2026-05-29",
        "last_error": "network failed",
    })

    report = doctor.build_doctor_report(backend)
    outputs = {check["key"]: check for check in report["checks"]}["outputs"]

    assert outputs["status"] == "warn"
    assert outputs["next_action"] == "python3 scripts/daily_update.py --months 1"
    assert outputs["action_payload"]["copy_command"] == (
        f"cd {backend}\npython3 scripts/daily_update.py --months 1"
    )
    assert outputs["action_payload"]["expected_outputs"] == [
        "backend/data/ohlcv.csv",
        "backend/out/update_status.json",
        "backend/out/summary.json",
        "backend/out/universe_report.csv",
        "backend/out/daily_brief.json",
        "backend/out/daily_check.json",
    ]


def test_doctor_uses_daily_update_when_universe_has_missing_data(tmp_path):
    import doctor

    backend = _minimal_backend(tmp_path)
    _write_universe(backend / "out" / "universe_report.csv", [
        {
            "code": "2330",
            "name": "台積電",
            "data_ok": "False",
            "daily_action": "avoid",
            "buffett_data_ok": "False",
            "data_as_of": "2026-05-29",
        }
    ])

    report = doctor.build_doctor_report(backend)
    universe = {check["key"]: check for check in report["checks"]}["universe_report"]

    assert universe["status"] == "warn"
    assert universe["next_action"] == "python3 scripts/daily_update.py --months 1"
    assert universe["action_payload"]["copy_command"] == (
        f"cd {backend}\npython3 scripts/daily_update.py --months 1"
    )
    assert universe["action_payload"]["expected_outputs"] == [
        "backend/data/ohlcv.csv",
        "backend/out/update_status.json",
        "backend/out/summary.json",
        "backend/out/universe_report.csv",
        "backend/out/daily_brief.json",
        "backend/out/daily_check.json",
    ]


def test_doctor_json_cli_outputs_machine_readable_report(tmp_path):
    backend = _minimal_backend(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPTS / "doctor.py"),
            "--backend",
            str(backend),
            "--json",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    body = json.loads(result.stdout)
    assert body["overall_status"] == "warn"
    assert "checks" in body
