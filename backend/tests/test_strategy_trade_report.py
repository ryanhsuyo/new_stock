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


def test_parse_args_supports_independent_market_reports():
    assert report.parse_args(["--market", "us"]).market == "us"
    assert report.parse_args(["--market", "tw"]).market == "tw"
    assert report.parse_args([]).market == "all"


def test_combined_report_keeps_tw_and_us_sections_separate():
    result = report.build_combined_report("# 台股報告\n台股內容", "# 美股報告\n美股內容")

    assert result.startswith("# New Stock 策略報告")
    assert "台股實際交易復盤與美股觀察策略，兩者不混算績效" in result
    assert "# 台股報告\n台股內容\n\n---\n\n# 美股報告\n美股內容" in result


def test_us_replay_rows_use_reader_facing_labels(monkeypatch):
    monkeypatch.setattr(report, "_read_replay_summary", lambda _path: {})

    rows = report._us_replay_rows()

    assert [row[0] for row in rows] == [
        "趨勢延續｜敏感出場",
        "趨勢延續｜保護線",
        "W 底突破",
        "突破策略｜偏差檢查",
    ]
    assert all("us_" not in cell for row in rows for cell in row)
    assert all("evaluation-only" not in cell for row in rows for cell in row)


def test_only_fresh_gate_passed_signals_reach_the_enter_bucket():
    trend = {
        "market_gate": {"bias": "bullish", "active": True},
        "candidates": [{
            "code": "RTX", "name": "RTX", "state": "candidate", "close": 100,
            "ma20": 98, "ma60": 90, "reasons": ["多頭排列"],
        }],
    }
    wbottom = {
        "market_gate": {"active": True},
        "patterns": [{
            "code": "AMZN", "name": "Amazon", "state": "breakout_today",
            "state_label": "今日突破頸線", "close": 110, "neckline": 108,
            "pattern_low": 95, "target_price": 121, "reasons": ["今日突破"],
        }],
    }

    rows = report._us_watch_rows(trend, wbottom)

    assert all(row.bucket == report.BUCKET_ENTER for row in rows)
    assert all(row.action.startswith("可紙上追蹤") for row in rows)
    assert "MA20 98" in rows[0].trigger
    assert "MA60 90" in rows[0].invalidation


def test_stale_and_gate_blocked_signals_fall_into_watch_not_enter():
    trend = {
        "market_gate": {"bias": "bearish", "active": False},
        "candidates": [{
            "code": "RTX", "name": "RTX", "state": "candidate", "close": 100,
            "ma20": 98, "ma60": 90, "reasons": [],
        }],
    }
    wbottom = {
        "market_gate": {"active": False},
        "patterns": [
            _wbottom_pattern("GD", "breakout_in_progress", 389.14),
            _wbottom_pattern("KO", "breakout_today", 84.07),
        ],
    }

    buckets = {row.code: row.bucket for row in report._us_watch_rows(trend, wbottom)}

    assert buckets == {"RTX": report.BUCKET_WATCH, "GD": report.BUCKET_WATCH, "KO": report.BUCKET_WATCH}


def test_a_ticker_never_lands_in_two_buckets():
    trend = {
        "market_gate": {"bias": "bullish", "active": True},
        "candidates": [{
            "code": "AMZN", "name": "Amazon", "state": "candidate", "close": 1,
            "ma20": 0.95, "ma60": 0.9, "reasons": [],
        }],
    }
    wbottom = {
        "market_gate": {"active": True},
        "patterns": [_wbottom_pattern("AMZN", "breakout_today", 1.0)],
    }

    rows = report._us_watch_rows(trend, wbottom)

    assert len(rows) == 1
    assert rows[0].strategy == "趨勢延續"


def test_us_daily_decision_blocks_new_tracking_when_both_gates_are_closed():
    trend = {"market_gate": {"active": False, "bias": "bearish"}}
    wbottom = {"market_gate": {"active": False}}

    result = report._us_daily_decision(trend, wbottom, actionable_count=0)

    assert result.startswith("今日不新增紙上追蹤")
    assert "趨勢濾網＝偏空" in result
    assert "只追蹤、不追價" in result


def test_us_daily_decision_reports_fresh_actionable_signals():
    result = report._us_daily_decision({}, {}, actionable_count=2)

    assert "今日有 2 檔當日新訊號可進入紙上追蹤" in result


def _forward_validation(**overrides) -> dict:
    result = {
        "as_of": "2026-07-31", "window_days": 30, "window_start": "2026-07-01",
        "covered_snapshot_days": 19, "covered_dates": [], "signal_count": 37,
        "evaluated_count": 37, "closed_count": 32, "open_count": 5,
        "no_stop_defined_count": 0,
        "stats": {"n": 37, "win_rate_pct": 10.8, "avg_return_pct": -6.35, "median_return_pct": -6.67},
        "market_reference": {"median_return_pct": -14.18, "falling_ratio_pct": 80.5,
                             "benchmark_code": "0050", "benchmark_return_pct": -6.33},
        "trades": [], "note": "進場基準為快照 generated_at 之後的第一個交易日開盤",
    }
    result.update(overrides)
    return result


