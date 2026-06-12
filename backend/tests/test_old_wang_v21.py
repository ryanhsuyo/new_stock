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
