"""交易價與同日 OHLCV 的唯讀完整性檢查。"""

from __future__ import annotations

from app.models.trade import TradeRecord
from app.services.signals_service import _load_ohlcv
from app.storage.json_store import load_trades


def build_trade_integrity_report(
    trades: list[TradeRecord] | None = None,
    ohlcv: dict[str, list[dict]] | None = None,
    *,
    tolerance_pct: float = 1.0,
) -> dict:
    records = trades if trades is not None else load_trades()
    market = ohlcv if ohlcv is not None else _load_ohlcv(None)
    by_key = {
        (code, str(row.get("date"))): row
        for code, rows in market.items()
        for row in rows
    }
    items: list[dict] = []
    for trade in records:
        row = by_key.get((trade.stock_id, trade.date))
        if row is None:
            items.append({
                "trade_id": trade.id,
                "status": "unverified",
                "reason": "同日行情不存在，請確認交易日或股票代碼",
            })
            continue
        low = float(row["low"])
        high = float(row["high"])
        close = float(row["close"])
        lower = low * (1 - tolerance_pct / 100)
        upper = high * (1 + tolerance_pct / 100)
        if lower <= trade.price <= upper:
            items.append({
                "trade_id": trade.id,
                "status": "ok",
                "reason": "成交價在同日高低區間內",
                "day_low": low,
                "day_high": high,
                "day_close": close,
            })
            continue
        anchor = low if trade.price < low else high
        items.append({
            "trade_id": trade.id,
            "status": "warning",
            "reason": "成交價落在同日高低區間外，請確認價格、日期、單位或除權息尺度",
            "day_low": low,
            "day_high": high,
            "day_close": close,
            "difference_pct": round((trade.price / anchor - 1) * 100, 2),
        })

    warning_count = sum(item["status"] == "warning" for item in items)
    unverified_count = sum(item["status"] == "unverified" for item in items)
    return {
        "checked_count": len(items),
        "warning_count": warning_count,
        "unverified_count": unverified_count,
        "performance_status": "provisional" if warning_count or unverified_count else "verified",
        "items": items,
    }
