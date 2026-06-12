"""
intraday_service.py — 盤中監控服務

本服務只做「日線計畫的盤中風控監控」，不產生正式 BUY/SELL 訊號。
正式訊號仍由 signals_service.run_daily_signals 以收盤日線輸出。
"""

from app.models.stock import IntradayMonitor
from app.services.signals_service import (
    MIN_ROWS,
    _avg_vol,
    _load_ohlcv,
    _ma,
    _old_wang_support_context,
    _stock_name,
    _volume_low_context,
)


def _round_price(value: float | None) -> float | None:
    return round(value, 2) if isinstance(value, (int, float)) else None


def _intraday_gap_context(rows: list[dict], open_price: float | None, low: float, high: float, price: float) -> dict:
    """
    用盤中開盤價與前一個收盤 K 的高低點判斷跳空。
    若未傳 open_price，回傳 none，避免用最新收盤 K 誤判盤中缺口。
    """
    if len(rows) < 1 or open_price is None:
        return {
            "gap_type": "none",
            "gap_support": None,
            "gap_resistance": None,
            "gap_broken": False,
            "note": "",
        }

    prev = rows[-1]
    if open_price > prev["high"]:
        support = round(prev["high"], 2)
        broken = low < support or price < support
        return {
            "gap_type": "gap_up",
            "gap_support": support,
            "gap_resistance": None,
            "gap_broken": broken,
            "note": f"盤中向上跳空，缺口支撐約 {support}",
        }

    if open_price < prev["low"]:
        resistance = round(prev["low"], 2)
        broken = high > resistance or price > resistance
        return {
            "gap_type": "gap_down",
            "gap_support": None,
            "gap_resistance": resistance,
            "gap_broken": broken,
            "note": f"盤中向下跳空，缺口壓力約 {resistance}",
        }

    return {
        "gap_type": "none",
        "gap_support": None,
        "gap_resistance": None,
        "gap_broken": False,
        "note": "",
    }


