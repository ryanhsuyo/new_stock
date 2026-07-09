"""
markets.py — 市場（region）相關 HTTP 端點。

目前僅美股 Phase 1 的唯讀端點：清單與資料源狀態。router 只做 HTTP，不做計算。
台股端點維持在既有 stocks / system router，不受影響。
"""

from fastapi import APIRouter

from app.services.us_analysis_service import get_us_analysis
from app.services.us_market_service import get_us_market_status, get_us_universe

router = APIRouter()


@router.get("/markets/us/universe")
def us_universe() -> list[dict]:
    """美股追蹤清單 + 基本行情狀態（region=US）。缺資料時 has_data=False。"""
    return get_us_universe()


@router.get("/markets/us/status")
def us_status() -> dict:
    """美股資料源 / 資料狀態：source_configured 反映資料源是否就緒。"""
    return get_us_market_status()


@router.get("/markets/us/analysis")
def us_analysis() -> list[dict]:
    """美股基本技術狀態（MA/RSI/漲跌幅/距均線/新鮮度 + 描述性狀態）。非買賣建議。"""
    return get_us_analysis()
