"""
test_us_wbottom.py — 美股 W 底觀察策略 us_wbottom_target。

固定測資驗證：型態偵測邊界（低點確認 / 間距 / 價差 / 突破新鮮度）、無未來洩漏、
量幅目標與失效價數學、觀察輸出狀態分類、回放（D+1 open、目標 / 停損出場、確定性）、
endpoint schema。不打真網路。**觀察用：非推薦、非買賣建議、非下單。**
"""

import copy

from fastapi.testclient import TestClient

from app.main import app
from app.services import us_wbottom_service as wb
from app.storage import us_market_store

client = TestClient(app)

DATES = [f"2026-{1 + i // 28:02d}-{i % 28 + 1:02d}" for i in range(60)]


def _rows(code, bars, dates=None):
    dates = dates or DATES
    return [{"date": d, "code": code, "open": str(o), "high": str(h), "low": str(lo),
             "close": str(c), "volume": "1000"}
            for d, (o, h, lo, c) in zip(dates, bars)]


def _w_bars(n=60, low1_i=10, low2_i=25, breakout_i=30, low_px=90.0, neck_px=100.0):
    """
    製造標準 W 底：兩低點 + 中間頸線高點 + 指定日突破。
    基線 low 帶微幅斜率，避免「全數並列最低」讓每天都被判成 swing low。
    """
    bars = [(95.0, 96.0, 94.0 + i * 0.01, 95.0) for i in range(n)]
    bars[low1_i] = (91.0, 92.0, low_px, 91.0)
    bars[low2_i] = (91.0, 92.0, low_px + 0.5, 91.0)
    mid = (low1_i + low2_i) // 2
    bars[mid] = (99.0, neck_px, 98.0, 99.0)          # 頸線高點 100
    for i in range(breakout_i, n):                    # 突破後停在 101（未達目標 110）
        bars[i] = (100.5, 101.5, 99.5, 101.0)
    bars[breakout_i - 1] = (99.0, 99.5, 98.0, 99.0)   # 突破前一日仍在頸線下
    return bars


def _series(bars, dates=None):
    return wb._series(_rows("AAA", bars, dates))


# ── 型態偵測邊界 ─────────────────────────────────────────────────────────────

def test_detects_textbook_w_breakout():
    s = _series(_w_bars())
    w = wb.find_w_breakout(s, 30)
    assert w is not None
    assert w["neckline"] == 100.0
    assert w["pattern_low"] == 90.0
    assert w["target"] == 110.0                       # 頸線 + (頸線 − 型態低)


def test_breakout_must_be_fresh():
    s = _series(_w_bars())
    assert wb.find_w_breakout(s, 31) is None          # 第二天仍在頸線上 → 不再是訊號


def test_low_gap_boundaries():
    # 間距 9（<10）不成立；間距 10 成立
    s9 = _series(_w_bars(low1_i=16, low2_i=25))
    assert wb.find_w_breakout(s9, 30) is None
    s10 = _series(_w_bars(low1_i=15, low2_i=25))
    assert wb.find_w_breakout(s10, 30) is not None


def test_low_diff_over_3pct_rejected():
    bars = _w_bars()
    bars[25] = (95.0, 96.0, 93.5, 95.0)               # 第二低 93.5 vs 90 → 差 3.9%
    assert wb.find_w_breakout(_series(bars), 30) is None


def test_breakout_too_late_after_second_low_rejected():
    # 突破在第二低點後 > 20 根 → 不成立
    bars = _w_bars(low1_i=5, low2_i=18, breakout_i=40)
    assert wb.find_w_breakout(_series(bars), 40) is None


def test_swing_low_needs_confirmation_no_lookahead():
    bars = _w_bars()
    s = _series(bars)
    before = wb.find_w_breakout(s, 30)
    mutated = copy.deepcopy(bars)
    mutated[31] = (50.0, 50.0, 40.0, 45.0)            # 竄改未來 bar
    assert wb.find_w_breakout(_series(mutated), 30) == before


# ── 觀察輸出（get_us_wbottom）────────────────────────────────────────────────

def _patch_env(monkeypatch, bars, *, gate=True, n=60):
    rows = _rows("AAA", bars)
    # 基準走升（收盤 > MA60）或走跌（收盤 < MA60）；恆定序列會 close == MA60 判 False
    bench = [(100.0, 101.0, 99.0, 100.0 + i if gate else 100.0 - i) for i in range(n)]
    data = {"AAA": rows, "SPY": _rows("SPY", bench), "QQQ": _rows("QQQ", bench)}
    monkeypatch.setattr(wb, "load_us_ohlcv", lambda: data)
    monkeypatch.setattr(wb, "load_us_leaders", lambda: [
        {"code": "AAA", "name": "A", "category": "Mega-cap Tech"},
        {"code": "SPY", "name": "SPY", "category": "ETF / Benchmark"},
        {"code": "QQQ", "name": "QQQ", "category": "ETF / Benchmark"},
    ])


def test_observation_breakout_in_progress(monkeypatch):
    _patch_env(monkeypatch, _w_bars(low1_i=35, low2_i=47, breakout_i=55))  # 近端突破、未達標未失效
    out = wb.get_us_wbottom()
    assert out["strategy"] == "us_wbottom_target"
    assert out["market_gate"]["active"] is True
    assert len(out["patterns"]) == 1
    p = out["patterns"][0]
    assert p["state"] == "breakout_in_progress"
    assert p["target_price"] == 110.0
    assert p["reasons"] and p["risk_notes"]
    assert any("非下單" in r for r in p["risk_notes"])


