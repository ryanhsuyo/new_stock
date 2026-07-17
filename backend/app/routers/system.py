from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.system import (
    DataStatus,
    FundamentalsPriorityMergeRequest,
    FundamentalsPriorityMergeResult,
    FundamentalsStatus,
    OfficialFundamentalsCoverageAudit,
    OfficialFundamentalsReportsRequest,
    OfficialFundamentalsReportsResult,
    OfficialFundamentalsStatus,
    PersonalBackupInfo,
    PersonalBackupResult,
    PersonalRestorePreview,
    PersonalRestoreRequest,
    PersonalRestoreResult,
    PmWorklist,
    PreMarketRiskReport,
    QualityMomentumLiteGuardCoverage,
    SignalAlertReviewRequest,
    SignalAlertReviewStatus,
    TradingSettings,
    UpdateWorkflowStatus,
    WorkflowStatus,
)
from app.services.daily_check_service import get_daily_check_report
from app.services.fundamental_service import get_fundamentals_status, get_priority_fill_csv_path, merge_priority_fill_csv
from app.services.official_fundamentals_api_service import (
    get_quality_momentum_lite_guard_coverage,
    get_official_fundamentals_coverage_audit,
    get_official_fundamentals_status,
    run_official_fundamentals_reports,
)
from app.services.personal_backup_service import (
    create_personal_backup,
    list_personal_backups,
    preview_personal_restore,
    restore_personal_backup,
)
from app.services.pm_worklist_service import get_pm_worklist
from app.services.pre_market_risk_service import get_pre_market_risk_report
from app.services.settings_service import get_trading_settings
from app.services.signal_alert_review_service import (
    acknowledge_current_signal_alerts,
    get_signal_alert_review_status,
)
from app.services.strategy_validation_service import load_strategy_validation_report, run_strategy_validation
from app.services.today_scan_service import load_today_scan_report
from app.services.update_service import get_data_status, trigger_background_update
from app.services.update_workflow_service import get_update_workflow_status
from app.services.workflow_service import get_workflow_status

router = APIRouter()


@router.get("/system/strategy-validation")
def strategy_validation() -> dict:
    """Read the latest generated walk-forward portfolio validation report."""
    report = load_strategy_validation_report()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="尚無台股策略驗收報告，請先產生 tw_portfolio_replay JSON",
        )
    return report


