from app.services.signals_service import (
    _old_wang_flag,
    _old_wang_support_context,
    _previous_high_context,
    _volume_low_context,
)


def _row(day: int, low: float, high: float, close: float, volume: int) -> dict:
    return {
        "date": f"2026-05-{day:02d}",
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def _hot_context() -> dict:
    return {
        "sector_rotation": {
            "by_code": {
                "2330": {
                    "sector": "AI",
                    "sector_score": 86,
                    "is_hot": True,
                },
            },
        },
    }


def test_market_block_can_still_flag_strong_gap_reclaim_as_cautious_candidate():
    result = _old_wang_flag(
        code="2330",
        close=110,
        ma5=105,
        ma10=104,
        ma20=103,
        ma60=90,
        rsi14=62,
        vol_ratio=0.7,
        long_trend="up",
        market_filter="block",
        breakout=False,
        breakdown=False,
        strong_reversal=False,
        holds_recent_low=True,
        stage="stage_2",
        rs_score=70,
        reward_risk_ratio=2.0,
        gap={"gap_type": "gap_up", "gap_support": 101, "bullish_gap_support": True, "bearish_gap_pressure": False},
        volume_low={"support": False, "price": 95, "note": "大量低點未確認"},
        chip={},
        context=_hot_context(),
        previous_close=99,
    )

    assert result["old_wang_flag"] is True
    assert "大盤風險下僅列強型態觀察" in result["old_wang_reason"]


def test_chip_against_is_risk_note_not_hard_block_for_strong_volume_high_breakout():
    result = _old_wang_flag(
        code="2330",
        close=120,
        ma5=110,
        ma10=108,
        ma20=105,
        ma60=90,
        rsi14=68,
        vol_ratio=0.7,
        long_trend="up",
        market_filter="caution",
        breakout=False,
        breakdown=False,
        strong_reversal=False,
        holds_recent_low=True,
        stage="stage_2",
        rs_score=75,
        reward_risk_ratio=2.0,
        gap={"gap_type": "none", "bullish_gap_support": False, "bearish_gap_pressure": False},
        volume_low={
            "support": True,
            "price": 100,
            "high_price": 115,
            "high_breakout": True,
            "note": "爆大量低點 100 已守住",
        },
        chip={"foreign_net_buy": -10_000, "investment_trust_net_buy": -1_000},
        context=_hot_context(),
        previous_close=118,
    )

    assert result["old_wang_flag"] is True
    assert result["old_wang_chip_signal"] == "against"
    assert "籌碼逆風，降級觀察" in result["old_wang_reason"]


def test_close_within_ma10_tolerance_can_flag_strong_gap_reclaim_candidate():
    result = _old_wang_flag(
        code="2330",
        close=73.3,
        ma5=68.16,
        ma10=73.44,
        ma20=72.16,
        ma60=60,
        rsi14=62,
        vol_ratio=0.36,
        long_trend="up",
        market_filter="caution",
        breakout=False,
        breakdown=False,
        strong_reversal=False,
        holds_recent_low=True,
        stage="stage_2",
        rs_score=70,
        reward_risk_ratio=2.0,
        gap={"gap_type": "gap_up", "gap_support": 68.0, "bullish_gap_support": True, "bearish_gap_pressure": False},
        volume_low={"support": False, "price": 64, "note": "大量低點未確認"},
        chip={},
        context=_hot_context(),
        previous_close=67.0,
    )

    assert result["old_wang_flag"] is True
    assert result["old_wang_ma_signal"] == "near_ma10"
    assert "貼近 MA10" in result["old_wang_reason"]


def test_parabolic_move_holds_ma10_is_old_wang_hold_not_top_guess():
    result = _old_wang_flag(
        code="2330",
        close=140,
        ma5=136,
        ma10=130,
        ma20=100,
        ma60=90,
        rsi14=86,
        vol_ratio=1.4,
        long_trend="up",
        market_filter="allow",
        breakout=False,
        breakdown=False,
        strong_reversal=False,
        holds_recent_low=True,
        stage="stage_2",
        rs_score=80,
        reward_risk_ratio=2.0,
        gap={"gap_type": "none", "bullish_gap_support": False, "bearish_gap_pressure": False},
        volume_low={"support": True, "price": 120, "note": "爆大量低點 120 已守住"},
        chip={},
        context=_hot_context(),
    )

    assert result["old_wang_parabolic_ma10_hold"] is True
    assert "parabolic_ma10_hold" in result["old_wang_signal"]
    assert "噴出看MA10" in result["old_wang_badges"]
    assert result["old_wang_previous_high_risk"] is False


def test_volume_context_marks_breakout_above_explosive_volume_high():
    rows = [_row(day, 95, 105, 100, 1_000_000) for day in range(1, 21)]
    rows.append(_row(21, low=120, high=150, close=145, volume=5_000_000))
    rows.extend(_row(day, low=130, high=148, close=145, volume=1_200_000) for day in range(22, 25))
    rows.append(_row(25, low=150, high=165, close=160, volume=2_000_000))

    result = _volume_low_context(rows, ma5=150)

    assert result["high_price"] == 150
    assert result["high_breakout"] is True


def test_previous_high_context_distinguishes_breakout_and_failed_breakout():
    breakout_rows = [_row(day, 95, 100, 98, 1_000_000) for day in range(1, 25)]
    breakout_rows.append(_row(25, low=100, high=112, close=111, volume=1_500_000))
    assert _previous_high_context(breakout_rows)["state"] == "breakout"

    failed_rows = [_row(day, 95, 100, 98, 1_000_000) for day in range(1, 25)]
    failed_rows.append(_row(25, low=96, high=112, close=99, volume=1_500_000))
    assert _previous_high_context(failed_rows)["state"] == "failed"


def test_all_ma_reclaim_marks_four_seas_dragon_turnaround():
    result = _old_wang_support_context(
        close=110,
        ma5=105,
        ma10=104,
        ma20=103,
        ma60=102,
        previous_close=99,
    )

    assert result["state"] == "all_ma_reclaim"
    assert result["all_ma_reclaim"] is True