def test_observation_target_reached(monkeypatch):
    bars = _w_bars(low1_i=30, low2_i=42, breakout_i=50)
    bars[55] = (111.0, 112.0, 110.5, 111.0)           # 收盤 ≥ 目標 110
    for i in range(56, 60):
        bars[i] = (111.0, 112.0, 110.5, 111.0)
    _patch_env(monkeypatch, bars)
    out = wb.get_us_wbottom()
    assert out["patterns"][0]["state"] == "target_reached"


def test_observation_invalidated(monkeypatch):
    bars = _w_bars(low1_i=30, low2_i=42, breakout_i=50)
    for i in range(55, 60):
        bars[i] = (89.0, 89.5, 88.0, 89.0)            # 跌破型態低 90
    _patch_env(monkeypatch, bars)
    out = wb.get_us_wbottom()
    assert out["patterns"][0]["state"] == "invalidated"


def test_observation_no_pattern_is_normal(monkeypatch):
    # 緩升無低點 → 無型態
    _patch_env(monkeypatch, [(95.0 + i * 0.05, 96.0 + i * 0.05, 94.0 + i * 0.05, 95.0 + i * 0.05)
                             for i in range(60)])
    out = wb.get_us_wbottom()
    assert out["patterns"] == []
    assert out["no_pattern_count"] == 1               # 空清單是常態，不是錯誤


def test_observation_gate_closed_noted(monkeypatch):
    _patch_env(monkeypatch, _w_bars(low1_i=35, low2_i=47, breakout_i=55), gate=False)
    out = wb.get_us_wbottom()
    assert out["market_gate"]["active"] is False
    p = out["patterns"][0]
    assert any("濾網" in r for r in p["reasons"])     # 仍列型態，但明講濾網關閉


# ── 回放（V1 出場）───────────────────────────────────────────────────────────

def _replay_env(bars):
    n = len(bars)
    bench = [(95.0, 96.0, 94.0, 200.0)] * n
    return ({"AAA": _rows("AAA", bars), "SPY": _rows("SPY", bench), "QQQ": _rows("QQQ", bench)},
            [{"code": "AAA", "name": "A", "category": "Mega-cap Tech"},
             {"code": "SPY", "name": "SPY", "category": "ETF / Benchmark"},
             {"code": "QQQ", "name": "QQQ", "category": "ETF / Benchmark"}])


def _gate_all_open(monkeypatch):
    monkeypatch.setattr(wb, "_market_filter_map",
                        lambda ohlcv: {d: True for d in DATES})


def test_replay_entry_next_open_and_target_exit(monkeypatch):
    _gate_all_open(monkeypatch)
    bars = _w_bars(breakout_i=30)
    bars[31] = (102.5, 103.0, 101.5, 102.0)           # D+1 open = 102.5（進場價）
    bars[40] = (110.5, 112.0, 110.0, 111.0)           # 收盤 ≥ 110 → 觸發
    bars[41] = (112.0, 113.0, 111.0, 112.5)           # 下一日 open = 112 出場
    for i in range(42, 60):
        bars[i] = (112.0, 113.0, 111.0, 112.5)
    ohlcv, leaders = _replay_env(bars)
    out = wb.run_wbottom_replay(DATES[0], DATES[35], ohlcv=ohlcv, leaders=leaders)
    t = out["trades"][0]
    assert (t["entry_date"], t["entry_price"]) == (DATES[31], 102.5)
    assert t["exit_reason"] == "target"
    assert (t["exit_date"], t["exit_price"]) == (DATES[41], 112.0)
    assert t["return_pct"] == round((112.0 - 102.5) / 102.5 * 100, 2)


def test_replay_pattern_low_stop(monkeypatch):
    _gate_all_open(monkeypatch)
    bars = _w_bars(breakout_i=30)
    for i in range(35, 60):
        bars[i] = (89.0, 89.5, 88.0, 89.0)            # 跌破型態低 90
    ohlcv, leaders = _replay_env(bars)
    out = wb.run_wbottom_replay(DATES[0], DATES[35], ohlcv=ohlcv, leaders=leaders)
    t = out["trades"][0]
    assert t["exit_reason"] == "pattern_low_stop"
    assert t["exit_date"] == DATES[36]


def test_replay_deterministic_and_frozen(monkeypatch):
    _gate_all_open(monkeypatch)
    ohlcv, leaders = _replay_env(_w_bars(breakout_i=30))
    a = wb.run_wbottom_replay(DATES[0], DATES[40], ohlcv=ohlcv, leaders=leaders)
    b = wb.run_wbottom_replay(DATES[0], DATES[40], ohlcv=ohlcv, leaders=leaders)
    assert a == b
    assert a["config"]["params_frozen"]["low_gap"] == [10, 40]
    assert a["limitations"]


# ── HTTP 端點 ─────────────────────────────────────────────────────────────────

def test_wbottom_endpoint_schema():
    res = client.get("/api/markets/us/strategy/w-bottom")
    assert res.status_code == 200
    body = res.json()
    assert body["strategy"] == "us_wbottom_target"
    assert isinstance(body["market_gate"]["active"], bool)
    assert isinstance(body["patterns"], list)
    assert isinstance(body["no_pattern_count"], int)
    for p in body["patterns"]:
        for key in ("code", "name", "category", "state", "state_label", "close",
                    "neckline", "pattern_low", "target_price", "dist_to_target_pct",
                    "breakout_date", "low_dates", "reasons", "risk_notes"):
            assert key in p
        assert p["state"] in wb.STATE_LABELS
        assert p["reasons"] and p["risk_notes"]
