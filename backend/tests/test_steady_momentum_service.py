from app.services.signals_service import _steady_momentum_indicator


def test_missing_fundamentals_are_labeled_as_incomplete_not_scored():
    result = _steady_momentum_indicator(
        close=100,
        ma20=95,
        ma60=90,
        long_trend="up",
        stage="stage_2",
        market_filter="allow",
        relative_strength_score=80,
        trend_score=80,
        entry_score=80,
        risk_score=30,
        reward_risk_ratio=2.0,
        rsi14=60,
        fundamental_guard={
            "fundamental_data_ok": False,
            "fundamental_data_missing_reason": "缺少 fundamentals.json 中 2330 的基本面資料",
        },
    )

    reason = result["steady_momentum_reason"]
    assert "基本面避雷6/10" not in reason
    assert "中性保留6/10" not in reason
    assert "基本面資料不足" in reason
    assert "未完成，無法評分" in reason
