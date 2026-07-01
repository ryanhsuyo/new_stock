def test_today_scan_endpoint_returns_report(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "load_today_scan_report", lambda: {
        "as_of": "2026-06-30",
        "formal_entries": [
            {
                "code": "2884",
                "name": "玉山金",
                "strategy_score_summary": {
                    "primary_strategy": "steady_momentum",
                    "summary_label": "第二 穩健 76，高於第一 老王 73",
                },
            }
        ],
        "old_wang_candidates": [],
        "steady_momentum_candidates": [],
        "risk_items": [],
    })

    response = client.get("/api/system/today-scan")

    assert response.status_code == 200
    body = response.json()
    assert body["as_of"] == "2026-06-30"
    assert body["formal_entries"][0]["strategy_score_summary"]["summary_label"] == "第二 穩健 76，高於第一 老王 73"


def test_today_scan_endpoint_returns_404_when_missing(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "load_today_scan_report", lambda: None)

    response = client.get("/api/system/today-scan")

    assert response.status_code == 404
    assert "today_scan.json" in response.json()["detail"]
