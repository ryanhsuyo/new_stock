"""
股票推薦服務。
get_recommendations() 讀取 backend/out/summary.json，
預設從 signal=="BUY" 的項目產生 StockRecommendation 列表。

注意：
  _OUT 動態取自 signals_service._OUT，確保測試 monkeypatch 時路徑一致。
  若 summary.json 不存在則回傳空列表。
"""

import json

import app.services.signals_service as _svc
from app.models.stock import ChipMetrics, StockRecommendation
from app.storage.chip_store import get_chip_metrics

# 名稱查詢統一走 signals_service._stock_name，避免維護兩份對照表

# 價格快查表（目前供測試或持倉估值使用；正式資料以最新收盤價為準）
MOCK_PRICES: dict[str, float] = {}


DEFAULT_RECOMMENDATION_STRATEGY = "steady_momentum"
VALID_RECOMMENDATION_STRATEGIES = {"steady_momentum", "old_wang"}


def _normalize_badges(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v)]
    if isinstance(value, str):
        return [v for v in value.split(",") if v]
    return []


def _normalize_strategy(strategy: str | None) -> str:
    if strategy == "core":
        return DEFAULT_RECOMMENDATION_STRATEGY
    if strategy not in VALID_RECOMMENDATION_STRATEGIES:
        return DEFAULT_RECOMMENDATION_STRATEGY
    return strategy


def _load_signals(strategy: str = DEFAULT_RECOMMENDATION_STRATEGY) -> list[dict]:
    """
    讀取 summary.json，回傳指定策略的訊號列表（依分數排序）。

    - old_wang：只回傳老王大盤籌碼輪動 tag 成立的標的
    - steady_momentum：只回傳穩健動能成立的標的

    _OUT 動態取自 signals_service._OUT，確保與 monkeypatch 一致。
    """
    strategy = _normalize_strategy(strategy)

    path = _svc._OUT / "summary.json"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        summary = json.load(f)

    signals = summary.get("signals", [])
    if strategy == "old_wang":
        hits = [s for s in signals if s.get("old_wang_flag")]
    else:
        hits = [s for s in signals if s.get("steady_momentum_flag")]

    hits.sort(
        key=lambda s: (
            s.get("steady_momentum_score", 0),
            s.get("entry_score", 0),
            s.get("old_wang_score", 0),
            s.get("score", 0),
        ),
        reverse=True,
    )
    return hits


