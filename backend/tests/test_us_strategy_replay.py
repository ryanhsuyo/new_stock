"""
test_us_strategy_replay.py — us_trend_follow 逐日回放（evaluation-only）。

固定 fixture 驗證：walk-forward 無未來資料洩漏、訊號只能在下一交易日 open 成交、
兩套退出規則、連續跌破 MA20 計數、MFE/MAE、unresolved、確定性。不打真網路。
"""

import copy

from app.services import us_strategy_replay_service as rp

# ── fixture 工具 ─────────────────────────────────────────────────────────────

DATES = [f"2026-06-{d:02d}" for d in range(1, 29)]  # 28 個「交易日」（資料日即交易日）


def _rows(code: str, bars: list[tuple[float, float, float, float]], dates: list[str] | None = None) -> list[dict]:
    """bars = [(open, high, low, close), ...]，依日期排序。"""
    dates = dates or DATES
    return [
        {"date": d, "code": code, "open": str(o), "high": str(h), "low": str(lo),
         "close": str(c), "volume": "1000"}
        for d, (o, h, lo, c) in zip(dates, bars)
    ]


def _flat_bars(n: int, px: float = 100.0) -> list[tuple[float, float, float, float]]:
    return [(px, px + 1, px - 1, px)] * n


def _leaders(*codes: str) -> list[dict]:
    return [{"code": c, "name": c, "category": "Mega-cap Tech"} for c in codes]


def _stub_classify(schedule: dict[tuple[str, str], str]):
    """以 (code, date) → bucket 的排程取代 production 分類（date 取 item 的 last_data_as_of）。"""
    def fake(item: dict, bias: str) -> dict:
        bucket = schedule.get((item["code"], item["last_data_as_of"]), "excluded")
        state = "candidate" if bucket == "candidate" else "watch"
        return {"bucket": bucket, "state": state,
                "reasons": [f"stub:{bucket}"], "risk_notes": ["stub"]}
    return fake


def _stub_bias(by_date: dict[str, str], default: str = "bullish"):
    calls = {"n": 0}

    def fake(by_code: dict) -> tuple[str, dict]:
        # 取任一 item 的 last_data_as_of 當「今天」
        day = next(iter(by_code.values()))["last_data_as_of"]
        calls["n"] += 1
        return by_date.get(day, default), {}
    return fake


# ── walk-forward：無未來資料洩漏 ─────────────────────────────────────────────

def test_asof_item_ignores_future_rows():
    rows = _rows("AAA", [(100 + i, 101 + i, 99 + i, 100 + i) for i in range(28)])
    d = DATES[20]
    item_full = rp._build_asof_item("AAA", "AAA", "X", rp._rows_asof(rows, d))
    # 竄改 D 之後的所有價格 → as-of D 的指標必須完全不變
    mutated = copy.deepcopy(rows)
    for r in mutated:
        if r["date"] > d:
            r["close"] = "999999"
            r["high"] = "999999"
    item_mutated = rp._build_asof_item("AAA", "AAA", "X", rp._rows_asof(mutated, d))
    assert item_full == item_mutated
    assert item_full["last_data_as_of"] == d
    # 與「資料只到 D」的世界一致（等價於截斷資料集重算）
    truncated = [r for r in rows if r["date"] <= d]
    assert rp._build_asof_item("AAA", "AAA", "X", truncated) == item_full


# ── 成交時點：D 收盤訊號 → D+1 open ─────────────────────────────────────────

def test_entry_uses_next_day_open(monkeypatch):
    bars = _flat_bars(28)
    bars[6] = (123.45, 124.0, 122.0, 123.0)   # DATES[6] 的 open 是進場價
    ohlcv = {"AAA": _rows("AAA", bars)}
    monkeypatch.setattr(rp, "classify_trend_follow",
                        _stub_classify({("AAA", DATES[5]): "candidate"}))
    monkeypatch.setattr(rp, "_market_context", _stub_bias({}))
    out = rp.run_replay(DATES[5], DATES[5], ohlcv=ohlcv, leaders=_leaders("AAA"))
    trades = out["trades"][rp.RULE_CANDIDATE_EXIT]
    assert len(trades) == 1
    assert trades[0]["signal_date"] == DATES[5]
    assert trades[0]["entry_date"] == DATES[6]
    assert trades[0]["entry_price"] == 123.45


def test_signal_on_last_day_is_unresolved(monkeypatch):
    ohlcv = {"AAA": _rows("AAA", _flat_bars(28))}
    last = DATES[27]
    monkeypatch.setattr(rp, "classify_trend_follow",
                        _stub_classify({("AAA", last): "candidate"}))
    monkeypatch.setattr(rp, "_market_context", _stub_bias({}))
    out = rp.run_replay(last, last, ohlcv=ohlcv, leaders=_leaders("AAA"))
    for rule in (rp.RULE_CANDIDATE_EXIT, rp.RULE_TREND_PROTECT):
        trades = out["trades"][rule]
        assert len(trades) == 1
        t = trades[0]
        assert t["unresolved"] is True
        assert t["entry_price"] is None and t["exit_price"] is None
        assert t["exit_reason"] == "no_next_open_for_entry"