@router.post("/system/strategy-validation")
def generate_strategy_validation(start: str, end: str) -> dict:
    """Run a paper walk-forward replay for an explicit date range."""
    try:
        return run_strategy_validation(start, end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/system/data-status", response_model=DataStatus)
def data_status() -> DataStatus:
    """
    查詢資料更新狀態。

    回傳欄位：
      - last_run_started_at   : 最後一次更新開始時間
      - last_run_finished_at  : 最後一次更新完成時間
      - last_run_status       : success | failed | running | stalled | stale | null
      - last_error            : 失敗訊息（成功時為 null）
      - last_warning          : 警告訊息（例如更新完成但資料仍過期）
      - last_data_as_of       : 資料最新日（YYYY-MM-DD）
      - schedule_health_status: 排程執行健康狀態
      - schedule_is_overdue   : 是否錯過至少一個已結束的平日更新
      - schedule_health_message: 排程健康的可讀說明
      - is_stale              : 資料是否已超過 2 天未更新
      - stale_days            : 距離最新資料日的日曆天數（資料不存在時為 null）
    """
    return DataStatus(**get_data_status())


@router.get("/system/pre-market-risk", response_model=PreMarketRiskReport)
def pre_market_risk() -> PreMarketRiskReport:
    """讀取本機隔夜行情與事件筆記，回傳可解釋的盤前風險提示。"""
    return PreMarketRiskReport(**get_pre_market_risk_report())


@router.get("/system/daily-check")
def daily_check() -> dict:
    """讀取每日 PM 摘要；由 scripts/daily_check.py --write-report 產生。"""
    report = get_daily_check_report()
    if report is None:
        raise HTTPException(status_code=404, detail="尚無 daily_check.json，請先執行 python3 scripts/daily_check.py --write-report")
    return report


@router.get("/system/signal-alert-reviews", response_model=SignalAlertReviewStatus)
def signal_alert_review_status() -> SignalAlertReviewStatus:
    """讀取目前 signal_alerts.json 是否已被人工檢視；不修改任何檔案。"""
    return SignalAlertReviewStatus(**get_signal_alert_review_status())


@router.post("/system/signal-alert-reviews/current", response_model=SignalAlertReviewStatus)
def acknowledge_signal_alert_review(payload: SignalAlertReviewRequest) -> SignalAlertReviewStatus:
    """標記目前 signal_alerts.json fingerprint 已檢視；只寫 review ledger，不改交易紀錄。"""
    return SignalAlertReviewStatus(**acknowledge_current_signal_alerts(
        reviewer=payload.reviewer,
        note=payload.note,
    ))


@router.get("/system/today-scan")
def today_scan() -> dict:
    """讀取 Today Scan 衍生報告；不重算策略、不寫入任何檔案。"""
    report = load_today_scan_report()
    if report is None:
        raise HTTPException(status_code=404, detail="尚無 today_scan.json，請先執行 python3 scripts/today_scan.py --write-report")
    return report


@router.get("/system/fundamentals-status", response_model=FundamentalsStatus)
def fundamentals_status() -> FundamentalsStatus:
    """查詢基本面避雷資料對 leaders 清單的覆蓋率。"""
    return FundamentalsStatus(**get_fundamentals_status())


@router.get("/system/fundamentals-official/status", response_model=OfficialFundamentalsStatus)
def official_fundamentals_status() -> OfficialFundamentalsStatus:
    """查詢官方基本面暫存報告檔狀態；不觸發外部資料抓取。"""
    return OfficialFundamentalsStatus(**get_official_fundamentals_status())


@router.post("/system/fundamentals-official/reports", response_model=OfficialFundamentalsReportsResult)
def official_fundamentals_reports(payload: OfficialFundamentalsReportsRequest) -> OfficialFundamentalsReportsResult:
    """觸發官方基本面暫存報告產生；僅 report-only，不寫入策略輸入。"""
    payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        return OfficialFundamentalsReportsResult(**run_official_fundamentals_reports(payload_dict))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/system/fundamentals-official/coverage-audit", response_model=OfficialFundamentalsCoverageAudit)
def official_fundamentals_coverage_audit() -> OfficialFundamentalsCoverageAudit:
    """讀取官方 report-only 覆蓋率稽核；不產生報告、不寫入策略輸入。"""
    try:
        return OfficialFundamentalsCoverageAudit(**get_official_fundamentals_coverage_audit())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/system/fundamentals-official/quality-momentum-lite-guard",
    response_model=QualityMomentumLiteGuardCoverage,
)
def quality_momentum_lite_guard_coverage() -> QualityMomentumLiteGuardCoverage:
    """讀取 Quality Momentum Lite guard 覆蓋率；只讀 report-only 暫存報告。"""
    try:
        return QualityMomentumLiteGuardCoverage(**get_quality_momentum_lite_guard_coverage())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/system/fundamentals-priority-fill")
def fundamentals_priority_fill() -> FileResponse:
    """下載基本面避雷優先補資料 CSV。"""
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


@router.get("/system/personal-backups", response_model=list[PersonalBackupInfo])
def personal_backups() -> list[dict]:
    """列出個人資料備份；只包含交易、復盤、觀察清單、盤後筆記與設定。"""
    return list_personal_backups()


@router.post("/system/personal-backups", response_model=PersonalBackupResult)
def create_personal_backup_endpoint() -> PersonalBackupResult:
    """建立個人資料備份，不包含行情與 generated out 檔。"""
    return PersonalBackupResult(**create_personal_backup())


@router.post("/system/personal-backups/restore-preview", response_model=PersonalRestorePreview)
def preview_personal_backup_restore(req: PersonalRestoreRequest) -> PersonalRestorePreview:
    """Dry-run 預覽個人資料還原；不寫入任何檔案。"""
    try:
        return PersonalRestorePreview(**preview_personal_restore(req.backup_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/system/personal-backups/restore", response_model=PersonalRestoreResult)
def restore_personal_backup_endpoint(req: PersonalRestoreRequest) -> PersonalRestoreResult:
    """正式還原個人資料；需 confirm=RESTORE_PERSONAL_DATA，且會先備份目前狀態。"""
    try:
        return PersonalRestoreResult(**restore_personal_backup(req.backup_id, confirm=req.confirm))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
