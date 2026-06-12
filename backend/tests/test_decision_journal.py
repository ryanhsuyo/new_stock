def test_decision_journal_starts_empty(client, tmp_path, monkeypatch):
    import app.storage.decision_journal_store as store

    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", tmp_path / "decision_journal.json")

    response = client.get("/api/decision-journal")

    assert response.status_code == 200
    assert response.json() == []


def test_create_decision_journal_entry_persists_with_workflow_snapshot(client, tmp_path, monkeypatch):
    import app.services.decision_journal_service as service
    import app.storage.decision_journal_store as store

    journal_path = tmp_path / "decision_journal.json"
    refresh_calls = []
    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", journal_path)
    monkeypatch.setattr(service, "_refresh_daily_check_safely", lambda: refresh_calls.append("daily_check"))
    monkeypatch.setattr(
        service,
        "get_workflow_status",
        lambda: {
            "overall_status": "ready",
            "headline": "資料與訊號已就緒",
        },
    )

    response = client.post(
        "/api/decision-journal",
        json={
            "date": "2026-05-22",
            "code": "2330",
            "name": "台積電",
            "decision": "hold",
            "reason": "守住 MA10，尚未跌破關鍵支撐。",
            "price": 2310,
            "shares": 1000,
            "key_price": "MA10 2280",
            "invalidation": "跌破 MA10 且爆量長黑",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"]
    assert body["created_at"]
    assert body["updated_at"] is None
    assert body["workflow_status"] == "ready"
    assert body["workflow_headline"] == "資料與訊號已就緒"
    assert body["decision"] == "hold"
    assert journal_path.exists()

    list_response = client.get("/api/decision-journal")
    assert list_response.status_code == 200
    assert list_response.json()[0]["code"] == "2330"
    assert refresh_calls == ["daily_check"]


def test_decision_journal_lists_newest_first_and_can_filter_by_code(client, tmp_path, monkeypatch):
    import app.services.decision_journal_service as service
    import app.storage.decision_journal_store as store

    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", tmp_path / "decision_journal.json")
    monkeypatch.setattr(
        service,
        "get_workflow_status",
        lambda: {"overall_status": "warning", "headline": "仍有提醒事項"},
    )

    for payload in [
        {"date": "2026-05-21", "code": "2408", "name": "南亞科", "decision": "watch", "reason": "等回測五日線。"},
        {"date": "2026-05-22", "code": "2330", "name": "台積電", "decision": "skip", "reason": "距離入場區間太遠。"},
    ]:
        response = client.post("/api/decision-journal", json=payload)
        assert response.status_code == 200

    response = client.get("/api/decision-journal")
    assert [item["code"] for item in response.json()] == ["2330", "2408"]

    filtered = client.get("/api/decision-journal?code=2408")
    assert [item["code"] for item in filtered.json()] == ["2408"]


def test_decision_journal_lists_same_second_entries_in_write_order(client, tmp_path, monkeypatch):
    import app.services.decision_journal_service as service
    import app.storage.decision_journal_store as store

    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", tmp_path / "decision_journal.json")
    monkeypatch.setattr(
        service,
        "get_workflow_status",
        lambda: {"overall_status": "ready", "headline": "資料與訊號已就緒"},
    )

    for payload in [
        {"date": "2026-05-22", "code": "2337", "name": "旺宏", "decision": "reduce", "reason": "破線先減碼。"},
        {"date": "2026-05-22", "code": "2408", "name": "南亞科", "decision": "hold", "reason": "守住關鍵價。"},
    ]:
        response = client.post("/api/decision-journal", json=payload)
        assert response.status_code == 200

    response = client.get("/api/decision-journal?date=2026-05-22")

    assert [item["code"] for item in response.json()] == ["2408", "2337"]


def test_decision_journal_can_filter_by_date_and_decision(client, tmp_path, monkeypatch):
    import app.services.decision_journal_service as service
    import app.storage.decision_journal_store as store

    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", tmp_path / "decision_journal.json")
    monkeypatch.setattr(
        service,
        "get_workflow_status",
        lambda: {"overall_status": "ready", "headline": "資料與訊號已就緒"},
    )

    for payload in [
        {"date": "2026-05-22", "code": "2337", "name": "旺宏", "decision": "reduce", "reason": "破線先減碼。"},
        {"date": "2026-05-22", "code": "2408", "name": "南亞科", "decision": "hold", "reason": "守住關鍵價。"},
        {"date": "2026-05-23", "code": "2303", "name": "聯電", "decision": "reduce", "reason": "隔日減碼。"},
    ]:
        response = client.post("/api/decision-journal", json=payload)
        assert response.status_code == 200

    by_date = client.get("/api/decision-journal?date=2026-05-22")
    assert [item["code"] for item in by_date.json()] == ["2408", "2337"]

    by_date_and_decision = client.get("/api/decision-journal?date=2026-05-22&decision=reduce")
    assert [item["code"] for item in by_date_and_decision.json()] == ["2337"]


def test_decision_journal_rejects_invalid_decision_and_empty_reason(client, tmp_path, monkeypatch):
    import app.storage.decision_journal_store as store

    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", tmp_path / "decision_journal.json")

    bad_decision = client.post(
        "/api/decision-journal",
        json={"date": "2026-05-22", "code": "2330", "name": "台積電", "decision": "guess", "reason": "x"},
    )
    assert bad_decision.status_code == 400

    empty_reason = client.post(
        "/api/decision-journal",
        json={"date": "2026-05-22", "code": "2330", "name": "台積電", "decision": "hold", "reason": "  "},
    )
    assert empty_reason.status_code == 400


def test_delete_decision_journal_entry_removes_only_matching_entry(client, tmp_path, monkeypatch):
    import app.services.decision_journal_service as service
    import app.storage.decision_journal_store as store

    refresh_calls = []
    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", tmp_path / "decision_journal.json")
    monkeypatch.setattr(service, "_refresh_daily_check_safely", lambda: refresh_calls.append("daily_check"))
    monkeypatch.setattr(
        service,
        "get_workflow_status",
        lambda: {"overall_status": "ready", "headline": "資料與訊號已就緒"},
    )

    first = client.post(
        "/api/decision-journal",
        json={"date": "2026-05-22", "code": "2337", "name": "旺宏", "decision": "reduce", "reason": "破線先減碼。"},
    ).json()
    second = client.post(
        "/api/decision-journal",
        json={"date": "2026-05-22", "code": "2408", "name": "南亞科", "decision": "hold", "reason": "守住關鍵價。"},
    ).json()

    response = client.delete(f"/api/decision-journal/{first['id']}")

    assert response.status_code == 200
    assert response.json() == {"deleted": first["id"]}
    remaining = client.get("/api/decision-journal").json()
    assert [item["id"] for item in remaining] == [second["id"]]
    assert refresh_calls == ["daily_check", "daily_check", "daily_check"]


def test_delete_decision_journal_entry_returns_404_when_missing(client, tmp_path, monkeypatch):
    import app.storage.decision_journal_store as store

    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", tmp_path / "decision_journal.json")

    response = client.delete("/api/decision-journal/not-found")

    assert response.status_code == 404


def test_update_decision_journal_entry_preserves_identity_and_snapshot(client, tmp_path, monkeypatch):
    import app.services.decision_journal_service as service
    import app.storage.decision_journal_store as store

    refresh_calls = []
    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", tmp_path / "decision_journal.json")
    monkeypatch.setattr(service, "_refresh_daily_check_safely", lambda: refresh_calls.append("daily_check"))
    monkeypatch.setattr(
        service,
        "get_workflow_status",
        lambda: {"overall_status": "warning", "headline": "建立時工作流"},
    )
    created = client.post(
        "/api/decision-journal",
        json={"date": "2026-05-22", "code": "2337", "name": "旺宏", "decision": "reduce", "reason": "原始理由。"},
    ).json()

    response = client.put(
        f"/api/decision-journal/{created['id']}",
        json={
            "date": "2026-05-23",
            "code": "2408",
            "name": "南亞科",
            "decision": "hold",
            "reason": "改成續抱，守住關鍵支撐。",
            "price": 343.5,
            "shares": 1000,
            "key_price": "爆量低 301",
            "invalidation": "跌破爆量低",
            "source": "manual",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["created_at"] == created["created_at"]
    assert created["updated_at"] is None
    assert body["updated_at"]
    assert body["workflow_status"] == "warning"
    assert body["workflow_headline"] == "建立時工作流"
    assert body["code"] == "2408"
    assert body["decision"] == "hold"
    assert body["key_price"] == "爆量低 301"
    assert refresh_calls == ["daily_check", "daily_check"]


def test_update_decision_journal_entry_returns_404_when_missing(client, tmp_path, monkeypatch):
    import app.storage.decision_journal_store as store

    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", tmp_path / "decision_journal.json")

    response = client.put(
        "/api/decision-journal/not-found",
        json={"date": "2026-05-22", "code": "2337", "name": "旺宏", "decision": "hold", "reason": "找不到。"},
    )

    assert response.status_code == 404


def test_decision_journal_summary_counts_requested_date(client, tmp_path, monkeypatch):
    import app.services.decision_journal_service as service
    import app.storage.decision_journal_store as store

    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", tmp_path / "decision_journal.json")
    monkeypatch.setattr(
        service,
        "get_workflow_status",
        lambda: {"overall_status": "ready", "headline": "資料與訊號已就緒"},
    )

    for payload in [
        {"date": "2026-05-22", "code": "2337", "name": "旺宏", "decision": "reduce", "reason": "破線先減碼。"},
        {"date": "2026-05-22", "code": "2408", "name": "南亞科", "decision": "hold", "reason": "守住關鍵價。"},
        {"date": "2026-05-22", "code": "2303", "name": "聯電", "decision": "reduce", "reason": "短線過熱。"},
        {"date": "2026-05-21", "code": "6443", "name": "元晶", "decision": "sell", "reason": "昨日出場。"},
    ]:
        response = client.post("/api/decision-journal", json=payload)
        assert response.status_code == 200

    response = client.get("/api/decision-journal/summary?date=2026-05-22")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-05-22"
    assert body["total_count"] == 3
    assert body["by_decision"] == {"hold": 1, "reduce": 2}
    assert body["recent_codes"] == ["2303", "2408", "2337"]


def test_bulk_create_decision_journal_from_portfolio_tasks_skips_existing(client, tmp_path, monkeypatch):
    import app.services.decision_journal_service as service
    import app.storage.decision_journal_store as store

    refresh_calls = []
    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", tmp_path / "decision_journal.json")
    monkeypatch.setattr(service, "_refresh_daily_check_safely", lambda: refresh_calls.append("daily_check"))
    monkeypatch.setattr(
        service,
        "get_workflow_status",
        lambda: {
            "overall_status": "warning",
            "headline": "閉環可用但有待補",
            "data_as_of": "2026-05-29",
            "portfolio_tasks": [
                {
                    "code": "2337",
                    "name": "旺宏",
                    "action": "hold",
                    "label": "續抱",
                    "reason": "守住 MA20，續抱觀察。",
                    "key_price": "MA20 157",
                    "invalidation": "跌破 MA20",
                    "holding_shares": 1000,
                },
                {
                    "code": "2408",
                    "name": "南亞科",
                    "action": "reduce",
                    "label": "減碼",
                    "reason": "跌破短均，先降風險。",
                    "key_price": "爆量低 300",
                    "invalidation": "跌破爆量低",
                    "holding_shares": 2000,
                },
            ],
        },
    )

    existing = {
        "date": "2026-05-29",
        "code": "2337",
        "name": "旺宏",
        "decision": "hold",
        "reason": "已手動記錄。",
    }
    assert client.post("/api/decision-journal", json=existing).status_code == 200

    response = client.post("/api/decision-journal/from-portfolio-tasks", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-05-29"
    assert body["total_task_count"] == 2
    assert body["created_count"] == 1
    assert body["skipped_count"] == 1
    assert body["skipped_codes"] == ["2337"]
    created = body["created_entries"][0]
    assert created["code"] == "2408"
    assert created["decision"] == "reduce"
    assert created["source"] == "workflow_bulk"
    assert created["shares"] == 2000

    journal = client.get("/api/decision-journal?date=2026-05-29").json()
    assert {entry["code"] for entry in journal} == {"2337", "2408"}
    assert refresh_calls == ["daily_check", "daily_check"]


def test_build_universe_report_review_draft_lists_unrecorded_actionable_items(monkeypatch):
    import app.services.decision_journal_service as service

    monkeypatch.setattr(service, "get_universe_report_json", lambda: [
        {
            "data_as_of": "2026-05-29",
            "code": "2337",
            "name": "旺宏",
            "daily_action": "exit",
            "daily_action_label": "出場處理",
            "daily_action_reason": "跌破 MA20，先處理風險。",
            "daily_key_price": "MA20 157",
            "daily_invalidation": "重新站回 MA20",
            "daily_priority": 91,
            "holding_shares": 0,
        },
        {
            "data_as_of": "2026-05-29",
            "code": "2408",
            "name": "南亞科",
            "daily_action": "wait_pullback",
            "daily_action_label": "等回測",
            "daily_action_reason": "距離進場區太遠，等 MA10。",
            "daily_key_price": "MA10 302.5",
            "daily_invalidation": "跌破爆量低",
            "daily_priority": 80,
        },
        {
            "data_as_of": "2026-05-29",
            "code": "2454",
            "name": "聯發科",
            "daily_action": "avoid",
            "daily_action_label": "暫不碰",
            "daily_action_reason": "過熱。",
        },
    ])
    monkeypatch.setattr(service, "load_decision_journal", lambda: [
        service.DecisionJournalEntry(
            id="x",
            created_at="2026-05-29T16:00:00",
            updated_at=None,
            date="2026-05-29",
            code="2408",
            name="南亞科",
            decision="watch",
            reason="已從報表記錄。",
            source="universe_report",
            workflow_status="warning",
            workflow_headline="有待補",
        )
    ])

    draft = service.build_universe_report_review_draft()

    assert draft["as_of"] == "2026-05-29"
    assert draft["actionable_count"] == 2
    assert draft["recorded_count"] == 1
    assert draft["missing_count"] == 1
    assert draft["items"][0]["code"] == "2337"
    assert draft["items"][0]["decision_suggestion"] == "skip"
    assert draft["items"][0]["reason"] == "跌破 MA20，先處理風險。"


def test_build_universe_report_review_workflow_summary_prioritizes_missing_items(monkeypatch):
    import app.services.decision_journal_service as service

    monkeypatch.setattr(service, "build_universe_report_review_draft", lambda as_of=None, limit=None: {
        "as_of": "2026-05-29",
        "actionable_count": 3,
        "recorded_count": 1,
        "missing_count": 2,
        "items": [
            {
                "code": "2337",
                "name": "旺宏",
                "action": "exit",
                "label": "出場處理",
                "decision_suggestion": "skip",
                "reason": "未持有但跌破支撐，不進場。",
                "priority": 91,
            },
            {
                "code": "2408",
                "name": "南亞科",
                "action": "wait_pullback",
                "label": "等回測",
                "decision_suggestion": "watch",
                "reason": "等 MA10 回測。",
                "priority": 80,
            },
        ],
    })

    summary = service.build_universe_report_review_workflow_summary(limit=5)

    assert summary["stage"] == "review_candidates"
    assert summary["headline"] == "補候選股復盤紀錄"
    assert summary["progress_label"] == "1/3 已復盤"
    assert summary["primary_action"]["label"] == "批次記錄前 2 檔"
    assert summary["primary_action"]["command"] == "POST /api/decision-journal/from-universe-report"
    assert summary["checklist"][0]["status"] == "done"
    assert summary["checklist"][1]["status"] == "todo"
    assert summary["top_items"][0]["code"] == "2337"


def test_build_universe_report_review_workflow_summary_marks_complete(monkeypatch):
    import app.services.decision_journal_service as service

    monkeypatch.setattr(service, "build_universe_report_review_draft", lambda as_of=None, limit=None: {
        "as_of": "2026-05-29",
        "actionable_count": 2,
        "recorded_count": 2,
        "missing_count": 0,
        "items": [],
    })

    summary = service.build_universe_report_review_workflow_summary()

    assert summary["stage"] == "complete"
    assert summary["headline"] == "候選股復盤已完成"
    assert summary["primary_action"]["label"] == "查看紀錄"
    assert [step["status"] for step in summary["checklist"]] == ["done", "done", "done"]


def test_create_missing_universe_report_entries_persists_suggested_decisions(tmp_path, monkeypatch):
    import app.services.decision_journal_service as service
    import app.storage.decision_journal_store as store

    refresh_calls = []
    monkeypatch.setattr(store, "DECISION_JOURNAL_PATH", tmp_path / "decision_journal.json")
    monkeypatch.setattr(service, "_refresh_daily_check_safely", lambda: refresh_calls.append("daily_check"))
    monkeypatch.setattr(service, "_workflow_snapshot", lambda: ("warning", "仍有候選股待復盤"))
    monkeypatch.setattr(service, "build_universe_report_review_draft", lambda as_of=None, limit=None: {
        "as_of": "2026-05-29",
        "actionable_count": 2,
        "recorded_count": 0,
        "missing_count": 2,
        "items": [
            {
                "code": "2337",
                "name": "旺宏",
                "decision_suggestion": "skip",
                "reason": "未持有但跌破支撐，不進場。",
                "key_price": "MA20 157",
                "invalidation": "重新站回 MA20",
            },
            {
                "code": "2408",
                "name": "南亞科",
                "decision_suggestion": "watch",
                "reason": "等 MA10 回測。",
                "key_price": "MA10 302",
                "invalidation": "跌破爆量低",
            },
        ],
    })

    result = service.create_missing_universe_report_entries(date="2026-05-29", limit=10)

    assert result.date == "2026-05-29"
    assert result.total_task_count == 2
    assert result.created_count == 2
    assert result.skipped_count == 0
    assert [entry.code for entry in result.created_entries] == ["2337", "2408"]
    assert result.created_entries[0].decision == "skip"
    assert result.created_entries[0].source == "universe_report"
    assert refresh_calls == ["daily_check"]


def test_decision_journal_universe_report_workflow_endpoint(client, monkeypatch):
    import app.routers.decision_journal as router

    monkeypatch.setattr(router, "build_universe_report_review_workflow_summary", lambda as_of=None, limit=10: {
        "stage": "review_candidates",
        "headline": "補候選股復盤紀錄",
        "detail": "x",
        "as_of": "2026-05-29",
        "progress_label": "1/3 已復盤",
        "actionable_count": 3,
        "recorded_count": 1,
        "missing_count": 2,
        "primary_action": {"label": "批次記錄前 2 檔", "command": "POST /api/decision-journal/from-universe-report", "kind": "api"},
        "checklist": [],
        "top_items": [],
    })

    response = client.get("/api/decision-journal/universe-report-workflow?date=2026-05-29&limit=5")

    assert response.status_code == 200
    assert response.json()["stage"] == "review_candidates"
    assert response.json()["as_of"] == "2026-05-29"


def test_build_universe_report_review_draft_suggests_sell_only_for_existing_holding(monkeypatch):
    import app.services.decision_journal_service as service

    monkeypatch.setattr(service, "get_universe_report_json", lambda: [
        {
            "data_as_of": "2026-05-29",
            "code": "2337",
            "name": "旺宏",
            "daily_action": "exit",
            "daily_action_label": "出場處理",
            "daily_action_reason": "持股跌破停損。",
            "holding_shares": 1000,
        },
    ])
    monkeypatch.setattr(service, "load_decision_journal", lambda: [])

    draft = service.build_universe_report_review_draft()

    assert draft["items"][0]["decision_suggestion"] == "sell"


def test_render_universe_report_review_markdown_keeps_human_decision_blank():
    import app.services.decision_journal_service as service

    markdown = service.render_universe_report_review_markdown({
        "as_of": "2026-05-29",
        "actionable_count": 1,
        "recorded_count": 0,
        "missing_count": 1,
        "items": [{
            "code": "2337",
            "name": "旺宏",
            "action": "exit",
            "label": "出場處理",
            "decision_suggestion": "sell",
            "reason": "跌破 MA20。",
            "key_price": "MA20 157",
            "invalidation": "重新站回 MA20",
        }],
    })

    assert "# 候選股復盤待辦 - 2026-05-29" in markdown
    assert "2337 旺宏" in markdown
    assert "建議 decision: sell" in markdown
    assert "- 實際決策：" in markdown
    assert "- 最終理由：" in markdown


def test_write_universe_report_review_markdown_writes_out_file(tmp_path, monkeypatch):
    import app.services.decision_journal_service as service

    monkeypatch.setattr(service, "build_universe_report_review_draft", lambda as_of=None, limit=None: {
        "as_of": "2026-05-29",
        "actionable_count": 0,
        "recorded_count": 0,
        "missing_count": 0,
        "items": [],
    })

    path = service.write_universe_report_review_markdown(out_dir=tmp_path)

    assert path == tmp_path / "universe_report_review_todo.md"
    assert "候選股復盤待辦" in path.read_text(encoding="utf-8")


def test_export_universe_review_todo_help_exits_0():
    import subprocess
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parent.parent / "scripts"
    result = subprocess.run(
        [sys.executable, str(scripts / "export_universe_review_todo.py"), "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--limit" in result.stdout
    assert "--date" in result.stdout


def test_export_universe_review_todo_run_prints_output_path(monkeypatch, tmp_path, capsys):
    import scripts.export_universe_review_todo as script

    path = tmp_path / "universe_report_review_todo.md"
    path.write_text("# x", encoding="utf-8")
    monkeypatch.setattr(script, "write_universe_report_review_markdown", lambda as_of=None, limit=None: path)

    code = script.run_export(script.parse_args(["--date", "2026-05-29", "--limit", "5"]))

    out = capsys.readouterr().out
    assert code == 0
    assert str(path) in out
