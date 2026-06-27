import json


def _summary(as_of: str, items: list[dict]):
    signals = []
    for item in items:
        signals.append({
            "code": item["code"],
            "name": item.get("name", item["code"]),
            "close": item.get("close", 100),
            "internal_signal": item.get("internal_signal", "watchlist"),
            "signal": item.get("signal", "HOLD"),
            "daily_action": item.get("daily_action", "wait_pullback"),
            "daily_action_label": item.get("daily_action_label", "等回測"),
            "daily_action_reason": item.get("daily_action_reason", "等待回測。"),
            "daily_key_price": item.get("daily_key_price", "MA10"),
            "daily_invalidation": item.get("daily_invalidation", "跌破 MA20"),
            "price_plan_note": item.get("price_plan_note", "依計畫"),
            "support_source": item.get("support_source", "recent_20d_low"),
            "resistance_source": item.get("resistance_source", "recent_20d_high"),
            "entry_source": item.get("entry_source", "MA20"),
            "stop_source": item.get("stop_source", "support_price"),
            "target_source": item.get("target_source", "resistance_price"),
        })
    return {
        "as_of": as_of,
        "generated_at": f"{as_of}T15:00:00",
        "rules_version": "rules-test",
        "rules_metadata": {
            "version": "rules-test",
            "strategy_profile": "two_strategy_daily_v1",
        },
        "batch_id": f"batch-{as_of}",
        "universe_size": len(signals),
        "data_ok_count": len(signals),
        "data_missing_count": 0,
        "signals": signals,
    }


def test_write_signal_snapshot_creates_compact_daily_file(tmp_path):
    from app.services.signal_snapshot_service import write_signal_snapshot

    path = write_signal_snapshot(_summary("2026-06-23", [{"code": "2330"}]), tmp_path)

    assert path.name == "signal_snapshot_2026-06-23.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["as_of"] == "2026-06-23"
    assert data["rules_version"] == "rules-test"
    assert data["rules_metadata"]["strategy_profile"] == "two_strategy_daily_v1"
    assert data["item_count"] == 1
    assert data["items"][0]["code"] == "2330"
    assert "daily_invalidation" in data["items"][0]
    assert data["items"][0]["entry_source"] == "MA20"
    assert data["items"][0]["target_source"] == "resistance_price"


def test_review_reports_no_previous_snapshot(tmp_path):
    from app.services.signal_snapshot_service import write_signal_snapshot_review

    path = write_signal_snapshot_review(_summary("2026-06-23", [{"code": "2330"}]), tmp_path)
    review = json.loads(path.read_text(encoding="utf-8"))

    assert review["status"] == "no_previous_snapshot"
    assert review["rules_version"] == "rules-test"
    assert review["previous_as_of"] is None
    assert review["items"] == []


def test_review_compares_previous_plan_to_current_run(tmp_path):
    from app.services.signal_snapshot_service import write_signal_snapshot, write_signal_snapshot_review

    write_signal_snapshot(_summary("2026-06-23", [
        {"code": "2330", "daily_action": "enter", "daily_action_label": "可小試"},
        {"code": "2303", "daily_action": "exit", "daily_action_label": "出場處理"},
        {"code": "2408", "daily_action": "hold", "daily_action_label": "續抱"},
    ]), tmp_path)

    path = write_signal_snapshot_review(_summary("2026-06-24", [
        {"code": "2330", "daily_action": "exit", "daily_action_label": "出場處理", "internal_signal": "exit_warning"},
        {"code": "2303", "daily_action": "hold", "daily_action_label": "續抱"},
        {"code": "2408", "daily_action": "hold", "daily_action_label": "續抱"},
    ]), tmp_path)

    review = json.loads(path.read_text(encoding="utf-8"))
    by_code = {item["code"]: item for item in review["items"]}
    assert review["status"] == "reviewed"
    assert review["previous_as_of"] == "2026-06-23"
    assert by_code["2330"]["outcome"] == "risk_triggered"
    assert by_code["2303"]["outcome"] == "risk_eased"
    assert by_code["2408"]["outcome"] == "unchanged"
    assert review["outcome_counts"]["risk_triggered"] == 1


def test_write_snapshot_and_review_compares_before_writing_current_snapshot(tmp_path):
    from app.services.signal_snapshot_service import write_signal_snapshot, write_snapshot_and_review

    write_signal_snapshot(_summary("2026-06-23", [{"code": "2330", "daily_action": "enter"}]), tmp_path)

    result = write_snapshot_and_review(_summary("2026-06-24", [
        {"code": "2330", "daily_action": "exit", "internal_signal": "exit_warning"}
    ]), tmp_path)

    review = json.loads(result["review_path"].read_text(encoding="utf-8"))
    assert review["previous_as_of"] == "2026-06-23"
    assert result["snapshot_path"].name == "signal_snapshot_2026-06-24.json"
