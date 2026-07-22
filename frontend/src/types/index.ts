export interface ChipMetrics {
  data_as_of: string | null
  holder_data_as_of: string | null
  foreign_net_buy: number | null
  investment_trust_net_buy: number | null
  retail_net_buy: number | null
  major_investor_net_buy: number | null
}

export type RecommendationStrategy = 'steady_momentum' | 'old_wang'

export type DailyChecklistStatus = 'pass' | 'warn' | 'fail' | 'info'
export type DailyChecklistCategory = 'market' | 'setup' | 'risk' | 'action' | string

export interface DailyChecklistItem {
  category: DailyChecklistCategory
  label: string
  status: DailyChecklistStatus
  detail: string
  key_price?: string
}

export interface MarketNoteInput {
  date: string
  title: string
  risk_level: string
  headline: string
  source?: string
  position_guidance?: string
  market_actions?: string[]
  index_notes?: string[]
  stock_notes?: string[]
  rules?: string[]
}

export interface MarketNoteSaveResult {
  saved: MarketNoteInput
  count: number
  replaced: boolean
  signals_rerun_required: boolean
  next_step: string
}

export interface DailyBriefStock {
  code: string
  name: string
  internal_signal?: string | null
  close?: number | null
  score?: number | null
  old_wang_score?: number | null
  old_wang_sector?: string | null
  old_wang_signal?: string | null
  strategy_alignment?: string | null
  aligned_strategies?: string[]
  strategy_conflict_notes?: string[]
  daily_action?: string | null
  daily_action_label?: string | null
  daily_key_price?: string | null
  daily_invalidation?: string | null
  entry_price_low?: number | null
  entry_price_high?: number | null
  stop_price?: number | null
  target_price?: number | null
  price_plan_note?: string | null
  reason?: string
}

export interface DailyBriefDataStatus {
  last_data_as_of: string | null
  generated_at?: string | null
  requested_as_of?: string | null
  universe_size: number
  data_ok_count: number
  data_missing_count: number
  data_ok_pct: number
  is_stale: boolean
  stale_days: number | null
  status_label: string
  message: string
  update_required: boolean
  update_command: string
  missing_stocks: Array<{ code?: string; name?: string; reason?: string }>
  files_written: string[]
}

export interface DailyBriefPositionGuidance {
  target_level: string
  risk_level: string
  source: string
  reason: string
  market_filter?: string | null
  old_wang_market_filter?: string | null
  old_wang_market_reason?: string | null
}

export interface ManualPlaybook {
  target_level: string
  target_position_pct?: number | null
  stance?: string | null
  focus_sectors: string[]
  risk_controls: string[]
  watch_codes: string[]
}

export interface ManualWatchlistReviewItem extends DailyBriefStock {
  found: boolean
  bucket: string
  decision_hint: string
  watch_price?: string
  entry_plan?: string
  stop_plan?: string
  exit_plan?: string
  invalidation?: string
}

export interface ManualWatchlistReview {
  as_of: string | null
  generated_at?: string | null
  manual_note_title?: string | null
  position_guidance?: DailyBriefPositionGuidance | null
  manual_playbook?: ManualPlaybook | null
  items: ManualWatchlistReviewItem[]
  summary: Record<string, number>
}

export interface DailyBriefTask {
  bucket: string
  code: string
  name: string
  trigger_action: string
  daily_action?: string | null
  watch_price: string
  entry_plan: string
  stop_plan: string
  exit_plan: string
  invalidation: string
  priority: number
  reason: string
  price_plan_note?: string
}

export interface DailyBrief {
  as_of: string | null
  generated_at?: string | null
  brief_generated_from: string
  data_status: DailyBriefDataStatus
  position_guidance: DailyBriefPositionGuidance
  manual_playbook?: ManualPlaybook | null
  manual_note_title?: string | null
  manual_note_status?: {
    date?: string
    applies_to_as_of?: string | null
    title?: string
    is_stale?: boolean
    update_required?: boolean
    stale_trading_days?: number | null
    status_label?: string
    stale_reason?: string
  } | null
  rotation_plan: {
    continue_hold: DailyBriefStock[]
    wait_pullback: DailyBriefStock[]
    entry_candidates: DailyBriefStock[]
    priority_reduce: DailyBriefStock[]
    avoid_no_chase: DailyBriefStock[]
    summary: Record<string, number>
  }
  manual_watchlist_review?: {
    items: ManualWatchlistReviewItem[]
    summary: Record<string, number>
  } | null
  tomorrow_tasks: DailyBriefTask[]
  tomorrow_checklist: string[]
  summary: Record<string, number>
}

export interface WorkflowAction {
  key: string
  title: string
  detail: string
  priority: number
  severity: 'danger' | 'warning' | 'info' | string
  action_type: 'update_data' | 'run_signals' | 'market_note' | 'fundamentals' | 'wait' | string
  command?: string | null
  copy_command?: string | null
  success_check?: string | null
  expected_outputs?: string[]
}

export interface WorkflowChecklistItem {
  key: string
  title: string
  detail: string
  status: 'done' | 'todo' | 'blocked' | 'running' | string
  action_type: string
  priority: number
}

export interface WorkflowPortfolioTask {
  code: string
  name: string
  action: string
  label: string
  reason: string
  key_price?: string | null
  invalidation?: string | null
  priority: number
  severity: 'danger' | 'warning' | 'info' | 'success' | string
  holding_shares?: number | null
  holding_position_pct?: number | null
  journal_recorded?: boolean
}

export interface WorkflowMetrics {
  blocker_count: number
  warning_count: number
  todo_step_count: number
  blocked_step_count: number
  done_step_count: number
  portfolio_task_count: number
  portfolio_danger_count: number
  decision_journal_today_count: number
  portfolio_tasks_without_journal_count: number
  universe_actionable_count: number
  universe_actionable_without_journal_count: number
}

