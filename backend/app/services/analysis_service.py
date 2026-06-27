"""
analysis_service.py — 單檔股票深度分析服務

依 backend/docs/signal_rules.md 實作：
  - 支撐 / 壓力：近 20 日 + 近 60 日靜態區間、MA20 / MA60 動態線
  - 趨勢線：偵測擺盪高低點（swing high / low），連接兩個有效點
  - 訊號：直接複用 signals_service._compute_signal，取 internal_signal（7 狀態）
  - reasons / risk_notes：從 signals_service 結果轉出

公開介面
--------
    analyse_stock(code: str, as_of_date: str | None = None) -> dict

回傳 dict 符合 StockAnalysis schema，可直接序列化成 JSON。
"""

from datetime import date as _date, timedelta as _timedelta
from pathlib import Path

from app.utils import count_missed_trading_days

# ── 複用 signals_service 的指標計算與訊號邏輯 ─────────────────────────────
# 以 import-then-call 方式，確保測試 monkeypatch signals_service 路徑時生效
from app.services.signals_service import (
    LEADERS_PATH,
    MIN_ROWS,
    _compute_signal,
    _daily_checklist,
    _daily_decision_plan,
    _flatten_codes,
    _load_ohlcv,
    _load_positions,
    _ma,
    _stock_name,
)

from app.models.analysis import (
    DataDiagnostic,
    OhlcvBar,
    PatternResult,
    PricePoint,
    StockAnalysis,
    SupportResistanceLine,
    TrendLine,
)
from app.services.pattern_service import detect_pattern

_CHART_BARS = 120   # 回傳給前端的最近 K 棒數量
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPAIR_COMMAND = "python3 scripts/daily_update.py --months 12"
_REPAIR_COPY_COMMAND = f"cd {_BACKEND_DIR}\n{_REPAIR_COMMAND}"

# ---------------------------------------------------------------------------
# 缺資料原因診斷
# ---------------------------------------------------------------------------

def _tracked_codes() -> set[str]:
    import json as _json

    if LEADERS_PATH.exists():
        with LEADERS_PATH.open(encoding="utf-8") as f:
            return set(_flatten_codes(_json.load(f)))
    return set()


def _build_data_diagnostic(code: str, rows: list[dict], actual_as_of: str) -> DataDiagnostic:
    row_count = len(rows)
    tracked = code in _tracked_codes()
    if not tracked:
        return DataDiagnostic(
            status="not_tracked",
            row_count=row_count,
            required_rows=MIN_ROWS,
            last_data_as_of=actual_as_of,
            message=f"股票 {code} 不在追蹤清單 leaders.json 中。",
            next_action_label="加入追蹤清單並回補",
            next_action_command=f"將代碼加入 backend/data/leaders.json 後，執行 {_REPAIR_COMMAND}",
            next_action_copy_command=_REPAIR_COPY_COMMAND,
        )
    if row_count == 0:
        return DataDiagnostic(
            status="no_ohlcv_data",
            row_count=0,
            required_rows=MIN_ROWS,
            last_data_as_of=actual_as_of,
            message=f"股票 {code} 已在追蹤清單中，但 ohlcv.csv 尚無日線資料。",
            next_action_label="回補日線資料",
            next_action_command=_REPAIR_COMMAND,
            next_action_copy_command=_REPAIR_COPY_COMMAND,
        )
    if row_count < MIN_ROWS:
        return DataDiagnostic(
            status="insufficient_rows",
            row_count=row_count,
            required_rows=MIN_ROWS,
            last_data_as_of=actual_as_of,
            message=f"股票 {code} 目前僅有 {row_count} 筆資料，需 {MIN_ROWS} 筆才能計算 MA60。",
            next_action_label="補足更多歷史資料",
            next_action_command=_REPAIR_COMMAND,
            next_action_copy_command=_REPAIR_COPY_COMMAND,
        )
    return DataDiagnostic(
        status="ok",
        row_count=row_count,
        required_rows=MIN_ROWS,
        last_data_as_of=actual_as_of,
        message="資料可用；正式分析使用最新收盤價，不是盤中即時市價。",
        next_action_label="",
        next_action_command="",
    )