def test_evidence_status_comes_before_the_candidate_list():
    # 負面績效放在候選之後等於沒放：閱讀動線是從上往下找今天能買什麼
    lines = "\n".join(report._evidence_status_lines(_forward_validation()))

    assert "-6.35%" in lines
    assert "勝率 10.8%" in lines
    assert "市場中位 -14.18%" in lines


def test_evidence_status_states_zero_sample_instead_of_going_blank():
    lines = "\n".join(report._evidence_status_lines(
        _forward_validation(signal_count=0, note="美股尚未保存 signal snapshot")
    ))

    assert "0 筆" in lines
    assert "美股尚未保存 signal snapshot" in lines
    assert "不要把「沒有反證」當成有效" in lines


def test_evidence_status_flags_signals_that_had_no_stop_price():
    lines = "\n".join(report._evidence_status_lines(_forward_validation(no_stop_defined_count=4)))

    assert "4 筆訊號沒有失效價" in lines
    assert "未計入上述統計" in lines


def test_evidence_status_does_not_invent_a_composite_score():
    # 把 -6.35% 和 -14.18% 壓成一個分數會製造樣本量撐不起的精確感
    lines = "\n".join(report._evidence_status_lines(_forward_validation()))

    for banned in ("健康度", "綜合評分", "策略排名", "評級"):
        assert banned not in lines


def test_tw_report_puts_evidence_above_the_conclusion(monkeypatch):
    monkeypatch.setattr(report, "_tw_forward_validation", lambda: _forward_validation())
    monkeypatch.setattr(report, "_tw_report_freshness", lambda: {
        "expected_as_of": "2026-07-31", "row_count": 76, "stale_count": 0,
        "stale_items": [], "is_complete": True,
    })
    monkeypatch.setattr(report, "build_closed_trades", lambda _trades: ([], []))
    monkeypatch.setattr(report, "_trade_price_warnings", lambda _trades: [])
    monkeypatch.setattr(report, "_tw_current_rows", lambda *_a, **_k: ([], [], "allow", []))
    monkeypatch.setattr(report, "_load_json", lambda *_args: {"as_of": "2026-07-31"})

    result = report.build_tw_report([])

    assert result.index(report.EVIDENCE_HEADING) < result.index("## 今日結論")
    assert result.index("-6.35%") < result.index("## 今日可能進場／觀察")


def test_tw_daily_and_audit_reports_have_separate_responsibilities(monkeypatch):
    monkeypatch.setattr(report, "_tw_report_freshness", lambda: {
        "expected_as_of": "2026-07-23",
        "row_count": 76,
        "stale_count": 0,
        "stale_items": [],
        "is_complete": True,
    })
    monkeypatch.setattr(report, "build_closed_trades", lambda _trades: ([], []))
    monkeypatch.setattr(report, "_trade_price_warnings", lambda _trades: [["warning"]])
    monkeypatch.setattr(report, "_tw_entry_check_rows", lambda _trades: [])
    monkeypatch.setattr(report, "_tw_current_rows", lambda *_a, **_k: (
        [["台積電 2330", "可小試", "ready", "100", "98–102", "95", "112", "條件成立"]],
        [], "allow", [],
    ))
    monkeypatch.setattr(report, "_load_json", lambda *_args: {"as_of": "2026-07-23"})

    daily = report.build_tw_report([])
    audit = report.build_tw_audit_report([])

    assert "# 台股每日行動報告" in daily
    assert "今日可能進場" in daily
    assert "逐筆進場合規檢核" not in daily
    assert "績效目前只能視為暫估" in daily
    assert "# 台股歷史交易稽核" in audit
    assert "逐筆進場合規檢核" in audit
    assert "今日可能進場" not in audit