def _signal_to_recommendation(sig: dict, strategy: str = "core") -> StockRecommendation:
    code      = sig["code"]
    close     = sig.get("close") or 0.0
    ma20      = sig.get("ma20")
    ma60      = sig.get("ma60")
    rsi14     = sig.get("rsi14")
    strategy = _normalize_strategy(strategy)
    score = sig.get("steady_momentum_score") if strategy == "steady_momentum" else sig.get("score", 60)
    score = score if score is not None else sig.get("score", 60)
    entry_score = sig.get("entry_score")
    trend_score = sig.get("trend_score")
    entry_type = sig.get("entry_type", "")
    internal  = sig.get("internal_signal", "")

    # reasons 來自 v2 signals（list）或舊格式（空）
    raw_reasons = sig.get("reasons", [])
    if isinstance(raw_reasons, list) and raw_reasons:
        reason_text = "；".join(raw_reasons)
    else:
        reason_text = f"收盤 {close}，RSI:{rsi14}"

    entry_label = {"entry_confirmed": "突破確認", "ready_to_enter": "準備入場"}.get(
        internal, entry_type or "買入"
    )
    score_text = ""
    if entry_score is not None and trend_score is not None:
        score_text = f" 進場分:{entry_score}，趨勢分:{trend_score}。"
    reason = f"[{entry_label}]{score_text} {reason_text}"

    if strategy == "old_wang":
        old_wang_signal = sig.get("old_wang_signal") or "old_wang"
        old_wang_reason = sig.get("old_wang_reason") or reason_text
        reason = f"[老王大盤籌碼輪動:{old_wang_signal}] {old_wang_reason}"
    elif strategy == "steady_momentum":
        steady_signal = sig.get("steady_momentum_signal") or "steady_momentum"
        steady_reason = sig.get("steady_momentum_reason") or reason_text
        reason = f"[穩健動能:{steady_signal}] {steady_reason}"

    risk_raw = sig.get("risk_note", "")
    if not risk_raw or risk_raw == "—":
        risk_warning = f"支撐參考 MA20({ma20})，跌破需留意；RSI:{rsi14}"
    else:
        risk_warning = risk_raw

    MOCK_PRICES[code] = close
    chip_raw = get_chip_metrics(code)
    tags = sig.get("strategy_tags", [])
    if isinstance(tags, str):
        tags = [t for t in tags.split(",") if t]
    if not isinstance(tags, list):
        tags = []
    old_wang_badges = _normalize_badges(sig.get("old_wang_badges"))

    recommendation_source = strategy

    return StockRecommendation(
        stock_id=code,
        name=_svc._stock_name(code),
        price=close,
        change_pct=0.0,
        score=float(score),
        reason=reason,
        risk_warning=risk_warning,
        volume=sig.get("volume"),
        vol_ratio=sig.get("vol_ratio"),
        position_size_pct=sig.get("position_size_pct"),
        position_size_note=sig.get("position_size_note"),
        chip=ChipMetrics(
            data_as_of=chip_raw.get("data_as_of"),
            holder_data_as_of=chip_raw.get("holder_data_as_of"),
            foreign_net_buy=chip_raw.get("foreign_net_buy"),
            investment_trust_net_buy=chip_raw.get("investment_trust_net_buy"),
            retail_net_buy=chip_raw.get("retail_net_buy"),
            major_investor_net_buy=chip_raw.get("major_investor_net_buy"),
        ),
        strategy_tags=tags,
        strategy_alignment=sig.get("strategy_alignment"),
        aligned_strategies=sig.get("aligned_strategies") or [],
        strategy_conflict_notes=sig.get("strategy_conflict_notes") or [],
        recommendation_source=recommendation_source,
        old_wang_market_regime=sig.get("old_wang_market_regime"),
        old_wang_market_filter=sig.get("old_wang_market_filter"),
        old_wang_market_source=sig.get("old_wang_market_source"),
        old_wang_market_reason=sig.get("old_wang_market_reason"),
        old_wang_tag=sig.get("old_wang_tag") or None,
        old_wang_score=sig.get("old_wang_score"),
        old_wang_raw_score=sig.get("old_wang_raw_score"),
        old_wang_badges=old_wang_badges,
        old_wang_reason=sig.get("old_wang_reason") or None,
        old_wang_volume_signal=sig.get("old_wang_volume_signal"),
        old_wang_gap_type=sig.get("old_wang_gap_type"),
        old_wang_gap_support=sig.get("old_wang_gap_support"),
        old_wang_gap_resistance=sig.get("old_wang_gap_resistance"),
        old_wang_gap_note=sig.get("old_wang_gap_note") or None,
        old_wang_ma_signal=sig.get("old_wang_ma_signal"),
        old_wang_volume_low_support=sig.get("old_wang_volume_low_support"),
        old_wang_volume_low_price=sig.get("old_wang_volume_low_price"),
        old_wang_support_state=sig.get("old_wang_support_state"),
        old_wang_ma_break_count=sig.get("old_wang_ma_break_count"),
        old_wang_previous_high_risk=sig.get("old_wang_previous_high_risk"),
        old_wang_chip_signal=sig.get("old_wang_chip_signal"),
        old_wang_previous_high_state=sig.get("old_wang_previous_high_state"),
        old_wang_previous_high_price=sig.get("old_wang_previous_high_price"),
        old_wang_volume_high_breakout=sig.get("old_wang_volume_high_breakout"),
        old_wang_volume_high_price=sig.get("old_wang_volume_high_price"),
        old_wang_all_ma_reclaim=sig.get("old_wang_all_ma_reclaim"),
        old_wang_parabolic_ma10_hold=sig.get("old_wang_parabolic_ma10_hold"),
        steady_momentum_flag=sig.get("steady_momentum_flag"),
        steady_momentum_tag=sig.get("steady_momentum_tag") or None,
        steady_momentum_score=sig.get("steady_momentum_score"),
        steady_momentum_signal=sig.get("steady_momentum_signal"),
        steady_momentum_reason=sig.get("steady_momentum_reason") or None,
        fundamental_flag=sig.get("fundamental_flag"),
        fundamental_tag=sig.get("fundamental_tag") or None,
        fundamental_score=sig.get("fundamental_score"),
        fundamental_signal=sig.get("fundamental_signal"),
        fundamental_reason=sig.get("fundamental_reason") or None,
        fundamental_data_ok=sig.get("fundamental_data_ok"),
        fundamental_data_missing_reason=sig.get("fundamental_data_missing_reason") or None,
        fundamental_quality_score=sig.get("fundamental_quality_score"),
        fundamental_value_score=sig.get("fundamental_value_score"),
        fundamental_safety_score=sig.get("fundamental_safety_score"),
        fundamental_growth_score=sig.get("fundamental_growth_score"),
        fundamental_data_completeness_pct=sig.get("fundamental_data_completeness_pct"),
        fundamental_missing_fields=sig.get("fundamental_missing_fields") or [],
        fundamental_scored_groups=sig.get("fundamental_scored_groups") or [],
        daily_checklist=sig.get("daily_checklist") or [],
    )


def get_recommendations(
    sort_by: str | None = None,
    min_score: float | None = None,
    strategy: str = DEFAULT_RECOMMENDATION_STRATEGY,
) -> list[StockRecommendation]:
    strategy = _normalize_strategy(strategy)
    signals = _load_signals(strategy)
    return [_signal_to_recommendation(s, strategy=strategy) for s in signals]


def get_all_current_prices() -> dict[str, float]:
    """回傳最新收盤價（BUY 標的），供持倉估值使用。"""
    if not MOCK_PRICES:
        get_recommendations()
    return MOCK_PRICES
