from fastapi import APIRouter, HTTPException, Query

from app.models.decision_journal import (
    DecisionJournalBulkCreateRequest,
    DecisionJournalBulkCreateResult,
    DecisionJournalCreate,
    DecisionJournalEntry,
    DecisionJournalSummary,
)
from app.services.decision_journal_service import (
    create_missing_portfolio_task_entries,
    create_missing_universe_report_entries,
    create_decision_journal_entry,
    delete_decision_journal_entry,
    build_universe_report_review_workflow_summary,
    get_decision_journal_summary,
    list_decision_journal,
    update_decision_journal_entry,
)

router = APIRouter()


@router.get("/decision-journal", response_model=list[DecisionJournalEntry])
def decision_journal(
    code: str | None = None,
    date: str | None = None,
    decision: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DecisionJournalEntry]:
    """讀取決策日誌；它只做復盤紀錄，不修改持倉或交易紀錄。"""
    try:
        return list_decision_journal(limit=limit, code=code, date=date, decision=decision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/decision-journal", response_model=DecisionJournalEntry)
def create_decision_journal(payload: DecisionJournalCreate) -> DecisionJournalEntry:
    """新增一筆買/賣/續抱/觀望/不動的決策紀錄。"""
    try:
        return create_decision_journal_entry(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/decision-journal/summary", response_model=DecisionJournalSummary)
def decision_journal_summary(date: str | None = None) -> DecisionJournalSummary:
    """指定日期的決策日誌統計，只做復盤摘要，不推論交易訊號。"""
    return get_decision_journal_summary(date=date)


@router.post("/decision-journal/from-portfolio-tasks", response_model=DecisionJournalBulkCreateResult)
def create_journal_from_portfolio_tasks(
    payload: DecisionJournalBulkCreateRequest,
) -> DecisionJournalBulkCreateResult:
    """將 workflow 中尚未記錄的持股待辦批次轉成決策日誌；不修改交易紀錄或持倉。"""
    try:
        return create_missing_portfolio_task_entries(date=payload.date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/decision-journal/universe-report-workflow")
def universe_report_review_workflow(date: str | None = None, limit: int = Query(default=10, ge=1, le=50)) -> dict:
    """候選股報表復盤 PM 工作流摘要；只讀取報表與決策紀錄，不修改資料。"""
    return build_universe_report_review_workflow_summary(as_of=date, limit=limit)


@router.post("/decision-journal/from-universe-report", response_model=DecisionJournalBulkCreateResult)
def create_journal_from_universe_report(
    payload: DecisionJournalBulkCreateRequest,
) -> DecisionJournalBulkCreateResult:
    """將 universe_report 中尚未記錄的可行動候選批次轉成決策日誌；不修改交易紀錄或持倉。"""
    try:
        return create_missing_universe_report_entries(date=payload.date, limit=payload.limit or 10)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/decision-journal/{entry_id}")
def delete_decision_journal(entry_id: str) -> dict:
    """刪除單筆決策日誌；不修改交易紀錄、持倉或現金。"""
    try:
        return delete_decision_journal_entry(entry_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/decision-journal/{entry_id}", response_model=DecisionJournalEntry)
def update_decision_journal(entry_id: str, payload: DecisionJournalCreate) -> DecisionJournalEntry:
    """更新單筆決策日誌內容；保留原本建立時間與 workflow snapshot。"""
    try:
        return update_decision_journal_entry(entry_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