def monitor_intraday(
    code: str,
    *,
    price: float | None = None,
    open_price: float | None = None,
    high: float | None = None,
    low: float | None = None,
    volume: int | None = None,
) -> IntradayMonitor:
    """
    回傳盤中監控狀態。

    Parameters
    ----------
    code:
        股票代碼。
    price/open_price/high/low/volume:
        盤中資料。若未提供 price，使用最新收盤價做靜態檢查。

    Notes
    -----
    - 此函式不寫 out/，不改變 summary/universe_report。
    - `invalidates_daily_plan=True` 代表盤中已破壞原本隔日計畫的關鍵觀察點，
      但仍須等收盤後才更新正式 signals。
    """
    rows = _load_ohlcv(None).get(code, [])
    name = _stock_name(code)
    if len(rows) < MIN_ROWS:
        return IntradayMonitor(
            stock_id=code,
            name=name,
            data_ok=False,
            data_missing_reason=f"資料不足（僅 {len(rows)} 日，需 {MIN_ROWS} 日）",
            action="先補齊日線資料，再做盤中監控",
        )

    closes = [r["close"] for r in rows]
    baseline_close = closes[-1]
    current_price = float(price if price is not None else baseline_close)
    current_open = float(open_price) if open_price is not None else None
    current_high = float(high if high is not None else max(current_price, current_open or current_price))
    current_low = float(low if low is not None else min(current_price, current_open or current_price))

    ma5 = _ma(closes, 5)
    ma10 = _ma(closes, 10)
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)
    support = _old_wang_support_context(current_price, ma5, ma10, ma20, ma60)
    volume_low = _volume_low_context(rows, ma5)
    gap = _intraday_gap_context(rows, current_open, current_low, current_high, current_price)

    touched_ma_levels: list[str] = []
    broken_ma_levels: list[str] = []
    for label, ma_value in (("MA5", ma5), ("MA10", ma10), ("MA20", ma20), ("MA60", ma60)):
        if ma_value is None:
            continue
        if current_low <= ma_value <= current_high or abs(current_price / ma_value - 1) <= 0.005:
            touched_ma_levels.append(label)
        if current_price < ma_value:
            broken_ma_levels.append(label)

    warnings: list[str] = []
    notes: list[str] = []
    if support["state"] == "short_stop_trend_intact":
        notes.append("盤中仍守 5/10/20/60，多頭結構未破壞")
    elif support["state"] == "short_stop":
        notes.append("盤中守住 5/10，但 20/60 結構仍需觀察")
    elif support["state"] == "mid_trend_intact":
        warnings.append("盤中跌破 5/10，短線止跌尚未確認")
    elif support["state"] == "partial_ma_break":
        warnings.append(f"盤中已跌破 {support['ma_break_count']} 條均線，觀察是否收回 5/10")
    elif support["previous_high_risk"]:
        warnings.append("盤中跌破 5/10/20/60，全破才視為前高型態風險升高")

    volume_low_price = volume_low.get("price")
    volume_low_broken = (
        isinstance(volume_low_price, (int, float))
        and (current_price < volume_low_price or current_low < volume_low_price * 0.995)
    )
    if volume_low_broken:
        warnings.append(f"盤中跌破爆大量低點 {volume_low_price}")
    elif isinstance(volume_low_price, (int, float)):
        notes.append(f"爆大量低點 {volume_low_price} 仍是盤中支撐觀察")

    if gap["gap_type"] == "gap_up":
        if gap["gap_broken"]:
            warnings.append(f"向上跳空缺口支撐 {gap['gap_support']} 盤中被回補")
        else:
            notes.append(f"向上跳空缺口支撐 {gap['gap_support']} 盤中仍守住")
    elif gap["gap_type"] == "gap_down":
        if gap["gap_broken"]:
            notes.append(f"向下跳空壓力 {gap['gap_resistance']} 盤中被收復")
        else:
            warnings.append(f"向下跳空壓力 {gap['gap_resistance']} 尚未收復")

    avg_v = _avg_vol([r["volume"] for r in rows], 20)
    projected_vol_ratio = round(volume / avg_v, 2) if volume is not None and avg_v > 0 else None
    if projected_vol_ratio is not None:
        if projected_vol_ratio >= 1.2:
            notes.append(f"盤中量能已達近 20 日均量 {projected_vol_ratio:.2f}x，量能有支持")
        elif projected_vol_ratio < 0.5:
            warnings.append(f"盤中量能僅近 20 日均量 {projected_vol_ratio:.2f}x，避免只看單一 K 線")

    invalidates_daily_plan = bool(
        support["previous_high_risk"]
        or volume_low_broken
        or (gap["gap_type"] == "gap_up" and gap["gap_broken"])
    )
    if support["previous_high_risk"] or volume_low_broken:
        monitor_signal = "risk"
        action = "盤中已破壞關鍵支撐，先停止新進場；收盤若無法收回再重算正式訊號"
    elif warnings:
        monitor_signal = "caution"
        action = "盤中轉為警戒，等收盤確認是否收回 5/10 或缺口支撐"
    else:
        monitor_signal = "healthy"
        action = "盤中結構未破壞，仍依原本收盤日線計畫監控"

    return IntradayMonitor(
        stock_id=code,
        name=name,
        latest_closed_date=rows[-1]["date"],
        data_ok=True,
        current_price=_round_price(current_price),
        current_open=_round_price(current_open),
        current_high=_round_price(current_high),
        current_low=_round_price(current_low),
        current_volume=volume,
        baseline_close=_round_price(baseline_close),
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        ma60=ma60,
        projected_vol_ratio=projected_vol_ratio,
        support_state=support["state"],
        ma_break_count=support["ma_break_count"],
        previous_high_risk=support["previous_high_risk"],
        touched_ma_levels=touched_ma_levels,
        broken_ma_levels=broken_ma_levels,
        volume_low_price=volume_low_price,
        volume_low_broken=volume_low_broken,
        gap_type=gap["gap_type"],
        gap_support=gap["gap_support"],
        gap_resistance=gap["gap_resistance"],
        gap_broken=gap["gap_broken"],
        monitor_signal=monitor_signal,
        invalidates_daily_plan=invalidates_daily_plan,
        action=action,
        warnings=warnings,
        notes=notes,
    )