def _diagnose_missing(code: str, rows: list[dict]) -> str:
    """
    三段式缺資料診斷：
      1. 不在追蹤清單（leaders.json）
      2. 在清單但尚未回補任何資料
      3. 有資料但不足 MIN_ROWS 天
    """
    leaders_set = _tracked_codes()

    if code not in leaders_set:
        return (
            f"股票 {code} 不在追蹤清單（leaders.json）中。"
            f"如需分析，請先將代碼加入 leaders.json，再執行 daily_update。"
        )
    if not rows:
        return (
            f"股票 {code} 已在追蹤清單中，但尚未回補歷史資料。"
            f"請執行：python3 scripts/daily_update.py --months 12"
        )
    return (
        f"股票 {code} 目前僅有 {len(rows)} 筆資料（需 {MIN_ROWS} 筆才能計算 MA60）。"
        f"請執行 daily_update 補足更多歷史資料。"
    )

# ---------------------------------------------------------------------------
# 支撐壓力線建構
# ---------------------------------------------------------------------------

def _build_support_lines(
    rows: list[dict],
    ma20: float | None,
    ma60: float | None,
) -> list[SupportResistanceLine]:
    """
    建立支撐線清單（由強到弱排列）：
      1. 近20日低點（靜態）
      2. 近60日低點（靜態，若與20日不同）
      3. MA20（動態，長線多頭時為短線支撐）
      4. MA60（動態，長線主支撐）
    """
    lines: list[SupportResistanceLine] = []

    # 1. 近20日低點支撐（不含今日）
    w20 = rows[-21:-1]
    if w20:
        p = round(min(r["low"] for r in w20), 2)
        lines.append(SupportResistanceLine(label="近20日低點支撐", price=p, type="static"))

    # 2. 近60日低點支撐（不含今日，與20日不同才加）
    w60 = rows[-61:-1]
    if len(rows) >= 62 and w60:
        p60 = round(min(r["low"] for r in w60), 2)
        if not lines or p60 < lines[0].price:
            lines.append(SupportResistanceLine(label="近60日低點支撐", price=p60, type="static"))

    # 3. MA20 動態支撐
    if ma20 is not None:
        lines.append(SupportResistanceLine(label="MA20 動態支撐", price=ma20, type="dynamic"))

    # 4. MA60 動態支撐
    if ma60 is not None:
        lines.append(SupportResistanceLine(label="MA60 動態支撐", price=ma60, type="dynamic"))

    return lines


def _build_resistance_lines(
    rows: list[dict],
    ma20: float | None,
    ma60: float | None,
) -> list[SupportResistanceLine]:
    """
    建立壓力線清單：
      1. 近20日高點（靜態）
      2. 近60日高點（靜態，若與20日不同）
    均線在多頭排列時為支撐，不列為壓力；收盤低於均線時均線才是壓力。
    """
    lines: list[SupportResistanceLine] = []

    w20 = rows[-21:-1]
    if w20:
        p = round(max(r["high"] for r in w20), 2)
        lines.append(SupportResistanceLine(label="近20日高點壓力", price=p, type="static"))

    w60 = rows[-61:-1]
    if len(rows) >= 62 and w60:
        p60 = round(max(r["high"] for r in w60), 2)
        if not lines or p60 > lines[0].price:
            lines.append(SupportResistanceLine(label="近60日高點壓力", price=p60, type="static"))

    return lines


# ---------------------------------------------------------------------------
# 擺盪點偵測
# ---------------------------------------------------------------------------

