"""
update_status 測試

覆蓋：
  GET /api/system/data-status
    - schema 欄位齊全
    - 未有任何更新時 is_stale=True, stale_days=None
    - 正常更新後 last_run_status=success
  run_full_update (update_service)
    - 成功路徑：狀態檔寫入 success
    - 失敗路徑 (backfill 失敗)：狀態檔寫入 failed，有 last_error
    - 失敗路徑 (signals 失敗)：狀態檔寫入 failed，有 last_error
    - 成功後 stale_days 為整數
  stale 計算
    - 資料日為今天 → stale_days = 0 → is_stale=False
    - 資料日為 10 天前 → is_stale=True

測試不依賴真實網路：backfill 透過 monkeypatch 覆蓋。
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_update(tmp_out, monkeypatch):
    """
    在 tmp_out 基礎上追加：
      - 將 update_store.UPDATE_STATUS_PATH 導向 tmp_out/update_status.json
      - 將 _run_backfill 替換為成功的 stub（避免網路呼叫）
    """
    import app.storage.update_store as store
    import app.services.update_service as svc

    status_path = tmp_out / "update_status.json"
    monkeypatch.setattr(store, "_OUT", tmp_out)
    monkeypatch.setattr(store, "UPDATE_STATUS_PATH", status_path)
    monkeypatch.setattr(svc, "_run_backfill", lambda months: (True, "stub OK"))

    def fake_run_daily_signals():
        as_of = date.today().isoformat()
        (tmp_out / "summary.json").write_text(
            json.dumps({"as_of": as_of, "signals": [], "files_written": ["summary.json", "universe_report.csv", "daily_brief.json"]}),
            encoding="utf-8",
        )
        (tmp_out / "universe_report.csv").write_text("code,name,data_ok,no_buy_reason\n", encoding="utf-8")
        (tmp_out / "daily_brief.json").write_text(
            json.dumps({"as_of": as_of, "data_status": {"last_data_as_of": as_of}}, ensure_ascii=False),
            encoding="utf-8",
        )
        return {"as_of": as_of}

    monkeypatch.setattr(svc, "run_daily_signals", fake_run_daily_signals)

    return tmp_out


# ---------------------------------------------------------------------------
# GET /api/system/data-status
# ---------------------------------------------------------------------------

class TestDataStatusAPI:

    def test_returns_200(self, client, tmp_update):
        resp = client.get("/api/system/data-status")
        assert resp.status_code == 200

    def test_schema_fields_present(self, client, tmp_update):
        body = client.get("/api/system/data-status").json()
        required = (
            "last_run_started_at",
            "last_run_finished_at",
            "last_run_status",
            "last_error",
            "last_error_summary",
            "last_warning",
            "last_warning_summary",
            "last_data_as_of",
            "coverage_report_path",
            "data_coverage_pct",
            "schedule_health_status",
            "schedule_is_overdue",
            "schedule_health_message",
            "manual_update_action",
            "price_basis",
            "price_basis_label",
            "price_basis_note",
            "is_stale",
            "stale_days",
        )
        for field in required:
            assert field in body, f"欄位缺失: {field}"

    def test_is_stale_true_when_no_prior_run(self, client, tmp_update):
        body = client.get("/api/system/data-status").json()
        assert body["is_stale"] is True

    def test_stale_days_none_when_no_data(self, client, tmp_update):
        body = client.get("/api/system/data-status").json()
        assert body["stale_days"] is None

    def test_last_run_status_null_when_never_run(self, client, tmp_update):
        body = client.get("/api/system/data-status").json()
        assert body["last_run_status"] is None

    def test_schedule_health_reports_never_run(self, client, tmp_update):
        body = client.get("/api/system/data-status").json()

        assert body["schedule_health_status"] == "never_run"
        assert body["schedule_is_overdue"] is False
        assert body["schedule_health_message"]

    def test_data_status_includes_manual_update_fallback_action(self, client, tmp_update):
        body = client.get("/api/system/data-status").json()

        action = body["manual_update_action"]
        assert action["action_type"] == "copy_command"
        assert action["command"] == "python3 scripts/daily_update.py --months 1"
        assert action["copy_command"].splitlines()[-1] == "python3 scripts/daily_update.py --months 1"
        assert "backend/out/update_status.json" in action["expected_outputs"]
        assert "backend/out/daily_check.json" in action["expected_outputs"]

    def test_is_stale_field_is_bool(self, client, tmp_update):
        body = client.get("/api/system/data-status").json()
        assert isinstance(body["is_stale"], bool)

    def test_status_reflects_success_after_update(self, client, tmp_update):
        """執行 run 後，API 應回報 success 並有 last_data_as_of。"""
        import app.services.update_service as svc
        svc.run_full_update(months=1)
        body = client.get("/api/system/data-status").json()
        assert body["last_run_status"] == "success"
        assert body["last_data_as_of"] is not None

    def test_recent_running_status_stays_running(self, client, tmp_update):
        import app.storage.update_store as store

        store.save_update_status({
            **store._EMPTY,
            "last_run_started_at": datetime.now().isoformat(timespec="seconds"),
            "last_run_status": "running",
        })

        body = client.get("/api/system/data-status").json()

        assert body["last_run_status"] == "running"
        assert body["schedule_health_status"] == "running"

    def test_stale_running_status_is_marked_stalled(self, client, tmp_update):
        import app.storage.update_store as store

        started = datetime.now() - timedelta(hours=3)
        store.save_update_status({
            **store._EMPTY,
            "last_run_started_at": started.isoformat(timespec="seconds"),
            "last_run_status": "running",
        })

        body = client.get("/api/system/data-status").json()

        assert body["last_run_status"] == "stalled"
        assert body["schedule_health_status"] == "stalled"
        assert "超過" in body["schedule_health_message"]

    def test_run_full_update_refreshes_daily_check_report(self, tmp_update, monkeypatch):
        import app.services.update_service as svc

        calls = []
        monkeypatch.setattr(svc, "_write_daily_check_report", lambda: calls.append("daily_check"))

        svc.run_full_update(months=1)

        assert calls == ["daily_check"]

    def test_run_full_update_writes_shared_batch_lineage(self, tmp_update, monkeypatch):
        import app.services.update_service as svc
        import app.storage.update_store as store

        monkeypatch.setattr(svc, "_run_chips_update", lambda: (True, "chips ok"))
        monkeypatch.setattr(svc, "_sync_fundamentals_template", lambda: (True, "sync ok"))
        monkeypatch.setattr(svc, "_import_fundamentals", lambda: (True, "import ok"))

        def fake_coverage_report(*, batch_id=None, **kwargs):
            return {
                "generated_at": "2026-06-23T20:00:00",
                "batch_id": batch_id,
                "expected_trading_day": "2026-06-22",
                "raw_ohlcv_as_of": "2026-06-22",
                "tracked_count": 1,
                "ok_count": 1,
                "coverage_pct": 100.0,
                "symbols": [],
            }

        def fake_write_coverage(report, out_dir):
            path = out_dir / "data_coverage_report.json"
            path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            return path

        def fake_run_daily_signals(lineage=None):
            assert lineage["batch_id"]
            summary = {"as_of": "2026-06-22", "lineage": lineage, "batch_id": lineage["batch_id"]}
            (tmp_update / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
            return summary

        monkeypatch.setattr(svc, "build_data_coverage_report", fake_coverage_report)
        monkeypatch.setattr(svc, "write_data_coverage_report", fake_write_coverage)
        monkeypatch.setattr(svc, "run_daily_signals", fake_run_daily_signals)

        svc.run_full_update(months=1)

        status = json.loads(store.UPDATE_STATUS_PATH.read_text(encoding="utf-8"))
        summary = json.loads((tmp_update / "summary.json").read_text(encoding="utf-8"))
        coverage = json.loads((tmp_update / "data_coverage_report.json").read_text(encoding="utf-8"))

        assert status["batch_id"]
        assert status["coverage_report_path"].endswith("data_coverage_report.json")
        assert summary["batch_id"] == status["batch_id"]
        assert coverage["batch_id"] == status["batch_id"]

    def test_failed_run_full_update_refreshes_daily_check_report(self, tmp_update, monkeypatch):
        import app.services.update_service as svc

        calls = []
        monkeypatch.setattr(svc, "_run_backfill", lambda months: (False, "connection refused"))
        monkeypatch.setattr(svc, "_write_daily_check_report", lambda: calls.append("daily_check"))

        svc.run_full_update(months=1)

        assert calls == ["daily_check"]

    def test_status_reflects_failure(self, client, tmp_update, monkeypatch):
        """backfill 失敗時，API 應回報 failed 並有 last_error。"""
        import app.services.update_service as svc
        monkeypatch.setattr(svc, "_run_backfill", lambda months: (False, "connection refused"))
        svc.run_full_update(months=1)
        body = client.get("/api/system/data-status").json()
        assert body["last_run_status"] == "failed"
        assert body["last_error"] is not None


class TestDailyCheckAPI:

    def test_returns_daily_check_json(self, client, tmp_path, monkeypatch):
        import app.services.daily_check_service as svc

        out = tmp_path / "out"
        out.mkdir()
        monkeypatch.setattr(svc, "_OUT", out)
        (out / "daily_check.json").write_text(
            json.dumps({
                "overall_status": "warn",
                "exit_code": 1,
                "data_as_of": "2026-05-29",
                "can_use_trade_outputs": True,
                "top_actions": [{
                    "key": "fundamentals",
                    "status": "warn",
                    "title": "基本面避雷覆蓋",
                    "message": "0/74",
                    "next_action": "補資料",
                }],
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        response = client.get("/api/system/daily-check")

        assert response.status_code == 200
        body = response.json()
        assert body["overall_status"] == "warn"
        assert body["data_as_of"] == "2026-05-29"
        assert body["top_actions"][0]["key"] == "fundamentals"

    def test_returns_404_when_daily_check_report_missing(self, client, tmp_path, monkeypatch):
        import app.services.daily_check_service as svc

        out = tmp_path / "out"
        out.mkdir()
        monkeypatch.setattr(svc, "_OUT", out)

        response = client.get("/api/system/daily-check")

        assert response.status_code == 404
        assert "daily_check.py --write-report" in response.json()["detail"]


class TestSignalAlertReviewsAPI:

    def test_get_signal_alert_review_status_reports_unreviewed_current_alerts(self, client, tmp_path, monkeypatch):
        import app.services.signal_alert_review_service as svc
        import app.routers.system as router

        out = tmp_path / "out"
        data = tmp_path / "data"
        out.mkdir()
        data.mkdir()
        monkeypatch.setattr(svc, "_OUT", out)
        monkeypatch.setattr(svc, "_DATA", data)
        monkeypatch.setattr(router, "get_signal_alert_review_status", svc.get_signal_alert_review_status)
        (out / "signal_alerts.json").write_text(
            json.dumps({
                "as_of": "2026-06-24",
                "previous_as_of": "2026-06-23",
                "alert_count": 1,
                "severity_counts": {"block": 1},
                "alerts": [{"code": "2330", "severity": "block", "title": "風險"}],
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        response = client.get("/api/system/signal-alert-reviews")

        assert response.status_code == 200
        body = response.json()
        assert body["review_required"] is True
        assert body["reviewed"] is False
        assert body["alert_count"] == 1
        assert body["current_fingerprint"]

    def test_post_signal_alert_review_marks_current_fingerprint_reviewed(self, client, tmp_path, monkeypatch):
        import app.services.signal_alert_review_service as svc
        import app.routers.system as router

        calls = []
        out = tmp_path / "out"
        data = tmp_path / "data"
        out.mkdir()
        data.mkdir()
        monkeypatch.setattr(svc, "_OUT", out)
        monkeypatch.setattr(svc, "_DATA", data)
        monkeypatch.setattr(svc, "_refresh_daily_check_safely", lambda: calls.append("daily_check"))
        monkeypatch.setattr(router, "acknowledge_current_signal_alerts", svc.acknowledge_current_signal_alerts)
        monkeypatch.setattr(router, "get_signal_alert_review_status", svc.get_signal_alert_review_status)
        (out / "signal_alerts.json").write_text(
            json.dumps({
                "as_of": "2026-06-24",
                "previous_as_of": "2026-06-23",
                "alert_count": 1,
                "severity_counts": {"block": 1},
                "alerts": [{"code": "2330", "severity": "block", "title": "風險"}],
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        response = client.post(
            "/api/system/signal-alert-reviews/current",
            json={"reviewer": "ryan", "note": "checked risk changes"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["reviewed"] is True
        assert body["reviewer"] == "ryan"
        assert (data / "signal_alert_reviews.json").exists()
        assert client.get("/api/system/signal-alert-reviews").json()["reviewed"] is True
        assert calls == ["daily_check"]


class TestTradingSettingsAPI:

    def test_returns_trading_fee_settings(self, client, monkeypatch):
        import app.services.settings_service as svc

        monkeypatch.setattr(svc, "load_trading_settings", lambda: {
            "brokerage_fee_rate": 0.001425,
            "brokerage_discount": 0.28,
            "min_brokerage_fee": 20,
            "sell_transaction_tax_rate": 0.003,
        })

        body = client.get("/api/system/settings/trading").json()

        assert body["brokerage_discount"] == 0.28
        assert body["min_brokerage_fee"] == 20


class TestFundamentalsStatusAPI:

    def test_returns_fundamentals_coverage(self, client, monkeypatch):
        import app.services.fundamental_service as svc

        monkeypatch.setattr(svc, "_load_leader_codes", lambda: ["2330", "2454"])
        monkeypatch.setattr(svc, "load_fundamentals", lambda: {
            "2330": {
                field: 1
                for field in svc.REQUIRED_FIELDS
            },
            "2454": {
                "roe_5y_avg": None,
            },
        })

        body = client.get("/api/system/fundamentals-status").json()

        assert body["total_codes"] == 2
        assert body["complete_count"] == 1
        assert "field_missing_counts" in body
        assert "next_fill_targets" in body
        assert "fundamentals_csv_validation" in body
        assert "priority_csv_validation" in body
        assert "priority_fill_readiness" in body
        assert "can_preview" in body["priority_fill_readiness"]
        assert body["incomplete_count"] == 1
        assert body["missing_count"] == 0
        assert body["coverage_pct"] == 50.0
        assert "2454" in body["incomplete"]

    def test_downloads_fundamentals_priority_fill_csv(self, client, tmp_path, monkeypatch):
        import app.services.fundamental_service as svc

        monkeypatch.setattr(svc, "_OUT", tmp_path)
        monkeypatch.setattr(svc, "build_priority_fill_rows", lambda limit=20: [{
            "code": "2408",
            "name": "南亞科",
            "priority_reason": "目前推薦/觀察名單",
            "missing_count": 1,
            "missing_fields": "roe_5y_avg",
            "missing_field_labels": "5 年平均 ROE",
            **{field: "" for field in svc.REQUIRED_FIELDS},
        }])

        response = client.get("/api/system/fundamentals-priority-fill")

        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "2408,南亞科" in response.text

    def test_previews_fundamentals_priority_fill_merge(self, client, monkeypatch):
        import app.routers.system as router

        monkeypatch.setattr(router, "merge_priority_fill_csv", lambda dry_run=True, confirm=None: {
            "dry_run": dry_run,
            "updated_code_count": 1,
            "updated_codes": ["2408"],
            "updated_field_count": 2,
            "added_count": 0,
            "added_codes": [],
            "csv_path": "/tmp/fundamentals.csv",
            "source": "/tmp/fundamentals_priority_fill.csv",
            "json_path": None,
            "imported_count": None,
            "validation": {"valid": True},
        })

        response = client.post("/api/system/fundamentals-priority-fill/merge", json={"dry_run": True})

        assert response.status_code == 200
        body = response.json()
        assert body["dry_run"] is True
        assert body["updated_field_count"] == 2

    def test_rejects_fundamentals_priority_fill_merge_without_confirm(self, client, monkeypatch):
        import app.routers.system as router

        def fail_merge(dry_run=True, confirm=None):
            raise ValueError("正式合併必須提供 confirm=MERGE_PRIORITY_FUNDAMENTALS")

        monkeypatch.setattr(router, "merge_priority_fill_csv", fail_merge)

        response = client.post("/api/system/fundamentals-priority-fill/merge", json={"dry_run": False})

        assert response.status_code == 400
        assert "MERGE_PRIORITY_FUNDAMENTALS" in response.json()["detail"]


# ---------------------------------------------------------------------------
# run_full_update — success path
# ---------------------------------------------------------------------------

class TestRunFullUpdateSuccess:

    def test_returns_success_status(self, tmp_update):
        import app.services.update_service as svc
        status = svc.run_full_update(months=1)
        assert status["last_run_status"] == "success"

    def test_started_at_set(self, tmp_update):
        import app.services.update_service as svc
        status = svc.run_full_update(months=1)
        assert status["last_run_started_at"] is not None

    def test_finished_at_set(self, tmp_update):
        import app.services.update_service as svc
        status = svc.run_full_update(months=1)
        assert status["last_run_finished_at"] is not None

    def test_last_error_is_none_on_success(self, tmp_update):
        import app.services.update_service as svc
        status = svc.run_full_update(months=1)
        assert status["last_error"] is None

    def test_last_data_as_of_is_date_string(self, tmp_update):
        import app.services.update_service as svc
        status = svc.run_full_update(months=1)
        assert status["last_data_as_of"] is not None
        # Should be a valid date string YYYY-MM-DD
        parsed = date.fromisoformat(status["last_data_as_of"])
        assert isinstance(parsed, date)

    def test_stale_days_is_integer(self, tmp_update):
        import app.services.update_service as svc
        status = svc.run_full_update(months=1)
        assert isinstance(status["stale_days"], int)

    def test_is_stale_is_bool(self, tmp_update):
        import app.services.update_service as svc
        status = svc.run_full_update(months=1)
        assert isinstance(status["is_stale"], bool)

    def test_writes_status_file(self, tmp_update):
        import app.services.update_service as svc
        import app.storage.update_store as store
        svc.run_full_update(months=1)
        assert store.UPDATE_STATUS_PATH.exists()
        saved = json.loads(store.UPDATE_STATUS_PATH.read_text(encoding="utf-8"))
        assert saved["last_run_status"] == "success"

    def test_writes_summary_json(self, tmp_update):
        import app.services.update_service as svc
        svc.run_full_update(months=1)
        assert (tmp_update / "summary.json").exists()

    def test_writes_universe_report(self, tmp_update):
        import app.services.update_service as svc
        svc.run_full_update(months=1)
        assert (tmp_update / "universe_report.csv").exists()

    def test_syncs_and_imports_fundamentals_before_signals(self, tmp_update, monkeypatch):
        import app.services.update_service as svc

        events = []
        monkeypatch.setattr(svc, "_sync_fundamentals_template", lambda: events.append("sync") or (True, "synced"))
        monkeypatch.setattr(svc, "_import_fundamentals", lambda: events.append("fundamentals") or (True, "imported"))

        def fake_run_daily_signals():
            events.append("signals")
            return {"as_of": date.today().isoformat()}

        monkeypatch.setattr(svc, "run_daily_signals", fake_run_daily_signals)

        status = svc.run_full_update(months=1)

        assert status["last_run_status"] == "success"
        assert events == ["sync", "fundamentals", "signals"]

    def test_import_fundamentals_returns_validation_error(self, tmp_path, monkeypatch):
        import app.services.update_service as svc

        csv_path = tmp_path / "fundamentals.csv"
        csv_path.write_text(
            "\n".join([
                "code,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
                "2330,abc,,,,,,,,,,",
            ]),
            encoding="utf-8",
        )
        monkeypatch.setattr(svc, "FUNDAMENTALS_CSV_PATH", csv_path)

        ok, message = svc._import_fundamentals()

        assert ok is False
        assert "row 2" in message
        assert "2330" in message
        assert "roe_5y_avg" in message

    def test_backfill_includes_current_month_flag(self, monkeypatch):
        import subprocess
        import app.services.update_service as svc

        seen = {}

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            return Result()

        monkeypatch.setattr(subprocess, "run", fake_run)
        ok, _ = svc._run_backfill(months=1)
        assert ok is True
        assert "--include-current-month" in seen["cmd"]

    def test_backfill_can_stream_subprocess_output(self, monkeypatch, capsys):
        import subprocess
        import app.services.update_service as svc

        seen = {}

        class FakeStdout:
            def __iter__(self):
                return iter(["[  1/76] 2330 ...\n", "  OK [TWSE]\n"])

        class FakeProcess:
            stdout = FakeStdout()
            returncode = 0

            def wait(self):
                return self.returncode

        def fake_popen(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["kwargs"] = kwargs
            return FakeProcess()

        monkeypatch.setattr(subprocess, "Popen", fake_popen)

        ok, output = svc._run_backfill(months=1, stream_output=True)

        captured = capsys.readouterr().out
        assert ok is True
        assert "--include-current-month" in seen["cmd"]
        assert seen["kwargs"]["stdout"] == subprocess.PIPE
        assert "[  1/76] 2330 ..." in captured
        assert "OK [TWSE]" in output


# ---------------------------------------------------------------------------
# run_full_update — failure path (backfill fails)
# ---------------------------------------------------------------------------

class TestRunFullUpdateBackfillFailure:

    def test_returns_failed_status(self, tmp_update, monkeypatch):
        import app.services.update_service as svc
        monkeypatch.setattr(svc, "_run_backfill", lambda months: (False, "timeout"))
        status = svc.run_full_update(months=1)
        assert status["last_run_status"] == "failed"

    def test_last_error_contains_message(self, tmp_update, monkeypatch):
        import app.services.update_service as svc
        monkeypatch.setattr(svc, "_run_backfill", lambda months: (False, "timeout"))
        status = svc.run_full_update(months=1)
        assert status["last_error"] is not None
        assert len(status["last_error"]) > 0

    def test_status_file_exists_on_failure(self, tmp_update, monkeypatch):
        import app.services.update_service as svc
        import app.storage.update_store as store
        monkeypatch.setattr(svc, "_run_backfill", lambda months: (False, "timeout"))
        svc.run_full_update(months=1)
        assert store.UPDATE_STATUS_PATH.exists()

    def test_status_file_readable_on_failure(self, tmp_update, monkeypatch):
        import app.services.update_service as svc
        import app.storage.update_store as store
        monkeypatch.setattr(svc, "_run_backfill", lambda months: (False, "timeout"))
        svc.run_full_update(months=1)
        saved = json.loads(store.UPDATE_STATUS_PATH.read_text(encoding="utf-8"))
        assert saved["last_run_status"] == "failed"
        assert saved["last_error"] is not None

    def test_finished_at_set_on_failure(self, tmp_update, monkeypatch):
        import app.services.update_service as svc
        monkeypatch.setattr(svc, "_run_backfill", lambda months: (False, "timeout"))
        status = svc.run_full_update(months=1)
        assert status["last_run_finished_at"] is not None

    def test_keyboard_interrupt_marks_status_failed(self, tmp_update, monkeypatch):
        import app.services.update_service as svc
        import app.storage.update_store as store

        def interrupted(months):
            raise KeyboardInterrupt()

        monkeypatch.setattr(svc, "_run_backfill", interrupted)

        with pytest.raises(KeyboardInterrupt):
            svc.run_full_update(months=1)

        saved = json.loads(store.UPDATE_STATUS_PATH.read_text(encoding="utf-8"))
        assert saved["last_run_status"] == "failed"
        assert saved["last_run_finished_at"] is not None
        assert "中斷" in saved["last_error_summary"]


# ---------------------------------------------------------------------------
# run_full_update — failure path (signals fail)
# ---------------------------------------------------------------------------

class TestRunFullUpdateSignalsFailure:

    def test_signals_failure_returns_failed(self, tmp_update, monkeypatch):
        import app.services.update_service as svc

        def _boom(as_of_date=None):
            raise RuntimeError("signals 計算炸掉了")

        # update_service 用 from ... import run_daily_signals，需在 svc 模組上 patch
        monkeypatch.setattr(svc, "run_daily_signals", _boom)
        status = svc.run_full_update(months=1)
        assert status["last_run_status"] == "failed"
        assert "signals" in status["last_error"]

    def test_signals_failure_writes_status(self, tmp_update, monkeypatch):
        import app.services.update_service as svc
        import app.storage.update_store as store

        monkeypatch.setattr(svc, "run_daily_signals",
                            lambda as_of_date=None: (_ for _ in ()).throw(RuntimeError("boom")))
        svc.run_full_update(months=1)
        saved = json.loads(store.UPDATE_STATUS_PATH.read_text(encoding="utf-8"))
        assert saved["last_run_status"] == "failed"


# ---------------------------------------------------------------------------
# stale 計算邏輯
# ---------------------------------------------------------------------------

class TestStaleCalculation:

    def test_no_data_is_stale(self):
        from app.services.update_service import _compute_stale
        is_stale, stale_days = _compute_stale(None)
        assert is_stale is True
        assert stale_days is None

    def test_today_is_not_stale(self):
        from app.services.update_service import _compute_stale
        today_str = date.today().isoformat()
        is_stale, stale_days = _compute_stale(today_str)
        assert stale_days == 0
        assert is_stale is False

    def test_yesterday_is_not_stale(self):
        from app.services.update_service import _compute_stale
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        is_stale, stale_days = _compute_stale(yesterday)
        assert stale_days == 1
        assert is_stale is False

    def test_weekend_gap_is_not_stale_on_monday(self, monkeypatch):
        import app.services.update_service as svc
        import app.utils as utils

        class FakeDate(date):
            @classmethod
            def today(cls):
                return cls(2026, 6, 15)  # Monday

        monkeypatch.setattr(svc, "date", FakeDate)
        monkeypatch.setattr(utils, "date", FakeDate)

        is_stale, stale_days = svc._compute_stale("2026-06-12")  # Friday

        assert stale_days == 3
        assert is_stale is False

    def test_ten_days_ago_is_stale(self):
        from app.services.update_service import _compute_stale
        old = (date.today() - timedelta(days=10)).isoformat()
        is_stale, stale_days = _compute_stale(old)
        assert is_stale is True
        assert stale_days == 10

    def test_invalid_date_string_is_stale(self):
        from app.services.update_service import _compute_stale
        is_stale, stale_days = _compute_stale("not-a-date")
        assert is_stale is True
        assert stale_days is None

    def test_choose_last_data_as_of_prefers_newer_summary_date(self):
        from app.services.update_service import _choose_last_data_as_of

        old_date = (date.today() - timedelta(days=7)).isoformat()
        fresh_date = date.today().isoformat()

        assert _choose_last_data_as_of(old_date, fresh_date) == fresh_date

    def test_get_data_status_reports_raw_ohlcv_as_of_when_newer_than_summary(self, monkeypatch, tmp_path):
        import app.services.update_service as svc

        ohlcv = tmp_path / "ohlcv.csv"
        ohlcv.write_text(
            "code,date,open,high,low,close,volume\n"
            "2330,2026-05-28,2300,2310,2290,2300,1000\n"
            "2330,2026-05-29,2340,2375,2330,2355,2000\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(svc, "OHLCV_PATH", ohlcv)
        monkeypatch.setattr(svc, "load_update_status", lambda: {
            "last_run_status": "success",
            "last_data_as_of": "2026-05-28",
        })
        monkeypatch.setattr(svc, "_get_last_data_as_of", lambda: "2026-05-28")
        monkeypatch.setattr(svc, "_compute_stale", lambda as_of: (False, 0))

        status = svc.get_data_status()

        assert status["last_data_as_of"] == "2026-05-28"
        assert status["raw_ohlcv_as_of"] == "2026-05-29"
        assert status["outputs_lag_raw_data"] is True
        assert "ohlcv.csv 已更新到 2026-05-29" in status["raw_data_warning"]
        assert status["price_basis"] == "latest_close"
        assert status["price_basis_label"] == "最新收盤價"
        assert "不是盤中即時市價" in status["price_basis_note"]

    def test_normalize_status_turns_stale_status_success_when_fresh(self):
        from app.services.update_service import _normalize_status_freshness

        status = _normalize_status_freshness({
            "last_run_status": "stale",
            "last_warning": "更新完成但資料仍過期",
            "last_warning_summary": "更新完成但資料仍過期",
        }, is_stale=False)

        assert status["last_run_status"] == "success"
        assert status["last_warning"] is None
        assert status["last_warning_summary"] is None


# ---------------------------------------------------------------------------
# _summarize_error 邏輯
# ---------------------------------------------------------------------------

class TestSummarizeError:

    def test_none_returns_none(self):
        from app.services.update_service import _summarize_error
        assert _summarize_error(None) is None

    def test_empty_string_returns_none(self):
        from app.services.update_service import _summarize_error
        assert _summarize_error("") is None

    def test_single_line(self):
        from app.services.update_service import _summarize_error
        assert _summarize_error("backfill 失敗: timeout") == "backfill 失敗: timeout"

    def test_multiline_returns_first_line(self):
        from app.services.update_service import _summarize_error
        err = "backfill 失敗:\nTraceback...\n  line 42"
        assert _summarize_error(err) == "backfill 失敗:"

    def test_truncated_to_max_len(self):
        from app.services.update_service import _summarize_error
        long_line = "x" * 200
        result = _summarize_error(long_line)
        assert len(result) == 120

    def test_failure_populates_summary_field(self, tmp_update, monkeypatch):
        import app.services.update_service as svc
        monkeypatch.setattr(svc, "_run_backfill", lambda months: (False, "connection refused"))
        status = svc.run_full_update(months=1)
        assert status.get("last_error_summary") is not None
        assert len(status["last_error_summary"]) <= 120

    def test_success_clears_summary_field(self, tmp_update):
        import app.services.update_service as svc
        status = svc.run_full_update(months=1)
        assert status.get("last_error_summary") is None

    def test_stale_after_update_is_not_marked_success(self, tmp_update, monkeypatch):
        import app.services.update_service as svc

        old_date = (date.today() - timedelta(days=10)).isoformat()
        monkeypatch.setattr(svc, "run_daily_signals", lambda: {"as_of": old_date})

        status = svc.run_full_update(months=1)

        assert status["last_run_status"] == "stale"
        assert status["is_stale"] is True
        assert status["last_error"] is None
        assert "資料仍過期" in status["last_warning"]
        assert status["last_warning_summary"] is not None


# ---------------------------------------------------------------------------
# POST /api/system/update-now
# ---------------------------------------------------------------------------

class TestUpdateNowAPI:

    def test_returns_200_and_started(self, client, tmp_update, monkeypatch):
        """正常觸發：回傳 status=started，且不阻塞。"""
        import app.services.update_service as svc
        import app.storage.update_store as store

        # stub 讓背景 thread 立即完成（避免干擾後續測試）
        monkeypatch.setattr(svc, "run_full_update", lambda months=1: None)
        monkeypatch.setattr(svc, "_bg_lock", __import__("threading").Lock())

        # 確保狀態非 running
        store.save_update_status({**store._EMPTY, "last_run_status": "success"})

        resp = client.post("/api/system/update-now")
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"

    def test_returns_409_when_already_running(self, client, tmp_update, monkeypatch):
        """狀態為 running 時，應回傳 409。"""
        import app.storage.update_store as store
        store.save_update_status({
            **store._EMPTY,
            "last_run_started_at": datetime.now().isoformat(timespec="seconds"),
            "last_run_status": "running",
        })

        resp = client.post("/api/system/update-now")
        assert resp.status_code == 409
        body = resp.json()
        assert body["detail"]["status"] == "running"

    def test_allows_restart_when_running_status_is_stalled(self, client, tmp_update, monkeypatch):
        import app.services.update_service as svc
        import app.storage.update_store as store

        started = datetime.now() - timedelta(hours=3)
        store.save_update_status({
            **store._EMPTY,
            "last_run_started_at": started.isoformat(timespec="seconds"),
            "last_run_status": "running",
        })
        monkeypatch.setattr(svc, "run_full_update", lambda months=1: None)
        monkeypatch.setattr(svc, "_bg_lock", __import__("threading").Lock())

        resp = client.post("/api/system/update-now")

        assert resp.status_code == 200
        assert resp.json()["status"] == "started"
