import csv


def _write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_get_official_fundamentals_reports_status_counts_rows(tmp_path, monkeypatch):
    import app.services.official_fundamentals_api_service as svc

    twse_bwibbu = tmp_path / "official_fundamentals_twse_bwibbu.csv"
    twse_monthly = tmp_path / "official_fundamentals_twse_monthly_revenue.csv"
    tpex_daily_pe = tmp_path / "official_fundamentals_tpex_daily_pe.csv"
    _write_csv(twse_bwibbu, ["code", "pe"], [{"code": "2330", "pe": "22.5"}])
    _write_csv(twse_monthly, ["code", "monthly_revenue_yoy_pct"], [
        {"code": "2330", "monthly_revenue_yoy_pct": "39.6"},
        {"code": "2303", "monthly_revenue_yoy_pct": "17.2"},
    ])

    monkeypatch.setattr(svc, "OFFICIAL_REPORTS", {
        "twse_bwibbu": {
            "label": "TWSE BWIBBU",
            "path": twse_bwibbu,
            "source": "twse_openapi_bwibbu_all",
        },
        "twse_monthly_revenue": {
            "label": "TWSE monthly revenue",
            "path": twse_monthly,
            "source": "twse_openapi_monthly_revenue_t187ap05_l",
        },
        "tpex_daily_pe": {
            "label": "TPEx daily PE",
            "path": tpex_daily_pe,
            "source": "tpex_after_trading_pe_qry_date",
        },
    })

    status = svc.get_official_fundamentals_status()

    assert status["overall_status"] == "partial"
    assert status["reports"]["twse_bwibbu"]["exists"] is True
    assert status["reports"]["twse_bwibbu"]["row_count"] == 1
    assert status["reports"]["twse_bwibbu"]["modified_at"] is not None
    assert status["reports"]["twse_monthly_revenue"]["row_count"] == 2
    assert status["reports"]["tpex_daily_pe"]["exists"] is False
    assert status["reports"]["tpex_daily_pe"]["row_count"] == 0


def test_official_fundamentals_status_endpoint(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "get_official_fundamentals_status", lambda: {
        "overall_status": "ready",
        "reports": {
            "twse_bwibbu": {
                "key": "twse_bwibbu",
                "label": "TWSE BWIBBU",
                "source": "twse_openapi_bwibbu_all",
                "path": "/tmp/twse.csv",
                "exists": True,
                "row_count": 1,
                "modified_at": "2026-06-29T00:00:00",
            }
        },
        "next_action_label": "可產生官方 report-only CSV",
    })

    response = client.get("/api/system/fundamentals-official/status")

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "ready"
    assert body["reports"]["twse_bwibbu"]["row_count"] == 1


def test_run_official_fundamentals_reports_endpoint_defaults_to_report_only(client, monkeypatch):
    import app.routers.system as router

    captured = {}

    def fake_run(payload):
        captured.update(payload)
        return {
            "dry_run": True,
            "apply": False,
            "requested_reports": ["twse_bwibbu", "twse_monthly_revenue", "tpex_daily_pe"],
            "reports": {
                "twse_bwibbu": {"path": "/tmp/twse.csv", "row_count": 1},
                "twse_monthly_revenue": {"path": "/tmp/monthly.csv", "row_count": 2},
                "tpex_daily_pe": {"path": "/tmp/tpex.csv", "row_count": 3},
            },
            "warnings": [],
        }

    monkeypatch.setattr(router, "run_official_fundamentals_reports", fake_run)

    response = client.post("/api/system/fundamentals-official/reports", json={})

    assert response.status_code == 200
    assert captured["apply"] is False
    assert captured["reports"] == ["twse_bwibbu", "twse_monthly_revenue", "tpex_daily_pe"]
    body = response.json()
    assert body["dry_run"] is True
    assert body["reports"]["tpex_daily_pe"]["row_count"] == 3


def test_run_official_fundamentals_reports_writes_report_only_csv(tmp_path, monkeypatch):
    import app.services.official_fundamentals_api_service as svc

    twse_bwibbu = tmp_path / "official_fundamentals_twse_bwibbu.csv"
    monkeypatch.setattr(svc, "OFFICIAL_REPORTS", {
        "twse_bwibbu": {
            "label": "TWSE BWIBBU",
            "path": twse_bwibbu,
            "source": "twse_openapi_bwibbu_all",
        },
    })
    monkeypatch.setattr(svc, "_sleep", lambda _seconds: None)
    monkeypatch.setattr(svc, "_fetch_twse_rows", lambda _url: [
        {
            "Code": "2330",
            "Name": "台積電",
            "PEratio": "22.5",
            "DividendYield": "1.7",
            "PBratio": "5.8",
        }
    ])

    result = svc.run_official_fundamentals_reports({"reports": ["twse_bwibbu"], "apply": False, "sleep": 0})

    assert result["dry_run"] is True
    assert result["apply"] is False
    assert result["reports"]["twse_bwibbu"]["row_count"] == 1
    assert twse_bwibbu.exists()
    rows = list(csv.DictReader(twse_bwibbu.open(encoding="utf-8")))
    assert rows[0]["code"] == "2330"
    assert rows[0]["pe"] == "22.5"


def test_run_official_fundamentals_reports_rejects_apply(client):
    response = client.post("/api/system/fundamentals-official/reports", json={"apply": True})

    assert response.status_code == 400
    assert "report-only" in response.json()["detail"]
