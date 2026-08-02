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


class _Result:
    returncode = 0


def _run_market(monkeypatch, tmp_path, market: str, produce: list[str]):
    """跑一次排程，subprocess 只負責「產生」指定的 artifact。"""
    commands: list[list[str]] = []

    def fake_run(command, cwd):
        for name in produce:
            (tmp_path / name).write_text("x", encoding="utf-8")
        commands.append(command)
        return _Result()

    monkeypatch.setattr(_MOD, "_OUT", tmp_path)
    monkeypatch.setattr(_MOD, "datetime", type("Clock", (), {
        "now": staticmethod(lambda: datetime(2026, 7, 24, 10, 1)),
    }))
    monkeypatch.setattr(_MOD.subprocess, "run", fake_run)
    return _MOD.main(["--market", market, "--force"]), commands


def test_report_refreshes_market_before_generating(monkeypatch, tmp_path):
    code, commands = _run_market(monkeypatch, tmp_path, "us", _MOD.REPORTS["us"]["artifacts"])

    assert code == 0
    assert commands[0][-3:] == ["--market", "us", "--force"]
    assert commands[1][-2:] == ["--market", "us"]
    assert (tmp_path / ".strategy_report_last_success_us").exists()


def test_tw_expects_all_three_profile_reports():
    names = _MOD.REPORTS["tw"]["artifacts"]

    assert sum(1 for name in names if name.startswith("strategy_trade_report_tw")) == 3
    assert "strategy_trade_report_tw_old_wang_2026-05-01.md" in names
    assert "strategy_trade_report_tw_steady_momentum_2026-05-01.md" in names


def test_partial_tw_output_does_not_get_marked_successful(monkeypatch, tmp_path):
    # 產生器中途失敗時，先寫好的兩份看起來是新的；只看 exit code 會把部分成功當整批成功
    partial = _MOD.REPORTS["tw"]["artifacts"][:2]

    code, _commands = _run_market(monkeypatch, tmp_path, "tw", partial)

    assert code == 1
    assert not (tmp_path / ".strategy_report_last_success_tw").exists()


def test_complete_tw_output_is_marked_successful(monkeypatch, tmp_path):
    code, _commands = _run_market(monkeypatch, tmp_path, "tw", _MOD.REPORTS["tw"]["artifacts"])

    assert code == 0
    assert (tmp_path / ".strategy_report_last_success_tw").exists()


def test_stale_artifact_from_a_previous_run_counts_as_missing(monkeypatch, tmp_path):
    for name in _MOD.REPORTS["tw"]["artifacts"]:
        (tmp_path / name).write_text("昨天的", encoding="utf-8")

    # 檔案存在但都比這次啟動早，等於這輪什麼都沒重新產生
    stale = _MOD.stale_artifacts("tw", datetime.now(), out_dir=tmp_path)

    assert stale == _MOD.REPORTS["tw"]["artifacts"]