def test_tw_daily_report_blocks_candidates_when_universe_dates_are_mixed(monkeypatch):
    monkeypatch.setattr(report, "_tw_report_freshness", lambda: {
        "expected_as_of": "2026-07-29",
        "row_count": 76,
        "stale_count": 1,
        "stale_items": [{"code": "9999", "name": "舊資料候選", "data_as_of": "2026-07-28"}],
        "is_complete": False,
    })
    monkeypatch.setattr(report, "build_closed_trades", lambda _trades: ([], []))
    monkeypatch.setattr(report, "_trade_price_warnings", lambda _trades: [])
    monkeypatch.setattr(report, "_tw_current_rows", lambda *_a, **_k: (
        [["舊資料候選 9999", "可小試", "ready", "100", "98–102", "95", "112", "條件成立"]],
        [["舊資料風險 8888", "降風險", "exit", "80", "78", "條件轉弱"]],
        "allow",
        [["舊資料擋下 7777", "ready", "60", "盤前風險 防守，停止新倉", "defensive"]],
    ))
    monkeypatch.setattr(report, "_load_json", lambda *_args: {"as_of": "2026-07-29"})

    daily = report.build_tw_report([])

    assert "今日動作清單暫停輸出" in daily
    assert "逐股資料日未完全一致" in daily
    assert "舊資料候選 9999 |" not in daily
    assert "舊資料風險 8888 |" not in daily
    # 資料日沒對齊時，風控擋下清單也不能照印，否則會暗示今天的候選是可信的
    assert "舊資料擋下 7777 |" not in daily


def test_tw_daily_rows_translate_internal_signal_and_market_filter(monkeypatch):
    monkeypatch.setattr(report, "_latest_tw_actions", lambda: (
        [],
        [{
            "name": "南亞",
            "code": "1303",
            "daily_action_label": "暫不進場",
            "internal_signal": "exit_warning",
            "close": "141.5",
            "support_price": "157",
            "daily_action_reason": "跌破支撐",
        }],
        [{"old_wang_market_filter": "block"}],
    ))

    _entries, exits, market_filter, _blocked = report._tw_current_rows()

    assert exits[0][2] == "出場警示"
    assert market_filter == "風險模式"


def test_us_report_lists_each_ticker_in_exactly_one_bucket(monkeypatch):
    patterns = [
        _wbottom_pattern("AMZN", "breakout_in_progress", 100.0, neckline=99.0),
        _wbottom_pattern("NVDA", "forming", 100.0, neckline=105.0),
        _wbottom_pattern("VRT", "forming", 100.0, neckline=125.0),
    ]

    result = _us_report_with(patterns, monkeypatch)

    for code in ("AMZN", "NVDA", "VRT"):
        assert result.count(f"{code} {code} |") == 1, code


def _wbottom_pattern(code: str, state: str, close: float, **overrides) -> dict:
    pattern = {
        "code": code, "name": code, "state": state, "state_label": state,
        "close": close, "neckline": close * 1.05, "pattern_low": close * 0.9,
        "target_price": close * 1.2, "reasons": [f"{code} 理由"],
    }
    pattern.update(overrides)
    return pattern


def _us_report_with(patterns: list[dict], monkeypatch) -> str:
    monkeypatch.setattr(report, "_current_us_status", lambda **_kwargs: (
        {"last_data_as_of": "2026-07-27"},
        {"as_of": "2026-07-27", "market_gate": {"bias": "bearish", "active": False}, "candidates": []},
        {"market_gate": {"active": False}, "patterns": patterns},
    ))
    monkeypatch.setattr(report, "_read_replay_summary", lambda _path: {})
    return report.build_us_report([])


def test_us_report_surfaces_invalidated_patterns_instead_of_dropping_them(monkeypatch):
    # 曾追蹤、現在條件已破壞的型態如果不列出，讀者會以為它還在觀察名單裡
    patterns = [
        _wbottom_pattern("AMZN", "invalidated", 231.39, pattern_low=233.59),
        _wbottom_pattern("PG", "forming", 148.63),
    ]

    result = _us_report_with(patterns, monkeypatch)
    changed_section = result.split("## 已完成 / 已失效")[1].split("\n## ")[0]

    assert "AMZN" in changed_section
    assert "已失效 1 檔" in result
    # 分桶數必須加總回全部型態，否則就是又有標的被靜靜丟掉
    assert "合計 2 檔，涵蓋全部追蹤標的" in result


def test_forming_patterns_split_between_watch_and_ignore_by_distance(monkeypatch):
    near = _wbottom_pattern("PG", "forming", 100.0, neckline=103.0)
    far = _wbottom_pattern("VRT", "forming", 100.0, neckline=125.0)

    result = _us_report_with([far, near], monkeypatch)
    watch_section = result.split("## 今日觀望")[1].split("\n## ")[0]
    ignore_section = result.split("## 今日不必看")[1].split("\n## ")[0]

    assert "PG" in watch_section and "VRT" not in watch_section
    assert "VRT" in ignore_section and "PG" not in ignore_section
    assert "等突破：離頸線 +3.0%" in watch_section


def test_watch_row_prices_carry_distance_and_reward_risk():
    wbottom = {
        "market_gate": {"active": False},
        "patterns": [_wbottom_pattern(
            "GD", "breakout_in_progress", 389.14,
            neckline=367.0, pattern_low=335.02, target_price=398.98,
        )],
    }

    row = report._us_watch_rows({"market_gate": {}, "candidates": []}, wbottom)[0]

    assert "（+2.5%）" in row.target                  # 觀察目標只剩 2.5% 空間
    assert "（-13.9%）" in row.invalidation           # 失效距離 13.9%
    assert row.reward_risk == "1 : 0.2（現價追進）"    # 上檔遠小於下檔，不值得追進


