import json

from app.services import us_signal_snapshot_service as snap
from app.services import signal_forward_validation_service as fv
from scripts import generate_strategy_trade_report as report


def _row(code: str, bucket: str, **overrides):
    values = {
        "bucket": bucket, "code": code, "label": f"{code} Inc. {code}",
        "action": "可紙上追蹤：次一交易日開盤", "strategy": "W 底突破", "close": 100.0,
        "trigger": "頸線 105（+5.0%）", "invalidation": "收盤跌破型態低 90",
        "target": "120（+20.0%）", "reward_risk": "1 : 1.0（頸線進場）",
        "reason": f"{code} 理由", "group": "hold", "trigger_note": "",
    }
    values.update(overrides)
    return report.UsWatchRow(**values)


def _gates(trend_active=True, wbottom_active=True):
    return {"bias": "bullish", "active": trend_active}, {"active": wbottom_active}


def test_snapshot_keeps_every_bucket_not_just_the_trackable_one():
    # 濾網關閉的日子最值得記錄「當時看到什麼但沒動」
    rows = [_row("AMZN", report.BUCKET_ENTER), _row("PG", report.BUCKET_WATCH),
            _row("RKLB", report.BUCKET_IGNORE), _row("MSFT", report.BUCKET_DONE),
            _row("SMCI", report.BUCKET_DEAD)]
    trend, wbottom = _gates()

    result = snap.build_us_signal_snapshot(rows, trend, wbottom, "2026-07-31")

    assert result["item_count"] == 5
    assert result["trackable_count"] == 1
    assert {item["bucket"] for item in result["items"]} == {
        report.BUCKET_ENTER, report.BUCKET_WATCH, report.BUCKET_IGNORE,
        report.BUCKET_DONE, report.BUCKET_DEAD,
    }


def test_snapshot_records_both_market_gates():
    trend, wbottom = _gates(trend_active=False, wbottom_active=True)

    gates = snap.build_us_signal_snapshot([], trend, wbottom, "2026-07-31")["market_gates"]

    assert gates == {"trend_bias": "bullish", "trend_active": False, "wbottom_active": True}


def test_rerunning_the_same_data_day_overwrites_instead_of_adding(tmp_path):
    first = snap.build_us_signal_snapshot([_row("PG", report.BUCKET_WATCH)], *_gates(), "2026-07-31")
    second = snap.build_us_signal_snapshot(
        [_row("PG", report.BUCKET_WATCH), _row("KO", report.BUCKET_ENTER)], *_gates(), "2026-07-31"
    )

    snap.write_us_signal_snapshot(first, tmp_path)
    path = snap.write_us_signal_snapshot(second, tmp_path)

    files = list((tmp_path / snap.SNAPSHOT_DIR_NAME).glob("*.json"))
    assert len(files) == 1
    assert json.loads(path.read_text(encoding="utf-8"))["item_count"] == 2


def _write_us_snapshot(tmp_path, as_of, generated_at, items):
    tmp_path.mkdir(parents=True, exist_ok=True)
    payload = {"as_of": as_of, "generated_at": generated_at,
               "market_gates": {"trend_bias": "bullish"}, "items": items}
    (tmp_path / f"us_signal_snapshot_{as_of}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _bars(days: dict[str, float]):
    return {day: {"open": p, "high": p, "low": p, "close": p} for day, p in days.items()}


def test_only_the_trackable_bucket_becomes_a_sample(tmp_path):
    # 觀望名單沒有發生過進場，拿它充樣本等於憑空製造績效
    _write_us_snapshot(tmp_path, "2026-07-01", "2026-07-01T20:00:00", [
        {"code": "AMZN", "label": "AMZN", "bucket": "enter", "invalidation": "收盤跌破型態低 90"},
        {"code": "PG", "label": "PG", "bucket": "watch", "invalidation": "收盤跌破型態低 90"},
        {"code": "RKLB", "label": "RKLB", "bucket": "ignore", "invalidation": "收盤跌破型態低 90"},
    ])
    days = ["2026-07-01", "2026-07-02", "2026-07-03"]
    prices = {code: _bars({d: 100.0 for d in days}) for code in ("AMZN", "PG", "RKLB")}

    result = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365,
        as_of="2026-07-03", market=fv.MARKET_US,
    )

    assert result["signal_count"] == 1
    assert [t["code"] for t in result["trades"]] == ["AMZN"]