# ── candidate_exit ───────────────────────────────────────────────────────────

def test_candidate_exit_on_first_non_candidate_day(monkeypatch):
    ohlcv = {"AAA": _rows("AAA", _flat_bars(28))}
    # D5 訊號 → D6 進場；D6 仍 candidate；D7 不再是 → D8 open 退出
    schedule = {("AAA", DATES[5]): "candidate", ("AAA", DATES[6]): "candidate"}
    monkeypatch.setattr(rp, "classify_trend_follow", _stub_classify(schedule))
    monkeypatch.setattr(rp, "_market_context", _stub_bias({}))
    out = rp.run_replay(DATES[5], DATES[5], ohlcv=ohlcv, leaders=_leaders("AAA"))
    t = out["trades"][rp.RULE_CANDIDATE_EXIT][0]
    assert t["exit_reason"] == "not_candidate"
    assert t["exit_date"] == DATES[8]
    assert t["holding_trading_days"] == 2       # D6 進、D8 出


def test_candidate_exit_can_trigger_on_entry_day(monkeypatch):
    ohlcv = {"AAA": _rows("AAA", _flat_bars(28))}
    # 只有 D5 是 candidate → D6 進場當天已不符 → D7 open 退出
    monkeypatch.setattr(rp, "classify_trend_follow",
                        _stub_classify({("AAA", DATES[5]): "candidate"}))
    monkeypatch.setattr(rp, "_market_context", _stub_bias({}))
    out = rp.run_replay(DATES[5], DATES[5], ohlcv=ohlcv, leaders=_leaders("AAA"))
    t = out["trades"][rp.RULE_CANDIDATE_EXIT][0]
    assert (t["entry_date"], t["exit_date"]) == (DATES[6], DATES[7])
    assert t["holding_trading_days"] == 1


# ── trend_protect_exit ───────────────────────────────────────────────────────

def _always_candidate(code: str) -> dict:
    return _stub_classify({(code, d): "candidate" for d in DATES})


def test_trend_protect_two_consecutive_closes_below_ma20(monkeypatch):
    # 前 20 天定在 100 → MA20≈100；之後兩天收 98（連續 2 日 < MA20）→ 第 2 天觸發
    bars = _flat_bars(28)
    bars[21] = (99.0, 99.5, 97.5, 98.0)
    bars[22] = (98.5, 99.0, 97.0, 98.0)
    ohlcv = {"AAA": _rows("AAA", bars)}
    monkeypatch.setattr(rp, "classify_trend_follow", _always_candidate("AAA"))
    monkeypatch.setattr(rp, "_market_context", _stub_bias({}))
    out = rp.run_replay(DATES[19], DATES[19], ohlcv=ohlcv, leaders=_leaders("AAA"))
    t = out["trades"][rp.RULE_TREND_PROTECT][0]
    assert t["exit_reason"] == "close_below_ma20_2d"
    assert t["exit_date"] == DATES[23]          # D22 為連續第 2 日 → D23 open 出


def test_trend_protect_single_dip_does_not_exit(monkeypatch):
    # 只跌破一天就收回 → 不觸發；資料結束仍持有 → open_at_data_end
    bars = _flat_bars(28)
    bars[21] = (99.0, 99.5, 97.5, 98.0)         # 僅 D21 跌破
    ohlcv = {"AAA": _rows("AAA", bars)}
    monkeypatch.setattr(rp, "classify_trend_follow", _always_candidate("AAA"))
    monkeypatch.setattr(rp, "_market_context", _stub_bias({}))
    out = rp.run_replay(DATES[19], DATES[19], ohlcv=ohlcv, leaders=_leaders("AAA"))
    t = out["trades"][rp.RULE_TREND_PROTECT][0]
    assert t["unresolved"] is True
    assert t["exit_reason"] == "open_at_data_end"


def test_trend_protect_close_below_ma60(monkeypatch):
    # MA60 需要 ≥ 60 筆資料才存在 → 用 65 天 fixture（前 62 天定在 100 建立 MA60≈100）
    dates65 = [f"2026-{4 + i // 28:02d}-{i % 28 + 1:02d}" for i in range(65)]  # 遞增即可
    bars = _flat_bars(65)
    bars[62] = (85.0, 86.0, 79.0, 80.0)         # 直接跌破 MA60(≈100)
    ohlcv = {"AAA": _rows("AAA", bars, dates=dates65)}
    sched = {("AAA", d): "candidate" for d in dates65}
    monkeypatch.setattr(rp, "classify_trend_follow", _stub_classify(sched))
    monkeypatch.setattr(rp, "_market_context", _stub_bias({}))
    out = rp.run_replay(dates65[60], dates65[60], ohlcv=ohlcv, leaders=_leaders("AAA"))
    t = out["trades"][rp.RULE_TREND_PROTECT][0]
    assert t["exit_reason"] == "close_below_ma60"
    assert t["exit_date"] == dates65[63]


