"""
test_us_breakout_replay.py — 老王美股版突破策略回放（evaluation-only）。

固定 fixture 驗證：進場三條件與邊界、無未來資料洩漏、大盤濾網、D+1 open 成交、
-8% 硬止損、MA10 連續 2 日出場、unresolved、確定性。不打真網路。
"""

import copy

from app.services import us_breakout_replay_service as rp

DATES = [f"2026-{1 + i // 28:02d}-{i % 28 + 1:02d}" for i in range(56)]


def _rows(code, bars, dates=None):
    dates = dates or DATES
    return [{"date": d, "code": code, "open": str(o), "high": str(h), "low": str(lo),
             "close": str(c), "volume": str(v)}
            for d, (o, h, lo, c, v) in zip(dates, bars)]


def _flat(n, px=100.0, vol=1000.0):
    return [(px, px + 1, px - 1, px, vol)] * n


def _leaders():
    return [{"code": "AAA", "name": "A", "category": "Mega-cap Tech"}]


def _mkt_on(monkeypatch, on=True):
    monkeypatch.setattr(rp, "_market_filter_map",
                        lambda ohlcv: {d: on for d in DATES})


# ── entry_signal：條件與邊界（純函式）───────────────────────────────────────

def _sig_series(close_last, vol_last):
    bars = _flat(25)
    bars[24] = (100.0, close_last + 1, 99.0, close_last, vol_last)
    return rp._series(_rows("AAA", bars))


def test_entry_requires_all_three_conditions():
    assert rp.entry_signal(_sig_series(105.0, 1500.0), 24) is True     # 全過
    assert rp.entry_signal(_sig_series(100.0, 1500.0), 24) is False    # 未創新高
    assert rp.entry_signal(_sig_series(105.0, 1499.0), 24) is False    # 量能 <1.5x
    assert rp.entry_signal(_sig_series(105.0, 1500.0), 20) is False    # 窗口不足時不觸發


def test_entry_volume_boundary_exactly_1_5x():
    assert rp.entry_signal(_sig_series(105.0, 1500.0), 24) is True     # >= 1.5x 成立


def test_entry_signal_no_lookahead():
    bars = _flat(30)
    bars[24] = (100.0, 106.0, 99.0, 105.0, 2000.0)
    s = rp._series(_rows("AAA", bars))
    before = rp.entry_signal(s, 24)
    mutated = copy.deepcopy(bars)
    mutated[25] = (999.0, 999.0, 1.0, 999.0, 99999.0)                  # 竄改未來 bar
    s2 = rp._series(_rows("AAA", mutated))
    assert rp.entry_signal(s2, 24) == before


# ── run：成交時點 / 濾網 / 出場 ──────────────────────────────────────────────

def _one_signal_bars(n=56):
    """第 24 根創新高+爆量 → D25 open 進場；之後維持高檔（不觸發出場）。"""
    bars = _flat(n)
    bars[24] = (100.0, 106.0, 99.0, 105.0, 2000.0)
    for i in range(25, n):
        bars[i] = (105.5, 106.5, 104.5, 105.5, 1000.0)                 # 高於 MA10，續抱
    return bars


def test_entry_at_next_open_and_market_filter(monkeypatch):
    bars = _one_signal_bars()
    bars[25] = (104.2, 106.5, 104.0, 105.5, 1000.0)                    # D25 open=104.2
    _mkt_on(monkeypatch, True)
    out = rp.run_breakout_replay(DATES[0], DATES[30], ohlcv={"AAA": _rows("AAA", bars)},
                                 leaders=_leaders())
    ts = out["trades"]
    assert len(ts) == 1
    assert ts[0]["signal_date"] == DATES[24]
    assert ts[0]["entry_date"] == DATES[25]
    assert ts[0]["entry_price"] == 104.2


def test_market_filter_blocks_signal(monkeypatch):
    _mkt_on(monkeypatch, False)
    out = rp.run_breakout_replay(DATES[0], DATES[30],
                                 ohlcv={"AAA": _rows("AAA", _one_signal_bars())},
                                 leaders=_leaders())
    assert out["trades"] == []
    assert out["market_filter"]["blocked_signals"] == 1