export interface WorkflowDecisionGuardrails {
  can_use_trade_outputs: boolean
  message: string
  blocked_outputs: string[]
  required_action?: string | null
  required_action_copy_command?: string | null
}

export interface WorkflowReadinessSection {
  key: string
  label: string
  status: 'ready' | 'warning' | 'blocked' | string
  message: string
  next_action_key?: string | null
}

export interface WorkflowReadinessReview {
  overall_label: string
  top_blocker_key?: string | null
  sections: WorkflowReadinessSection[]
}

export interface WorkflowStatus {
  overall_status: 'ready' | 'warning' | 'blocked' | 'running' | string
  can_trade_today: boolean
  headline: string
  data_as_of?: string | null
  next_actions: WorkflowAction[]
  close_checklist: WorkflowChecklistItem[]
  portfolio_tasks: WorkflowPortfolioTask[]
  workflow_metrics: WorkflowMetrics
  decision_guardrails?: WorkflowDecisionGuardrails
  readiness_review?: WorkflowReadinessReview
  checks: Record<string, Record<string, unknown>>
}

export interface SignalAlertPreview {
  severity: 'block' | 'warn' | 'info' | string
  code: string
  name: string
  title: string
  action_label: string
  review_focus: string[]
}

export interface PmWorklistItem {
  key: string
  title: string
  detail: string
  priority: number
  severity: 'danger' | 'warning' | 'info' | string
  status: 'todo' | 'done' | string
  action_type: 'data_repair' | 'data_freshness' | 'fundamentals' | 'decision_journal' | 'daily_check' | string
  action_label: string
  command: string
  source: string
  metric: string
  focus_codes: string[]
  action_payload?: {
    kind?: string
    command?: string
    method?: string
    endpoint?: string
    date?: string | null
    limit?: number
    confirm_message?: string
    copy_text?: string
    copy_command?: string
    preview_items?: string[]
    preview_alerts?: SignalAlertPreview[]
    file_path?: string
    focus_limit?: number
    dry_run?: boolean
    expected_outputs?: string[]
  }
}

export interface TodayFocusItem {
  category: 'portfolio_risk' | 'entry_candidate' | 'review_needed' | string
  code: string
  name: string
  label: string
  reason: string
  short_reason?: string
  detail_reason?: string
  next_action: string
  action_label?: string
  primary_metric?: string
  severity: 'danger' | 'warning' | 'info' | 'success' | string
  source: 'portfolio' | 'universe_report' | 'daily_check' | 'pm_worklist' | 'workflow' | string
  price_basis: string
  as_of?: string | null
}

export interface PmWorklist {
  generated_at: string
  overall_status: 'clear' | 'action_required' | string
  headline: string
  primary_action?: PmWorklistItem | null
  today_focus: TodayFocusItem[]
  items: PmWorklistItem[]
}

export interface SignalAlertReviewStatus {
  alerts_file: string
  reviews_file: string
  review_required: boolean
  reviewed: boolean
  current_fingerprint?: string | null
  latest_reviewed_fingerprint?: string | null
  alert_count: number
  as_of?: string | null
  previous_as_of?: string | null
  severity_counts: Record<string, number>
  reviewed_at?: string | null
  reviewer?: string | null
  note?: string | null
}

export interface DailyCheckAction {
  key: string
  status: 'ok' | 'warn' | 'block' | 'info' | string
  title: string
  message: string
  next_action: string
  details?: {
    workflow_stage?: string | null
    workflow_headline?: string | null
    workflow_primary_action?: {
      label?: string | null
      command?: string | null
      kind?: 'download' | 'file' | 'api' | string
    } | null
    workflow_checklist?: Array<{
      key: string
      label?: string | null
      detail?: string | null
      status?: 'done' | 'todo' | 'blocked' | string
    }>
    [key: string]: unknown
  }
  action_payload?: {
    kind?: string
    command?: string
    copy_command?: string
    copy_text?: string
    file_path?: string
    method?: string
    endpoint?: string
    dry_run?: boolean
    confirm_message?: string
    preview_items?: string[]
    preview_alerts?: SignalAlertPreview[]
    expected_outputs?: string[]
  }
}

export interface DailyCheckDataRepairItem {
  code: string
  name: string
  status: 'no_data' | 'insufficient' | string
  status_label: string
  row_count: number
  required_rows: number
  last_data_as_of?: string | null
}

export interface DailyCheckDataRepairSummary {
  total_count: number
  no_data_count: number
  insufficient_count: number
  command: string
  top_items: DailyCheckDataRepairItem[]
}

export interface DailyCheckReport {
  overall_status: 'ok' | 'warn' | 'block' | string
  exit_code: number
  generated_at: string
  source_report_generated_at?: string | null
  data_as_of?: string | null
  snapshot_is_stale?: boolean
  snapshot_stale_reason?: string
  snapshot_refresh_command?: string
  snapshot_refresh_copy_command?: string
  snapshot_refresh_expected_outputs?: string[]
  can_use_trade_outputs: boolean
  data_repair?: DailyCheckDataRepairSummary
  top_actions: DailyCheckAction[]
}

export interface UpdateWorkflowAction {
  key: string
  title: string
  detail: string
  action_type: string
  command?: string | null
  copy_command?: string | null
  expected_outputs: string[]
}

export interface UpdateWorkflowStep {
  key: string
  label: string
  status: 'done' | 'warning' | 'blocked' | 'running' | string
  message: string
  command?: string | null
}

export interface UpdateWorkflowStatus {
  generated_at: string
  overall_status: 'ready' | 'action_required' | 'blocked' | string
  headline: string
  can_use_trade_outputs: boolean
  current_step: string
  next_action?: UpdateWorkflowAction | null
  steps: UpdateWorkflowStep[]
  checks: Record<string, unknown>
}

export type DecisionJournalDecision = 'buy' | 'sell' | 'hold' | 'skip' | 'reduce' | 'watch'

export interface DecisionJournalCreate {
  date: string
  code: string
  name: string
  decision: DecisionJournalDecision
  reason: string
  price?: number | null
  shares?: number | null
  key_price?: string | null
  invalidation?: string | null
  source?: string
}

