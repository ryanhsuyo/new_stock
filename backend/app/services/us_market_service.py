"""
us_market_service.py — 美股 Phase 1 唯讀呈現邏輯（清單 + 基本行情）。

只讀 `us_leaders.json` × `ohlcv_us.csv` 做基本呈現；**不做美股訊號 / 策略 / 推薦 /
下單 / 交易決策**。與台股流程完全分離。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.services.markets import SUPPORTED_MARKETS
from app.services.price_source import get_price_source
from app.services.trading_calendar_service import (
    count_missed_trading_days_since,
    is_trading_day,
    previous_trading_day,
)
from app.storage.us_market_store import load_us_leaders, load_us_ohlcv

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

# 美股新鮮度判斷：weekend-aware、**不含 NYSE 假日**（依範圍，先不做完整假日曆）。
# 傳空 calendar 給既有 trading_calendar 函式，避免台股假日誤套到美股。
_US_CALENDAR = {"holidays": set(), "makeup_trading_days": set()}
# 容忍 1 個交易日，避免美股當日收盤前（EOD bar 尚未產生）被誤判為 stale。
STALE_TOLERANCE_TRADING_DAYS = 1


def _us_today() -> date:
    """目前的美股日期（以 America/New_York 為準；缺 tzdata 時退回 UTC）。"""
    tz = SUPPORTED_MARKETS["US"].timezone
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(tz)).date()
        except Exception:  # pragma: no cover
            pass
    return datetime.now(timezone.utc).date()


def _expected_trading_day(today: date) -> date:
    """今天若為交易日則今天，否則往前找最近交易日（weekend-aware，無假日）。"""
    return today if is_trading_day(today, _US_CALENDAR) else previous_trading_day(today, _US_CALENDAR)


def compute_us_freshness(last_data_as_of: str | None, today: date | None = None) -> dict:
    """
    依 last_data_as_of 估算資料新鮮度。
      - last_data_as_of 缺失 / 無法解析 → is_stale=True、days_since_last=None。
      - days_since_last：last_data_as_of 之後、到 expected_trading_day 為止的**交易日數**。
      - is_stale：落後超過 STALE_TOLERANCE_TRADING_DAYS 個交易日。
    """
    day = today or _us_today()
    expected = _expected_trading_day(day)
    result = {"expected_trading_day": expected.isoformat(), "days_since_last": None, "is_stale": True}
    if not last_data_as_of:
        return result
    try:
        last = datetime.strptime(last_data_as_of, "%Y-%m-%d").date()
    except ValueError:
        return result
    behind = count_missed_trading_days_since(
        last, today=expected + timedelta(days=1), calendar=_US_CALENDAR
    )
    result["days_since_last"] = behind
    result["is_stale"] = behind > STALE_TOLERANCE_TRADING_DAYS
    return result


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
    last_data_as_of = max(last_dates) if last_dates else None
    freshness = compute_us_freshness(last_data_as_of)

    return {
        "region":              "US",
        # source_configured：資料源是否就緒（Yahoo 免 key → 恆 True）
        "source_configured":   source.is_available(),
        "source_label":        getattr(source, "label", "US"),
        "universe_size":       len(universe),
        "tickers_with_data":   len(with_data),
        "last_data_as_of":     last_data_as_of,
        # 資料新鮮度（weekend-aware，容忍 1 個交易日；不含 NYSE 假日）
        "expected_trading_day": freshness["expected_trading_day"],
        "days_since_last":      freshness["days_since_last"],
        "is_stale":             freshness["is_stale"],
        "backfill_command":    "cd backend && python3.11 scripts/backfill_ohlcv_us.py",
    }


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
