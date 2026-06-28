from __future__ import annotations

from pydantic import BaseModel, Field


class DataStatus(BaseModel):
    last_run_started_at: str | None = None
    last_run_finished_at: str | None = None
    last_run_status: str | None = None       # "success" | "failed" | "running" | "stalled" | "stale" | None
    last_error: str | None = None
    last_error_summary: str | None = None    # 錯誤第一行，max 120 chars，供前端 banner 顯示
    last_warning: str | None = None
    last_warning_summary: str | None = None  # 警告第一行，max 120 chars，供前端 banner 顯示
    last_data_as_of: str | None = None       # YYYY-MM-DD
    schedule_health_status: str = "never_run"
    schedule_is_overdue: bool = False
    schedule_health_message: str = "尚無自動更新完成紀錄。"
    raw_ohlcv_as_of: str | None = None       # ohlcv.csv 原始資料最新日
    outputs_lag_raw_data: bool = False       # True 表示回補後尚未重算交易輸出
    raw_data_warning: str | None = None
    price_basis: str = "latest_close"         # latest_close：最新收盤價；非即時報價
    price_basis_label: str = "最新收盤價"
    price_basis_note: str = "投組估值與正式訊號使用 ohlcv.csv 最新收盤價，不是盤中即時市價。"
    is_stale: bool = True
    stale_days: int | None = None


class FundamentalsStatus(BaseModel):
    total_codes: int
    complete_count: int
    incomplete_count: int
    missing_count: int
    coverage_pct: float
    complete_codes: list[str]
    incomplete: dict[str, list[str]]
    missing_codes: list[str]
    required_fields: list[str]
    field_labels: dict[str, str] = {}
    field_missing_counts: dict[str, int] = {}
    next_fill_targets: list[dict] = []
    csv_path: str | None = None
    json_path: str | None = None
    priority_csv_path: str | None = None
    fundamentals_csv_validation: dict | None = None
    priority_csv_validation: dict | None = None
    priority_fill_readiness: dict | None = None
    priority_fill_guide: dict | None = None
    workflow_summary: dict | None = None


class FundamentalsPriorityMergeRequest(BaseModel):
    dry_run: bool = True
    confirm: str | None = None


class FundamentalsPriorityMergeResult(BaseModel):
    dry_run: bool
    updated_code_count: int
    updated_codes: list[str]
    updated_field_count: int
    added_count: int
    added_codes: list[str]
    csv_path: str
    source: str
    json_path: str | None = None
    imported_count: int | None = None
    validation: dict
    merge_allowed: bool = False
    blocked_reason: str | None = None
    complete_codes: list[str] = []
    partial_codes: list[str] = []
    empty_codes: list[str] = []
    row_statuses: list[dict] = []
    warning_count: int = 0
    warnings: list[dict] = []
    fundamental_preview: list[dict] = []
    signals_refresh_required: bool = False
    next_action_label: str | None = None


class OfficialFundamentalsReportStatus(BaseModel):
    key: str
    label: str
    source: str
    path: str
    exists: bool
    row_count: int
    modified_at: str | None = None


class OfficialFundamentalsStatus(BaseModel):
    overall_status: str
    reports: dict[str, OfficialFundamentalsReportStatus]
    next_action_label: str | None = None


class OfficialFundamentalsReportsRequest(BaseModel):
    reports: list[str] = Field(default_factory=lambda: ["twse_bwibbu", "twse_monthly_revenue", "tpex_daily_pe"])
    apply: bool = False
    sleep: float = 1.0
    tpex_daily_pe_date: str | None = None


class OfficialFundamentalsReportsResult(BaseModel):
    dry_run: bool
    apply: bool
    requested_reports: list[str]
    reports: dict[str, dict]
    warnings: list[str] = Field(default_factory=list)


class PersonalBackupFile(BaseModel):
    key: str | None = None
    source: str | None = None
    backup_path: str | None = None
    target: str | None = None
    exists: bool | None = None
    exists_in_backup: bool | None = None
    target_exists: bool | None = None
    action: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    current_sha256: str | None = None
    checksum_ok: bool | None = None


class PersonalBackupInfo(BaseModel):
    backup_id: str
    created_at: str | None = None
    file_count: int = 0
    missing_count: int = 0
    path: str | None = None
    modified_at: str | None = None


class PersonalBackupResult(BaseModel):
    backup_id: str
    created_at: str
    kind: str
    file_count: int
    missing_count: int
    files: list[PersonalBackupFile]