export interface DecisionJournalEntry extends DecisionJournalCreate {
  id: string
  created_at: string
  updated_at?: string | null
  workflow_status?: string | null
  workflow_headline?: string | null
}

export interface DecisionJournalSummary {
  date?: string | null
  total_count: number
  by_decision: Record<string, number>
  recent_codes: string[]
}

export interface DecisionJournalBulkCreateResult {
  date: string
  total_task_count: number
  created_count: number
  skipped_count: number
  skipped_codes: string[]
  created_entries: DecisionJournalEntry[]
}

export interface UniverseReportReviewWorkflow {
  stage: 'review_candidates' | 'complete' | 'no_actionable_candidates' | string
  headline: string
  detail: string
  as_of?: string | null
  progress_label: string
  actionable_count: number
  recorded_count: number
  missing_count: number
  primary_action: {
    label: string
    command: string
    kind: 'api' | 'link' | string
  }
  checklist: Array<{
    key: string
    label: string
    detail: string
    status: 'done' | 'todo' | 'blocked' | string
  }>
  top_items: Array<{
    code: string
    name: string
    action: string
    label: string
    decision_suggestion: DecisionJournalDecision
    reason: string
    key_price?: string | null
    invalidation?: string | null
    priority?: number | null
  }>
}

export interface StockRecommendation {
  stock_id: string
  name: string
  price: number
  change_pct: number
  score: number
  reason: string
  risk_warning: string
  volume: number | null
  vol_ratio: number | null
  position_size_pct: number | null
  position_size_note: string | null
  chip: ChipMetrics
  strategy_tags: string[]
  recommendation_source: string
  old_wang_market_regime: string | null
  old_wang_market_filter: string | null
  old_wang_market_source: string | null
  old_wang_market_reason: string | null
  old_wang_tag: string | null
  old_wang_score: number | null
  old_wang_raw_score: number | null
  old_wang_badges: string[]
  old_wang_reason: string | null
  old_wang_volume_signal: string | null
  old_wang_gap_type: string | null
  old_wang_gap_support: number | null
  old_wang_gap_resistance: number | null
  old_wang_gap_note: string | null
  old_wang_ma_signal: string | null
  old_wang_volume_low_support: boolean | null
  old_wang_volume_low_price: number | null
  old_wang_support_state: string | null
  old_wang_ma_break_count: number | null
  old_wang_previous_high_risk: boolean | null
  old_wang_chip_signal: string | null
  old_wang_previous_high_state: string | null
  old_wang_previous_high_price: number | null
  old_wang_volume_high_breakout: boolean | null
  old_wang_volume_high_price: number | null
  old_wang_all_ma_reclaim: boolean | null
  old_wang_parabolic_ma10_hold: boolean | null
  steady_momentum_flag: boolean | null
  steady_momentum_tag: string | null
  steady_momentum_score: number | null
  steady_momentum_signal: string | null
  steady_momentum_reason: string | null
  fundamental_flag: boolean | null
  fundamental_tag: string | null
  fundamental_score: number | null
  fundamental_signal: string | null
  fundamental_reason: string | null
  fundamental_data_ok: boolean | null
  fundamental_data_missing_reason: string | null
  fundamental_quality_score: number | null
  fundamental_value_score: number | null
  fundamental_safety_score: number | null
  fundamental_growth_score: number | null
  daily_checklist?: DailyChecklistItem[]
}

export interface IntradayMonitor {
  stock_id: string
  name: string
  mode: 'intraday_monitor'
  latest_closed_date: string | null
  data_ok: boolean
  data_missing_reason: string
  current_price: number | null
  current_open: number | null
  current_high: number | null
  current_low: number | null
  current_volume: number | null
  baseline_close: number | null
  ma5: number | null
  ma10: number | null
  ma20: number | null
  ma60: number | null
  projected_vol_ratio: number | null
  support_state: string
  ma_break_count: number
  previous_high_risk: boolean
  touched_ma_levels: string[]
  broken_ma_levels: string[]
  volume_low_price: number | null
  volume_low_broken: boolean
  gap_type: string
  gap_support: number | null
  gap_resistance: number | null
  gap_broken: boolean
  monitor_signal: 'healthy' | 'caution' | 'risk' | 'data_missing'
  invalidates_daily_plan: boolean
  action: string
  warnings: string[]
  notes: string[]
  official_signal_note: string
}

export interface TradeRecord {
  id: string
  stock_id: string
  name: string
  trade_type: 'buy' | 'sell'
  date: string
  price: number
  shares: number
  gross_amount?: number | null
  fee?: number | null
  tax?: number | null
  net_amount?: number | null
  note: string
  created_at: string
}

export interface TradingSettings {
  brokerage_fee_rate: number
  brokerage_discount: number
  min_brokerage_fee: number
  sell_transaction_tax_rate: number
}

export interface StrategyValidationTrade {
  code: string
  name: string
  market: string
  side: 'buy' | 'sell'
  signal_date: string
  fill_date: string
  fill_price: number
  shares: number
  fee: number
  tax: number
  realized_pnl: number | null
  reason: string
  strategy: string
  tradingview_url: string
  analysis_hash: string
}

export interface StrategyValidationOpenPosition {
  code: string
  name: string
  market: string
  shares: number
  entry_cost: number
  entry_date: string
  entry_price: number
  strategy: string
  close: number
  estimated_liquidation_value: number
  unrealized_pnl_after_exit_cost: number
  tradingview_url: string
  analysis_hash: string
}

export interface StrategyValidationSkippedEntry {
  code: string
  name: string
  market: string
  signal_date: string
  fill_date: string
  reason_code: string
  reason: string
  risk_level: string
  tradingview_url: string
  analysis_hash: string
}

export interface StrategyValidationRiskDay {
  date: string
  level: string
  score: number
  data_as_of: string | null
  max_position_pct: number
  max_exposure_pct: number
  max_new_positions: number
}