def _find_swing_lows(rows: list[dict], window: int = 5) -> list[dict]:
    """
    偵測擺盪低點：
    rows[i] 是擺盪低點若 low[i] ≤ 前後各 window 根 K 棒的 low。

    返回 [{"date": str, "price": float}, ...]，由舊到新排列。
    限制：只看最近 120 根，避免資料太舊。
    """
    lows  = [r["low"]  for r in rows[-120:]]
    dates = [r["date"] for r in rows[-120:]]
    result: list[dict] = []

    for i in range(window, len(lows) - window):
        is_low = all(lows[i] <= lows[i - j] for j in range(1, window + 1)) and \
                 all(lows[i] <= lows[i + j] for j in range(1, window + 1))
        if is_low:
            result.append({"date": dates[i], "price": lows[i]})

    return result


def _find_swing_highs(rows: list[dict], window: int = 5) -> list[dict]:
    """
    偵測擺盪高點：high[i] ≥ 前後各 window 根 K 棒的 high。
    """
    highs = [r["high"] for r in rows[-120:]]
    dates = [r["date"] for r in rows[-120:]]
    result: list[dict] = []

    for i in range(window, len(highs) - window):
        is_high = all(highs[i] >= highs[i - j] for j in range(1, window + 1)) and \
                  all(highs[i] >= highs[i + j] for j in range(1, window + 1))
        if is_high:
            result.append({"date": dates[i], "price": highs[i]})

    return result


# ---------------------------------------------------------------------------
# 趨勢線建構
# ---------------------------------------------------------------------------

def _row_indexes_by_date(rows: list[dict]) -> dict[str, int]:
    return {str(row["date"]): index for index, row in enumerate(rows)}


def _select_multi_touch_pair(
    rows: list[dict],
    swings: list[dict],
    *,
    direction: str,
    tolerance: float = 0.02,
) -> tuple[dict, dict, int] | None:
    if len(swings) < 3 or direction not in {"up", "down"}:
        return None

    row_indexes = _row_indexes_by_date(rows)
    indexed_swings = []
    for swing in swings:
        index = row_indexes.get(str(swing.get("date")))
        price = swing.get("price")
        if index is None or not isinstance(price, (int, float)) or price <= 0:
            return None
        indexed_swings.append((index, swing))
    if any(
        left[0] >= right[0]
        for left, right in zip(indexed_swings, indexed_swings[1:])
    ):
        return None

    best = None
    best_rank = None
    for first in range(len(indexed_swings) - 1):
        p1_index, p1 = indexed_swings[first]
        p1_price = float(p1["price"])
        for second in range(first + 1, len(indexed_swings)):
            p2_index, p2 = indexed_swings[second]
            p2_price = float(p2["price"])
            if direction == "up" and p2_price <= p1_price:
                continue
            if direction == "down" and p2_price >= p1_price:
                continue

            slope = (p2_price - p1_price) / (p2_index - p1_index)
            touches = 0
            violated = False
            for swing_index, swing in indexed_swings[first:]:
                projected = p1_price + slope * (swing_index - p1_index)
                if projected <= 0:
                    violated = True
                    break
                price = float(swing["price"])
                error = abs(price - projected) / projected
                if direction == "up" and price < projected * (1 - tolerance):
                    violated = True
                    break
                if direction == "down" and price > projected * (1 + tolerance):
                    violated = True
                    break
                if error <= tolerance:
                    touches += 1

            if violated or touches < 3:
                continue
            rank = (touches, p2_index, p2_index - p1_index)
            if best_rank is None or rank > best_rank:
                best = (p1, p2, touches)
                best_rank = rank

    return best

