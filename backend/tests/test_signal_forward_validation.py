import json
from pathlib import Path

import pytest

from app.services import signal_forward_validation_service as fv


def _bars(code_days: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    return {
        day: {"open": price, "high": price, "low": price, "close": price}
        for day, price in code_days.items()
    }


def _write_snapshot(tmp_path: Path, as_of: str, generated_at: str, items: list[dict]) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    payload = {"as_of": as_of, "generated_at": generated_at, "items": items}
    (tmp_path / f"signal_snapshot_{as_of}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _buy(code: str, invalidation: str | None = "跌破 90") -> dict:
    return {"code": code, "name": code, "signal": "BUY", "daily_invalidation": invalidation}


def test_entry_waits_for_generated_at_not_data_date(tmp_path):
    # 快照 as_of 2026-06-26 但 2026-06-30 才產出；用 as_of 次日進場等於拿到當時不存在的訊號
    _write_snapshot(tmp_path, "2026-06-26", "2026-06-30T14:09:12", [_buy("2330")])
    days = ["2026-06-26", "2026-06-29", "2026-06-30", "2026-07-01"]
    prices = {"2330": _bars({d: 100.0 for d in days})}

    result = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365, as_of="2026-07-01"
    )

    assert result["trades"][0]["entry_date"] == "2026-07-01"


def test_entry_is_next_market_day_when_snapshot_lands_same_day(tmp_path):
    _write_snapshot(tmp_path, "2026-07-08", "2026-07-08T17:06:27", [_buy("2330")])
    days = ["2026-07-08", "2026-07-09", "2026-07-10"]
    prices = {"2330": _bars({d: 100.0 for d in days})}

    result = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365, as_of="2026-07-10"
    )

    assert result["trades"][0]["entry_date"] == "2026-07-09"


def test_stop_exits_at_next_open_after_the_close_that_broke_it(tmp_path):
    _write_snapshot(tmp_path, "2026-07-01", "2026-07-01T16:00:00", [_buy("2330", "跌破 95")])
    days = ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-06"]
    prices = {"2330": _bars({"2026-07-01": 100.0, "2026-07-02": 100.0,
                             "2026-07-03": 94.0, "2026-07-06": 90.0})}

    trade = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365, as_of="2026-07-06"
    )["trades"][0]

    assert (trade["exit_date"], trade["exit_reason"]) == ("2026-07-06", fv.EXIT_STOP)
    assert trade["closed"] is True


def test_signal_without_invalidation_is_excluded_from_stats_not_backfilled(tmp_path):
    # 沒有失效價就沒有出場規則；補一個值等於發明一條當時不存在的規則
    _write_snapshot(tmp_path, "2026-07-01", "2026-07-01T16:00:00",
                    [_buy("2330", None), _buy("2317", "跌破 95")])
    days = ["2026-07-01", "2026-07-02", "2026-07-03"]
    prices = {"2330": _bars({d: 100.0 for d in days}), "2317": _bars({d: 100.0 for d in days})}

    result = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365, as_of="2026-07-03"
    )

    assert result["signal_count"] == 2
    assert result["evaluated_count"] == 1
    assert result["no_stop_defined_count"] == 1


def test_window_reports_actual_snapshot_days_not_calendar_days(tmp_path):
    _write_snapshot(tmp_path, "2026-07-06", "2026-07-06T16:00:00", [_buy("2330")])
    _write_snapshot(tmp_path, "2026-07-20", "2026-07-20T16:00:00", [_buy("2330")])
    days = ["2026-07-06", "2026-07-07", "2026-07-20", "2026-07-21"]
    prices = {"2330": _bars({d: 100.0 for d in days})}

    result = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=30, as_of="2026-07-21"
    )

    # 窗口涵蓋 30 個日曆日，但只有 2 天真的有快照
    assert result["covered_snapshot_days"] == 2
    assert result["window_days"] == 30


