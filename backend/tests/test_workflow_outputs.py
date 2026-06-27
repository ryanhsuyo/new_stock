def test_workflow_outputs_define_primary_commands():
    from app.services.workflow_outputs import (
        DAILY_CHECK_OUTPUTS,
        DAILY_UPDATE_OUTPUTS,
        SIGNAL_OUTPUTS,
        expected_outputs_for_command,
    )

    assert expected_outputs_for_command("python3 scripts/daily_update.py --months 1") == DAILY_UPDATE_OUTPUTS
    assert expected_outputs_for_command("python3 scripts/daily_update.py --months 12") == DAILY_UPDATE_OUTPUTS
    assert expected_outputs_for_command("python3 scripts/run_signals.py") == SIGNAL_OUTPUTS
    assert expected_outputs_for_command("python3 scripts/daily_check.py --write-report") == DAILY_CHECK_OUTPUTS
    assert expected_outputs_for_command("POST /api/system/fundamentals-priority-fill/merge") == []


def test_signal_outputs_include_daily_check_and_today_scan_snapshots():
    from app.services.workflow_outputs import SIGNAL_OUTPUTS

    assert SIGNAL_OUTPUTS == [
        "backend/out/summary.json",
        "backend/out/universe_report.csv",
        "backend/out/daily_brief.json",
        "backend/out/today_scan.json",
        "backend/out/daily_check.json",
    ]
