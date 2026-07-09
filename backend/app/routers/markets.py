"""
markets.py — 市場（region）相關 HTTP 端點。

目前僅美股 Phase 1 的唯讀端點：清單與資料源狀態。router 只做 HTTP，不做計算。
台股端點維持在既有 stocks / system router，不受影響。
"""

from fastapi import APIRouter

from app.services.us_market_service import get_us_market_status, get_us_universe

router = APIRouter()


@router.get("/markets/us/universe")
def us_universe() -> list[dict]:
    """美股追蹤清單 + 基本行情狀態（region=US）。缺資料時 has_data=False。"""
    return get_us_universe()


@router.get("/markets/us/status")
def us_status() -> dict:
    """美股資料源 / 資料狀態：source_configured 反映是否已設定 FINNHUB_API_KEY。"""
    return get_us_market_status()
