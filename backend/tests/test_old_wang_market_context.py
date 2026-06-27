from app.services.signals_service import _market_context


def _row(day: int, close: float, volume: int = 1_000_000) -> dict:
    return {
        "date": f"2026-05-{day:02d}",
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": volume,
    }


def _series(base: float, step: float, n: int = 80) -> list[dict]:
    return [_row(i + 1, base + i * step) for i in range(n)]


def test_old_wang_market_regime_is_strong_when_tse_and_otc_hold_ma5_ma10_and_volume_lows():
    ohlcv = {
        "TSE": _series(100, 1),
        "OTC": _series(50, 0.5),
        "0050": _series(80, 0.8),
    }
    for code in ("TSE", "OTC"):
        rows = ohlcv[code]
        rows[-4]["volume"] = 5_000_000
        rows[-4]["low"] = rows[-4]["close"] - 2
        rows[-1]["close"] = rows[-1]["close"] + 3
        rows[-1]["low"] = rows[-4]["low"] + 1

    ctx = _market_context(ohlcv)

    assert ctx["old_wang_market_regime"] == "strong"
    assert ctx["old_wang_market_filter"] == "allow"
    assert ctx["old_wang_market_source"] == "TSE/OTC"


def test_old_wang_market_regime_is_risk_when_one_index_breaks_volume_low():
    ohlcv = {
        "TSE": _series(100, 1),
        "OTC": _series(50, 0.5),
        "0050": _series(80, 0.8),
    }
    ohlcv["TSE"][-4]["volume"] = 5_000_000
    ohlcv["TSE"][-4]["low"] = 170
    ohlcv["TSE"][-1]["low"] = 160
    ohlcv["TSE"][-1]["close"] = 162

    ctx = _market_context(ohlcv)

    assert ctx["old_wang_market_regime"] == "risk"
    assert ctx["old_wang_market_filter"] == "block"


def test_old_wang_market_context_keeps_exchange_filters_separate():
    ohlcv = {
        "TSE": _series(100, 1),
        "OTC": _series(50, 0.5),
        "0050": _series(80, 0.8),
    }
    for code in ("TSE", "OTC"):
        rows = ohlcv[code]
        rows[-4]["volume"] = 5_000_000
        rows[-4]["low"] = rows[-4]["close"] - 2
        rows[-1]["close"] = rows[-1]["close"] + 3
        rows[-1]["low"] = rows[-4]["low"] + 1

    ohlcv["OTC"][-1]["low"] = ohlcv["OTC"][-4]["low"] - 5
    ohlcv["OTC"][-1]["close"] = ohlcv["OTC"][-4]["low"] - 4

    ctx = _market_context(ohlcv)
    by_exchange = ctx["old_wang_market_by_exchange"]

    assert by_exchange["TWSE"]["old_wang_market_filter"] == "allow"
    assert by_exchange["TWSE"]["old_wang_market_source"] == "TSE"
    assert by_exchange["TPEX"]["old_wang_market_filter"] == "block"
    assert by_exchange["TPEX"]["old_wang_market_source"] == "OTC"


def test_old_wang_market_context_falls_back_to_benchmark_when_tse_otc_missing():
    ohlcv = {"0050": _series(80, 0.8)}

    ctx = _market_context(ohlcv)

    assert ctx["old_wang_market_source"] == "0050"
    assert ctx["old_wang_market_regime"] in ("strong", "caution", "risk", "unknown")


def test_old_wang_market_context_falls_back_when_tse_otc_rows_are_insufficient():
    ohlcv = {
        "TSE": _series(100, 1, n=6),
        "OTC": _series(50, 0.5, n=6),
        "0050": _series(80, 0.8, n=80),
    }

    ctx = _market_context(ohlcv)

    assert ctx["old_wang_market_source"] == "0050"
    assert ctx["old_wang_market_filter"] == "allow"


def test_old_wang_market_context_uses_tse_otc_after_short_ma_window_is_ready():
    ohlcv = {
        "TSE": _series(100, 1, n=12),
        "OTC": _series(50, 0.5, n=12),
        "0050": _series(80, 0.8, n=80),
    }
    for code in ("TSE", "OTC"):
        rows = ohlcv[code]
        rows[-4]["volume"] = 5_000_000
        rows[-4]["low"] = rows[-4]["close"] - 2
        rows[-1]["close"] = rows[-1]["close"] + 3
        rows[-1]["low"] = rows[-4]["low"] + 1

    ctx = _market_context(ohlcv)

    assert ctx["old_wang_market_source"] == "TSE/OTC"
    assert ctx["old_wang_market_filter"] == "allow"
