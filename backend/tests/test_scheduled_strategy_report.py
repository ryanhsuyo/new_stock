"""分市場報告排程的時間、刷新順序與成功 marker。"""

import importlib.util
from datetime import datetime, time as dtime
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "scheduled_strategy_report",
    Path(__file__).resolve().parent.parent / "scripts" / "scheduled_strategy_report.py",
)
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def test_report_thresholds_are_us_1000_and_tw_1540():
    assert _MOD.REPORTS["us"]["threshold"] == dtime(10, 0)
    assert _MOD.REPORTS["tw"]["threshold"] == dtime(15, 40)


def test_report_refreshes_market_before_generating(monkeypatch, tmp_path):
    commands = []

    class Result:
        returncode = 0

    monkeypatch.setattr(_MOD, "_OUT", tmp_path)
    monkeypatch.setattr(_MOD, "datetime", type("Clock", (), {
        "now": staticmethod(lambda: datetime(2026, 7, 24, 10, 1)),
    }))
    monkeypatch.setattr(
        _MOD.subprocess,
        "run",
        lambda command, cwd: commands.append(command) or Result(),
    )

    assert _MOD.main(["--market", "us", "--force"]) == 0
    assert commands[0][-3:] == ["--market", "us", "--force"]
    assert commands[1][-2:] == ["--market", "us"]
    assert (tmp_path / ".strategy_report_last_success_us").exists()