export interface StrategyValidationResult {
  mode: string
  mode_label: string
  initial_cash: number
  start_date: string
  end_date: string
  final_equity_after_estimated_liquidation_cost: number
  net_pnl: number
  return_pct: number
  max_drawdown_pct: number
  realized_pnl: number
  total_fees: number
  total_tax: number
  trade_event_count: number
  buy_count: number
  sell_count: number
  cash: number
  open_positions: StrategyValidationOpenPosition[]
  trades: StrategyValidationTrade[]
  equity_curve: { date: string; equity: number }[]
  skipped_entry_count?: number
  skipped_entries?: StrategyValidationSkippedEntry[]
  risk_by_day?: StrategyValidationRiskDay[]
  entry_guardrails?: Record<string, { max_position_pct: number; max_exposure_pct: number; max_new_positions: number }>
}

export interface StrategyValidationRunStatus {
  status: 'idle' | 'running' | 'success' | 'failed'
  started_at: string | null
  finished_at: string | null
  error: string | null
  start: string | null
  end: string | null
}

export interface StrategyValidationReport {
  report_id: string
  generated_at: string
  config: Record<string, unknown>
  limitations: string[]
  results: Record<string, StrategyValidationResult>
}

export interface UsValidationTrade {
  code: string
  name: string
  category: string
  strategy: string
  signal_date: string
  entry_date: string | null
  entry_price: number | null
  exit_date: string | null
  exit_price: number | null
  exit_reason: string
  holding_trading_days: number | null
  return_pct: number | null
  unresolved: boolean
  tradingview_url: string
}

export interface UsValidationResult {
  strategy: string
  strategy_label: string
  exit_rule: string
  summary: Record<string, number | string | null | Record<string, number>>
  trades: UsValidationTrade[]
  limitations: string[]
}

export interface UsStrategyValidationReport {
  region: 'US'
  currency: 'USD'
  requested_start: string
  requested_end: string
  start_date: string
  end_date: string
  method: string
  results: Record<string, UsValidationResult>
}

export interface BuyRequest {
  stock_id: string
  name: string
  date: string
  price: number
  shares: number
  note?: string
}

export interface SellRequest {
  stock_id: string
  date: string
  price: number
  shares: number
  note?: string
}

export interface Position {
  stock_id: string
  name: string
  total_shares: number
  avg_cost: number
  total_cost: number
  current_price: number
  current_value: number
  unrealized_pnl: number
  return_rate: number
}

export interface Stats {
  period: 'monthly' | 'all'
  buy_count: number
  sell_count: number
  realized_pnl: number
  unrealized_pnl: number
  win_rate: number
}

export interface OhlcvBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface PricePoint {
  date: string
  price: number
}

export interface SupportResistanceLine {
  label: string
  price: number
  type: 'static' | 'dynamic'
}

export interface TrendLine {
  valid: boolean
  p1: PricePoint | null
  p2: PricePoint | null
  note: string
}

export interface PatternResult {
  pattern_type: 'none' | 'w_bottom' | 'm_top' | 'head_and_shoulders_bottom'
  pattern_status: 'none' | 'forming' | 'confirmed' | 'failed'
  neckline: number | null
  note: string
}

export interface StockDataDiagnostic {
  status: 'ok' | 'not_tracked' | 'no_ohlcv_data' | 'insufficient_rows' | string
  row_count: number
  required_rows: number
  last_data_as_of: string | null
  price_basis: string
  price_basis_label: string
  price_basis_note: string
  message: string
  next_action_label: string
  next_action_command: string
  next_action_copy_command?: string
}

export interface StockTrackingResult {
  code: string
  name: string
  group: string
  added: boolean
  message: string
  next_action_label: string
  next_action_command: string
  next_action_copy_command?: string
  signals_refresh_required: boolean
}

export interface StockAnalysis {
  code: string
  stock_id: string
  name: string
  as_of: string
  data_ok: boolean
  data_missing_reason: string
  data_diagnostic: StockDataDiagnostic
  is_stale: boolean
  stale_days: number
  close: number | null
  ma5: number | null
  ma20: number | null
  ma60: number | null
  rsi14: number | null
  vol_ratio: number | null
  long_trend: string
  short_trend: string
  signal: string
  score: number
  trend_score: number
  entry_score: number
  risk_score: number
  market_regime: string
  market_filter: string
  old_wang_market_regime?: string
  old_wang_market_filter?: string
  old_wang_market_source?: string
  old_wang_market_reason?: string
  relative_strength_score: number | null
  relative_strength_60d: number | null
  relative_strength_120d: number | null
  stage: string
  entry_price_low: number | null
  entry_price_high: number | null
  stop_price: number | null
  target_price: number | null
  risk_pct: number | null
  reward_pct: number | null
  reward_risk_ratio: number | null
  price_plan_note: string
  position_size_pct: number
  position_size_note: string
  strategy_tags: string[]
  old_wang_flag: boolean
  old_wang_tag: string | null
  old_wang_score: number | null
  old_wang_raw_score: number | null
  old_wang_signal: string
  old_wang_reason: string
  old_wang_sector: string
  old_wang_volume_signal: string
  old_wang_gap_type: string
  old_wang_gap_support: number | null
  old_wang_gap_resistance: number | null
  old_wang_gap_note: string
  old_wang_ma_signal: string
  old_wang_volume_low_support: boolean
  old_wang_volume_low_price: number | null
  old_wang_support_state: string
  old_wang_ma_break_count: number
  old_wang_previous_high_risk: boolean
  old_wang_chip_signal: string
  old_wang_previous_high_state?: string
  old_wang_previous_high_price?: number | null
  old_wang_volume_high_breakout?: boolean
  old_wang_volume_high_price?: number | null
  old_wang_all_ma_reclaim?: boolean
  old_wang_parabolic_ma10_hold?: boolean
  steady_momentum_flag?: boolean
  steady_momentum_tag?: string | null
  steady_momentum_score?: number | null
  steady_momentum_signal?: string
  steady_momentum_reason?: string
  daily_action?: string
  daily_action_label?: string
  daily_action_identity?: string
  daily_action_reason?: string
  daily_key_price?: string
  daily_invalidation?: string
  daily_priority?: number
  daily_checklist?: DailyChecklistItem[]
  reasons: string[]
  risk_notes: string[]
  no_buy_reason: string
  support_lines: SupportResistanceLine[]
  resistance_lines: SupportResistanceLine[]
  uptrend_line: TrendLine
  downtrend_line: TrendLine
  pattern: PatternResult
  ohlcv: OhlcvBar[]
}

