"""scheduled_update wrapper 的決策邏輯：錯過補跑、一天成功一次即止。"""

import importlib.util
from datetime import datetime, time as dtime
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "scheduled_update",
    Path(__file__).resolve().parent.parent / "scripts" / "scheduled_update.py",
)
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
should_run = _MOD.should_run

TH = dtime(15, 30)


def test_before_threshold_never_runs():
    run, _ = should_run(datetime(2026, 7, 13, 9, 0), None, TH)
    assert run is False


def test_after_threshold_no_marker_runs():
    run, _ = should_run(datetime(2026, 7, 13, 15, 30), None, TH)
    assert run is True


def test_already_succeeded_today_after_threshold_skips():
    run, _ = should_run(
        datetime(2026, 7, 13, 21, 0),
        datetime(2026, 7, 13, 15, 31), TH)
    assert run is False


def test_missed_yesterday_runs_on_boot_after_threshold():
    # 昨天 15:30 後成功過，但今天門檻已過而尚未跑 → 開機補跑
    run, _ = should_run(
        datetime(2026, 7, 13, 19, 50),
        datetime(2026, 7, 12, 22, 28), TH)
    assert run is True


def test_success_before_todays_threshold_reruns_after():
    # 今天早上（門檻前）跑過的成功不算，過門檻後要再跑一次拿今日資料
    run, _ = should_run(
        datetime(2026, 7, 13, 16, 0),
        datetime(2026, 7, 13, 8, 45), TH)
    assert run is True


def test_us_threshold_morning():
    run, _ = should_run(datetime(2026, 7, 13, 8, 29), None, dtime(8, 30))
    assert run is False
    run, _ = should_run(datetime(2026, 7, 13, 8, 30), None, dtime(8, 30))
    assert run is True
