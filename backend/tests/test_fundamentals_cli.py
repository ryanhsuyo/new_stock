import subprocess
import sys
from argparse import Namespace
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
_SCRIPTS = _BACKEND / "scripts"


def test_import_fundamentals_help_exits_0():
    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "import_fundamentals.py"), "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--csv" in result.stdout
    assert "--merge-priority-csv" in result.stdout
    assert "--validate-priority-csv" in result.stdout
    assert "--dry-run" in result.stdout


def test_import_fundamentals_reports_invalid_csv_value(tmp_path):
    csv_path = tmp_path / "fundamentals.csv"
    out_path = tmp_path / "fundamentals.json"
    csv_path.write_text(
        "\n".join([
            "code,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2330,abc,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPTS / "import_fundamentals.py"),
            "--csv",
            str(csv_path),
            "--out",
            str(out_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "row 2" in result.stderr
    assert "2330" in result.stderr
    assert "roe_5y_avg" in result.stderr
    assert not out_path.exists()


def test_check_fundamentals_help_exits_0():
    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "check_fundamentals.py"), "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--leaders" in result.stdout
    assert "--write-priority-csv" in result.stdout


def test_check_fundamentals_prints_csv_validation_summary():
    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "check_fundamentals.py")],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "正式 CSV" in result.stdout
    assert "priority CSV" in result.stdout
    assert "valid=True" in result.stdout
    assert "priority 狀態" in result.stdout
    assert "下一步" in result.stdout


def test_check_fundamentals_rebuilds_report_after_writing_priority_csv(monkeypatch, tmp_path):
    import scripts.check_fundamentals as script

    reports = [
        {"priority_csv_validation": {"row_count": 5}},
        {"priority_csv_validation": {"row_count": 20}},
    ]
    monkeypatch.setattr(script, "build_fundamentals_status", lambda codes: reports.pop(0))
    monkeypatch.setattr(script, "write_priority_fill_csv", lambda limit=20: tmp_path / "priority.csv")

    report = script._build_report_after_requested_writes(
        Namespace(write_priority_csv=True, write_report=False, priority_limit=20),
        ["2330"],
    )

    assert report["priority_csv_validation"]["row_count"] == 20


def test_check_fundamentals_prints_priority_issue_summary(capsys):
    import scripts.check_fundamentals as script

    report = {
        "priority_fill_readiness": {
            "status": "invalid",
            "suggested_action": "先修正 CSV 內的錯誤值",
        },
        "priority_fill_guide": {
            "next_action_label": "先修正 CSV 錯誤",
        },
        "priority_csv_validation": {
            "errors": [{
                "row_number": 3,
                "code": "2408",
                "field": "roe_5y_avg",
                "value": "abc",
                "message": "必須是數字",
            }],
            "warnings": [],
        },
    }

    script._print_priority_workflow_summary(report)

    out = capsys.readouterr().out
    assert "priority 狀態" in out
    assert "invalid" in out
    assert "第 3 列" in out
    assert "2408" in out
    assert "roe_5y_avg" in out


def test_sync_fundamentals_template_help_exits_0():
    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "sync_fundamentals_template.py"), "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--leaders" in result.stdout


def test_merge_priority_fundamentals_help_exits_0():
    result = subprocess.run(
        [sys.executable, str(_SCRIPTS / "merge_priority_fundamentals.py"), "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--apply" in result.stdout
    assert "--confirm" in result.stdout


def test_merge_priority_fundamentals_preview_prints_next_action(monkeypatch, capsys):
    import scripts.merge_priority_fundamentals as script

    monkeypatch.setattr(script, "merge_priority_fill_csv", lambda dry_run=True, confirm=None: {
        "dry_run": True,
        "merge_allowed": True,
        "updated_code_count": 1,
        "updated_field_count": 11,
        "complete_codes": ["2330"],
        "partial_codes": [],
        "empty_codes": ["2454"],
        "warning_count": 0,
        "warnings": [],
        "buffett_preview": [{
            "code": "2330",
            "name": "台積電",
            "buffett_data_ok": True,
            "buffett_score": 86,
            "buffett_signal": "品質價值觀察",
        }],
        "signals_refresh_required": False,
        "next_action_label": "可合併，合併後重新產生訊號",
    })

    code = script.run_merge(script.parse_args([]))

    out = capsys.readouterr().out
    assert code == 0
    assert "預覽" in out
    assert "可合併" in out
    assert "2330 台積電" in out
    assert "下一步" in out


def test_merge_priority_fundamentals_apply_writes_report(monkeypatch, tmp_path, capsys):
    import scripts.merge_priority_fundamentals as script

    calls = {}

    def fake_merge(dry_run=True, confirm=None):
        calls["dry_run"] = dry_run
        calls["confirm"] = confirm
        return {
            "dry_run": False,
            "merge_allowed": True,
            "updated_code_count": 1,
            "updated_field_count": 11,
            "complete_codes": ["2330"],
            "partial_codes": [],
            "empty_codes": [],
            "warning_count": 0,
            "warnings": [],
            "buffett_preview": [],
            "signals_refresh_required": True,
            "next_action_label": "重新產生訊號",
            "json_path": str(tmp_path / "fundamentals.json"),
        }

    monkeypatch.setattr(script, "merge_priority_fill_csv", fake_merge)
    monkeypatch.setattr(script, "write_fundamentals_report", lambda: tmp_path / "fundamentals_report.json")

    code = script.run_merge(script.parse_args(["--apply", "--confirm", "MERGE_PRIORITY_FUNDAMENTALS"]))

    out = capsys.readouterr().out
    assert code == 0
    assert calls == {"dry_run": False, "confirm": "MERGE_PRIORITY_FUNDAMENTALS"}
    assert "正式合併" in out
    assert "python3 scripts/run_signals.py" in out


def test_merge_priority_fundamentals_returns_error_for_invalid_csv(monkeypatch, capsys):
    import scripts.merge_priority_fundamentals as script

    def fake_merge(dry_run=True, confirm=None):
        raise ValueError("priority CSV validation failed: row 2 code 2330 field pe value 'xx' 必須是數字")

    monkeypatch.setattr(script, "merge_priority_fill_csv", fake_merge)

    code = script.run_merge(script.parse_args([]))

    captured = capsys.readouterr()
    assert code == 1
    assert "priority CSV validation failed" in captured.err
