import json
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse

from app.models.analysis import StockAnalysis
from app.models.market_note import MarketNoteInput
from app.models.stock import IntradayMonitor, StockRecommendation, StockTrackingRequest, StockTrackingResult
from app.services.analysis_service import analyse_stock
from app.services.daily_brief_service import get_daily_brief, get_manual_watchlist_review
from app.services.intraday_service import monitor_intraday
from app.services.leader_service import add_stock_to_tracking
from app.services.market_note_service import list_market_notes, upsert_market_note
from app.services.signals_service import (
    check_required_files,
    get_signals_status,
    get_summary,
    get_universe,
    get_universe_report_json,
    trigger_background_signals,
)
from app.services.stock_service import get_recommendations

router = APIRouter()

_OUT = Path(__file__).resolve().parent.parent.parent / "out"


# ── /stocks/universe must be declared BEFORE /stocks/{code}/... ───────────────

@router.get("/stocks/universe")
def stocks_universe() -> list[dict]:
    """
    回傳目前追蹤股票的資料狀態清單（leaders.json × ohlcv.csv 交叉比對）。

    每筆包含：code, name, has_data, row_count, last_data_as_of, data_status
    data_status: "ok" | "insufficient" | "no_data"
    """
    return get_universe()


@router.get("/stocks/{code}/analysis", response_model=StockAnalysis)
def get_stock_analysis(
    code: str,
    as_of: str | None = Query(default=None, description="基準日 YYYY-MM-DD，預設今日"),
) -> StockAnalysis:
    """
    單檔股票深度分析：支撐壓力線、趨勢線、訊號、reasons、risk_notes。
    資料不足時回傳 data_ok=false 並說明原因，不拋 500。
    """
    return analyse_stock(code, as_of_date=as_of)


@router.post("/stocks/{code}/tracking", response_model=StockTrackingResult)
def add_tracking_stock(code: str, payload: StockTrackingRequest) -> StockTrackingResult:
    """把單檔加入 leaders.json 的手動追蹤群組；不觸發長時間回補。"""
    try:
        result = add_stock_to_tracking(code, name=payload.name, group=payload.group or "手動追蹤")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StockTrackingResult(**result)


@router.get("/stocks/{code}/intraday-monitor", response_model=IntradayMonitor)
def get_intraday_monitor(
    code: str,
    price: float | None = Query(default=None, description="盤中價格；未傳則用最新收盤價作監控基準"),
    open_price: float | None = Query(default=None, description="盤中開盤價，用於判斷上下跳空"),
    high: float | None = Query(default=None, description="盤中最高價"),
    low: float | None = Query(default=None, description="盤中最低價"),
    volume: int | None = Query(default=None, description="盤中累積成交量"),
) -> IntradayMonitor:
    """
    盤中監控：只檢查日線計畫是否被盤中價格破壞。

    這個 endpoint 不產生正式 BUY/SELL/HOLD；正式訊號仍由收盤後 signals 流程產生。
    """
    return monitor_intraday(
        code,
        price=price,
        open_price=open_price,
        high=high,
        low=low,
        volume=volume,
    )


@router.get("/stocks/recommendations", response_model=list[StockRecommendation])
def list_recommendations(
    strategy: str = Query(
        default="core",
        description="core=核心技術策略V2；old_wang=老王短波段；buffett=巴菲特長期品質價值",
    ),
) -> list[StockRecommendation]:
    return get_recommendations(strategy=strategy)


@router.get("/stocks/market-notes")
def get_market_notes() -> list[dict]:
    """列出人工盤後筆記，依日期新到舊排序。"""
    return list_market_notes()


@router.post("/stocks/market-notes")
def save_market_note(note: MarketNoteInput) -> dict:
    """新增或覆蓋指定日期的人工盤後筆記。"""
    return upsert_market_note(note.model_dump())


# ---------------------------------------------------------------------------
# 訊號 endpoints
# ---------------------------------------------------------------------------

@router.get("/stocks/signals/status")
def signals_status() -> dict:
    """回傳 out/ 各檔案存在狀態、最後更新時間、summary 的 as_of / generated_at。"""
    return get_signals_status()


@router.post("/stocks/signals/run")
def trigger_signals(as_of_date: str | None = Body(default=None, embed=True)) -> dict:
    """
    在背景執行訊號計算，立即回傳 202-like dict。
    Body（JSON，選填）：{"as_of_date": "YYYY-MM-DD"}

    - 前置條件不足時回傳 400
    - 已在執行中時回傳 409
    - 否則立即回傳 {"message": "...", "status": "started"}
    - 進度請透過 GET /api/stocks/signals/status 的 run_status 欄位輪詢
    """
    missing = check_required_files()
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "缺少必要資料檔，請先執行 backfill 或建立對應檔案",
                "missing_files": missing,
            },
        )
    result = trigger_background_signals(as_of_date=as_of_date)
    if result["status"] == "already_running":
        raise HTTPException(
            status_code=409,
            detail={"message": "訊號計算已在執行中，請稍候", "status": "running"},
        )
    return {"message": "訊號計算已開始", "status": "started"}


@router.get("/stocks/signals/summary")
def get_signals_summary() -> dict:
    """讀取最近一次 run 產生的 summary.json。"""
    data = get_summary()
    if not data:
        raise HTTPException(
            status_code=404,
            detail="尚無訊號資料，請先呼叫 POST /api/stocks/signals/run",
        )
    return data


@router.get("/stocks/signals/daily-brief")
def get_signals_daily_brief() -> dict:
    """讀取最近一次 run 產生的 daily_brief.json。"""
    data = get_daily_brief(_OUT)
    if not data:
        raise HTTPException(
            status_code=404,
            detail="尚無每日作戰報告，請先呼叫 POST /api/stocks/signals/run",
        )
    return data


@router.get("/stocks/signals/manual-watchlist-review")
def get_signals_manual_watchlist_review() -> dict:
    """讀取人工盤後觀察股逐檔校正表。"""
    data = get_manual_watchlist_review(_OUT)
    if not data:
        raise HTTPException(
            status_code=404,
            detail="尚無人工觀察股校正表，請先產生 daily_brief.json",
        )
    return data


@router.get("/stocks/signals/universe-report")
def get_universe_report_as_json() -> list[dict]:
    """讀取最近一次 run 產生的 universe_report.csv，以 JSON array 回傳。"""
    data = get_universe_report_json()
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="尚無報表資料，請先呼叫 POST /api/stocks/signals/run",
        )
    return data


@router.get("/stocks/signals/universe_report")
def get_universe_report() -> FileResponse:
    """下載最近一次 run 產生的 universe_report.csv。"""
    path = _OUT / "universe_report.csv"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="尚無報表資料，請先呼叫 POST /api/stocks/signals/run",
        )
    return FileResponse(
        path=str(path),
        media_type="text/csv",
        filename="universe_report.csv",
    )
