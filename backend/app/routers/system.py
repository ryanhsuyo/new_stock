from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.system import (
    DataStatus,
    FundamentalsPriorityMergeRequest,
    FundamentalsPriorityMergeResult,
    FundamentalsStatus,
    PmWorklist,
    TradingSettings,
    UpdateWorkflowStatus,
    WorkflowStatus,
)
from app.services.daily_check_service import get_daily_check_report
from app.services.fundamental_service import get_fundamentals_status, get_priority_fill_csv_path, merge_priority_fill_csv
from app.services.pm_worklist_service import get_pm_worklist
from app.services.settings_service import get_trading_settings
from app.services.update_service import get_data_status, trigger_background_update
from app.services.update_workflow_service import get_update_workflow_status
from app.services.workflow_service import get_workflow_status

router = APIRouter()


@router.get("/system/data-status", response_model=DataStatus)
def data_status() -> DataStatus:
    """
    查詢資料更新狀態。

    回傳欄位：
      - last_run_started_at   : 最後一次更新開始時間
      - last_run_finished_at  : 最後一次更新完成時間
      - last_run_status       : success | failed | running | stale | null
      - last_error            : 失敗訊息（成功時為 null）
      - last_warning          : 警告訊息（例如更新完成但資料仍過期）
      - last_data_as_of       : 資料最新日（YYYY-MM-DD）
      - is_stale              : 資料是否已超過 2 天未更新
      - stale_days            : 距離最新資料日的日曆天數（資料不存在時為 null）
    """
    return DataStatus(**get_data_status())


@router.get("/system/daily-check")
def daily_check() -> dict:
    """讀取每日 PM 摘要；由 scripts/daily_check.py --write-report 產生。"""
    report = get_daily_check_report()
    if report is None:
        raise HTTPException(status_code=404, detail="尚無 daily_check.json，請先執行 python3 scripts/daily_check.py --write-report")
    return report


@router.get("/system/fundamentals-status", response_model=FundamentalsStatus)
def fundamentals_status() -> FundamentalsStatus:
    """查詢巴菲特基本面資料對 leaders 清單的覆蓋率。"""
    return FundamentalsStatus(**get_fundamentals_status())


@router.get("/system/fundamentals-priority-fill")
def fundamentals_priority_fill() -> FileResponse:
    """下載巴菲特基本面優先補資料 CSV。"""
    path = get_priority_fill_csv_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="尚無基本面優先補資料 CSV")
    return FileResponse(
        path=str(path),
        media_type="text/csv",
        filename="fundamentals_priority_fill.csv",
    )


@router.post("/system/fundamentals-priority-fill/merge", response_model=FundamentalsPriorityMergeResult)
def merge_fundamentals_priority_fill(payload: FundamentalsPriorityMergeRequest) -> FundamentalsPriorityMergeResult:
    """預覽或正式合併基本面優先補資料 CSV。"""
    try:
        return FundamentalsPriorityMergeResult(**merge_priority_fill_csv(
            dry_run=payload.dry_run,
            confirm=payload.confirm,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/system/settings/trading", response_model=TradingSettings)
def trading_settings() -> TradingSettings:
    """讀取交易費率設定，供前端估算交易成本。"""
    return TradingSettings(**get_trading_settings())


@router.get("/system/workflow-status", response_model=WorkflowStatus)
def workflow_status() -> WorkflowStatus:
    """PM 視角的每日工作流狀態：目前能不能操作，以及下一步優先做什麼。"""
    return WorkflowStatus(**get_workflow_status())


@router.get("/system/pm-worklist", response_model=PmWorklist)
def pm_worklist() -> PmWorklist:
    """PM 首頁工作佇列：跨資料修復、基本面、候選復盤與 Daily Check 的優先順序。"""
    return PmWorklist(**get_pm_worklist())


@router.get("/system/update-workflow", response_model=UpdateWorkflowStatus)
def update_workflow() -> UpdateWorkflowStatus:
    """每日更新流程狀態：告訴 Dashboard 目前卡在哪一步，以及下一個可執行動作。"""
    return UpdateWorkflowStatus(**get_update_workflow_status())


@router.post("/system/update-now")
def update_now() -> dict:
    """
    手動觸發資料更新（backfill + signals）。

    - 若目前已在執行中，回傳 409。
    - 否則在背景啟動更新，立即回傳 202-like dict。
    - 進度請透過 GET /api/system/data-status 輪詢。
    """
    result = trigger_background_update(months=1)
    if result["status"] == "already_running":
        raise HTTPException(
            status_code=409,
            detail={"message": "資料更新已在執行中，請稍候", "status": "running"},
        )
    return {"message": "資料更新已開始", "status": "started"}