def test_trend_protect_gate_inactive_exits(monkeypatch):
    ohlcv = {"AAA": _rows("AAA", _flat_bars(28))}
    monkeypatch.setattr(rp, "classify_trend_follow", _always_candidate("AAA"))
    monkeypatch.setattr(rp, "_market_context", _stub_bias({DATES[24]: "bearish"}))
    out = rp.run_replay(DATES[20], DATES[20], ohlcv=ohlcv, leaders=_leaders("AAA"))
    t = out["trades"][rp.RULE_TREND_PROTECT][0]
    assert t["exit_reason"] == "gate_inactive"
    assert t["exit_date"] == DATES[25]


def test_no_signal_when_gate_inactive(monkeypatch):
    ohlcv = {"AAA": _rows("AAA", _flat_bars(28))}
    monkeypatch.setattr(rp, "classify_trend_follow", _always_candidate("AAA"))
    monkeypatch.setattr(rp, "_market_context", _stub_bias({}, default="bearish"))
    out = rp.run_replay(DATES[5], DATES[10], ohlcv=ohlcv, leaders=_leaders("AAA"))
    assert out["trades"][rp.RULE_CANDIDATE_EXIT] == []
    assert all(not s["gate_active"] and s["candidates"] == [] for s in out["snapshots"])


# ── MFE / MAE ────────────────────────────────────────────────────────────────

def test_mfe_mae_from_highs_lows(monkeypatch):
    bars = _flat_bars(28)
    bars[6] = (100.0, 101.0, 99.0, 100.0)       # 進場 open=100
    bars[7] = (100.0, 110.0, 95.0, 100.0)       # 期間高 110（+10%）、低 95（−5%）
    ohlcv = {"AAA": _rows("AAA", bars)}
    schedule = {("AAA", DATES[5]): "candidate", ("AAA", DATES[6]): "candidate"}
    monkeypatch.setattr(rp, "classify_trend_follow", _stub_classify(schedule))
    monkeypatch.setattr(rp, "_market_context", _stub_bias({}))
    out = rp.run_replay(DATES[5], DATES[5], ohlcv=ohlcv, leaders=_leaders("AAA"))
    t = out["trades"][rp.RULE_CANDIDATE_EXIT][0]  # D7 不符 → D8 出
    assert t["mfe_pct"] == 10.0
    assert t["mae_pct"] == -5.0


# ── 契約與確定性 ─────────────────────────────────────────────────────────────

def test_trade_fields_and_summary_shape(monkeypatch):
    ohlcv = {"AAA": _rows("AAA", _flat_bars(28))}
    monkeypatch.setattr(rp, "classify_trend_follow",
                        _stub_classify({("AAA", DATES[5]): "candidate"}))
    monkeypatch.setattr(rp, "_market_context", _stub_bias({}))
    out = rp.run_replay(DATES[5], DATES[5], ohlcv=ohlcv, leaders=_leaders("AAA"))
    t = out["trades"][rp.RULE_CANDIDATE_EXIT][0]
    for key in ("code", "category", "signal_date", "entry_date", "entry_price",
                "exit_date", "exit_price", "exit_rule", "exit_reason",
                "holding_trading_days", "return_pct", "mfe_pct", "mae_pct",
                "market_bias_at_entry", "entry_reasons", "unresolved"):
        assert key in t
    for rule in (rp.RULE_CANDIDATE_EXIT, rp.RULE_TREND_PROTECT):
        s = out["summary"][rule]
        for key in ("signals", "completed_trades", "unresolved_trades", "win_rate_pct",
                    "avg_return_pct", "median_return_pct", "best_trade_pct", "worst_trade_pct",
                    "avg_holding_trading_days", "avg_mfe_pct", "avg_mae_pct",
                    "reentry_within_3d", "exit_reason_counts"):
            assert key in s
    assert out["limitations"]                    # 限制必須揭露


def test_replay_is_deterministic(monkeypatch):
    bars = [(100 + i * 0.5, 101 + i * 0.5, 99 + i * 0.5, 100 + i * 0.5) for i in range(28)]
    ohlcv = {"AAA": _rows("AAA", bars), "BBB": _rows("BBB", _flat_bars(28))}
    schedule = {("AAA", d): "candidate" for d in DATES[5:12]}
    schedule.update({("BBB", d): "candidate" for d in DATES[7:9]})
    monkeypatch.setattr(rp, "classify_trend_follow", _stub_classify(schedule))
    monkeypatch.setattr(rp, "_market_context", _stub_bias({DATES[9]: "mixed"}))
    a = rp.run_replay(DATES[5], DATES[11], ohlcv=ohlcv, leaders=_leaders("AAA", "BBB"))
    b = rp.run_replay(DATES[5], DATES[11], ohlcv=ohlcv, leaders=_leaders("AAA", "BBB"))
    assert a == b