def _build_uptrend_line(rows: list[dict], window: int = 5) -> TrendLine:
    """
    上升趨勢線：連接最近兩個**遞增**擺盪低點（p1.price < p2.price）。
    若找不到，回傳 valid=False。

    signal_rules.md §2.6：趨勢線只連有效高低點。
    """
    swings = _find_swing_lows(rows, window)

    candidate = _select_multi_touch_pair(rows, swings, direction="up")
    if candidate is not None:
        p1, p2, touch_count = candidate
        return TrendLine(
            valid=True,
            p1=PricePoint(date=p1["date"], price=p1["price"]),
            p2=PricePoint(date=p2["date"], price=p2["price"]),
            note=f"連接遞增擺盪低點，多點確認（{touch_count} 個有效觸點）",
        )

    # 從最新往前找兩個遞增低點
    for i in range(len(swings) - 1, 0, -1):
        p2 = swings[i]
        for j in range(i - 1, -1, -1):
            p1 = swings[j]
            if p2["price"] > p1["price"]:   # 低點遞增 → 上升趨勢
                return TrendLine(
                    valid=True,
                    p1=PricePoint(date=p1["date"], price=p1["price"]),
                    p2=PricePoint(date=p2["date"], price=p2["price"]),
                    note="連接兩個遞增擺盪低點（上升趨勢線）",
                )

    return TrendLine(
        valid=False, p1=None, p2=None,
        note="未找到有效遞增擺盪低點，無法確認上升趨勢線",
    )


