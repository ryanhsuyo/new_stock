"""
test_us_watch_signals.py — 美股 Phase 3 觀察訊號（非推薦、非買賣建議）。

純規則以受控輸入驗證五種訊號；大盤基準與端到端用 fixture ohlcv_us.csv（monkeypatch）。
"""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.services import us_watch_signal_service as ws
from app.storage import us_market_store

client = TestClient(app)

VALID_SIGNALS = {"watch_breakout", "watch_pullback", "trend_up", "overheated", "avoid_weak"}


def _derive(**kw):
    base = dict(close=112.0, ma20=110.0, ma60=100.0, rsi=58.0, dist_ma20=1.8,
                row_count=65, recent_high=130.0, market_bias="bullish")
    base.update(kw)
    return ws.derive_watch_signal(**base)


# ── 五種訊號（受控輸入）─────────────────────────────────────────────────────

def test_signal_avoid_weak_insufficient_rows():
    sig, reasons, risks = _derive(row_count=30)
    assert sig == "avoid_weak" and reasons and risks


def test_signal_avoid_weak_below_ma60():
    sig, *_ = _derive(close=90.0, ma20=100.0, ma60=95.0)
    assert sig == "avoid_weak"


def test_signal_overheated_by_rsi():
    sig, *_ = _derive(close=130.0, ma60=100.0, ma20=110.0, rsi=75.0, dist_ma20=8.0, recent_high=131.0)
    assert sig == "overheated"


def test_signal_watch_pullback():
    sig, *_ = _derive(close=104.0, ma20=108.0, ma60=100.0, rsi=50.0, dist_ma20=-3.7, recent_high=115.0)
    assert sig == "watch_pullback"


def test_signal_watch_breakout_near_high():
    sig, *_ = _derive(close=119.5, ma20=110.0, ma60=100.0, rsi=62.0, dist_ma20=8.6, recent_high=120.0)
    assert sig == "watch_breakout"


def test_signal_trend_up_mid_trend():
    sig, *_ = _derive(close=112.0, ma20=110.0, ma60=100.0, rsi=58.0, dist_ma20=1.8, recent_high=130.0)
    assert sig == "trend_up"


def test_weak_market_adds_downgrade_risk_note():
    _, _, risks = _derive(market_bias="bearish")
    assert any("降級" in r for r in risks)


# ── 大盤基準 SPY/QQQ ─────────────────────────────────────────────────────────

def _bench(spy_above, qqq_above):
    def item(above):
        return {"last_close": 110.0 if above else 90.0, "ma60": 100.0}
    return {"SPY": item(spy_above), "QQQ": item(qqq_above)}


def test_market_bullish_when_both_above():
    bias, _ = ws._market_context(_bench(True, True))
    assert bias == "bullish"


def test_market_bearish_when_both_below():
    bias, _ = ws._market_context(_bench(False, False))
    assert bias == "bearish"


def test_market_mixed_when_split():
    bias, _ = ws._market_context(_bench(True, False))
    assert bias == "mixed"


def test_market_unknown_when_missing_ma60():
    bias, _ = ws._market_context({"SPY": {"last_close": 100.0, "ma60": None}, "QQQ": {"last_close": 100.0, "ma60": 90.0}})
    assert bias == "unknown"


# ── 端到端（fixture）─────────────────────────────────────────────────────────

def _write_fixture(path, codes, n=65):
    start = date(2026, 1, 1)
    lines = ["date,code,open,high,low,close,volume"]
    for code in codes:
        for i in range(n):
            d = (start + timedelta(days=i)).isoformat()
            px = 100 + i
            lines.append(f"{d},{code},{px},{px + 1},{px - 1},{px},1000")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_get_watch_signals_with_fixture(tmp_path, monkeypatch):
    csv_path = tmp_path / "ohlcv_us.csv"
    _write_fixture(csv_path, ["AAPL", "MSFT", "NVDA", "TSLA", "SPY", "QQQ"], 65)
    monkeypatch.setattr(us_market_store, "OHLCV_US_PATH", csv_path)

    out = ws.get_us_watch_signals()
    assert out["market_bias"] == "bullish"          # SPY/QQQ 上升 → 站上 MA60
    assert out["as_of"] is not None
    assert len(out["signals"]) == 6
    for s in out["signals"]:
        assert s["signal"] in VALID_SIGNALS
        for key in ("code", "name", "close", "status", "signal", "reasons",
                    "risk_notes", "priority", "data_as_of"):
            assert key in s
        assert isinstance(s["reasons"], list) and isinstance(s["risk_notes"], list)
    # 依 priority 由高到低排序
    prios = [s["priority"] for s in out["signals"]]
    assert prios == sorted(prios, reverse=True)


def test_get_watch_signals_no_data_is_honest(tmp_path, monkeypatch):
    monkeypatch.setattr(us_market_store, "OHLCV_US_PATH", tmp_path / "missing.csv")
    out = ws.get_us_watch_signals()
    assert out["market_bias"] == "unknown"
    assert out["as_of"] is None
    assert len(out["signals"]) >= 1
    assert all(s["signal"] == "avoid_weak" for s in out["signals"])


# ── 端點 ─────────────────────────────────────────────────────────────────────

def test_us_signals_endpoint_schema():
    res = client.get("/api/markets/us/signals")
    assert res.status_code == 200
    body = res.json()
    assert body["market_bias"] in {"bullish", "bearish", "mixed", "unknown"}
    assert isinstance(body["signals"], list)
    for s in body["signals"]:
        assert s["signal"] in VALID_SIGNALS
        assert "priority" in s and "reasons" in s
