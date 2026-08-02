import pytest

from scripts import generate_strategy_trade_report as report


def _candidate(code: str, *, old_wang=True, steady=False, market_filter="allow") -> dict:
    return {
        "code": code, "name": code, "close": "100",
        "internal_signal": "ready_to_enter", "daily_action": "enter",
        "daily_action_label": "可小試", "daily_action_reason": "條件成立",
        "old_wang_flag": str(old_wang), "steady_momentum_flag": str(steady),
        "old_wang_market_filter": market_filter,
    }


@pytest.fixture
def _flat_portfolio(monkeypatch):
    monkeypatch.setattr(report, "_current_exposure_pct", lambda: 0.0)


def _set_risk(monkeypatch, level: str, degraded: bool = False, **extra) -> None:
    monkeypatch.setattr(report, "_current_pre_market_risk", lambda: {
        "level": level, "level_label": level, "degraded": degraded, **extra,
    })


def test_defensive_risk_empties_the_entry_list_and_keeps_every_candidate_visible(
    monkeypatch, _flat_portfolio
):
    _set_risk(monkeypatch, "defensive")
    candidates = [_candidate(f"200{i}") for i in range(5)]

    allowed, blocked = report._apply_entry_guardrails(candidates, "old_wang")

    assert allowed == []
    assert len(blocked) == 5
    assert all(row["reason_code"] == "pre_market_gate" for row in blocked)
    assert all("停止新倉" in row["reason"] for row in blocked)


def test_daily_entry_limit_keeps_only_the_allowed_count(monkeypatch, _flat_portfolio):
    _set_risk(monkeypatch, "normal")
    candidates = [_candidate(f"200{i}") for i in range(6)]

    allowed, blocked = report._apply_entry_guardrails(candidates, "old_wang")

    # old_wang normal 上限 4 檔
    assert len(allowed) == report.ENTRY_GUARDRAIL_PROFILES["old_wang"]["normal"]["max_new_positions"]
    assert len(allowed) + len(blocked) == 6
    assert all(row["reason_code"] == "daily_entry_limit" for row in blocked)


def test_market_filter_block_stops_short_swing_entries(monkeypatch, _flat_portfolio):
    # 報告以前只把「風險模式」印成一行字，一列都沒擋掉
    _set_risk(monkeypatch, "normal")
    candidates = [_candidate("2330", market_filter="block")]

    allowed, blocked = report._apply_entry_guardrails(candidates, "old_wang")

    assert allowed == []
    assert blocked[0]["reason_code"] == "market_filter_block"


def test_market_filter_block_does_not_stop_steady_momentum(monkeypatch, _flat_portfolio):
    # 老王濾網是短波段用的，不該連帶擋掉另一套策略
    _set_risk(monkeypatch, "normal")
    candidates = [_candidate("2330", old_wang=False, steady=True, market_filter="block")]

    allowed, blocked = report._apply_entry_guardrails(candidates, "steady_momentum")

    assert [row["code"] for row in allowed] == ["2330"]
    assert blocked == []


def test_same_ticker_can_pass_one_profile_and_be_blocked_in_another(monkeypatch, _flat_portfolio):
    _set_risk(monkeypatch, "normal")
    shared = _candidate("2330", old_wang=True, steady=True)
    fillers = [_candidate(f"900{i}", old_wang=False, steady=True) for i in range(3)]

    ow_allowed, _ = report._apply_entry_guardrails([shared], "old_wang")
    sm_allowed, sm_blocked = report._apply_entry_guardrails(fillers + [shared], "steady_momentum")

    assert [row["code"] for row in ow_allowed] == ["2330"]
    # steady_momentum normal 上限 3 檔，第 4 檔的 2330 被擋
    assert "2330" not in [row["code"] for row in sm_allowed]
    assert [row["code"] for row in sm_blocked] == ["2330"]


def test_candidates_outside_the_profile_are_recorded_not_silently_dropped(
    monkeypatch, _flat_portfolio
):
    _set_risk(monkeypatch, "normal")
    candidates = [_candidate("2330", old_wang=True, steady=False)]

    allowed, blocked = report._apply_entry_guardrails(candidates, "steady_momentum")

    assert allowed == []
    assert blocked[0]["reason_code"] == "profile_mismatch"


def test_exposure_limit_blocks_when_already_full(monkeypatch):
    _set_risk(monkeypatch, "normal")
    monkeypatch.setattr(report, "_current_exposure_pct", lambda: 95.0)

    allowed, blocked = report._apply_entry_guardrails([_candidate("2330")], "old_wang")

    assert allowed == []
    assert blocked[0]["reason_code"] == "total_exposure_limit"


def test_disabling_guardrails_restores_the_previous_behaviour(monkeypatch):
    monkeypatch.setattr(report, "GUARDRAILS_ENABLED", False)
    candidates = [_candidate(f"200{i}", market_filter="block") for i in range(6)]

    allowed, blocked = report._apply_entry_guardrails(candidates, "old_wang")

    assert allowed == candidates
    assert blocked == []


def test_guardrails_never_touch_the_exit_path(monkeypatch, _flat_portfolio):
    """風控只影響進場清單。擋掉賣出訊號會把風控變成風險本身。"""
    _set_risk(monkeypatch, "extreme")
    monkeypatch.setattr(report, "_latest_tw_actions", lambda *_a, **_k: (
        [_candidate("2330")],
        [{"code": "1303", "name": "南亞", "close": "100", "daily_action": "exit",
          "daily_action_label": "出場", "internal_signal": "exit_warning",
          "support_price": "95", "daily_action_reason": "跌破支撐"}],
        [{"old_wang_market_filter": "block"}],
    ))

    entry_rows, exit_rows, _filter, blocked_rows = report._tw_current_rows("old_wang")

    assert entry_rows == []
    assert len(blocked_rows) == 1
    assert len(exit_rows) == 1 and "南亞 1303" in exit_rows[0][0]


def test_blocked_rows_show_readable_reasons_not_reason_codes(monkeypatch, _flat_portfolio):
    _set_risk(monkeypatch, "defensive")

    rows = report._tw_blocked_rows(
        report._apply_entry_guardrails([_candidate("2330")], "old_wang")[1]
    )

    assert "pre_market_gate" not in rows[0][3]
    assert "停止新倉" in rows[0][3]


def test_report_warns_that_limits_do_not_compose_across_profiles(monkeypatch):
    monkeypatch.setattr(report, "_tw_forward_validation", lambda: {
        "signal_count": 0, "window_days": 30, "note": "測試", "stats": {}, "market_reference": {},
    })
    monkeypatch.setattr(report, "_tw_report_freshness", lambda: {
        "expected_as_of": "2026-07-31", "row_count": 76, "stale_count": 0,
        "stale_items": [], "is_complete": True,
    })
    monkeypatch.setattr(report, "build_closed_trades", lambda _t: ([], []))
    monkeypatch.setattr(report, "_trade_price_warnings", lambda _t: [])
    monkeypatch.setattr(report, "_tw_current_rows", lambda *_a, **_k: ([], [], "allow", []))
    monkeypatch.setattr(report, "_load_json", lambda *_a: {"as_of": "2026-07-31"})

    result = report.build_tw_report([], "old_wang")

    assert "上限僅在本報告內有效" in result
    assert "放大實際曝險" in result


def test_each_profile_writes_its_own_report_path():
    paths = {profile: report.tw_report_path(profile) for profile in report.GUARDRAIL_PROFILES}

    assert len(set(paths.values())) == 3
    assert paths["combined"] == report.TW_REPORT_PATH
