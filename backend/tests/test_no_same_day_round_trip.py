"""不當沖：任何引擎都不得產生「同一天進場又出場」的部位。

使用者規則（2026-08-03）：台股與美股都至少隔一個交易日才出場。這條在多個
地方各自成立，所以測試也放在一起，避免哪天某個引擎悄悄違反。
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

import pytest

from app.services import signal_forward_validation_service as fv

_OUT = Path(__file__).resolve().parents[1] / "out"


def _bars(days: dict[str, tuple[float, float]]):
    return {d: {"open": o, "high": max(o, c), "low": min(o, c), "close": c}
            for d, (o, c) in days.items()}


def _snapshot(tmp_path: Path, as_of: str, generated_at: str, stop: str | None = "跌破 90"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    payload = {"as_of": as_of, "generated_at": generated_at, "items": [
        {"code": "2330", "name": "台積電", "signal": "BUY", "daily_invalidation": stop},
    ]}
    (tmp_path / f"signal_snapshot_{as_of}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def test_entry_on_the_last_data_day_has_no_result_yet(tmp_path):
    # 用當天開盤→收盤估值就是一筆當沖損益
    _snapshot(tmp_path, "2026-07-01", "2026-07-01T16:00:00")
    days = ["2026-07-01", "2026-07-02"]
    prices = {"2330": _bars({d: (100.0, 105.0) for d in days})}

    result = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365, as_of="2026-07-02"
    )
    trade = result["trades"][0]

    assert trade["exit_reason"] == fv.AWAITING_NEXT_SESSION
    assert (trade["exit_date"], trade["return_pct"]) == (None, None)
    assert result["evaluated_count"] == 0
    assert result["awaiting_next_session_count"] == 1


def test_stop_hit_on_the_entry_day_still_exits_the_next_session(tmp_path):
    """進場當天就跌破失效價，出場仍必須是下一個交易日開盤，不是當天收盤。"""
    _snapshot(tmp_path, "2026-07-01", "2026-07-01T16:00:00", "跌破 95")
    days = ["2026-07-01", "2026-07-02", "2026-07-03"]
    prices = {"2330": _bars({"2026-07-01": (100.0, 100.0),
                             "2026-07-02": (100.0, 90.0),
                             "2026-07-03": (88.0, 88.0)})}

    trade = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365, as_of="2026-07-03"
    )["trades"][0]

    assert trade["entry_date"] == "2026-07-02"
    assert trade["exit_date"] == "2026-07-03"
    assert trade["exit_reason"] == fv.EXIT_STOP


def test_no_scored_trade_ever_closes_on_its_entry_day(tmp_path):
    _snapshot(tmp_path, "2026-07-01", "2026-07-01T16:00:00", "跌破 999")
    days = ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-06"]
    prices = {"2330": _bars({d: (100.0, 100.0) for d in days})}

    trades = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365, as_of="2026-07-06"
    )["trades"]

    for trade in trades:
        if trade["exit_date"]:
            assert trade["exit_date"] > trade["entry_date"], trade


@pytest.mark.parametrize("filename", [
    "us_wbottom_replay_2021-09-01_2026-07-10.csv",
    "us_breakout_replay_2021-09-01_2026-07-10.csv",
])
def test_us_replays_hold_at_least_one_session(filename):
    path = _OUT / filename
    if not path.exists():
        pytest.skip(f"本機沒有 {filename}")

    same_day = [
        row for row in csv.DictReader(path.open(encoding="utf-8"))
        if row.get("unresolved") == "False" and row.get("entry_date") == row.get("exit_date")
    ]

    assert same_day == []


def test_tw_portfolio_replay_never_buys_and_sells_the_same_name_same_day():
    reports = sorted(_OUT.glob("tw_portfolio_replay_*.json"))
    if not reports:
        pytest.skip("本機沒有台股組合回放結果")

    payload = json.loads(reports[-1].read_text(encoding="utf-8"))
    for mode, result in (payload.get("results") or {}).items():
        sides: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
        for trade in result.get("trades", []):
            sides[trade["code"]][trade["fill_date"]].add(trade["side"])
        offenders = [
            (code, day) for code, by_day in sides.items()
            for day, s in by_day.items() if {"buy", "sell"} <= s
        ]
        assert offenders == [], f"{mode}: {offenders}"
