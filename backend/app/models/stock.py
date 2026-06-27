from pydantic import BaseModel, Field


class ChipMetrics(BaseModel):
    data_as_of: str | None = None
    holder_data_as_of: str | None = None
    foreign_net_buy: float | None = None             # 外資買賣超（張 / 或資料來源原單位）
    investment_trust_net_buy: float | None = None    # 投信買賣超
    retail_net_buy: float | None = None              # 散戶買賣超 / 代理值
    major_investor_net_buy: float | None = None      # 大戶買賣超 / 代理值


class StockTrackingRequest(BaseModel):
    name: str | None = None
    group: str | None = None


class StockTrackingResult(BaseModel):
    code: str
    name: str
    group: str
    added: bool
    message: str
    next_action_label: str
    next_action_command: str
    next_action_copy_command: str = ""
    signals_refresh_required: bool = True


class StockRecommendation(BaseModel):
    stock_id: str
    name: str
    price: float
    change_pct: float
    score: float          # 0–100，分析分數
    reason: str           # 推薦理由
    risk_warning: str     # 風險提醒
    volume: int | None = None
    vol_ratio: float | None = None
    position_size_pct: int | None = None
    position_size_note: str | None = None
    chip: ChipMetrics = Field(default_factory=ChipMetrics)
    strategy_tags: list[str] = Field(default_factory=list)
    strategy_alignment: str | None = None
    aligned_strategies: list[str] = Field(default_factory=list)
    strategy_conflict_notes: list[str] = Field(default_factory=list)
    recommendation_source: str = "steady_momentum"    # steady_momentum | old_wang
    old_wang_market_regime: str | None = None
    old_wang_market_filter: str | None = None
    old_wang_market_source: str | None = None
    old_wang_market_reason: str | None = None
    old_wang_tag: str | None = None
    old_wang_score: float | None = None
    old_wang_raw_score: float | None = None
    old_wang_badges: list[str] = Field(default_factory=list)
    old_wang_reason: str | None = None
    old_wang_volume_signal: str | None = None
    old_wang_gap_type: str | None = None
    old_wang_gap_support: float | None = None
    old_wang_gap_resistance: float | None = None
    old_wang_gap_note: str | None = None
    old_wang_ma_signal: str | None = None
    old_wang_volume_low_support: bool | None = None
    old_wang_volume_low_price: float | None = None
    old_wang_support_state: str | None = None
    old_wang_ma_break_count: int | None = None
    old_wang_previous_high_risk: bool | None = None
    old_wang_chip_signal: str | None = None
    old_wang_previous_high_state: str | None = None
    old_wang_previous_high_price: float | None = None
    old_wang_volume_high_breakout: bool | None = None
    old_wang_volume_high_price: float | None = None
    old_wang_all_ma_reclaim: bool | None = None
    old_wang_parabolic_ma10_hold: bool | None = None
    steady_momentum_flag: bool | None = None
    steady_momentum_tag: str | None = None
    steady_momentum_score: float | None = None
    steady_momentum_signal: str | None = None
    steady_momentum_reason: str | None = None
    fundamental_flag: bool | None = None
    fundamental_tag: str | None = None
    fundamental_score: float | None = None
    fundamental_signal: str | None = None
    fundamental_reason: str | None = None
    fundamental_data_ok: bool | None = None
    fundamental_data_missing_reason: str | None = None
    fundamental_quality_score: float | None = None
    fundamental_value_score: float | None = None
    fundamental_safety_score: float | None = None
    fundamental_growth_score: float | None = None
    fundamental_data_completeness_pct: float | None = None
    fundamental_missing_fields: list[str] = Field(default_factory=list)
    fundamental_scored_groups: list[str] = Field(default_factory=list)
    daily_checklist: list[dict] = Field(default_factory=list)


class IntradayMonitor(BaseModel):
    stock_id: str
    name: str
    mode: str = "intraday_monitor"
    latest_closed_date: str | None = None
    data_ok: bool
    data_missing_reason: str = ""

    # 即時/手動輸入值；未傳入時以最新收盤價作為監控基準。
    current_price: float | None = None
    current_open: float | None = None
    current_high: float | None = None
    current_low: float | None = None
    current_volume: int | None = None

    # 收盤日線基準值。
    baseline_close: float | None = None
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    projected_vol_ratio: float | None = None

    support_state: str = "unknown"
    ma_break_count: int = 0
    previous_high_risk: bool = False
    touched_ma_levels: list[str] = Field(default_factory=list)
    broken_ma_levels: list[str] = Field(default_factory=list)

    volume_low_price: float | None = None
    volume_low_broken: bool = False
    gap_type: str = "none"
    gap_support: float | None = None
    gap_resistance: float | None = None
    gap_broken: bool = False

    monitor_signal: str = "data_missing"  # healthy | caution | risk | data_missing
    invalidates_daily_plan: bool = False
    action: str = ""
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    official_signal_note: str = "盤中監控不產生正式買賣訊號，正式訊號仍以收盤日線為準"