def test_etf_never_trades(monkeypatch):
    _mkt_on(monkeypatch, True)
    out = rp.run_breakout_replay(
        DATES[0], DATES[30], ohlcv={"SPY": _rows("SPY", _one_signal_bars())},
        leaders=[{"code": "SPY", "name": "SPY", "category": "ETF / Benchmark"}])
    assert out["trades"] == []


def test_hard_stop_loss_exits_next_open(monkeypatch):
    bars = _one_signal_bars()
    # 進場 100（D25 open）→ D30 收盤 91.5 < 92 → 止損 → D31 open 出
    bars[25] = (100.0, 106.5, 99.0, 105.5, 1000.0)
    bars[30] = (92.0, 93.0, 90.0, 91.5, 1000.0)
    bars[31] = (91.0, 92.0, 90.0, 91.5, 1000.0)
    _mkt_on(monkeypatch, True)
    out = rp.run_breakout_replay(DATES[0], DATES[26],
                                 ohlcv={"AAA": _rows("AAA", bars)}, leaders=_leaders())
    t = out["trades"][0]
    assert t["exit_reason"] == "stop_loss"
    assert t["exit_date"] == DATES[31]
    assert t["exit_price"] == 91.0
    assert t["return_pct"] == -9.0


def test_ma10_two_day_break_exits(monkeypatch):
    bars = _one_signal_bars()
    # 高檔一段時間後連兩日收在 MA10 下方 → 第 2 日觸發 → 下一日 open 出
    bars[40] = (100.0, 101.0, 99.0, 100.0, 1000.0)
    bars[41] = (100.0, 101.0, 99.0, 100.0, 1000.0)
    bars[42] = (99.5, 100.5, 98.5, 99.0, 1000.0)
    _mkt_on(monkeypatch, True)
    out = rp.run_breakout_replay(DATES[0], DATES[26],
                                 ohlcv={"AAA": _rows("AAA", bars)}, leaders=_leaders())
    t = out["trades"][0]
    assert t["exit_reason"] == "ma10_break"
    assert t["exit_date"] == DATES[42]


def test_single_day_below_ma10_holds(monkeypatch):
    bars = _one_signal_bars()
    bars[40] = (100.0, 101.0, 99.0, 100.0, 1000.0)                     # 只跌一天就收回
    _mkt_on(monkeypatch, True)
    out = rp.run_breakout_replay(DATES[0], DATES[26],
                                 ohlcv={"AAA": _rows("AAA", bars)}, leaders=_leaders())
    t = out["trades"][0]
    assert t["unresolved"] is True
    assert t["exit_reason"] == "open_at_data_end"


def test_signal_on_last_day_unresolved(monkeypatch):
    bars = _flat(25)
    bars[24] = (100.0, 106.0, 99.0, 105.0, 2000.0)                     # 最後一根才觸發
    _mkt_on(monkeypatch, True)
    out = rp.run_breakout_replay(DATES[0], DATES[24],
                                 ohlcv={"AAA": _rows("AAA", bars, DATES[:25])},
                                 leaders=_leaders())
    t = out["trades"][0]
    assert t["unresolved"] is True and t["exit_reason"] == "no_next_open_for_entry"


def test_deterministic_and_contract(monkeypatch):
    _mkt_on(monkeypatch, True)
    ohlcv = {"AAA": _rows("AAA", _one_signal_bars())}
    a = rp.run_breakout_replay(DATES[0], DATES[30], ohlcv=ohlcv, leaders=_leaders())
    b = rp.run_breakout_replay(DATES[0], DATES[30], ohlcv=ohlcv, leaders=_leaders())
    assert a == b
    assert a["config"]["params_frozen"]["stop_pct"] == 0.92            # 參數凍結
    for key in ("signals", "completed_trades", "unresolved_trades", "exit_reason_counts"):
        assert key in a["summary"]
    assert a["limitations"]