def test_empty_window_reports_zero_instead_of_reaching_further_back(tmp_path):
    _write_snapshot(tmp_path, "2026-01-05", "2026-01-05T16:00:00", [_buy("2330")])
    days = ["2026-01-05", "2026-07-21"]
    prices = {"2330": _bars({d: 100.0 for d in days})}

    result = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=30, as_of="2026-07-21"
    )

    assert result["signal_count"] == 0
    assert result["trades"] == []
    assert "無訊號" in result["note"]


def test_market_reference_accompanies_strategy_return(tmp_path):
    # 跌段裡「少跌」和「賺錢」長得完全不一樣，只給策略報酬會被誤讀
    _write_snapshot(tmp_path, "2026-07-01", "2026-07-01T16:00:00", [_buy("2330", "跌破 1")])
    days = ["2026-07-01", "2026-07-02", "2026-07-03"]
    prices = {
        "2330": _bars({"2026-07-01": 100.0, "2026-07-02": 100.0, "2026-07-03": 95.0}),
        "2317": _bars({"2026-07-01": 100.0, "2026-07-02": 100.0, "2026-07-03": 70.0}),
        fv.BENCHMARK_CODE: _bars({"2026-07-01": 100.0, "2026-07-02": 100.0, "2026-07-03": 98.0}),
    }

    ref = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365, as_of="2026-07-03"
    )["market_reference"]

    assert ref["median_return_pct"] is not None
    assert ref["benchmark_return_pct"] == -2.0
    assert ref["universe_count"] == 3


def test_snapshot_risk_state_is_preferred_over_rebuilding_it(tmp_path):
    payload = {
        "as_of": "2026-07-01", "generated_at": "2026-07-01T16:00:00",
        "pre_market_risk": {"level": "defensive"},
        "items": [{**_buy("2330"), "old_wang_market_filter": "block",
                   "old_wang_market_regime": "risk"}],
    }
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "signal_snapshot_2026-07-01.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    days = ["2026-07-01", "2026-07-02", "2026-07-03"]
    prices = {"2330": _bars({d: 100.0 for d in days})}

    result = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365, as_of="2026-07-03"
    )
    trade = result["trades"][0]

    assert trade["risk_source"] == "snapshot"
    assert trade["pre_market_risk"] == "defensive"
    assert trade["market_filter"] == "block"
    assert result["risk_source_counts"] == {"snapshot": 1, "rebuilt": 0}


def test_old_snapshots_without_risk_fields_are_marked_rebuilt(tmp_path):
    # 舊快照缺欄位是事實，不能讓事後重算的值假裝是當時記錄的
    _write_snapshot(tmp_path, "2026-07-01", "2026-07-01T16:00:00", [_buy("2330")])
    days = ["2026-07-01", "2026-07-02", "2026-07-03"]
    prices = {"2330": _bars({d: 100.0 for d in days})}

    result = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365, as_of="2026-07-03"
    )

    assert result["trades"][0]["risk_source"] == "rebuilt"
    assert result["risk_source_counts"] == {"snapshot": 0, "rebuilt": 1}


def test_parse_stop_reads_the_price_out_of_human_text():
    assert fv._parse_stop("跌破 2318.93") == 2318.93
    assert fv._parse_stop("") is None
    assert fv._parse_stop(None) is None


@pytest.mark.parametrize("window_days,expected", [(30, (37, 32, 10.8, -6.35)), (400, (54, 48, 11.1, -6.94))])
def test_live_snapshots_reproduce_the_documented_baseline(window_days, expected):
    """change 文件引用的數字必須能重現，否則證據狀態區塊印的是隨時間漂走的東西。"""
    from app.services.strategy_validation_service import _load_prices

    data_dir = Path(__file__).resolve().parents[1] / "data"
    snapshot_dir = Path(__file__).resolve().parents[1] / "out" / "signal_snapshots"
    if not snapshot_dir.exists():
        pytest.skip("本機沒有 signal_snapshots")

    prices, days = _load_prices(data_dir)
    result = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=snapshot_dir, window_days=window_days, as_of="2026-07-31"
    )
    signals, closed, win_rate, avg = expected
    assert result["signal_count"] == signals
    assert result["closed_count"] == closed
    assert result["stats"]["win_rate_pct"] == win_rate
    assert result["stats"]["avg_return_pct"] == avg