export interface HoldingAnalysis {
  avg_cost: number
  shares: number
  unrealized_pnl: number | null
  return_rate: number | null
  analysis: StockAnalysis
}

export interface FileInfo {
  exists: boolean
  path: string
  last_modified?: string
  as_of?: string
  generated_at?: string
  row_count?: number
  status_label?: string
  update_required?: boolean
  parse_error?: string
  optional?: boolean
}

export interface PortfolioSummary {
  total_positions: number
  total_cost: number
  total_market_value: number
  total_unrealized_pnl: number
  hold_count: number
  take_profit_warning_count: number
  exit_warning_count: number
  invalidated_count: number
}

export interface DataStatus {
  last_run_started_at: string | null
  last_run_finished_at: string | null
  last_run_status: string | null    // 'success' | 'failed' | 'running' | null
  last_error: string | null
  last_error_summary: string | null // 錯誤第一行摘要，max 120 chars
  last_data_as_of: string | null    // YYYY-MM-DD
  raw_ohlcv_as_of?: string | null
  outputs_lag_raw_data?: boolean
  raw_data_warning?: string | null
  schedule_health_status?: string
  schedule_is_overdue?: boolean
  schedule_health_message?: string
  manual_update_action?: UpdateWorkflowAction
  price_basis?: string
  price_basis_label?: string
  price_basis_note?: string
  is_stale: boolean
  stale_days: number | null
}

export interface PreMarketRiskSignal {
  key: string
  code: string
  label: string
  data_as_of: string | null
  change_pct: number | null
  status: 'ok' | 'warning' | 'severe' | 'missing' | string
  points: number
  reason: string
}

export interface PreMarketRiskReport {
  generated_at: string
  level: 'normal' | 'watch' | 'defensive' | 'extreme' | 'unknown' | string
  level_label: string
  score: number
  headline: string
  data_as_of: string | null
  data_freshness: Record<string, unknown>
  can_open_new_positions: boolean
  max_exposure_pct: number | null
  signals: PreMarketRiskSignal[]
  latest_event: {
    date?: string | null
    title?: string
    headline?: string
    risk_level?: string
    source?: string
    status?: string
    is_stale?: boolean
    points?: number
  } | null
  guidance: {
    new_positions?: string
    opening_rule?: string
    max_exposure_pct?: number | null
  }
  official_sources: Array<{ label: string; url: string; scope: string }>
  limitations: string[]
}

export interface FundamentalsStatus {
  total_codes: number
  complete_count: number
  incomplete_count: number
  missing_count: number
  coverage_pct: number
  complete_codes: string[]
  incomplete: Record<string, string[]>
  missing_codes: string[]
  required_fields: string[]
  field_labels?: Record<string, string>
  field_missing_counts?: Record<string, number>
  next_fill_targets?: Array<{
    code: string
    name: string
    missing_count: number
    missing_fields: string[]
    missing_field_labels: string[]
    priority_reason: string
  }>
  csv_path?: string | null
  json_path?: string | null
  priority_csv_path?: string | null
  fundamentals_csv_validation?: FundamentalsCsvValidation | null
  priority_csv_validation?: FundamentalsCsvValidation | null
  priority_fill_readiness?: {
    status: 'not_generated' | 'empty' | 'invalid' | 'ready_to_preview' | 'ready_to_merge' | string
    can_preview: boolean
    can_merge: boolean
    message: string
    suggested_action: string
    filled_code_count: number
    filled_field_count: number
    complete_code_count?: number
    partial_code_count?: number
    row_count: number
  } | null
  priority_fill_guide?: {
    next_action_label: string
    complete_ready_count: number
    partial_count: number
    empty_count: number
    warning_count: number
    format_note: string
    example_values: Record<string, string>
  } | null
  workflow_summary?: FundamentalsWorkflowSummary | null
}

export interface OfficialFundamentalsReportStatus {
  key: string
  label: string
  source: string
  path: string
  exists: boolean
  row_count: number
  modified_at?: string | null
}

export interface OfficialFundamentalsStatus {
  overall_status: 'missing' | 'partial' | 'ready' | string
  reports: Record<string, OfficialFundamentalsReportStatus>
  next_action_label?: string | null
}

export interface OfficialFundamentalsReportsResult {
  dry_run: boolean
  apply: boolean
  requested_reports: string[]
  reports: Record<string, {
    path?: string
    row_count?: number
    source?: string
    [key: string]: unknown
  }>
  warnings: string[]
}

export interface OfficialFundamentalsCoverageAudit {
  priority_csv_path: string
  target_count: number
  report_count: number
  available_cell_count: number
  coverage_pct: number
  missing_report_files: string[]
  formally_fillable_official_fields: string[]
  blocked_formal_fields: string[]
  reports: Record<string, {
    key: string
    label: string
    source: string
    path: string
    status: string
    exists: boolean
    row_count: number
    available_count: number
    missing_row_count: number
    key_fields: string[]
  }>
  codes: Array<{
    code: string
    name: string
    priority_reason: string
    available_report_count: number
    reports: Record<string, {
      status: string
      present_fields: string[]
      skip_reason: string
    }>
  }>
  next_action_label?: string | null
}