def test_reaching_the_measured_move_target_does_not_close_the_position(tmp_path):
    """紙上追蹤沒有定義停利動作；加一條會把贏家封頂、輸家留到停損。"""
    _write_us_snapshot(tmp_path, "2026-07-01", "2026-07-01T20:00:00", [
        {"code": "AMZN", "label": "AMZN", "bucket": "enter", "invalidation": "收盤跌破型態低 90"},
    ])
    days = ["2026-07-01", "2026-07-02", "2026-07-03"]
    prices = {"AMZN": _bars({"2026-07-01": 100.0, "2026-07-02": 130.0, "2026-07-03": 125.0})}

    trade = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365,
        as_of="2026-07-03", market=fv.MARKET_US,
    )["trades"][0]

    assert trade["exit_reason"] == fv.EXIT_OPEN
    assert trade["closed"] is False


def test_us_stop_uses_the_pattern_low_from_the_invalidation_text():
    assert fv._us_stop_price({"invalidation": "收盤跌破型態低 197.97；頸線進場停損 -7.5%"}) == 197.97
    assert fv._us_stop_price({"invalidation": "已跌破型態低 26.7"}) == 26.7


def test_us_benchmark_is_spy_not_the_taiwan_etf(tmp_path):
    _write_us_snapshot(tmp_path, "2026-07-01", "2026-07-01T20:00:00", [
        {"code": "AMZN", "label": "AMZN", "bucket": "enter", "invalidation": "收盤跌破型態低 1"},
    ])
    days = ["2026-07-01", "2026-07-02", "2026-07-03"]
    prices = {"AMZN": _bars({d: 100.0 for d in days}),
              "SPY": _bars({"2026-07-01": 100.0, "2026-07-02": 100.0, "2026-07-03": 104.0})}

    ref = fv.build_signal_forward_validation(
        prices, days, snapshot_dir=tmp_path, window_days=365,
        as_of="2026-07-03", market=fv.MARKET_US,
    )["market_reference"]

    assert ref["benchmark_code"] == "SPY"
    assert ref["benchmark_return_pct"] == 4.0


def test_markets_are_tagged_so_results_cannot_be_pooled(tmp_path):
    empty = fv.build_signal_forward_validation(
        {}, [], snapshot_dir=tmp_path, as_of="2026-07-31", market=fv.MARKET_US
    )

    assert empty["market"] == fv.MARKET_US
    assert empty["signal_count"] == 0


def test_us_report_evidence_comes_from_us_snapshots_only(monkeypatch):
    monkeypatch.setattr(report, "_us_forward_validation", lambda: {
        "signal_count": 0, "window_days": 180, "stats": {}, "market_reference": {},
        "note": "本窗口沒有可紙上追蹤的訊號",
    })
    monkeypatch.setattr(report, "_tw_forward_validation", lambda: {
        "signal_count": 37, "window_days": 30, "covered_snapshot_days": 19,
        "closed_count": 32, "open_count": 5, "no_stop_defined_count": 0,
        "stats": {"avg_return_pct": -6.35, "win_rate_pct": 10.8},
        "market_reference": {}, "note": "台股",
    })
    monkeypatch.setattr(report, "_read_replay_summary", lambda _p: {})
    monkeypatch.setattr(report, "_current_us_status", lambda **_k: (
        {"last_data_as_of": "2026-07-31"},
        {"as_of": "2026-07-31", "market_gate": {"bias": "mixed", "active": True}, "candidates": []},
        {"market_gate": {"active": True}, "patterns": []},
    ))

    result = report.build_us_report([])

    assert "0 筆" in result
    assert "37" not in result.split("## 今日結論")[0]
