from app.services.daily_brief_service import build_daily_brief


def test_daily_brief_groups_keep_strong_no_chase_and_trim_weak():
    summary = {
        "as_of": "2026-05-14",
        "generated_at": "2026-05-14T15:20:00",
        "universe_size": 5,
        "data_ok_count": 4,
        "data_missing_count": 1,
        "requested_as_of": None,
        "files_written": ["summary.json", "universe_report.csv", "daily_brief.json"],
        "market_context": {
            "market_filter": "allow",
            "old_wang_market_filter": "caution",
            "old_wang_market_reason": "未守 MA5/MA10，轉保守",
        },
        "manual_market_note": {
            "title": "盤後風控筆記：維持五成水位",
            "risk_level": "caution",
            "source": "user_pasted_report",
            "position_guidance": "短線資金持股水位維持約五成，汰弱留強。",
            "rules": ["水位維持五成", "弱勢股優先減碼"],
            "playbook": {
                "target_level": "五成",
                "target_position_pct": 50,
                "stance": "balanced",
                "focus_sectors": ["記憶體"],
                "risk_controls": ["弱勢股優先減碼"],
                "watch_codes": ["2408", "2344", "9999"],
            },
        },
        "signals": [
            {
                "code": "2408",
                "name": "南亞科",
                "data_ok": True,
                "data_missing": False,
                "internal_signal": "watchlist",
                "strategy_alignment": "strong_alignment",
                "aligned_strategies": ["old_wang", "buffett"],
                "strategy_conflict_notes": [],
                "old_wang_flag": True,
                "old_wang_score": 96,
                "old_wang_sector": "記憶體面板",
                "old_wang_signal": "previous_high_breakout,volume_low_support,parabolic_ma10_hold",
                "old_wang_support_state": "short_stop_trend_intact",
                "old_wang_reason": "前高突破且守 MA5/MA10",
                "no_buy_reason": "RSI 過熱但仍守 MA5/MA10，跌破短均再減碼",
                "daily_action": "hold",
                "daily_action_label": "續抱觀察",
                "daily_key_price": "MA10 312.1",
                "daily_invalidation": "跌破 MA10 312.1",
                "entry_price_low": None,
                "entry_price_high": None,
                "stop_price": 312.1,
                "target_price": 353.0,
                "price_plan_note": "高檔強勢股，持有者看 MA10，不追價",
                "buffett_data_ok": False,
            },
            {
                "code": "2472",
                "name": "立隆電",
                "data_ok": True,
                "data_missing": False,
                "internal_signal": "watchlist",
                "strategy_alignment": "no_alignment",
                "aligned_strategies": [],
                "strategy_conflict_notes": [],
                "old_wang_flag": False,
                "old_wang_score": 83,
                "old_wang_sector": "被動元件",
                "old_wang_signal": "previous_high_failed,parabolic_ma10_hold",
                "old_wang_support_state": "short_stop_trend_intact",
                "no_buy_reason": "RSI 過熱且前高未突破，不追價",
                "daily_action": "wait_pullback",
                "daily_action_label": "等回測",
                "daily_key_price": "MA10 66.48",
                "daily_invalidation": "跌破 MA10 66.48",
                "entry_price_low": 64.0,
                "entry_price_high": 68.0,
                "stop_price": 62.0,
                "target_price": 74.0,
                "price_plan_note": "等回測 MA10 且守住再評估",
                "buffett_data_ok": False,
            },
            {
                "code": "2344",
                "name": "華邦電",
                "data_ok": True,
                "data_missing": False,
                "internal_signal": "watchlist",
                "strategy_alignment": "single_strategy",
                "aligned_strategies": ["old_wang"],
                "strategy_conflict_notes": [],
                "old_wang_flag": True,
                "old_wang_score": 91,
                "old_wang_sector": "記憶體面板",
                "old_wang_signal": "previous_high_breakout,parabolic_ma10_hold",
                "old_wang_support_state": "short_stop_trend_intact",
                "no_buy_reason": "前高附近不追價，等回測 MA5/MA10",
                "daily_action": "wait_pullback",
                "daily_action_label": "等回測",
                "daily_key_price": "MA5 119.9",
                "daily_invalidation": "跌破 MA5 119.9",
                "entry_price_low": 116.0,
                "entry_price_high": 121.0,
                "stop_price": 110.0,
                "target_price": 136.0,
                "price_plan_note": "等回測 MA5 / MA10，不追價",
                "buffett_data_ok": False,
            },
            {
                "code": "3324",
                "name": "雙鴻",
                "data_ok": True,
                "data_missing": False,
                "internal_signal": "exit_warning",
                "strategy_alignment": "conflict",
                "aligned_strategies": ["old_wang"],
                "strategy_conflict_notes": ["核心技術已轉風險，老王訊號不可覆蓋出場"],
                "score": 42,
                "no_buy_reason": "收盤跌破 MA60，長線偏空",
                "daily_action": "exit",
                "daily_action_label": "出場處理",
                "daily_key_price": "MA60 1042.8",
                "daily_invalidation": "重新站回 MA60 後再評估",
                "entry_price_low": None,
                "entry_price_high": None,
                "stop_price": 1042.8,
                "target_price": 1120.0,
                "price_plan_note": "長線破線，先處理風險",
                "buffett_data_ok": False,
            },
            {
                "code": "00919",
                "name": "群益台灣精選高息",
                "data_ok": False,
                "data_missing": True,
                "data_missing_reason": "資料不足（僅 20 日，需 60 日）",
                "internal_signal": "watchlist",
                "strategy_alignment": "no_alignment",
                "aligned_strategies": [],
                "strategy_conflict_notes": [],
                "old_wang_flag": False,
                "old_wang_score": 52,
                "old_wang_sector": "ETF",
                "old_wang_signal": "",
                "old_wang_support_state": "",
                "no_buy_reason": "資料不足且短線無共振，不追價",
                "daily_action": "avoid",
                "daily_action_label": "暫不碰",
                "daily_key_price": "MA20 24.1",
                "daily_invalidation": "等待重新轉強或出現買點",
                "entry_price_low": None,
                "entry_price_high": None,
                "stop_price": None,
                "target_price": None,
                "price_plan_note": "條件不足，暫不建立部位",
                "buffett_data_ok": False,
            },
        ],
    }

    brief = build_daily_brief(summary)

    assert brief["position_guidance"]["target_level"] == "五成"
    assert brief["manual_playbook"]["target_position_pct"] == 50
    assert brief["manual_playbook"]["focus_sectors"] == ["記憶體"]
    review = brief["manual_watchlist_review"]
    assert [item["code"] for item in review["items"]] == ["2408", "2344", "9999"]
    assert review["items"][0]["bucket"] == "continue_hold"
    assert review["items"][0]["decision_hint"] == "續抱觀察"
    assert review["items"][1]["bucket"] == "wait_pullback"
    assert review["items"][1]["entry_plan"] == "116 - 121"
    assert review["items"][2]["found"] is False
    assert review["items"][2]["decision_hint"] == "不在追蹤清單"
    assert review["summary"]["continue_hold_count"] == 1
    assert review["summary"]["wait_pullback_count"] == 1
    assert review["summary"]["missing_count"] == 1
    assert brief["keep_strong"][0]["code"] == "2408"
    assert {"2408", "2472"}.issubset({item["code"] for item in brief["no_chase"]})
    assert brief["trim_weak"][0]["code"] == "3324"
    assert brief["sector_focus"][0]["sector"] == "記憶體面板"
    assert brief["buffett_status"]["missing"] == 5
    assert {item["code"] for item in brief["rotation_plan"]["continue_hold"]} == {"2408"}
    assert {item["code"] for item in brief["rotation_plan"]["wait_pullback"]} == {"2344", "2472"}
    assert brief["rotation_plan"]["priority_reduce"][0]["code"] == "3324"
    assert {item["code"] for item in brief["rotation_plan"]["avoid_no_chase"]} == {"00919"}
    assert brief["rotation_plan"]["summary"]["priority_reduce_count"] == 1
    rotation_codes = []
    for bucket in ("continue_hold", "wait_pullback", "entry_candidates", "priority_reduce", "avoid_no_chase"):
        rotation_codes.extend(item["code"] for item in brief["rotation_plan"][bucket])
    assert len(rotation_codes) == len(set(rotation_codes))

    task_by_code = {item["code"]: item for item in brief["tomorrow_tasks"]}
    assert task_by_code["2408"]["bucket"] == "continue_hold"
    assert task_by_code["2408"]["watch_price"] == "MA10 312.1"
    assert task_by_code["2408"]["exit_plan"] == "目標/壓力 353"
    assert task_by_code["2472"]["bucket"] == "wait_pullback"
    assert task_by_code["2472"]["entry_plan"] == "64 - 68"
    assert task_by_code["3324"]["bucket"] == "priority_reduce"
    assert task_by_code["3324"]["trigger_action"] == "出場處理"
    assert task_by_code["00919"]["bucket"] == "avoid_no_chase"

    data_status = brief["data_status"]
    assert data_status["last_data_as_of"] == "2026-05-14"
    assert data_status["generated_at"] == "2026-05-14T15:20:00"
    assert data_status["universe_size"] == 5
    assert data_status["data_ok_count"] == 4
    assert data_status["data_missing_count"] == 1
    assert data_status["data_ok_pct"] == 80.0
    assert isinstance(data_status["is_stale"], bool)
    assert data_status["stale_days"] >= 0
    assert data_status["status_label"] in {"資料最新", "資料可能過期"}
    assert data_status["message"]
    assert data_status["files_written"] == ["summary.json", "universe_report.csv", "daily_brief.json"]
    assert data_status["update_required"] == data_status["is_stale"]
    assert data_status["update_command"] == "python3 scripts/daily_update.py --months 1"
    assert data_status["missing_stocks"] == [
        {
            "code": "00919",
            "name": "群益台灣精選高息",
            "reason": "資料不足（僅 20 日，需 60 日）",
        }
    ]

    summary_without_files = {**summary, "files_written": []}
    fallback_status = build_daily_brief(summary_without_files)["data_status"]
    assert fallback_status["files_written"] == ["summary.json", "universe_report.csv", "daily_brief.json"]