def _build_downtrend_line(rows: list[dict], window: int = 5) -> TrendLine:
    """
    下降趨勢線：連接最近兩個**遞減**擺盪高點（p1.price > p2.price）。
    """
    swings = _find_swing_highs(rows, window)

    candidate = _select_multi_touch_pair(rows, swings, direction="down")
    if candidate is not None:
        p1, p2, touch_count = candidate
        return TrendLine(
            valid=True,
            p1=PricePoint(date=p1["date"], price=p1["price"]),
            p2=PricePoint(date=p2["date"], price=p2["price"]),
            note=f"連接遞減擺盪高點，多點確認（{touch_count} 個有效觸點）",
        )

    for i in range(len(swings) - 1, 0, -1):
        p2 = swings[i]
        for j in range(i - 1, -1, -1):
            p1 = swings[j]
            if p2["price"] < p1["price"]:   # 高點遞減 → 下降趨勢
                return TrendLine(
                    valid=True,
                    p1=PricePoint(date=p1["date"], price=p1["price"]),
                    p2=PricePoint(date=p2["date"], price=p2["price"]),
                    note="連接兩個遞減擺盪高點（下降趨勢線）",
                )

    return TrendLine(
        valid=False, p1=None, p2=None,
        note="未找到有效遞減擺盪高點，無法確認下降趨勢線",
    )


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def analyse_stock(code: str, as_of_date: str | None = None) -> StockAnalysis:
    """
    單檔股票深度分析。

    Parameters
    ----------
    code : str
        股票代碼（例如 "2330"）
    as_of_date : str | None
        計算基準日（YYYY-MM-DD）。None = 今日。

    Returns
    -------
    StockAnalysis
        含支撐壓力、趨勢線、訊號、reasons、risk_notes 的完整分析結果。
    """
    if as_of_date is None:
        as_of_date = _date.today().isoformat()

    name      = _stock_name(code)
    ohlcv     = _load_ohlcv(as_of_date)
    rows      = ohlcv.get(code, [])
    positions = _load_positions()

    # as_of 使用資料實際最後一筆日期，而非請求的截止日。
    # 這樣前端「基準日」才能與圖表最後一根 K 棒一致。
    actual_as_of = rows[-1]["date"] if rows else as_of_date
    data_diagnostic = _build_data_diagnostic(code, rows, actual_as_of)

    # 資料新鮮度：以交易日（週一～週五）計算錯過的已收盤交易日數
    try:
        data_date = _date.fromisoformat(actual_as_of)
        stale_days = (_date.today() - data_date).days
        is_stale = count_missed_trading_days(data_date) > 0
    except ValueError:
        stale_days = 0
        is_stale = False

    # ── 資料不足（含三段式診斷） ──────────────────────────────────────────
    if len(rows) < MIN_ROWS:
        reason = _diagnose_missing(code, rows)
        return StockAnalysis(
            code=code, stock_id=code, name=name, as_of=actual_as_of,
            data_ok=False,
            data_missing_reason=reason,
            data_diagnostic=data_diagnostic,
            is_stale=is_stale,
            stale_days=stale_days,
            close=rows[-1]["close"] if rows else None,
            ma5=None, ma20=None, ma60=None, rsi14=None, vol_ratio=None,
            long_trend="unknown", short_trend="unknown",
            signal="DATA_MISSING", score=0,
            trend_score=0, entry_score=0, risk_score=0,
            market_regime="unknown", market_filter="neutral",
            relative_strength_score=None,
            relative_strength_60d=None, relative_strength_120d=None,
            stage="unknown",
            entry_price_low=None,
            entry_price_high=None,
            stop_price=None, target_price=None,
            risk_pct=None, reward_pct=None, reward_risk_ratio=None,
            price_plan_note="資料不足，無法估算進出場價格",
            reasons=[reason],
            risk_notes=["資料不足，無法進行技術分析"],
            no_buy_reason=reason,
            support_lines=[],
            resistance_lines=[],
            uptrend_line=TrendLine(valid=False, note=reason),
            downtrend_line=TrendLine(valid=False, note=reason),
            pattern=PatternResult(
                pattern_type="none", pattern_status="none",
                note="資料不足，無法進行型態辨識",
            ),
        )

    # ── K 棒資料（最近 _CHART_BARS 根，供前端圖表使用）──────────────────────
    chart_rows = rows[-_CHART_BARS:]
    ohlcv_bars = [
        OhlcvBar(
            date=r["date"], open=r["open"], high=r["high"],
            low=r["low"], close=r["close"], volume=r["volume"],
        )
        for r in chart_rows
    ]

    # ── 複用 signals_service 訊號計算 ─────────────────────────────────────
    sig = _compute_signal(code, rows, positions)
    sig.update(_daily_decision_plan(sig))
    sig["daily_checklist"] = _daily_checklist(sig)

    # reasons 已是 list；risk_note 是分號分隔字串
    risk_raw  = sig.get("risk_note", "")
    risk_notes = (
        [n.strip() for n in risk_raw.split("；") if n.strip() and n.strip() != "—"]
        if risk_raw and risk_raw != "—" else []
    )

    # ── 支撐壓力線 ────────────────────────────────────────────────────────
    ma20 = sig["ma20"]
    ma60 = sig["ma60"]
    support_lines    = _build_support_lines(rows, ma20, ma60)
    resistance_lines = _build_resistance_lines(rows, ma20, ma60)

    # ── 趨勢線 ────────────────────────────────────────────────────────────
    uptrend_line   = _build_uptrend_line(rows)
    downtrend_line = _build_downtrend_line(rows)

    # ── 型態辨識 ──────────────────────────────────────────────────────────
    pattern = detect_pattern(rows)

    # 型態加減分已由 signals_service._compute_signal 統一處理；
    # analysis endpoint 僅轉出同一份結果，避免單股與批次分析分數不一致。
    final_score = sig["score"]
    final_reasons = sig.get("reasons", [])
    final_risk_notes = risk_notes

    return StockAnalysis(
        code=code,
        stock_id=code,
        name=name,
        as_of=actual_as_of,
        data_ok=True,
        data_missing_reason="",
        data_diagnostic=data_diagnostic,
        is_stale=is_stale,
        stale_days=stale_days,
        close=sig["close"],
        ma5=sig["ma5"],
        ma20=ma20,
        ma60=ma60,
        rsi14=sig["rsi14"],
        vol_ratio=sig["vol_ratio"],
        long_trend=sig["long_trend"],
        short_trend=sig["short_trend"],
        signal=sig["internal_signal"],    # 7 狀態（分析 endpoint 不受舊契約限制）
        score=final_score,
        trend_score=sig.get("trend_score", 0),
        entry_score=sig.get("entry_score", 0),
        risk_score=sig.get("risk_score", 0),
        market_regime=sig.get("market_regime", "unknown"),
        market_filter=sig.get("market_filter", "neutral"),
        old_wang_market_regime=sig.get("old_wang_market_regime", "unknown"),
        old_wang_market_filter=sig.get("old_wang_market_filter", "neutral"),
        old_wang_market_source=sig.get("old_wang_market_source", ""),
        old_wang_market_reason=sig.get("old_wang_market_reason", ""),
        relative_strength_score=sig.get("relative_strength_score"),
        relative_strength_60d=sig.get("relative_strength_60d"),
        relative_strength_120d=sig.get("relative_strength_120d"),
        stage=sig.get("stage", "unknown"),
        entry_price_low=sig.get("entry_price_low"),
        entry_price_high=sig.get("entry_price_high"),
        stop_price=sig.get("stop_price"),
        target_price=sig.get("target_price"),
        risk_pct=sig.get("risk_pct"),
        reward_pct=sig.get("reward_pct"),
        reward_risk_ratio=sig.get("reward_risk_ratio"),
        price_plan_note=sig.get("price_plan_note", ""),
        position_size_pct=sig.get("position_size_pct", 0),
        position_size_note=sig.get("position_size_note", ""),
        strategy_tags=sig.get("strategy_tags", []),
        old_wang_flag=sig.get("old_wang_flag", False),
        old_wang_tag=sig.get("old_wang_tag") or None,
        old_wang_score=sig.get("old_wang_score"),
        old_wang_raw_score=sig.get("old_wang_raw_score"),
        old_wang_signal=sig.get("old_wang_signal", ""),
        old_wang_reason=sig.get("old_wang_reason", ""),
        old_wang_sector=sig.get("old_wang_sector", ""),
        old_wang_volume_signal=sig.get("old_wang_volume_signal", "unknown"),
        old_wang_gap_type=sig.get("old_wang_gap_type", "none"),
        old_wang_gap_support=sig.get("old_wang_gap_support"),
        old_wang_gap_resistance=sig.get("old_wang_gap_resistance"),
        old_wang_gap_note=sig.get("old_wang_gap_note", ""),
        old_wang_ma_signal=sig.get("old_wang_ma_signal", "unknown"),
        old_wang_volume_low_support=sig.get("old_wang_volume_low_support", False),
        old_wang_volume_low_price=sig.get("old_wang_volume_low_price"),
        old_wang_support_state=sig.get("old_wang_support_state", "unknown"),
        old_wang_ma_break_count=sig.get("old_wang_ma_break_count", 0),
        old_wang_previous_high_risk=sig.get("old_wang_previous_high_risk", False),
        old_wang_chip_signal=sig.get("old_wang_chip_signal", "unknown"),
        old_wang_previous_high_state=sig.get("old_wang_previous_high_state", "none"),
        old_wang_previous_high_price=sig.get("old_wang_previous_high_price"),
        old_wang_volume_high_breakout=sig.get("old_wang_volume_high_breakout", False),
        old_wang_volume_high_price=sig.get("old_wang_volume_high_price"),
        old_wang_all_ma_reclaim=sig.get("old_wang_all_ma_reclaim", False),
        old_wang_parabolic_ma10_hold=sig.get("old_wang_parabolic_ma10_hold", False),
        daily_action=sig.get("daily_action", ""),
        daily_action_label=sig.get("daily_action_label", ""),
        daily_action_identity=sig.get("daily_action_identity", ""),
        daily_action_reason=sig.get("daily_action_reason", ""),
        daily_key_price=sig.get("daily_key_price", ""),
        daily_invalidation=sig.get("daily_invalidation", ""),
        daily_priority=sig.get("daily_priority", 99),
        daily_checklist=sig.get("daily_checklist", []),
        reasons=final_reasons,
        risk_notes=final_risk_notes,
        no_buy_reason=sig.get("no_buy_reason", ""),
        support_lines=support_lines,
        resistance_lines=resistance_lines,
        uptrend_line=uptrend_line,
        downtrend_line=downtrend_line,
        pattern=pattern,
        ohlcv=ohlcv_bars,
    )
