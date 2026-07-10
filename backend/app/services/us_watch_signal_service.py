"""
us_watch_signal_service.py — 美股 Phase 3：觀察訊號（**非推薦、非買賣建議、非下單**）。

在 Phase 2 的基本技術指標（close / MA20 / MA60 / RSI14 / 20日漲跌幅 / 距 MA20 /
新鮮度）之上，產生**描述性觀察訊號**，並用 SPY / QQQ 當大盤基準調整個股觀察優先度。

明確不做：買賣建議、下單、正式推薦；**不套用台股 old_wang / steady_momentum**；
不改台股主流程。與台股完全分離、自帶輕量規則（複用 us_analysis_service 指標）。
"""

from __future__ import annotations

from app.services.us_analysis_service import (
    OVERHEATED_DIST_MA20,
    OVERHEATED_RSI,
    get_us_analysis,
)
from app.storage.us_market_store import load_us_ohlcv

BENCHMARKS = ("SPY", "QQQ")
MIN_SIGNAL_ROWS = 60          # 需算得出 MA60 才做趨勢/觀察判斷
NEAR_HIGH_RATIO = 0.985       # 收盤在 20 日高的 1.5% 內視為「逼近高點」

SIGNAL_LABELS = {
    "watch_breakout": "觀察突破",
    "watch_pullback": "觀察回檔",
    "trend_up":       "趨勢向上",
    "overheated":     "過熱",
    "avoid_weak":     "偏弱 / 資料不足",
}

# priority 為「觀察優先度（排序用）」——**非推薦分數、非買賣訊號**。數字越大越優先看。
_BASE_PRIORITY = {"watch_breakout": 80, "watch_pullback": 70, "trend_up": 60, "overheated": 40, "avoid_weak": 10}
_MARKET_ADJ = {"bullish": 0, "mixed": -15, "bearish": -25, "unknown": -10}

_MARKET_NOTE = {
    "bullish": "SPY / QQQ 皆在 MA60 上方，大盤偏多",
    "bearish": "SPY / QQQ 皆在 MA60 下方，大盤偏弱（個股觀察優先度降級）",
    "mixed":   "SPY / QQQ 分歧，大盤中性",
    "unknown": "大盤基準（SPY/QQQ）資料不足",
}
_MARKET_REASON = {
    "bullish": "大盤（SPY/QQQ）在 MA60 上方",
    "bearish": "大盤（SPY/QQQ）在 MA60 下方",
    "mixed":   "大盤（SPY/QQQ）分歧",
    "unknown": "大盤基準資料不足",
}


