"""
signals API 整合測試

覆蓋：
  POST /api/stocks/signals/run
    - 異步：立即回傳 {"status": "started"}
    - 已在執行中時回傳 409
    - 缺 leaders.json → 400 + missing_files 清單
  GET /api/stocks/signals/status
    - 未執行 run 時：檔案 exists=false
    - 執行 run 後：exists=true，含 last_modified / as_of / generated_at
  GET /api/stocks/recommendations
    - 回傳 list[StockRecommendation]，schema 欄位齊
"""

import json
from pathlib import Path

import pytest

from app.models.trade import TradeRecord
from app.services.signals_service import run_daily_signals


# ---------------------------------------------------------------------------
# Fixture：同步執行 signals（供需要驗證 output 的測試使用）
# ---------------------------------------------------------------------------

@pytest.fixture()
def signals_result(tmp_out):
    """直接呼叫 run_daily_signals()，回傳 summary dict。"""
    return run_daily_signals()


# ---------------------------------------------------------------------------
# POST /api/stocks/signals/run（異步行為）
# ---------------------------------------------------------------------------

class TestSignalsRun:

    def test_returns_200_with_started(self, client, tmp_out, monkeypatch):
        import app.services.signals_service as svc
        monkeypatch.setattr(svc, "run_daily_signals", lambda as_of_date=None: {})
        resp = client.post("/api/stocks/signals/run", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"

    def test_already_running_returns_409(self, client, tmp_out, monkeypatch):
        import app.services.signals_service as svc
        monkeypatch.setattr(svc, "_signals_run_status", {"status": "running", "error": None})
        resp = client.post("/api/stocks/signals/run", json={})
        assert resp.status_code == 409

    def test_missing_leaders_returns_400(self, client, tmp_out, monkeypatch):
        import app.services.signals_service as svc
        monkeypatch.setattr(svc, "LEADERS_PATH", Path("/nonexistent/leaders.json"))
        resp = client.post("/api/stocks/signals/run", json={})
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "missing_files" in detail
        assert any("leaders" in f for f in detail["missing_files"])

    def test_missing_ohlcv_returns_400(self, client, tmp_out, monkeypatch):
        import app.services.signals_service as svc
        monkeypatch.setattr(svc, "OHLCV_PATH", Path("/nonexistent/ohlcv.csv"))
        resp = client.post("/api/stocks/signals/run", json={})
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert any("ohlcv" in f for f in detail["missing_files"])


# ---------------------------------------------------------------------------
# signals output 驗證（透過 signals_result fixture 同步執行）
# ---------------------------------------------------------------------------

class TestSignalsOutput:

    def test_top_level_fields_present(self, signals_result):
        for field in ("as_of", "generated_at", "universe_size",
                      "data_ok_count", "data_missing_count",
                      "data_ok_counts", "no_buy_reason_counts", "signals",
                      "rules_version", "rules_metadata",
                      "out_dir", "files_written"):
            assert field in signals_result, f"欄位缺失：{field}"
        assert signals_result["rules_metadata"]["version"] == signals_result["rules_version"]

    def test_signal_snapshot_outputs_are_written(self, signals_result, tmp_out):
        as_of = signals_result["as_of"]
        snapshot_path = tmp_out / "signal_snapshots" / f"signal_snapshot_{as_of}.json"
        review_path = tmp_out / "signal_snapshot_review.json"
        alerts_path = tmp_out / "signal_alerts.json"
        today_scan_path = tmp_out / "today_scan.json"
        today_scan_snapshot_path = tmp_out / "today_scans" / f"today_scan_{as_of}.json"

        assert snapshot_path.exists()
        assert review_path.exists()
        assert alerts_path.exists()
        assert today_scan_path.exists()
        assert today_scan_snapshot_path.exists()
        assert "signal_snapshot_review.json" in signals_result["files_written"]
        assert f"signal_snapshots/signal_snapshot_{as_of}.json" in signals_result["files_written"]
        assert "signal_alerts.json" in signals_result["files_written"]
        assert "today_scan.json" in signals_result["files_written"]
        assert f"today_scans/today_scan_{as_of}.json" in signals_result["files_written"]
        assert "signal_alert_count" in signals_result
        assert "signal_alert_summary" in signals_result

    def test_load_positions_from_trades_includes_buy_fee(self, monkeypatch):
        import app.services.signals_service as svc

        trades = [
            TradeRecord(
                id="t1",
                stock_id="2330",
                name="台積電",
                trade_type="buy",
                date="2026-05-01",
                price=100.0,
                shares=1000,
                note="",
                created_at="2026-05-01T00:00:00",
            )
        ]
        monkeypatch.setattr(svc, "load_trades", lambda: trades)
        monkeypatch.setattr(svc, "load_stock_names", lambda: {"2330": "台積電"})

        positions = svc._load_positions()

        assert positions["source"] == "trades"
        assert positions["holdings"]["2330"]["shares"] == 1000
        assert positions["holdings"]["2330"]["avg_cost"] == 100.14

    def test_data_ok_count_positive(self, signals_result):
        assert signals_result["data_ok_count"] > 0

    def test_data_ok_counts_keys_are_chinese(self, signals_result):
        assert set(signals_result["data_ok_counts"].keys()) == {"買入", "賣出", "觀望"}

    def test_signals_list_not_empty(self, signals_result):
        assert len(signals_result["signals"]) > 0

    def test_each_signal_has_required_fields(self, signals_result):
        required = ("code", "data_ok", "data_missing", "signal",
                    "calculation_status", "calculation_error",
                    "entry_type", "no_buy_reason",
                    "close", "ma5", "ma10", "ma20", "ma60", "rsi14", "volume", "vol_ratio")
        for sig in signals_result["signals"]:
            for field in required:
                assert field in sig, f"{sig['code']}: 欄位缺失 {field}"

    def test_each_signal_has_professional_filter_fields(self, signals_result):
        required = (
            "trend_score", "entry_score", "risk_score",
            "market_regime", "market_filter",
            "old_wang_market_regime", "old_wang_market_filter",
            "old_wang_market_source", "old_wang_market_reason",
            "relative_strength_score", "relative_strength_60d", "relative_strength_120d",
            "stage", "entry_price_low", "entry_price_high",
            "stop_price", "target_price", "risk_pct", "reward_pct",
            "reward_risk_ratio", "price_plan_note",
            "support_source", "resistance_source",
            "entry_source", "stop_source", "target_source",
            "position_size_pct", "position_size_note",
            "holding_shares", "holding_avg_cost", "holding_position_pct",
            "strategy_alignment", "aligned_strategies", "strategy_conflict_notes",
            "strategy_tags", "old_wang_flag", "old_wang_tag", "old_wang_score",
            "old_wang_signal", "old_wang_reason", "old_wang_sector", "sector_score",
            "old_wang_volume_signal", "old_wang_gap_type", "old_wang_gap_support",
            "old_wang_gap_resistance", "old_wang_gap_note",
            "old_wang_ma_signal", "old_wang_volume_low_support",
            "old_wang_volume_low_price", "old_wang_support_state",
            "old_wang_ma_break_count", "old_wang_previous_high_risk",
            "old_wang_chip_signal", "old_wang_raw_score",
            "old_wang_previous_high_state", "old_wang_previous_high_price",
            "old_wang_volume_high_breakout", "old_wang_volume_high_price",
            "old_wang_all_ma_reclaim", "old_wang_parabolic_ma10_hold",
            "fundamental_flag", "fundamental_tag", "fundamental_score", "fundamental_signal",
            "fundamental_reason", "fundamental_data_ok", "fundamental_data_missing_reason",
            "fundamental_quality_score", "fundamental_value_score", "fundamental_safety_score",
            "fundamental_growth_score", "fundamental_data_completeness_pct",
            "fundamental_missing_fields", "fundamental_scored_groups",
            "daily_action", "daily_action_label", "daily_action_identity",
            "daily_action_reason", "daily_key_price", "daily_invalidation",
            "daily_priority", "daily_checklist",
        )
        for sig in signals_result["signals"]:
            for field in required:
                assert field in sig, f"{sig['code']}: 專業濾網欄位缺失 {field}"

    def test_price_source_fields_are_strings(self, signals_result):
        source_fields = (
            "support_source", "resistance_source",
            "entry_source", "stop_source", "target_source",
        )
        for sig in signals_result["signals"]:
            for field in source_fields:
                assert isinstance(sig[field], str), f"{sig['code']}: {field} 應為字串"

    def test_daily_decision_fields_are_actionable(self, signals_result):
        valid_actions = {
            "enter", "wait_pullback", "hold", "reduce", "exit", "avoid", "long_watch",
        }
        for sig in signals_result["signals"]:
            assert sig["daily_action"] in valid_actions
            assert sig["daily_action_label"]
            assert sig["daily_action_identity"] in ("已持有", "未持有")
            assert sig["daily_action_reason"]
            assert sig["daily_invalidation"]
            assert isinstance(sig["daily_priority"], int)

    def test_daily_checklist_is_structured_and_actionable(self, signals_result):
        required_categories = {"market", "setup", "risk", "action"}
        valid_statuses = {"pass", "warn", "fail", "info"}
        for sig in signals_result["signals"]:
            checklist = sig["daily_checklist"]
            assert isinstance(checklist, list)
            assert len(checklist) >= 4
            assert required_categories.issubset({item["category"] for item in checklist})
            for item in checklist:
                assert set(item).issuperset({"category", "label", "status", "detail"})
                assert item["status"] in valid_statuses
                assert item["label"]
                assert item["detail"]

    def test_professional_scores_in_range(self, signals_result):
        for sig in signals_result["signals"]:
            for field in ("trend_score", "entry_score", "risk_score"):
                assert 0 <= sig[field] <= 100, f"{sig['code']} {field}={sig[field]} 超出範圍"

    def test_summary_has_market_context(self, signals_result):
        ctx = signals_result["market_context"]
        assert ctx["benchmark_code"] == "0050"
        assert ctx["market_regime"] in ("bull", "neutral", "bear", "unknown")
        assert ctx["market_filter"] in ("allow", "caution", "block", "neutral")
        assert isinstance(ctx["reason"], str)
        assert ctx["old_wang_market_regime"] in ("strong", "caution", "risk", "unknown")
        assert ctx["old_wang_market_filter"] in ("allow", "caution", "block", "neutral")
        assert isinstance(ctx["old_wang_market_reason"], str)

    def test_summary_has_strategy_catalog_and_buckets(self, signals_result):
        catalog = signals_result["strategy_catalog"]
        buckets = signals_result["recommendation_buckets"]
        assert "old_wang_market_chip_rotation" in catalog
        assert "steady_momentum_v1" in catalog
        assert "core_technical_v2" not in catalog
        assert "fundamental_guard_v1" not in catalog
        assert set(buckets.keys()) == {"old_wang", "steady_momentum"}
        assert isinstance(buckets["old_wang"], list)
        assert isinstance(buckets["steady_momentum"], list)

    def test_steady_momentum_candidates_have_score_breakdown(self, signals_result):
        candidates = [
            s for s in signals_result["signals"] if s.get("steady_momentum_flag")
        ]
        for sig in candidates:
            assert 75 <= sig["steady_momentum_score"] <= 100
            reason = sig["steady_momentum_reason"]
            assert "趨勢" in reason
            assert "相對強度" in reason
            assert "進場位置" in reason
            assert "風險報酬" in reason
            assert "過熱控制" in reason
            assert "基本面避雷" in reason

    def test_fundamental_guard_requires_fundamental_data(self, signals_result):
        for sig in signals_result["signals"]:
            assert sig["fundamental_data_ok"] is False
            assert sig["fundamental_flag"] is False
            assert sig["fundamental_score"] is None
            assert "fundamentals" in sig["fundamental_data_missing_reason"]

    def test_signal_values_are_valid(self, signals_result):
        valid = {"BUY", "SELL", "HOLD", "DATA_MISSING"}
        for sig in signals_result["signals"]:
            assert sig["signal"] in valid
            assert isinstance(sig["data_ok"], bool)
            assert isinstance(sig["data_missing"], bool)
            assert sig["data_ok"] != sig["data_missing"]

    def test_buy_signal_has_empty_no_buy_reason(self, signals_result):
        for sig in signals_result["signals"]:
            if sig["signal"] == "BUY":
                assert sig["no_buy_reason"] == ""
                assert sig["entry_type"] in ("pullback", "breakout", "squeeze")

    def test_non_buy_signal_has_chinese_reason(self, signals_result):
        for sig in signals_result["signals"]:
            if sig["signal"] != "BUY":
                assert sig["no_buy_reason"] != "", \
                    f"{sig['code']} signal={sig['signal']} 應有 no_buy_reason"

    def test_writes_summary_json(self, signals_result, tmp_out):
        assert (tmp_out / "summary.json").exists()

    def test_writes_universe_report_csv(self, signals_result, tmp_out):
        assert (tmp_out / "universe_report.csv").exists()

    def test_files_written_lists_both_files(self, signals_result):
        as_of = signals_result["as_of"]
        assert set(signals_result["files_written"]) == {
            "summary.json",
            "universe_report.csv",
            "daily_brief.json",
            "today_scan.json",
            f"today_scans/today_scan_{as_of}.json",
            "signal_snapshot_review.json",
            f"signal_snapshots/signal_snapshot_{as_of}.json",
            "signal_alerts.json",
            "fundamentals_report.json",
            "fundamentals_priority_fill.csv",
        }

    def test_summary_json_content_matches_result(self, signals_result, tmp_out):
        on_disk = json.loads((tmp_out / "summary.json").read_text(encoding="utf-8"))
        assert on_disk["as_of"] == signals_result["as_of"]
        assert on_disk["data_ok_count"] == signals_result["data_ok_count"]
        assert len(on_disk["signals"]) == len(signals_result["signals"])
        assert on_disk["rules_version"] == signals_result["rules_version"]
        assert on_disk["rules_metadata"]["strategy_profile"] == "two_strategy_daily_v1"

    def test_manual_run_creates_signal_lineage(self, signals_result, tmp_out):
        on_disk = json.loads((tmp_out / "summary.json").read_text(encoding="utf-8"))

        assert signals_result["batch_id"].startswith("signals-")
        assert signals_result["lineage"]["batch_id"] == signals_result["batch_id"]
        assert signals_result["lineage"]["source"] == "run_daily_signals"
        assert on_disk["batch_id"] == signals_result["batch_id"]

    def test_as_of_date_param_accepted(self, tmp_out):
        result = run_daily_signals(as_of_date="2025-12-31")
        assert result["as_of"] == "2025-12-31"

    def test_corrupt_previous_summary_is_ignored(self, tmp_out):
        import app.services.signals_service as svc

        (tmp_out / "summary.json").write_text('{"as_of": "2026-05-19", "signals": [', encoding="utf-8")

        assert svc.get_summary() == {}


# ---------------------------------------------------------------------------
# GET /api/stocks/signals/status
# ---------------------------------------------------------------------------

class TestSignalsStatus:

    def test_returns_200(self, client):
        resp = client.get("/api/stocks/signals/status")
        assert resp.status_code == 200

    def test_has_required_top_level_keys(self, client):
        body = client.get("/api/stocks/signals/status").json()
        assert "run_status" in body
        assert "out_dir" in body
        assert "out_files" in body
        assert "data_files" in body

    def test_out_files_keys_present(self, client):
        out_files = client.get("/api/stocks/signals/status").json()["out_files"]
        assert "summary_json" in out_files
        assert "universe_report_csv" in out_files
        assert "daily_brief_json" in out_files

    def test_data_files_keys_present(self, client):
        data_files = client.get("/api/stocks/signals/status").json()["data_files"]
        assert "leaders_json" in data_files
        assert "ohlcv_csv" in data_files
        assert "market_notes_json" in data_files
        assert "positions_json" in data_files

    def test_status_includes_manual_note_status_from_summary(self, client, tmp_out):
        import app.services.signals_service as svc

        summary = {
            "as_of": "2026-05-19",
            "generated_at": "2026-05-20T13:40:25",
            "manual_market_note": {
                "date": "2026-05-14",
                "applies_to_as_of": "2026-05-19",
                "is_stale": True,
                "update_required": True,
                "stale_trading_days": 3,
                "status_label": "舊筆記",
                "stale_reason": "距離訊號基準日 3 個交易日，請更新人工盤後筆記",
            },
        }
        (svc._OUT / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

        body = client.get("/api/stocks/signals/status").json()

        assert body["manual_note_status"] == {
            "date": "2026-05-14",
            "applies_to_as_of": "2026-05-19",
            "is_stale": True,
            "update_required": True,
            "stale_trading_days": 3,
            "status_label": "舊筆記",
            "stale_reason": "距離訊號基準日 3 個交易日，請更新人工盤後筆記",
        }

    def test_status_exposes_summary_parse_error(self, client, tmp_out):
        import app.services.signals_service as svc

        (svc._OUT / "summary.json").write_text('{"as_of": "2026-05-19"', encoding="utf-8")

        body = client.get("/api/stocks/signals/status").json()

        assert body["out_files"]["summary_json"]["exists"] is True
        assert "parse_error" in body["out_files"]["summary_json"]

    def test_status_exposes_daily_brief_parse_error(self, client, tmp_out):
        import app.services.signals_service as svc

        (svc._OUT / "daily_brief.json").write_text('{"as_of": "2026-05-19"', encoding="utf-8")

        body = client.get("/api/stocks/signals/status").json()

        assert body["out_files"]["daily_brief_json"]["exists"] is True
        assert "parse_error" in body["out_files"]["daily_brief_json"]

    def test_file_info_has_exists_and_path(self, client):
        body = client.get("/api/stocks/signals/status").json()
        for section in (body["out_files"], body["data_files"]):
            for info in section.values():
                assert "exists" in info
                assert "path" in info

    def test_positions_json_marked_optional(self, client):
        data_files = client.get("/api/stocks/signals/status").json()["data_files"]
        assert data_files["positions_json"].get("optional") is True


class TestMarketNotesApi:

    def test_get_market_notes_returns_list(self, client, tmp_path, monkeypatch):
        import app.storage.market_note_store as store

        notes_path = tmp_path / "market_notes.json"
        notes_path.write_text(
            json.dumps([
                {"date": "2026-05-19", "title": "盤後筆記", "risk_level": "risk", "headline": "測試"}
            ], ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(store, "MARKET_NOTES_PATH", notes_path)

        resp = client.get("/api/stocks/market-notes")

        assert resp.status_code == 200
        assert resp.json()[0]["date"] == "2026-05-19"

    def test_post_market_note_upserts_by_date(self, client, tmp_path, monkeypatch):
        import app.storage.market_note_store as store

        notes_path = tmp_path / "market_notes.json"
        monkeypatch.setattr(store, "MARKET_NOTES_PATH", notes_path)

        resp = client.post("/api/stocks/market-notes", json={
            "date": "2026-05-20",
            "title": "5/20 盤後筆記",
            "risk_level": "caution",
            "headline": "更新人工盤後筆記，避免沿用舊結論。",
            "market_actions": ["確認 MA10", "汰弱留強"],
        })

        assert resp.status_code == 200
        body = resp.json()
        assert body["saved"]["date"] == "2026-05-20"
        assert body["saved"]["market_actions"] == ["確認 MA10", "汰弱留強"]
        assert body["replaced"] is False
        assert body["signals_rerun_required"] is True
        assert body["next_step"] == "POST /api/stocks/signals/run"

    def test_post_market_note_rejects_invalid_date(self, client, tmp_path, monkeypatch):
        import app.storage.market_note_store as store

        notes_path = tmp_path / "market_notes.json"
        monkeypatch.setattr(store, "MARKET_NOTES_PATH", notes_path)

        resp = client.post("/api/stocks/market-notes", json={
            "date": "2026/05/20",
            "title": "5/20 盤後筆記",
            "risk_level": "caution",
            "headline": "日期格式錯誤，不應寫入。",
        })

        assert resp.status_code == 422
        assert not notes_path.exists()

    def test_run_status_idle_by_default(self, client):
        import app.services.signals_service as svc
        svc._signals_run_status = {"status": "idle", "error": None}
        body = client.get("/api/stocks/signals/status").json()
        assert body["run_status"] == "idle"

    def test_after_run_summary_shows_exists_and_meta(self, client, tmp_out, signals_result):
        status = client.get("/api/stocks/signals/status").json()
        info = status["out_files"]["summary_json"]
        assert info["exists"] is True
        assert "last_modified" in info
        assert "as_of" in info
        assert "generated_at" in info

    def test_after_run_daily_brief_shows_exists_and_meta(self, client, tmp_out, signals_result):
        status = client.get("/api/stocks/signals/status").json()
        info = status["out_files"]["daily_brief_json"]
        assert info["exists"] is True
        assert "last_modified" in info
        assert "as_of" in info
        assert "generated_at" in info
        assert "status_label" in info
        assert "update_required" in info

    def test_status_reads_universe_report_as_of_and_row_count(self, client, tmp_out):
        report = tmp_out / "universe_report.csv"
        report.write_text(
            "code,name,data_as_of,data_ok,no_buy_reason\n"
            "2330,台積電,2026-05-28,true,\n"
            "2454,聯發科,2026-05-29,true,等回測\n",
            encoding="utf-8",
        )

        status = client.get("/api/stocks/signals/status").json()
        info = status["out_files"]["universe_report_csv"]

        assert info["exists"] is True
        assert info["row_count"] == 2
        assert info["as_of"] == "2026-05-29"

    def test_before_run_summary_shows_not_exists(self, client, tmp_out):
        status = client.get("/api/stocks/signals/status").json()
        assert status["out_files"]["summary_json"]["exists"] is False

    def test_manual_watchlist_review_endpoint_returns_compact_review(self, client, tmp_out):
        brief = {
            "as_of": "2026-05-27",
            "manual_watchlist_review": {
                "items": [
                    {
                        "code": "8046",
                        "name": "南電",
                        "found": True,
                        "bucket": "entry_candidates",
                        "decision_hint": "可小試",
                        "entry_plan": "877.15 - 923.1",
                    }
                ],
                "summary": {
                    "total": 1,
                    "found_count": 1,
                    "missing_count": 0,
                    "entry_candidates_count": 1,
                },
            },
        }
        (tmp_out / "daily_brief.json").write_text(json.dumps(brief), encoding="utf-8")

        resp = client.get("/api/stocks/signals/manual-watchlist-review")

        assert resp.status_code == 200
        body = resp.json()
        assert body["as_of"] == "2026-05-27"
        assert body["summary"]["entry_candidates_count"] == 1
        assert body["items"][0]["code"] == "8046"
        assert body["items"][0]["decision_hint"] == "可小試"

    def test_manual_watchlist_review_endpoint_404_before_daily_brief(self, client, tmp_out):
        resp = client.get("/api/stocks/signals/manual-watchlist-review")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/stocks/recommendations
# ---------------------------------------------------------------------------

class TestRecommendations:

    def test_returns_200(self, client):
        resp = client.get("/api/stocks/recommendations")
        assert resp.status_code == 200

    def test_returns_list(self, client):
        body = client.get("/api/stocks/recommendations").json()
        assert isinstance(body, list)

    def test_schema_fields_present(self, client, signals_result):
        body = client.get("/api/stocks/recommendations").json()
        required = ("stock_id", "name", "price", "change_pct",
                    "score", "reason", "risk_warning", "chip",
                    "volume", "vol_ratio",
                    "position_size_pct", "position_size_note",
                    "strategy_tags", "recommendation_source",
                    "strategy_alignment", "aligned_strategies", "strategy_conflict_notes",
                    "old_wang_tag", "old_wang_score", "old_wang_raw_score", "old_wang_reason",
                    "old_wang_badges",
                    "old_wang_volume_signal", "old_wang_gap_type",
                    "old_wang_gap_support", "old_wang_gap_resistance",
                    "old_wang_gap_note", "old_wang_ma_signal",
                    "old_wang_volume_low_support", "old_wang_volume_low_price",
                    "old_wang_support_state", "old_wang_ma_break_count",
                    "old_wang_previous_high_risk", "old_wang_chip_signal",
                    "old_wang_previous_high_state", "old_wang_previous_high_price",
                    "old_wang_volume_high_breakout", "old_wang_volume_high_price",
                    "old_wang_all_ma_reclaim", "old_wang_parabolic_ma10_hold",
                    "steady_momentum_flag", "steady_momentum_tag", "steady_momentum_score",
                    "steady_momentum_signal", "steady_momentum_reason",
                    "fundamental_flag", "fundamental_tag", "fundamental_score",
                    "fundamental_signal", "fundamental_reason", "fundamental_data_ok",
                    "fundamental_data_missing_reason", "fundamental_quality_score",
                    "fundamental_value_score", "fundamental_safety_score",
                    "fundamental_growth_score", "fundamental_data_completeness_pct",
                    "fundamental_missing_fields", "fundamental_scored_groups")
        for rec in body:
            for field in required:
                assert field in rec, f"StockRecommendation 欄位缺失：{field}"

    def test_chip_fields_present(self, client, signals_result):
        body = client.get("/api/stocks/recommendations").json()
        required = (
            "data_as_of",
            "holder_data_as_of",
            "foreign_net_buy",
            "investment_trust_net_buy",
            "retail_net_buy",
            "major_investor_net_buy",
        )
        for rec in body:
            for field in required:
                assert field in rec["chip"], f"{rec['stock_id']} chip 欄位缺失：{field}"

    def test_field_types(self, client, signals_result):
        for rec in client.get("/api/stocks/recommendations").json():
            assert isinstance(rec["stock_id"], str)
            assert isinstance(rec["name"], str)
            assert isinstance(rec["price"], (int, float))
            assert isinstance(rec["change_pct"], (int, float))
            assert isinstance(rec["score"], (int, float))

    def test_score_in_range(self, client, signals_result):
        for rec in client.get("/api/stocks/recommendations").json():
            assert 0 <= rec["score"] <= 100, \
                f"{rec['stock_id']} score={rec['score']} 超出 0–100 範圍"

    def test_default_strategy_returns_steady_momentum_signals(self, client, signals_result, tmp_out):
        buy_codes = {
            s["code"] for s in signals_result["signals"] if s.get("steady_momentum_flag")
        }
        rec_codes  = {r["stock_id"]
                      for r in client.get("/api/stocks/recommendations").json()}
        assert rec_codes == buy_codes, \
            f"recommendations 與穩健動能 signals 不一致：{rec_codes} vs {buy_codes}"

    def test_old_wang_strategy_returns_tagged_signals(self, client, signals_result):
        old_wang_codes = {
            s["code"] for s in signals_result["signals"] if s.get("old_wang_flag")
        }
        rec_codes = {
            r["stock_id"]
            for r in client.get("/api/stocks/recommendations?strategy=old_wang").json()
        }
        assert rec_codes == old_wang_codes

    def test_steady_momentum_strategy_returns_steady_momentum_flagged_signals(self, client, signals_result):
        expected = {
            s["code"] for s in signals_result["signals"]
            if s.get("steady_momentum_flag")
        }
        rec_codes = {
            r["stock_id"]
            for r in client.get("/api/stocks/recommendations?strategy=steady_momentum").json()
        }
        assert rec_codes == expected

    def test_unknown_strategy_uses_default_recommendation_bucket(self, client, signals_result):
        steady_codes = {
            r["stock_id"]
            for r in client.get("/api/stocks/recommendations?strategy=steady_momentum").json()
        }
        unknown_codes = {
            r["stock_id"]
            for r in client.get("/api/stocks/recommendations?strategy=unknown").json()
        }
        assert unknown_codes == steady_codes

    def test_empty_list_when_no_summary(self, client, tmp_out):
        body = client.get("/api/stocks/recommendations").json()
        assert body == []