export interface FundamentalsWorkflowSummary {
  stage: 'generate_priority_csv' | 'fill_priority_csv' | 'fix_priority_csv' | 'ready_to_merge' | string
  headline: string
  detail: string
  coverage_label: string
  primary_action: {
    label: string
    command: string
    kind: 'download' | 'file' | 'api' | string
  }
  checklist: Array<{
    key: string
    label: string
    detail: string
    status: 'done' | 'todo' | 'blocked' | string
  }>
  focus_targets: Array<{
    code: string
    name: string
    missing_count: number
    missing_fields: string[]
    missing_field_labels: string[]
    priority_reason: string
  }>
  field_missing_counts: Record<string, number>
}

export interface FundamentalsCsvValidation {
  valid: boolean
  row_count: number
  filled_code_count: number
  filled_field_count: number
  complete_code_count?: number
  complete_codes?: string[]
  partial_codes?: string[]
  empty_codes?: string[]
  duplicate_codes?: string[]
  missing_code_rows?: number[]
  errors?: Array<{
    row_number: number
    code?: string
    field?: string
    value?: string | number | null
    message: string
  }>
  warnings?: Array<{
    row_number: number
    code?: string
    field?: string
    value?: string | number | null
    message: string
  }>
}

export interface FundamentalsPriorityMergeResult {
  dry_run: boolean
  updated_code_count: number
  updated_codes: string[]
  updated_field_count: number
  added_count: number
  added_codes: string[]
  csv_path: string
  source: string
  json_path?: string | null
  imported_count?: number | null
  validation: Record<string, unknown>
  merge_allowed?: boolean
  blocked_reason?: string | null
  complete_codes?: string[]
  partial_codes?: string[]
  empty_codes?: string[]
  row_statuses?: Array<{
    row_number: number
    code: string
    status: 'complete' | 'partial' | 'empty' | string
    filled_field_count: number
    missing_field_count: number
    filled_fields: string[]
    missing_fields: string[]
  }>
  warning_count?: number
  warnings?: Array<Record<string, unknown>>
  fundamental_preview?: Array<{
    code: string
    name: string
    fundamental_flag: boolean
    fundamental_score?: number | null
    fundamental_signal?: string | null
    fundamental_data_ok: boolean
    fundamental_reason?: string | null
    fundamental_data_missing_reason?: string | null
    fundamental_quality_score?: number | null
    fundamental_value_score?: number | null
    fundamental_safety_score?: number | null
    fundamental_growth_score?: number | null
  }>
  signals_refresh_required?: boolean
  next_action_label?: string | null
}

export interface SignalsStatus {
  run_status: 'idle' | 'running' | 'success' | 'failed' | string
  run_error?: string | null
  out_dir: string
  manual_note_status?: {
    date?: string
    applies_to_as_of?: string | null
    is_stale?: boolean
    update_required?: boolean
    stale_trading_days?: number | null
    status_label?: string
    stale_reason?: string
  } | null
  out_files: {
    summary_json: FileInfo
    universe_report_csv: FileInfo
    daily_brief_json: FileInfo
  }
  data_files: {
    leaders_json: FileInfo
    ohlcv_csv: FileInfo
    market_notes_json?: FileInfo
    fundamentals_json?: FileInfo
    positions_json: FileInfo
  }
}

export interface StockUniverseItem {
  code: string
  name: string
  /** 市場維度 scaffold：現有台股皆為 'TW'，美股（'US'）尚未接真資料 */
  region?: 'TW' | 'US'
  has_data: boolean
  row_count: number
  last_data_as_of: string | null
  data_status: 'ok' | 'insufficient' | 'no_data'
}

// ── 美股（US Market — Phase 1）──────────────────────────────────────────────
export interface UsUniverseItem {
  code: string
  name: string
  /** 觀察用分類（如 "Mega-cap Tech"）；非產業標準分類、非推薦 */
  category: string
  region: 'US'
  has_data: boolean
  row_count: number
  last_data_as_of: string | null
  last_close: number | null
  data_status: 'ok' | 'no_data'
}

export interface UsMarketStatus {
  region: 'US'
  /** 資料源是否就緒（Yahoo 免 key → 恆 true；Finnhub optional 需 key） */
  source_configured: boolean
  source_label?: string
  universe_size: number
  tickers_with_data: number
  /** 回補可觀測性：完全無資料的 ticker 代碼（已排序） */
  missing_tickers?: string[]
  /** 回補可觀測性：有資料但筆數 < 60（算不出 MA60 / 觀察訊號）的代碼（已排序） */
  insufficient_tickers?: string[]
  /** 所有有資料 ticker 的最小 row_count；無資料時 null */
  min_row_count?: number | null
  last_data_as_of: string | null
  /** 資料新鮮度（weekend-aware，容忍 1 個交易日；不含 NYSE 假日） */
  expected_trading_day?: string | null
  days_since_last?: number | null
  is_stale?: boolean
  backfill_command?: string
}

export interface UsUpdateStatus {
  status: 'idle' | 'running' | 'success' | 'failed' | string
  started_at: string | null
  finished_at: string | null
  error: string | null
  months: number | null
}

/**
 * 美股資料新鮮度精簡契約（/markets/us/data-freshness）。
 * 供 freshness badge 呈現：資料源 / 最後更新日 / 是否過期。
 */
export interface UsDataFreshness {
  region: 'US'
  /** 資料源標籤（如 "Yahoo Finance（美股，非官方、免 key）"） */
  source: string
  /** 資料源是否就緒 */
  source_configured: boolean
  /** 最後有資料的交易日；尚無資料時 null */
  last_updated: string | null
  /** 是否過期（weekend-aware，容忍 1 個交易日；資料缺失亦視為過期） */
  stale: boolean
  /** 落後幾個交易日；無法判斷時 null */
  days_since_last: number | null
  /** 預期最新交易日 */
  expected_trading_day: string | null
}

