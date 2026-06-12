"""
analysis.py — 單檔股票分析的 Pydantic models

對應 GET /api/stocks/{code}/analysis 的 response schema。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class OhlcvBar(BaseModel):
    """單根 K 棒資料，供前端圖表使用。"""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PricePoint(BaseModel):
    """趨勢線上的一個錨點：日期 + 價格。"""
    date: str
    price: float


class SupportResistanceLine(BaseModel):
    """單條支撐或壓力線。"""
    label: str           # 人可讀說明，例如「近20日低點支撐」
    price: float         # 價格水位
    type: str            # "static"（區間高低點）或 "dynamic"（均線）


class TrendLine(BaseModel):
    """趨勢線：兩個錨點確定一條線；valid=False 表示資料不足或無法辨識。"""
    valid: bool
    p1: PricePoint | None = None
    p2: PricePoint | None = None
    note: str            # 說明文字或失效原因


class PatternResult(BaseModel):
    """型態辨識結果。"""
    pattern_type: str    # "none" | "w_bottom" | "m_top" | "head_and_shoulders_bottom"
    pattern_status: str  # "none" | "forming" | "confirmed" | "failed"
    neckline: float | None = None   # 頸線價格；pattern_type="none" 時為 null
    note: str = ""       # 說明文字


class DataDiagnostic(BaseModel):
    """單檔分析資料診斷，供前端顯示價格基準與缺資料下一步。"""
    status: str = "ok"                  # ok | not_tracked | no_ohlcv_data | insufficient_rows
    row_count: int = 0
    required_rows: int = 60
    last_data_as_of: str | None = None
    price_basis: str = "latest_close"
    price_basis_label: str = "最新收盤價"
    price_basis_note: str = "技術分析、支撐壓力與買入預填使用 ohlcv.csv 最新收盤價，不是盤中即時市價。"
    message: str = ""
    next_action_label: str = ""
    next_action_command: str = ""
    next_action_copy_command: str = ""


class StockAnalysis(BaseModel):
    """單檔股票完整分析結果。"""
    code: str
    stock_id: str   # 與 code 相同；對齊 signal_rules.md 欄位名稱及 StockRecommendation
    name: str
    as_of: str

    # 資料狀態
    data_ok: bool
    data_missing_reason: str    # data_ok=False 時說明原因；正常時為 ""
    data_diagnostic: DataDiagnostic = Field(default_factory=DataDiagnostic)

    # 資料新鮮度（as_of 為資料最後一筆日期；stale_days 為距今日曆天數）
    is_stale: bool = False      # True 表示錯過 ≥1 個已收盤交易日（週一～週五）未更新
    stale_days: int = 0         # 距今曆日數（供顯示用）；0 = 最新

    # 技術指標
    close: float | None
    ma5: float | None
    ma20: float | None
    ma60: float | None
    rsi14: float | None
    vol_ratio: float | None

    # 趨勢判斷
    long_trend: str     # "up" | "down" | "neutral" | "unknown"
    short_trend: str    # "up" | "down" | "neutral" | "unknown"

    # 訊號（7 狀態，此 endpoint 不受 BUY/SELL/HOLD 相容限制）
    signal: str
    score: int          # 0–100
    trend_score: int = 0
    entry_score: int = 0
    risk_score: int = 0

    # 專業濾網
    market_regime: str = "unknown"       # "bull" | "neutral" | "bear" | "unknown"
    market_filter: str = "neutral"       # "allow" | "caution" | "block" | "neutral"
    old_wang_market_regime: str = "unknown"
    old_wang_market_filter: str = "neutral"
    old_wang_market_source: str = ""
    old_wang_market_reason: str = ""
    relative_strength_score: int | None = None
    relative_strength_60d: float | None = None
    relative_strength_120d: float | None = None
    stage: str = "unknown"               # "stage_1" | "stage_2" | "stage_3" | "stage_4" | "unknown"
    entry_price_low: float | None = None
    entry_price_high: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    risk_pct: float | None = None
    reward_pct: float | None = None
    reward_risk_ratio: float | None = None
    price_plan_note: str = ""
    position_size_pct: int = 0
    position_size_note: str = ""
    strategy_tags: list[str] = []
    old_wang_flag: bool = False
    old_wang_tag: str | None = None
    old_wang_score: int | None = None
    old_wang_raw_score: int | None = None
    old_wang_signal: str = ""
    old_wang_reason: str = ""
    old_wang_sector: str = ""
    old_wang_volume_signal: str = "unknown"
    old_wang_gap_type: str = "none"
    old_wang_gap_support: float | None = None
    old_wang_gap_resistance: float | None = None
    old_wang_gap_note: str = ""
    old_wang_ma_signal: str = "unknown"
    old_wang_volume_low_support: bool = False
    old_wang_volume_low_price: float | None = None
    old_wang_support_state: str = "unknown"
    old_wang_ma_break_count: int = 0
    old_wang_previous_high_risk: bool = False
    old_wang_chip_signal: str = "unknown"
    old_wang_previous_high_state: str = "none"
    old_wang_previous_high_price: float | None = None
    old_wang_volume_high_breakout: bool = False
    old_wang_volume_high_price: float | None = None
    old_wang_all_ma_reclaim: bool = False
    old_wang_parabolic_ma10_hold: bool = False
    daily_action: str = ""
    daily_action_label: str = ""
    daily_action_identity: str = ""
    daily_action_reason: str = ""
    daily_key_price: str = ""
    daily_invalidation: str = ""
    daily_priority: int = 99
    daily_checklist: list[dict] = []

    # 解釋
    reasons: list[str]
    risk_notes: list[str]
    no_buy_reason: str  # 非入場時的單句摘要

    # 支撐壓力線（可多條，供前端畫線）
    support_lines: list[SupportResistanceLine]
    resistance_lines: list[SupportResistanceLine]

    # 趨勢線（第一版：連接兩個有效高/低點）
    uptrend_line: TrendLine
    downtrend_line: TrendLine

    # 型態辨識
    pattern: PatternResult

    # K 棒資料（最近 120 根，供前端圖表繪製）
    ohlcv: list[OhlcvBar] = []


class HoldingAnalysis(BaseModel):
    """持股分析：成本資訊 + 技術分析結果。"""
    avg_cost: float                        # 持股均價（由 trades.json 推算）
    shares: int                            # 持股股數
    unrealized_pnl: float | None = None   # 未實現損益；資料不足時 None
    return_rate: float | None = None       # 報酬率 %；資料不足時 None
    analysis: StockAnalysis                # 完整技術分析（含 signal / reasons / risk_notes / pattern）


class PortfolioSummary(BaseModel):
    """投組總覽摘要。"""
    total_positions: int           # 持股檔數
    total_cost: float              # 總持股成本
    total_market_value: float      # 收盤估值（無最新收盤價者以成本代替）
    total_unrealized_pnl: float    # 總未實現損益
    hold_count: int                # signal=hold 數量
    take_profit_warning_count: int # signal=take_profit_warning 數量
    exit_warning_count: int        # signal=exit_warning 數量
    invalidated_count: int         # signal=invalidated 數量
