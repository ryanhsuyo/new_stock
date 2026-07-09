"""
us_market_service.py — 美股 Phase 1 唯讀呈現邏輯（清單 + 基本行情）。

只讀 `us_leaders.json` × `ohlcv_us.csv` 做基本呈現；**不做美股訊號 / 策略 / 推薦 /
下單 / 交易決策**。與台股流程完全分離。
"""

from __future__ import annotations

from app.services.price_source import get_price_source
from app.storage.us_market_store import load_us_leaders, load_us_ohlcv


def get_us_universe() -> list[dict]:
    """
    回傳美股追蹤清單的資料狀態（us_leaders.json × ohlcv_us.csv 交叉比對）。

    每筆：code / name / region('US') / has_data / row_count / last_data_as_of /
    last_close / data_status（"ok" | "no_data"）。
    """
    leaders = load_us_leaders()
    ohlcv = load_us_ohlcv()

    result: list[dict] = []
    for item in leaders:
        code = item["code"]
        rows = ohlcv.get(code, [])
        row_count = len(rows)
        last_row = rows[-1] if rows else None
        result.append({
            "code":            code,
            "name":            item["name"],
            "region":          "US",
            "has_data":        row_count > 0,
            "row_count":       row_count,
            "last_data_as_of": last_row["date"] if last_row else None,
            "last_close":      _to_float(last_row["close"]) if last_row else None,
            "data_status":     "ok" if row_count > 0 else "no_data",
        })
    return sorted(result, key=lambda x: x["code"])


def get_us_market_status() -> dict:
    """
    美股資料源 / 資料狀態摘要，供前端誠實呈現「尚未設定資料源 / 尚未更新」。
    """
    source = get_price_source("US")
    universe = get_us_universe()
    with_data = [u for u in universe if u["has_data"]]
    last_dates = [u["last_data_as_of"] for u in with_data if u["last_data_as_of"]]

    return {
        "region":              "US",
        # source_configured：是否已設定 FINNHUB_API_KEY（不外洩 key 本身）
        "source_configured":   source.is_available(),
        "source_label":        getattr(source, "label", "US"),
        "universe_size":       len(universe),
        "tickers_with_data":   len(with_data),
        "last_data_as_of":     max(last_dates) if last_dates else None,
        "backfill_command":    "cd backend && python3 scripts/backfill_ohlcv_us.py",
    }


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