/**
 * Phase 2：美股基本技術狀態（描述性，非買賣建議）。
 * `no_data`（算不出指標）與 `weak`（跌破 MA60，真正弱勢）刻意分開；
 * `recovering` = 站上 MA20/MA60 但 MA20 < MA60（均線尚未翻多）。
 */
export type UsTechStatus =
  | 'trend_up'
  | 'recovering'
  | 'pullback_watch'
  | 'overheated'
  | 'weak'
  | 'no_data'

export interface UsAnalysisItem {
  code: string
  name: string
  /** 觀察用分類（如 "Mega-cap Tech"）；非產業標準分類、非推薦 */
  category: string
  region: 'US'
  data_status: 'ok' | 'no_data'
  row_count: number
  last_data_as_of: string | null
  last_close: number | null
  ma20: number | null
  ma60: number | null
  rsi14: number | null
  change_20d_pct: number | null
  dist_ma20_pct: number | null
  dist_ma60_pct: number | null
  days_since_last: number | null
  status: UsTechStatus
  status_label: string
}

export interface UsStockAnalysis extends UsAnalysisItem {
  currency: 'USD'
  as_of: string | null
  data_ok: boolean
  close: number | null
  reasons: string[]
  risk_notes: string[]
  ohlcv: Array<{ date: string; open: number; high: number; low: number; close: number; volume: number }>
}

/** Phase 3：美股觀察訊號（描述性，非推薦 / 非買賣建議） */
export type UsWatchSignal = 'watch_breakout' | 'watch_pullback' | 'trend_up' | 'overheated' | 'avoid_weak'

export interface UsWatchSignalItem {
  code: string
  name: string
  /** 觀察用分類（如 "Mega-cap Tech"）；非產業標準分類、非推薦 */
  category: string
  close: number | null
  status: UsTechStatus
  signal: UsWatchSignal
  signal_label: string
  reasons: string[]
  risk_notes: string[]
  /** 觀察優先度（排序用，越大越優先看）；非推薦分數、非買賣訊號 */
  priority: number
  data_as_of: string | null
}

export interface UsWatchSignals {
  as_of: string | null
  market_bias: 'bullish' | 'bearish' | 'mixed' | 'unknown'
  market_note: string
  benchmarks: Record<string, { above_ma60: boolean | null; close: number | null; ma60: number | null }>
  signals: UsWatchSignalItem[]
}

/**
 * 美股觀察策略 us_trend_follow（大盤守門的趨勢延續）。
 * **非推薦、非買賣建議、非下單**；state 只有觀察語言，rank 只是觀察排序。
 */
export type UsStrategyState = 'candidate' | 'watch' | 'avoid' | 'overheated'

export interface UsStrategyCandidate {
  code: string
  name: string
  category: string
  close: number | null
  state: UsStrategyState
  rank: number
  reasons: string[]
  risk_notes: string[]
  data_as_of: string | null
}

export interface UsStrategyExcluded {
  code: string
  name: string
  category: string
  close: number | null
  state: UsStrategyState
  reasons: string[]
  data_as_of: string | null
}

export interface UsTrendFollow {
  as_of: string | null
  strategy: 'us_trend_follow'
  strategy_label: string
  market_gate: {
    active: boolean
    bias: 'bullish' | 'bearish' | 'mixed' | 'unknown'
    note: string
  }
  candidates: UsStrategyCandidate[]
  excluded: UsStrategyExcluded[]
}

/**
 * 美股觀察策略 us_wbottom_target（W 底突破 + 量幅目標）。
 * **非推薦、非買賣建議、非下單**；頸線 / 目標 / 失效價為觀察用關鍵價位。
 */
export type UsWbottomState =
  | 'breakout_today'
  | 'breakout_in_progress'
  | 'target_reached'
  | 'invalidated'
  | 'forming'

export interface UsWbottomPattern {
  code: string
  name: string
  category: string
  state: UsWbottomState
  state_label: string
  close: number | null
  neckline: number
  pattern_low: number
  target_price: number
  dist_to_target_pct: number | null
  breakout_date: string | null
  low_dates: string[]
  reasons: string[]
  risk_notes: string[]
}

export interface UsWbottom {
  as_of: string | null
  strategy: 'us_wbottom_target'
  strategy_label: string
  market_gate: {
    active: boolean
    detail: Record<string, boolean>
    note: string
  }
  patterns: UsWbottomPattern[]
  no_pattern_count: number
  note: string
}

export interface WatchlistItem {
  code: string
  name: string
  added_at: string
  region?: 'TW' | 'US'
}

export interface WatchlistGroup {
  name: string
  stocks: WatchlistItem[]
}

export interface SignalsSummary {
  as_of: string
  generated_at?: string
  universe_size: number
  data_ok_count: number
  data_missing_count: number
  signal_counts: Record<string, number>
  market_context?: {
    benchmark_code?: string
    market_regime?: string
    market_filter?: string
    reason?: string
    old_wang_market_regime?: string
    old_wang_market_filter?: string
    old_wang_market_source?: string
    old_wang_market_reason?: string
  }
  manual_market_note?: {
    date: string
    title: string
    risk_level: 'caution' | 'risk' | 'neutral' | string
    source?: string
    headline: string
    applies_to_as_of?: string | null
    stale_trading_days?: number
    is_stale?: boolean
    update_required?: boolean
    status_label?: string
    stale_reason?: string
    position_guidance?: string
    market_actions?: string[]
    index_notes?: string[]
    stock_notes?: string[]
    rules?: string[]
  } | null
  no_buy_reason_counts: Record<string, number>
  change_report?: SignalChangeReport
}

export interface SignalChangeItem {
  code: string
  name: string
  internal_signal: string
  previous_signal?: string
  score?: number | null
  entry_score?: number | null
  old_wang_score?: number | null
  old_wang_badges?: string[]
  no_buy_reason?: string
}

export interface SignalChangeReport {
  has_previous: boolean
  previous_as_of: string | null
  new_recommendations: SignalChangeItem[]
  removed_recommendations: SignalChangeItem[]
  signal_changes: SignalChangeItem[]
  summary: {
    new_count: number
    removed_count: number
    changed_count: number
  }
}

