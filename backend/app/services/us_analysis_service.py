"""
us_analysis_service.py — 美股 Phase 2：基本技術狀態（唯讀，非策略、非買賣建議）。

從 ohlcv_us.csv 讀美股資料，算基本技術指標（MA20 / MA60 / RSI14 / 20 日漲跌幅 /
距 MA20、MA60 / 資料新鮮度），並歸類成**描述性技術狀態**（trend_up /
recovering / pullback_watch / overheated / weak / no_data）。

**不套用 old_wang / steady_momentum，不產生買賣建議，不下單。** 與台股流程分離、
自帶輕量指標函式（不耦合 signals_service）。
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.storage.us_market_store import load_us_leaders, load_us_ohlcv

MIN_ROWS = 20          # 至少要能算 MA20 才做技術判斷
RSI_PERIOD = 14
OVERHEATED_RSI = 70.0
OVERHEATED_DIST_MA20 = 15.0   # 距 MA20 超過 +15% 視為過熱

STATUS_LABELS = {
    "trend_up":       "趨勢向上",
    "recovering":     "趨勢修復中",
    "pullback_watch": "回檔觀察",
    "overheated":     "過熱",
    "weak":           "弱勢",
    "no_data":        "資料不足",
}


def _is_num(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _closes(rows: list[dict]) -> list[float]:
    return [float(r["close"]) for r in rows if _is_num(r.get("close"))]


def _sma(vals: list[float], n: int) -> float | None:
    return round(sum(vals[-n:]) / n, 2) if len(vals) >= n else None


def _rsi(vals: list[float], period: int = RSI_PERIOD) -> float | None:
    if len(vals) < period + 1:
        return None
    deltas = [vals[i] - vals[i - 1] for i in range(len(vals) - period, len(vals))]
    gains = sum(d for d in deltas if d > 0)
    losses = sum(-d for d in deltas if d < 0)
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    rs = (gains / period) / (losses / period)
    return round(100 - 100 / (1 + rs), 1)


def _pct_change(vals: list[float], n: int) -> float | None:
    if len(vals) < n + 1:
        return None
    prev = vals[-1 - n]
    if prev == 0:
        return None
    return round((vals[-1] - prev) / prev * 100, 2)


def _dist_pct(last: float | None, ma: float | None) -> float | None:
    if last is None or ma in (None, 0):
        return None
    return round((last - ma) / ma * 100, 2)


def _days_since(last_date: str | None, today: date) -> int | None:
    if not last_date:
        return None
    try:
        d = datetime.strptime(last_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    return max(0, (today - d).days)


def classify_status(
    row_count: int,
    close: float | None,
    ma20: float | None,
    ma60: float | None,
    rsi: float | None,
    dist_ma20: float | None,
) -> str:
    """
    描述性技術狀態（非買賣建議）。依序判斷：
      - no_data：資料不足（< MIN_ROWS）或算不出 MA20 / 收盤 —— **只代表無法計算**。
      - overheated：RSI >= 70 或 距 MA20 >= +15%。
      - weak：收盤跌破 MA60（長線偏弱）—— **真正弱勢，與 no_data 分開**。
      - trend_up：收盤 >= MA20，且（無 MA60 或 MA20 >= MA60，均線已翻多）。
      - recovering：收盤同時站上 MA20 與 MA60，但 MA20 < MA60（均線尚未翻多，趨勢修復中）。
      - pullback_watch：收盤 < MA20，但仍守住 MA60（或尚無 MA60）。
    """
    if row_count < MIN_ROWS or close is None or ma20 is None:
        return "no_data"
    if (rsi is not None and rsi >= OVERHEATED_RSI) or (
        dist_ma20 is not None and dist_ma20 >= OVERHEATED_DIST_MA20
    ):
        return "overheated"
    if ma60 is not None and close < ma60:
        return "weak"
    # 至此：無 MA60，或收盤已站上 MA60
    if close >= ma20:
        if ma60 is None or ma20 >= ma60:
            return "trend_up"
        return "recovering"
    return "pullback_watch"


def get_us_analysis() -> list[dict]:
    """回傳每檔美股的基本技術狀態；無資料時指標為 null、狀態 no_data（非 weak）。"""
    leaders = load_us_leaders()
    ohlcv = load_us_ohlcv()
    today = datetime.now(timezone.utc).date()

    out: list[dict] = []
    for item in leaders:
        code = item["code"]
        rows = ohlcv.get(code, [])
        closes = _closes(rows)
        row_count = len(closes)
        last_close = closes[-1] if closes else None
        last_date = rows[-1]["date"] if rows else None

        ma20 = _sma(closes, 20)
        ma60 = _sma(closes, 60)
        rsi = _rsi(closes)
        change_20d = _pct_change(closes, 20)
        dist20 = _dist_pct(last_close, ma20)
        dist60 = _dist_pct(last_close, ma60)
        days_since = _days_since(last_date, today)
        status = classify_status(row_count, last_close, ma20, ma60, rsi, dist20)

        out.append({
            "code":            code,
            "name":            item["name"],
            "category":        item.get("category", ""),
            "region":          "US",
            "data_status":     "ok" if row_count > 0 else "no_data",
            "row_count":       row_count,
            "last_data_as_of": last_date,
            "last_close":      last_close,
            "ma20":            ma20,
            "ma60":            ma60,
            "rsi14":           rsi,
            "change_20d_pct":  change_20d,
            "dist_ma20_pct":   dist20,
            "dist_ma60_pct":   dist60,
            "days_since_last": days_since,
            "status":          status,
            "status_label":    STATUS_LABELS[status],
        })
    return sorted(out, key=lambda x: x["code"])


def get_us_stock_analysis(code: str, as_of: str | None = None) -> dict | None:
    """Single-stock US research payload with a 120-bar chart window."""
    normalized = code.strip().upper()
    leaders = {item["code"]: item for item in load_us_leaders()}
    if normalized not in leaders:
        return None
    rows = load_us_ohlcv().get(normalized, [])
    if as_of:
        rows = [row for row in rows if row["date"] <= as_of]
    closes = _closes(rows)
    last = rows[-1] if rows else None
    ma20, ma60, rsi = _sma(closes, 20), _sma(closes, 60), _rsi(closes)
    close = float(last["close"]) if last and _is_num(last.get("close")) else None
    dist20 = _dist_pct(close, ma20)
    status = classify_status(len(closes), close, ma20, ma60, rsi, dist20)
    reasons = [f"技術狀態：{STATUS_LABELS[status]}"]
    if close is not None and ma20 is not None:
        reasons.append(f"收盤 {close:.2f}，相對 MA20 {dist20:+.2f}%")
    if ma20 is not None and ma60 is not None:
        reasons.append(f"MA20 {ma20:.2f} / MA60 {ma60:.2f}")
    risk_notes = [] if rows else ["尚無 OHLCV，無法計算技術狀態"]
    if len(rows) < 60:
        risk_notes.append(f"目前僅 {len(rows)} 筆，少於 MA60 所需 60 筆")
    item = leaders[normalized]
    return {"code": normalized, "name": item.get("name", normalized), "category": item.get("category", ""),
            "region": "US", "currency": "USD", "as_of": last["date"] if last else as_of,
            "row_count": len(rows), "data_ok": len(rows) >= MIN_ROWS, "close": close,
            "ma20": ma20, "ma60": ma60, "rsi14": rsi, "change_20d_pct": _pct_change(closes, 20),
            "dist_ma20_pct": dist20, "dist_ma60_pct": _dist_pct(close, ma60),
            "status": status, "status_label": STATUS_LABELS[status], "reasons": reasons,
            "risk_notes": risk_notes, "ohlcv": rows[-120:]}