def _is_num(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _recent_high(rows: list[dict], n: int = 20) -> float | None:
    highs = [float(r["high"]) for r in rows[-n:] if _is_num(r.get("high"))]
    return max(highs) if highs else None


def _market_context(by_code: dict) -> tuple[str, dict]:
    detail: dict = {}
    flags: list = []
    for b in BENCHMARKS:
        it = by_code.get(b)
        close = it["last_close"] if it else None
        ma60 = it["ma60"] if it else None
        above = (close >= ma60) if (close is not None and ma60 is not None) else None
        detail[b] = {"above_ma60": above, "close": close, "ma60": ma60}
        flags.append(above)
    if any(f is None for f in flags):
        return "unknown", detail
    if all(flags):
        return "bullish", detail
    if not any(flags):
        return "bearish", detail
    return "mixed", detail


def derive_watch_signal(
    *,
    close: float | None,
    ma20: float | None,
    ma60: float | None,
    rsi: float | None,
    dist_ma20: float | None,
    row_count: int,
    recent_high: float | None,
    market_bias: str,
) -> tuple[str, list[str], list[str]]:
    """
    純函式：由指標推出觀察訊號 + reasons + risk_notes（描述性，非買賣建議）。
    優先序：資料不足 → 跌破 MA60（弱）→ 過熱 → 回檔（跌破 MA20 但守 MA60）→ 逼近高（突破觀察）→ 趨勢延續。
    """
    if row_count < MIN_SIGNAL_ROWS or ma20 is None or ma60 is None or close is None:
        return "avoid_weak", ["資料不足或尚未回補（需 ≥ 60 筆）"], ["資料不足，暫不判斷"]

    overheated = (rsi is not None and rsi >= OVERHEATED_RSI) or (
        dist_ma20 is not None and dist_ma20 >= OVERHEATED_DIST_MA20
    )
    near_high = recent_high is not None and close >= recent_high * NEAR_HIGH_RATIO

    reasons: list[str] = []
    risks: list[str] = []

    if close < ma60:
        sig = "avoid_weak"
        reasons.append(f"收盤 {close:.2f} 在 MA60 {ma60} 下方（長線偏弱）")
        risks.append("長線趨勢偏弱，觀察優先度低")
    elif overheated:
        sig = "overheated"
        if rsi is not None and rsi >= OVERHEATED_RSI:
            reasons.append(f"RSI {rsi} 偏高")
        if dist_ma20 is not None and dist_ma20 >= OVERHEATED_DIST_MA20:
            reasons.append(f"距 MA20 +{dist_ma20}%")
        risks.append("追高風險，留意拉回")
    elif close < ma20:
        sig = "watch_pullback"
        reasons.append(f"回檔至 MA20 {ma20} 下方，但守住 MA60 {ma60}")
        risks.append("跌破 MA60 則轉弱")
    elif near_high:
        sig = "watch_breakout"
        reasons.append(f"站上 MA20 / MA60，逼近 20 日高 {recent_high:.2f}")
        risks.append("留意假突破 / 量能不足")
    else:
        sig = "trend_up"
        reasons.append(f"收盤 {close:.2f} 站上 MA20 {ma20} 與 MA60 {ma60}")
        risks.append("趨勢延續中，非入場建議")

    reasons.append(_MARKET_REASON[market_bias])
    if market_bias in ("bearish", "mixed", "unknown") and sig != "avoid_weak":
        risks.append("大盤偏弱，個股觀察優先度已降級")
    return sig, reasons, risks


def get_us_watch_signals() -> dict:
    """
    美股觀察訊號總表。ohlcv_us.csv 不存在 / 無資料時，誠實回傳每檔 avoid_weak、
    market_bias=unknown（不假裝有訊號）。
    """
    analysis = get_us_analysis()
    by_code = {x["code"]: x for x in analysis}
    ohlcv = load_us_ohlcv()
    bias, benchmarks = _market_context(by_code)
    dates = [x["last_data_as_of"] for x in analysis if x["last_data_as_of"]]

    signals: list[dict] = []
    for a in analysis:
        rows = ohlcv.get(a["code"], [])
        signal, reasons, risks = derive_watch_signal(
            close=a["last_close"], ma20=a["ma20"], ma60=a["ma60"], rsi=a["rsi14"],
            dist_ma20=a["dist_ma20_pct"], row_count=a["row_count"],
            recent_high=_recent_high(rows, 20), market_bias=bias,
        )
        signals.append({
            "code":         a["code"],
            "name":         a["name"],
            "category":      a.get("category", ""),
            "close":        a["last_close"],
            "status":       a["status"],          # Phase 2 技術狀態
            "signal":       signal,               # Phase 3 觀察訊號
            "signal_label": SIGNAL_LABELS[signal],
            "reasons":      reasons,
            "risk_notes":   risks,
            "priority":     max(0, _BASE_PRIORITY[signal] + _MARKET_ADJ[bias]),
            "data_as_of":   a["last_data_as_of"],
        })
    signals.sort(key=lambda s: (-s["priority"], s["code"]))

    return {
        "as_of":       max(dates) if dates else None,
        "market_bias": bias,
        "market_note": _MARKET_NOTE[bias],
        "benchmarks":  benchmarks,
        "signals":     signals,
    }
