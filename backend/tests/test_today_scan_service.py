import csv
import json


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_universe(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "code",
        "name",
        "internal_signal",
        "daily_action",
        "daily_action_label",
        "daily_action_reason",
        "old_wang_flag",
        "old_wang_score",
        "old_wang_signal",
        "old_wang_reason",
        "steady_momentum_flag",
        "steady_momentum_score",
        "steady_momentum_signal",
        "steady_momentum_reason",
        "entry_score",
        "risk_score",
        "entry_price_low",
        "entry_price_high",
        "stop_price",
        "target_price",
        "reward_risk_ratio",
        "vol_ratio",
        "rsi14",
        "close",
        "data_as_of",
        "no_buy_reason",
        "risk_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_today_scan_report_groups_current_candidates(tmp_path):
    from app.services.today_scan_service import build_today_scan_report

    out = tmp_path / "out"
    _write_json(out / "summary.json", {
        "as_of": "2026-06-25",
        "generated_at": "2026-06-26T03:10:51",
        "rules_version": "rules-test",
        "rules_metadata": {"strategy_profile": "two_strategy_daily_v1"},
        "universe_size": 4,
        "data_ok_count": 4,
        "data_missing_count": 0,
        "signal_counts": {"ready_to_enter": 1, "watchlist": 2, "exit_warning": 1},
        "market_context": {
            "market_regime": "bull",
            "market_filter": "allow",
            "old_wang_market_regime": "risk",
            "old_wang_market_filter": "block",
            "old_wang_market_reason": "TSE/OTC 未能同時守住 MA5/MA10",
        },
    })
    _write_json(out / "daily_brief.json", {"as_of": "2026-06-25"})
    _write_universe(out / "universe_report.csv", [
        {
            "code": "2337",
            "name": "旺宏",
            "internal_signal": "ready_to_enter",
            "daily_action": "enter",
            "daily_action_label": "可小試",
            "daily_action_reason": "進場條件成立，可分批",
            "old_wang_flag": "False",
            "old_wang_score": "65",
            "steady_momentum_flag": "True",
            "steady_momentum_score": "95",
            "entry_score": "95",
            "risk_score": "35",
            "entry_price_low": "156.58",
            "entry_price_high": "164.73",
            "stop_price": "156.58",
            "target_price": "192",
            "reward_risk_ratio": "6.02",
            "vol_ratio": "1.54",
            "rsi14": "52.27",
            "close": "161.5",
            "data_as_of": "2026-06-25",
        },
        {
            "code": "2303",
            "name": "聯電",
            "internal_signal": "watchlist",
            "daily_action": "wait_pullback",
            "daily_action_label": "等回測",
            "daily_action_reason": "大盤濾網封鎖追價",
            "old_wang_flag": "True",
            "old_wang_score": "90",
            "old_wang_signal": "low_hold_rebound",
            "old_wang_reason": "短均線轉強但不追高",
            "steady_momentum_flag": "False",
            "steady_momentum_score": "55",
            "entry_score": "60",
            "risk_score": "20",
            "close": "160",
            "data_as_of": "2026-06-25",
        },
        {
            "code": "6239",
            "name": "力成",
            "internal_signal": "watchlist",
            "daily_action": "wait_pullback",
            "daily_action_label": "等回測",
            "daily_action_reason": "距 MA20 過遠",
            "old_wang_flag": "False",
            "old_wang_score": "45",
            "steady_momentum_flag": "True",
            "steady_momentum_score": "88",
            "steady_momentum_signal": "trend_pullback_watch",
            "steady_momentum_reason": "中期趨勢偏多",
            "entry_score": "55",
            "risk_score": "25",
            "close": "120",
            "data_as_of": "2026-06-25",
        },
        {
            "code": "2603",
            "name": "長榮",
            "internal_signal": "exit_warning",
            "daily_action": "reduce",
            "daily_action_label": "降低風險",
            "daily_action_reason": "跌破關鍵支撐",
            "old_wang_flag": "False",
            "old_wang_score": "20",
            "steady_momentum_flag": "False",
            "steady_momentum_score": "30",
            "entry_score": "20",
            "risk_score": "85",
            "close": "175",
            "data_as_of": "2026-06-25",
            "risk_note": "趨勢轉弱",
        },
    ])

    report = build_today_scan_report(out)

    assert report["as_of"] == "2026-06-25"
    assert report["rules_version"] == "rules-test"
    assert report["data_status"]["universe_size"] == 4
    assert report["market_context"]["old_wang_market_filter"] == "block"
    assert [item["code"] for item in report["formal_entries"]] == ["2337"]
    assert [item["code"] for item in report["old_wang_candidates"]] == ["2303"]
    assert [item["code"] for item in report["steady_momentum_candidates"]] == ["2337", "6239"]
    assert [item["code"] for item in report["risk_items"]] == ["2603"]
    steady_summary = report["formal_entries"][0]["strategy_score_summary"]
    assert steady_summary == {
        "primary_strategy": "steady_momentum",
        "primary_label": "第二 穩健",
        "primary_score": 95,
        "old_wang_level": "low",
        "steady_momentum_level": "high",
        "score_gap": 30,
        "summary_label": "第二 穩健 95，高於第一 老王 65",
    }
    old_wang_summary = report["old_wang_candidates"][0]["strategy_score_summary"]
    assert old_wang_summary["primary_strategy"] == "old_wang"
    assert old_wang_summary["primary_label"] == "第一 老王"
    assert old_wang_summary["primary_score"] == 90
    assert old_wang_summary["summary_label"] == "第一 老王 90，高於第二 穩健 55"
    assert "老王大盤濾網目前封鎖" in report["notes"][0]
    assert report["data_freshness"]["expected_as_of"] == "2026-06-25"
    assert report["data_freshness"]["stale_count"] == 0


def test_build_today_scan_report_summarizes_partial_stale_rows(tmp_path):
    from app.services.today_scan_service import build_today_scan_report

    out = tmp_path / "out"
    _write_json(out / "summary.json", {"as_of": "2026-06-25", "generated_at": "now"})
    _write_json(out / "daily_brief.json", {"as_of": "2026-06-25"})
    _write_universe(out / "universe_report.csv", [
        {
            "code": "2330",
            "name": "台積電",
            "internal_signal": "watchlist",
            "daily_action": "wait",
            "old_wang_flag": "False",
            "steady_momentum_flag": "False",
            "data_as_of": "2026-06-25",
        },
        {
            "code": "5425",
            "name": "台半",
            "internal_signal": "watchlist",
            "daily_action": "wait",
            "old_wang_flag": "True",
            "old_wang_score": "80",
            "steady_momentum_flag": "False",
            "data_as_of": "2026-06-24",
        },
        {
            "code": "2492",
            "name": "華新科",
            "internal_signal": "watchlist",
            "daily_action": "wait",
            "old_wang_flag": "False",
            "steady_momentum_flag": "True",
            "steady_momentum_score": "78",
            "data_as_of": "2026-06-21",
        },
    ])

    report = build_today_scan_report(out)

    assert report["data_freshness"] == {
        "expected_as_of": "2026-06-25",
        "row_count": 3,
        "fresh_count": 1,
        "stale_count": 2,
        "missing_date_count": 0,
        "date_counts": {
            "2026-06-21": 1,
            "2026-06-24": 1,
            "2026-06-25": 1,
        },
        "top_stale_items": [
            {"code": "2492", "name": "華新科", "data_as_of": "2026-06-21"},
            {"code": "5425", "name": "台半", "data_as_of": "2026-06-24"},
        ],
    }
    assert "2 檔股票資料日落後" in report["notes"][0]


def test_today_scan_report_includes_bucket_notes(tmp_path):
    from app.services.today_scan_service import build_today_scan_report

    out = tmp_path / "out"
    _write_json(out / "summary.json", {"as_of": "2026-06-25"})
    _write_json(out / "daily_brief.json", {"as_of": "2026-06-25"})
    _write_universe(out / "universe_report.csv", [])

    report = build_today_scan_report(out)

    assert "可小試" in report["bucket_notes"]["formal_entries"]
    assert "價格計畫" in report["bucket_notes"]["formal_entries"]
    assert "短波段觀察" in report["bucket_notes"]["old_wang_candidates"]
    assert "不追高" in report["bucket_notes"]["old_wang_candidates"]
    assert "Quality Momentum Lite" in report["bucket_notes"]["steady_momentum_candidates"]
    assert "輕量基本面避雷" in report["bucket_notes"]["steady_momentum_candidates"]
    assert "R/R" in report["bucket_notes"]["steady_momentum_candidates"]
    assert "過熱" in report["bucket_notes"]["steady_momentum_candidates"]
    assert "先處理風險" in report["bucket_notes"]["risk_items"]


def test_today_scan_report_includes_blocked_usage_status_from_daily_check(tmp_path):
    from app.services.today_scan_service import build_today_scan_report

    out = tmp_path / "out"
    _write_json(out / "summary.json", {"as_of": "2026-06-25", "generated_at": "now"})
    _write_json(out / "daily_brief.json", {"as_of": "2026-06-25"})
    _write_json(out / "daily_check.json", {
        "as_of": "2026-06-25",
        "can_use_trade_outputs": False,
        "top_actions": [
            {
                "key": "signal_alerts",
                "status": "block",
                "title": "訊號快照變化警示",
                "message": "偵測到 2 筆 block 警示。",
                "next_action": "先查看 signal_alerts.json。",
            }
        ],
    })
    _write_universe(out / "universe_report.csv", [
        {
            "code": "2337",
            "name": "旺宏",
            "internal_signal": "ready_to_enter",
            "daily_action": "enter",
            "daily_action_label": "可小試",
            "old_wang_flag": "False",
            "steady_momentum_flag": "True",
            "steady_momentum_score": "95",
            "entry_score": "95",
            "risk_score": "35",
            "close": "161.5",
            "data_as_of": "2026-06-25",
        },
    ])

    report = build_today_scan_report(out)

    assert report["formal_entries"][0]["code"] == "2337"
    assert report["usage_status"] == {
        "can_use_trade_outputs": False,
        "status": "blocked_by_daily_check",
        "headline": "Today Scan 可供復盤，但交易輸出暫不可用",
        "reason": "訊號快照變化警示：偵測到 2 筆 block 警示。",
        "next_action": "先查看 signal_alerts.json。",
        "blocking_action_key": "signal_alerts",
        "blocking_action_status": "block",
    }


def test_refresh_today_scan_usage_status_preserves_candidates(tmp_path):
    from app.services.today_scan_service import refresh_today_scan_usage_status

    out = tmp_path / "out"
    out.mkdir(parents=True)
    blocked_status = {
        "can_use_trade_outputs": False,
        "status": "blocked_by_daily_check",
        "headline": "Today Scan 可供復盤，但交易輸出暫不可用",
        "reason": "訊號快照變化警示：偵測到 2 筆 block 警示。",
        "next_action": "先查看 signal_alerts.json。",
        "blocking_action_key": "signal_alerts",
        "blocking_action_status": "block",
    }
    report = {
        "as_of": "2026-06-25",
        "generated_at": "now",
        "formal_entries": [{"code": "2337", "name": "旺宏"}],
        "old_wang_candidates": [],
        "steady_momentum_candidates": [],
        "risk_items": [],
        "usage_status": blocked_status,
    }
    _write_json(out / "today_scan.json", report)
    _write_json(out / "today_scans" / "today_scan_2026-06-25.json", report)
    _write_json(out / "daily_check.json", {
        "data_as_of": "2026-06-25",
        "can_use_trade_outputs": True,
        "top_actions": [
            {"key": "manual_market_note", "status": "warn", "title": "更新人工盤後筆記"},
        ],
    })

    refreshed = refresh_today_scan_usage_status(out)

    assert refreshed is True
    loaded = json.loads((out / "today_scan.json").read_text(encoding="utf-8"))
    assert loaded["formal_entries"] == [{"code": "2337", "name": "旺宏"}]
    assert loaded["usage_status"] == {
        "can_use_trade_outputs": True,
        "status": "ready",
        "headline": "Today Scan 可供盤後復盤",
        "reason": "Daily Check 未封鎖交易輸出；仍需依價格計畫、停損與風險報酬檢查候選。",
        "next_action": "先看可小試與風險分桶，再逐檔確認價格計畫。",
        "blocking_action_key": None,
        "blocking_action_status": None,
    }
    snapshot = json.loads((out / "today_scans" / "today_scan_2026-06-25.json").read_text(encoding="utf-8"))
    assert snapshot["usage_status"] == loaded["usage_status"]


def test_write_and_load_today_scan_round_trip(tmp_path):
    from app.services.today_scan_service import load_today_scan_report, write_today_scan_report

    out = tmp_path / "out"
    _write_json(out / "summary.json", {"as_of": "2026-06-25", "generated_at": "now"})
    _write_universe(out / "universe_report.csv", [])

    path = write_today_scan_report(out)
    loaded = load_today_scan_report(out)

    assert path == out / "today_scan.json"
    assert loaded["as_of"] == "2026-06-25"
    snapshot = out / "today_scans" / "today_scan_2026-06-25.json"
    assert snapshot.exists()
    assert json.loads(snapshot.read_text(encoding="utf-8"))["as_of"] == "2026-06-25"