class PersonalRestoreRequest(BaseModel):
    backup_id: str
    confirm: str | None = None


class PersonalRestorePreview(BaseModel):
    backup_id: str
    dry_run: bool
    can_restore: bool
    restore_confirmation: str
    files: list[PersonalBackupFile]


class PersonalRestoreResult(BaseModel):
    backup_id: str
    restored: bool
    restored_files: list[str]
    restored_count: int
    pre_restore_backup_id: str
    pre_restore_backup_path: str


class TradingSettings(BaseModel):
    brokerage_fee_rate: float
    brokerage_discount: float
    min_brokerage_fee: float
    sell_transaction_tax_rate: float


class WorkflowAction(BaseModel):
    key: str
    title: str
    detail: str
    priority: int
    severity: str
    action_type: str
    command: str | None = None
    copy_command: str | None = None
    success_check: str | None = None
    expected_outputs: list[str] = Field(default_factory=list)
    action_payload: dict = Field(default_factory=dict)


class WorkflowChecklistItem(BaseModel):
    key: str
    title: str
    detail: str
    status: str
    action_type: str
    priority: int


class WorkflowPortfolioTask(BaseModel):
    code: str
    name: str
    action: str
    label: str
    reason: str
    key_price: str | None = None
    invalidation: str | None = None
    priority: int
    severity: str
    holding_shares: int | None = None
    holding_position_pct: float | None = None
    journal_recorded: bool = False


class WorkflowMetrics(BaseModel):
    blocker_count: int
    warning_count: int
    todo_step_count: int
    blocked_step_count: int
    done_step_count: int
    portfolio_task_count: int
    portfolio_danger_count: int
    decision_journal_today_count: int = 0
    portfolio_tasks_without_journal_count: int = 0
    universe_actionable_count: int = 0
    universe_actionable_without_journal_count: int = 0


class WorkflowDecisionGuardrails(BaseModel):
    can_use_trade_outputs: bool
    message: str
    blocked_outputs: list[str]
    required_action: str | None = None
    required_action_copy_command: str | None = None
    required_action_expected_outputs: list[str] = Field(default_factory=list)
    action_payload: dict = Field(default_factory=dict)


class WorkflowReadinessSection(BaseModel):
    key: str
    label: str
    status: str
    message: str
    next_action_key: str | None = None


class WorkflowReadinessReview(BaseModel):
    overall_label: str
    top_blocker_key: str | None = None
    sections: list[WorkflowReadinessSection]


class WorkflowStatus(BaseModel):
    overall_status: str
    can_trade_today: bool
    headline: str
    data_as_of: str | None = None
    next_actions: list[WorkflowAction]
    close_checklist: list[WorkflowChecklistItem]
    portfolio_tasks: list[WorkflowPortfolioTask]
    workflow_metrics: WorkflowMetrics
    decision_guardrails: WorkflowDecisionGuardrails
    readiness_review: WorkflowReadinessReview
    checks: dict[str, dict]


class PmWorklistItem(BaseModel):
    key: str
    title: str
    detail: str
    priority: int
    severity: str
    status: str
    action_type: str
    action_label: str
    command: str
    source: str
    metric: str
    focus_codes: list[str] = Field(default_factory=list)
    action_payload: dict = Field(default_factory=dict)


class TodayFocusItem(BaseModel):
    category: str
    code: str
    name: str
    label: str
    reason: str
    next_action: str
    severity: str
    source: str
    price_basis: str
    as_of: str | None = None


class PmWorklist(BaseModel):
    generated_at: str
    overall_status: str
    headline: str
    primary_action: PmWorklistItem | None = None
    today_focus: list[TodayFocusItem] = Field(default_factory=list)
    items: list[PmWorklistItem]


class UpdateWorkflowAction(BaseModel):
    key: str
    title: str
    detail: str
    action_type: str
    command: str | None = None
    copy_command: str | None = None
    expected_outputs: list[str] = Field(default_factory=list)
    action_payload: dict = Field(default_factory=dict)


class UpdateWorkflowStep(BaseModel):
    key: str
    label: str
    status: str
    message: str
    command: str | None = None


class UpdateWorkflowStatus(BaseModel):
    generated_at: str
    overall_status: str
    headline: str
    can_use_trade_outputs: bool
    current_step: str
    next_action: UpdateWorkflowAction | None = None
    steps: list[UpdateWorkflowStep]
    checks: dict