def test_reward_risk_reports_no_room_when_target_is_already_passed():
    assert report._reward_risk(110.0, 108.0, 90.0) == "已無空間"
    assert report._reward_risk(None, 108.0, 90.0) == "—"


def test_invalidation_reason_explains_current_failure_not_old_breakout():
    pattern = _wbottom_pattern(
        "AMZN", "invalidated", 231.39, pattern_low=233.59, breakout_date="2026-07-20",
        reasons=["2026-07-20 收盤 249.99 突破頸線 249.71"],
    )

    reason = report._invalidation_reason(pattern)

    assert "跌破型態低 233.59" in reason
    assert "低 0.9%" in reason
    assert "突破頸線" not in reason


def test_report_translates_market_gate_jargon(monkeypatch):
    result = _us_report_with([_wbottom_pattern("PG", "forming", 100.0)], monkeypatch)

    assert "bearish" not in result
    assert "偏空" in result


def test_target_reached_patterns_are_not_shown_as_still_waiting_to_break_out():
    # 已達量幅目標的型態收盤遠在頸線之上，若沒獨立處理就會掉進「離頸線 -12.6%，等突破」
    wbottom = {"market_gate": {"active": True}, "patterns": [_wbottom_pattern(
        "MSFT", "target_reached", 464.72,
        neckline=405.99, pattern_low=373.35, target_price=438.63, breakout_date="2026-07-30",
    )]}

    row = report._us_watch_rows({"market_gate": {}, "candidates": []}, wbottom)[0]

    assert row.bucket == report.BUCKET_DONE
    assert "等突破" not in row.action
    assert (row.trigger, row.target, row.reward_risk) == ("—", "—", "—")
    assert "量幅目標 438.63" in row.reason


def test_forming_reward_risk_is_measured_at_the_neckline_not_at_today_close():
    # 量幅目標 = 頸線 +（頸線 − 型態低），所以在頸線進場時每檔都是 1:1；
    # 用今天收盤當進場價會憑空造出「這檔 1:10、那檔 1:1」的假差異
    wbottom = {"market_gate": {"active": False}, "patterns": [_wbottom_pattern(
        "NVDA", "forming", 200.75,
        neckline=213.99, pattern_low=197.97, target_price=230.01,
    )]}

    row = report._us_watch_rows({"market_gate": {}, "candidates": []}, wbottom)[0]

    assert row.reward_risk == "1 : 1.0（頸線進場）"
    assert "頸線進場停損 -7.5%" in row.invalidation
    assert row.trigger_note == "站上 213.99（+6.6%）"


def test_trend_row_keeps_the_wbottom_pattern_that_dedup_would_discard():
    # 同一檔只能出現在一個桶，但「兩套策略同時看到它」不該跟著被丟掉
    trend = {
        "market_gate": {"bias": "mixed"},
        "candidates": [{"code": "GD", "name": "GD", "state": "watch",
                        "close": 383.42, "ma20": 376.49, "ma60": 356.98, "reasons": ["多頭排列"]}],
    }
    wbottom = {"market_gate": {"active": True}, "patterns": [
        _wbottom_pattern("GD", "breakout_in_progress", 383.42, neckline=367.0),
    ]}

    rows = report._us_watch_rows(trend, wbottom)

    assert len(rows) == 1
    assert "W 底" in rows[0].reason and "367" in rows[0].reason


def test_conclusion_names_the_price_that_would_make_a_stock_enterable(monkeypatch):
    patterns = [
        _wbottom_pattern("PG", "forming", 100.0, neckline=103.0),
        _wbottom_pattern("VRT", "forming", 100.0, neckline=125.0),
    ]

    result = _us_report_with(patterns, monkeypatch)

    assert "最接近可進場：PG 站上 103" in result
    assert "VRT" not in result.split("## 今日可紙上追蹤")[0]  # 太遠的不進結論


def test_next_trigger_note_says_so_when_nothing_is_close():
    assert "等新型態成形" in report._next_trigger_note([])


def test_invalidated_row_drops_prices_that_no_longer_mean_anything():
    wbottom = {"market_gate": {"active": False}, "patterns": [
        _wbottom_pattern("AMZN", "invalidated", 231.39, pattern_low=233.59, target_price=265.83),
    ]}

    row = report._us_watch_rows({"market_gate": {}, "candidates": []}, wbottom)[0]

    assert row.bucket == report.BUCKET_DEAD
    assert (row.trigger, row.target, row.reward_risk) == ("—", "—", "—")
    assert row.invalidation == "已跌破型態低 233.59"
