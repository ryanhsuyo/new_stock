"""
markets.py — 市場（region）相關 HTTP 端點。

目前僅美股 Phase 1 的唯讀端點：清單與資料源狀態。router 只做 HTTP，不做計算。
台股端點維持在既有 stocks / system router，不受影響。
"""

from fastapi import APIRouter, HTTPException

from app.services.us_analysis_service import get_us_analysis, get_us_stock_analysis
from app.services.us_market_service import (
    get_us_data_freshness,
    get_us_market_status,
    get_us_universe,
)
from app.services.us_strategy_service import get_us_trend_follow
from app.services.us_watch_signal_service import get_us_watch_signals
from app.services.us_wbottom_service import get_us_wbottom
from app.services.us_strategy_validation_service import run_us_strategy_validation
from app.services.us_update_service import get_us_update_status, trigger_us_background_update

router = APIRouter()


@router.get("/markets/us/universe")
def us_universe() -> list[dict]:
    """美股追蹤清單 + 基本行情狀態（region=US）。缺資料時 has_data=False。"""
    return get_us_universe()


@router.get("/markets/us/status")
def us_status() -> dict:
    """美股資料源 / 資料狀態：source_configured 反映資料源是否就緒。"""
    return get_us_market_status()


@router.get("/markets/us/update-status")
def us_update_status() -> dict:
    return get_us_update_status()


@router.post("/markets/us/update-now")
def us_update_now(months: int = 1) -> dict:
    try:
        return trigger_us_background_update(months)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/markets/us/data-freshness")
def us_data_freshness() -> dict:
    """美股資料新鮮度精簡契約：source / last_updated / stale。供前端 freshness badge。"""
    return get_us_data_freshness()


@router.get("/markets/us/analysis")
def us_analysis() -> list[dict]:
    """美股基本技術狀態（MA/RSI/漲跌幅/距均線/新鮮度 + 描述性狀態）。非買賣建議。"""
    return get_us_analysis()


@router.get("/markets/us/analysis/{code}")
def us_stock_analysis(code: str, as_of: str | None = None) -> dict:
    result = get_us_stock_analysis(code, as_of)
    if result is None:
        raise HTTPException(status_code=404, detail=f"美股 {code.upper()} 不在追蹤清單")
    return result


@router.get("/markets/us/signals")
def us_signals() -> dict:
    """美股觀察訊號（含 SPY/QQQ 大盤基準）。**非推薦、非買賣建議、非下單。**"""
    return get_us_watch_signals()


@router.get("/markets/us/strategy/trend-follow")
def us_strategy_trend_follow() -> dict:
    """美股觀察策略 us_trend_follow（大盤守門的趨勢延續）。**非推薦、非買賣建議、非下單。**"""
    return get_us_trend_follow()


@router.get("/markets/us/strategy/w-bottom")
def us_strategy_wbottom() -> dict:
    """美股觀察策略 us_wbottom_target（W 底突破 + 量幅目標）。**非推薦、非買賣建議、非下單。**"""
    return get_us_wbottom()


@router.post("/markets/us/strategy-validation")
def us_strategy_validation(start: str, end: str) -> dict:
    """Run the approved US strategy replays for a requested date range."""
    try:
        return run_us_strategy_validation(start, end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
