from types import SimpleNamespace

from scripts import generate_strategy_trade_report as report


def _analysis(**overrides):
    values = {
        "as_of": "2026-04-29",
        "close": 167.0,
        "signal": "watchlist",
        "strategy_tags": ["core_technical_v2", "old_wang_market_chip_rotation"],
        "old_wang_flag": True,
        "old_wang_tag": "old_wang_market_chip_rotation",
        "entry_price_low": 136.12,
        "entry_price_high": 145.84,
        "stop_price": 136.12,
        "target_price": 190.25,
        "daily_action": "wait_pullback",
        "daily_action_label": "等回測",
        "daily_action_reason": "等 5/10 或支撐確認",
        "reasons": [],
        "risk_notes": [],
        "price_plan_note": "等待回測",
        "no_buy_reason": "不追高",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_entry_plan_uses_previous_data_day(monkeypatch):
    seen = {}
    monkeypatch.setattr(report, "_previous_data_date", lambda code, trade_date: "2026-04-29")

    def fake_analysis(code, as_of):
        seen["args"] = (code, as_of)
        return _analysis()

    monkeypatch.setattr(report, "_safe_analysis", fake_analysis)

    plan = report._entry_plan("2337", "2026-04-30")

    assert seen["args"] == ("2337", "2026-04-29")
    assert plan.as_of == "2026-04-29"
    assert plan.target_price == 190.25


def test_entry_assessment_rejects_price_at_or_above_target():
    plan = report.EntryPlan(
        as_of="2026-04-29",
        close=167.0,
        signal="watchlist",
        strategy="老王",
        entry_price_low=136.12,
        entry_price_high=145.84,
        stop_price=136.12,
        target_price=171.5,
        daily_action="wait_pullback",
        daily_action_label="等回測",
        daily_action_reason="不追高",
        reason="不追高",
    )

    result = report._entry_assessment(plan, 174.0)

    assert result.startswith("不合規：")
    assert "已達/高於止盈 171.5" in result
    assert "高於建議上緣 145.84" in result


def test_entry_assessment_accepts_confirmed_entry_inside_zone():
    plan = report.EntryPlan(
        as_of="2026-05-01",
        close=100.0,
        signal="ready_to_enter",
        strategy="其他（核心技術）",
        entry_price_low=98.0,
        entry_price_high=102.0,
        stop_price=95.0,
        target_price=112.0,
        daily_action="enter",
        daily_action_label="可進場",
        daily_action_reason="條件成立",
        reason="條件成立",
    )

    assert report._entry_assessment(plan, 100.0).startswith("合規：")


def test_split_market_trades_separates_us_tickers():
    tw, us = report._split_market_trades([
        {"stock_id": "2337"},
        {"stock_id": "AAPL"},
    ])

    assert [item["stock_id"] for item in tw] == ["2337"]
    assert [item["stock_id"] for item in us] == ["AAPL"]