def test_daily_brief_does_not_use_stale_manual_note_for_position_guidance():
    summary = {
        "as_of": "2026-05-19",
        "generated_at": "2026-05-20T11:58:59",
        "universe_size": 1,
        "data_ok_count": 1,
        "data_missing_count": 0,
        "market_context": {
            "market_filter": "caution",
            "old_wang_market_filter": "block",
            "old_wang_market_reason": "TSE/OTC 跌破爆大量低點，老王大盤濾網轉風險",
        },
        "manual_market_note": {
            "date": "2026-05-14",
            "applies_to_as_of": "2026-05-19",
            "title": "盤後風控筆記：維持五成水位",
            "risk_level": "caution",
            "source": "user_pasted_report",
            "position_guidance": "短線資金持股水位維持約五成，汰弱留強。",
            "rules": ["水位維持五成", "弱勢股優先減碼"],
            "is_stale": True,
            "update_required": True,
            "stale_trading_days": 3,
            "status_label": "舊筆記",
            "stale_reason": "距離訊號基準日 3 個交易日，請更新人工盤後筆記",
        },
        "signals": [],
    }

    brief = build_daily_brief(summary)

    assert brief["position_guidance"]["target_level"] == "依系統水位"
    assert brief["position_guidance"]["source"] == "system"
    assert brief["position_guidance"]["reason"] == "TSE/OTC 跌破爆大量低點，老王大盤濾網轉風險"
    assert brief["manual_playbook"] is None
    assert brief["manual_watchlist_review"]["items"] == []
    assert brief["tomorrow_checklist"] == []
    assert brief["manual_note_status"]["is_stale"] is True
    assert brief["manual_note_status"]["update_required"] is True
    assert brief["manual_note_status"]["stale_trading_days"] == 3
    assert brief["manual_note_status"]["status_label"] == "舊筆記"