export interface TodayScanStrategyScoreSummary {
  primary_strategy: 'old_wang' | 'steady_momentum' | 'none' | string
  primary_label: string
  primary_score: number
  old_wang_level: 'high' | 'mid' | 'low' | string
  steady_momentum_level: 'high' | 'mid' | 'low' | string
  score_gap: number
  summary_label: string
}

export interface TodayScanItem {
  code: string
  name: string
  close?: number | null
  internal_signal?: string | null
  daily_action?: string | null
  daily_action_label?: string | null
  old_wang_score?: number | null
  old_wang_signal?: string | null
  steady_momentum_score?: number | null
  steady_momentum_signal?: string | null
  strategy_score_summary?: TodayScanStrategyScoreSummary
  entry_score?: number | null
  risk_score?: number | null
  entry_price_low?: number | null
  entry_price_high?: number | null
  stop_price?: number | null
  target_price?: number | null
  reward_risk_ratio?: number | null
  vol_ratio?: number | null
  rsi14?: number | null
  data_as_of?: string | null
  reason?: string
}

export interface TodayScanFreshnessItem {
  code: string
  name: string
  data_as_of?: string | null
}

export interface TodayScanDataFreshness {
  expected_as_of?: string | null
  row_count?: number
  fresh_count?: number
  stale_count?: number
  missing_date_count?: number
  date_counts?: Record<string, number>
  top_stale_items?: TodayScanFreshnessItem[]
}

export interface TodayScanUsageStatus {
  can_use_trade_outputs: boolean
  status: 'ready' | 'no_candidates' | 'blocked_by_daily_check' | string
  headline: string
  reason: string
  next_action?: string | null
  blocking_action_key?: string | null
  blocking_action_status?: string | null
}

export interface TodayScanReport {
  as_of: string | null
  generated_at?: string | null
  rules_version?: string | null
  rules_metadata?: Record<string, unknown>
  data_status?: Record<string, unknown>
  market_context?: Record<string, unknown>
  signal_counts?: Record<string, unknown>
  formal_entries: TodayScanItem[]
  old_wang_candidates: TodayScanItem[]
  steady_momentum_candidates: TodayScanItem[]
  risk_items: TodayScanItem[]
  usage_status?: TodayScanUsageStatus
  bucket_notes?: Record<string, string>
  data_freshness?: TodayScanDataFreshness
  notes?: string[]
}

export interface UniverseReportItem {
  code: string
  name: string
  data_ok: boolean
  data_missing: boolean
  signal: string
  internal_signal: string
  entry_type: string
  score: number | null
  trend_score?: number | null
  entry_score?: number | null
  risk_score?: number | null
  long_trend: string
  short_trend: string
  market_regime?: string
  market_filter?: string
  old_wang_market_regime?: string
  old_wang_market_filter?: string
  old_wang_market_source?: string
  old_wang_market_reason?: string
  relative_strength_score?: number | null
  relative_strength_60d?: number | null
  relative_strength_120d?: number | null
  stage?: string
  entry_price_low?: number | null
  entry_price_high?: number | null
  stop_price?: number | null
  target_price?: number | null
  risk_pct?: number | null
  reward_pct?: number | null
  reward_risk_ratio?: number | null
  price_plan_note?: string
  position_size_pct?: number | null
  position_size_note?: string
  holding_shares?: number | null
  holding_avg_cost?: number | null
  holding_position_pct?: number | null
  support_price: number | null
  resistance_price: number | null
  pattern_type: string
  pattern_status: string
  no_buy_reason: string
  risk_note: string
  close: number | null
  ma5: number | null
  ma10?: number | null
  ma20: number | null
  ma60: number | null
  rsi14: number | null
  vol_ratio: number | null
  strategy_tags?: string
  old_wang_flag?: boolean
  old_wang_tag?: string
  old_wang_score?: number | null
  old_wang_raw_score?: number | null
  old_wang_signal?: string
  old_wang_reason?: string
  old_wang_sector?: string
  sector_score?: number | null
  old_wang_volume_signal?: string
  old_wang_gap_type?: string
  old_wang_gap_support?: number | null
  old_wang_gap_resistance?: number | null
  old_wang_gap_note?: string
  old_wang_ma_signal?: string
  old_wang_volume_low_support?: boolean
  old_wang_volume_low_price?: number | null
  old_wang_support_state?: string
  old_wang_ma_break_count?: number | null
  old_wang_previous_high_risk?: boolean
  old_wang_chip_signal?: string
  old_wang_previous_high_state?: string
  old_wang_previous_high_price?: number | null
  old_wang_volume_high_breakout?: boolean
  old_wang_volume_high_price?: number | null
  old_wang_all_ma_reclaim?: boolean
  old_wang_parabolic_ma10_hold?: boolean
  steady_momentum_flag?: boolean
  steady_momentum_tag?: string | null
  steady_momentum_score?: number | null
  steady_momentum_signal?: string
  steady_momentum_reason?: string
  fundamental_flag?: boolean
  fundamental_tag?: string
  fundamental_score?: number | null
  fundamental_signal?: string
  fundamental_reason?: string
  fundamental_data_ok?: boolean
  fundamental_data_missing_reason?: string
  fundamental_quality_score?: number | null
  fundamental_value_score?: number | null
  fundamental_safety_score?: number | null
  fundamental_growth_score?: number | null
  daily_action?: string
  daily_action_label?: string
  daily_action_identity?: string
  daily_action_reason?: string
  daily_key_price?: string
  daily_invalidation?: string
  daily_priority?: number | null
  daily_checklist?: DailyChecklistItem[]
  reasons: string
  /** 後端補充：交易所（TWSE / TPEX），來源 stock_markets.json */
  exchange: string
  /** 後端補充：篩選用市場分類（TWSE / TPEX / ETF），ETF 代碼以 "0" 開頭 */
  market: string
}
