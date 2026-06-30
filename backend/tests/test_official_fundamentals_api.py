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


def test_official_fundamentals_coverage_audit_endpoint(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "get_official_fundamentals_coverage_audit", lambda: {
        "priority_csv_path": "/tmp/fundamentals_priority_fill.csv",
        "target_count": 2,
        "report_count": 7,
        "available_cell_count": 3,
        "coverage_pct": 21.4,
        "missing_report_files": ["dividend"],
        "formally_fillable_official_fields": ["pe"],
        "blocked_formal_fields": ["roe_5y_avg", "dividend_years"],
        "reports": {
            "twse_bwibbu": {
                "key": "twse_bwibbu",
                "label": "TWSE BWIBBU",
                "source": "twse_openapi_bwibbu_all",
                "path": "/tmp/twse.csv",
                "status": "ready",
                "exists": True,
                "row_count": 1,
                "available_count": 1,
                "missing_row_count": 1,
                "key_fields": ["pe"],
            }
        },
        "codes": [
            {
                "code": "2330",
                "name": "台積電",
                "priority_reason": "目前推薦/觀察名單",
                "available_report_count": 1,
                "reports": {
                    "twse_bwibbu": {
                        "status": "available",
                        "present_fields": ["pe"],
                        "skip_reason": "",
                    }
                },
            }
        ],
        "next_action_label": "先補齊缺失的 official report-only CSV",
    })

    response = client.get("/api/system/fundamentals-official/coverage-audit")

    assert response.status_code == 200
    body = response.json()
    assert body["target_count"] == 2
    assert body["reports"]["twse_bwibbu"]["available_count"] == 1
    assert body["codes"][0]["reports"]["twse_bwibbu"]["present_fields"] == ["pe"]
    assert body["blocked_formal_fields"] == ["roe_5y_avg", "dividend_years"]


def test_official_fundamentals_coverage_audit_endpoint_returns_404_when_priority_csv_missing(client, monkeypatch):
    import app.routers.system as router

    def missing_audit():
        raise FileNotFoundError("尚無 fundamentals_priority_fill.csv")

    monkeypatch.setattr(router, "get_official_fundamentals_coverage_audit", missing_audit)

    response = client.get("/api/system/fundamentals-official/coverage-audit")

    assert response.status_code == 404
    assert "fundamentals_priority_fill.csv" in response.json()["detail"]


def test_quality_momentum_lite_guard_coverage_endpoint(client, monkeypatch):
    import app.routers.system as router

    monkeypatch.setattr(router, "get_quality_momentum_lite_guard_coverage", lambda: {
        "priority_csv_path": "/tmp/fundamentals_priority_fill.csv",
        "target_count": 2,
        "guard_count": 5,
        "available_guard_count": 6,
        "coverage_pct": 60.0,
        "formal_apply_fields": ["pe"],
        "reference_only_fields": [
            "operating_margin_reference",
            "debt_to_equity_inputs",
            "revenue_growth_reference",
            "eps_reference",
        ],
        "warnings": [
            "Only pe is a direct official apply field; other lite guard references must stay report-only until formulas and history depth are validated."
        ],
        "codes": [
            {
                "code": "2330",
                "name": "台積電",
                "priority_reason": "目前推薦/觀察名單",
                "available_guard_count": 4,
                "guards": {
                    "pe": {
                        "status": "available",
                        "source_report": "twse_bwibbu",
                        "present_fields": ["pe"],
                        "skip_reason": "",
                    }
                },
            }
        ],
        "next_action_label": "只可作為 Quality Momentum Lite read-only guard 覆蓋率參考",
    })

    response = client.get("/api/system/fundamentals-official/quality-momentum-lite-guard")

    assert response.status_code == 200
    body = response.json()
    assert body["target_count"] == 2
    assert body["formal_apply_fields"] == ["pe"]
    assert body["reference_only_fields"] == [
        "operating_margin_reference",
        "debt_to_equity_inputs",
        "revenue_growth_reference",
        "eps_reference",
    ]
    assert body["codes"][0]["guards"]["pe"]["source_report"] == "twse_bwibbu"


def test_quality_momentum_lite_guard_coverage_endpoint_returns_404_when_priority_csv_missing(client, monkeypatch):
    import app.routers.system as router

    def missing_guard_coverage():
        raise FileNotFoundError("尚無 fundamentals_priority_fill.csv")

    monkeypatch.setattr(router, "get_quality_momentum_lite_guard_coverage", missing_guard_coverage)

    response = client.get("/api/system/fundamentals-official/quality-momentum-lite-guard")

    assert response.status_code == 404
    assert "fundamentals_priority_fill.csv" in response.json()["detail"]


def test_run_official_fundamentals_reports_endpoint_defaults_to_report_only(client, monkeypatch):
    import app.routers.system as router

    captured = {}

    def fake_run(payload):
        captured.update(payload)
        return {
            "dry_run": True,
            "apply": False,
            "requested_reports": [
                "twse_bwibbu",
                "twse_monthly_revenue",
                "tpex_daily_pe",
                "profitability",
                "balance_sheet",
                "income_statement",
                "dividend",
            ],
            "reports": {
                "twse_bwibbu": {"path": "/tmp/twse.csv", "row_count": 1},
                "twse_monthly_revenue": {"path": "/tmp/monthly.csv", "row_count": 2},
                "tpex_daily_pe": {"path": "/tmp/tpex.csv", "row_count": 3},
                "profitability": {"path": "/tmp/profitability.csv", "row_count": 4},
                "balance_sheet": {"path": "/tmp/balance_sheet.csv", "row_count": 5},
                "income_statement": {"path": "/tmp/income_statement.csv", "row_count": 6},
                "dividend": {"path": "/tmp/dividend.csv", "row_count": 7},
            },
            "warnings": [],
        }

    monkeypatch.setattr(router, "run_official_fundamentals_reports", fake_run)

    response = client.post("/api/system/fundamentals-official/reports", json={})

    assert response.status_code == 200
    assert captured["apply"] is False
    assert captured["reports"] == [
        "twse_bwibbu",
        "twse_monthly_revenue",
        "tpex_daily_pe",
        "profitability",
        "balance_sheet",
        "income_statement",
        "dividend",
    ]
    body = response.json()
    assert body["dry_run"] is True
    assert body["reports"]["balance_sheet"]["row_count"] == 5
    assert body["reports"]["income_statement"]["row_count"] == 6
    assert body["reports"]["dividend"]["row_count"] == 7


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


def test_run_official_fundamentals_reports_writes_profitability_csv(tmp_path, monkeypatch):
    import app.services.official_fundamentals_api_service as svc

    profitability = tmp_path / "official_fundamentals_profitability.csv"
    monkeypatch.setattr(svc, "OFFICIAL_REPORTS", {
        "profitability": {
            "label": "Official profitability summary reference",
            "path": profitability,
            "source": "twse_tpex_openapi_profitability",
        },
    })
    monkeypatch.setattr(svc, "_sleep", lambda _seconds: None)
    def fake_fetch(url):
        if url == svc.TWSE_PROFITABILITY_URL:
            return [
                {
                    "公司代號": "2330",
                    "公司名稱": "台積電",
                    "年度": "114",
                    "季別": "1",
                    "營業利益率(%)": "49.20",
                    "稅前純益率(%)": "52.10",
                    "稅後純益率(%)": "41.30",
                }
            ]
        if url == svc.TPEX_PROFITABILITY_URL:
            return [
                {
                    "公司代號": "6488",
                    "公司名稱": "環球晶",
                    "年度": "114",
                    "季別": "1",
                    "營業利益率(%)": "24.50",
                    "稅前純益率(%)": "28.60",
                    "稅後純益率(%)": "21.40",
                }
            ]
        return []

    monkeypatch.setattr(svc, "_fetch_twse_rows", fake_fetch)

    result = svc.run_official_fundamentals_reports({"reports": ["profitability"], "apply": False, "sleep": 0})

    assert result["reports"]["profitability"]["row_count"] == 2
    rows = list(csv.DictReader(profitability.open(encoding="utf-8")))
    assert rows[0]["code"] == "2330"
    assert rows[0]["operating_margin"] == "49.20"
    assert rows[0]["source"] == "twse_openapi_profitability_t187ap17_l"
    assert rows[1]["code"] == "6488"
    assert rows[1]["source"] == "tpex_openapi_profitability_187ap17_o"


def test_run_official_fundamentals_reports_writes_balance_sheet_csv(tmp_path, monkeypatch):
    import app.services.official_fundamentals_api_service as svc

    balance_sheet = tmp_path / "official_fundamentals_balance_sheet.csv"
    monkeypatch.setattr(svc, "OFFICIAL_REPORTS", {
        "balance_sheet": {
            "label": "Official balance sheet reference",
            "path": balance_sheet,
            "source": "twse_tpex_openapi_balance_sheet_ci",
        },
    })
    monkeypatch.setattr(svc, "_sleep", lambda _seconds: None)

    def fake_fetch(url):
        if url == svc.TWSE_BALANCE_SHEET_CI_URL:
            return [
                {
                    "公司代號": "2330",
                    "公司名稱": "台積電",
                    "年度": "115",
                    "季別": "1",
                    "資產總額": "6930430052.00",
                    "負債總額": "2713508871.00",
                    "權益總額": "4216921181.00",
                }
            ]
        if url == svc.TPEX_BALANCE_SHEET_CI_URL:
            return [
                {
                    "SecuritiesCompanyCode": "6488",
                    "CompanyName": "環球晶",
                    "年度": "115",
                    "季別": "1",
                    "資產總計": "223698757.00",
                    "負債總計": "93870412.00",
                    "權益總計": "129828345.00",
                }
            ]
        return []

    monkeypatch.setattr(svc, "_fetch_twse_rows", fake_fetch)

    result = svc.run_official_fundamentals_reports({"reports": ["balance_sheet"], "apply": False, "sleep": 0})

    assert result["reports"]["balance_sheet"]["row_count"] == 2
    rows = list(csv.DictReader(balance_sheet.open(encoding="utf-8")))
    assert rows[0]["code"] == "2330"
    assert rows[0]["total_assets"] == "6930430052.00"
    assert rows[0]["source"] == "twse_openapi_balance_sheet_t187ap07_l_ci"
    assert rows[1]["code"] == "6488"
    assert rows[1]["source"] == "tpex_openapi_balance_sheet_t187ap07_o_ci"


def test_run_official_fundamentals_reports_writes_income_statement_csv(tmp_path, monkeypatch):
    import app.services.official_fundamentals_api_service as svc

    income_statement = tmp_path / "official_fundamentals_income_statement.csv"
    monkeypatch.setattr(svc, "OFFICIAL_REPORTS", {
        "income_statement": {
            "label": "Official income statement reference",
            "path": income_statement,
            "source": "twse_tpex_openapi_income_statement_ci",
        },
    })
    monkeypatch.setattr(svc, "_sleep", lambda _seconds: None)

    def fake_fetch(url):
        if url == svc.TWSE_INCOME_STATEMENT_CI_URL:
            return [
                {
                    "公司代號": "2330",
                    "公司名稱": "台積電",
                    "年度": "115",
                    "季別": "1",
                    "營業收入": "839254000.00",
                    "營業利益（損失）": "411716000.00",
                    "本期淨利（淨損）": "361560000.00",
                    "基本每股盈餘（元）": "13.94",
                }
            ]
        if url == svc.TPEX_INCOME_STATEMENT_CI_URL:
            return [
                {
                    "SecuritiesCompanyCode": "6488",
                    "CompanyName": "環球晶",
                    "Year": "115",
                    "Season": "1",
                    "營業收入": "15421032.00",
                    "營業利益（損失）": "3370880.00",
                    "本期淨利（淨損）": "2586174.00",
                    "基本每股盈餘（元）": "5.93",
                }
            ]
        return []

    monkeypatch.setattr(svc, "_fetch_twse_rows", fake_fetch)

    result = svc.run_official_fundamentals_reports({"reports": ["income_statement"], "apply": False, "sleep": 0})

    assert result["reports"]["income_statement"]["row_count"] == 2
    rows = list(csv.DictReader(income_statement.open(encoding="utf-8")))
    assert rows[0]["code"] == "2330"
    assert rows[0]["revenue"] == "839254000.00"
    assert rows[0]["eps"] == "13.94"
    assert rows[0]["source"] == "twse_openapi_income_statement_t187ap06_l_ci"
    assert rows[1]["code"] == "6488"
    assert rows[1]["source"] == "tpex_openapi_income_statement_t187ap06_o_ci"


def test_run_official_fundamentals_reports_writes_dividend_csv(tmp_path, monkeypatch):
    import app.services.official_fundamentals_api_service as svc

    dividend = tmp_path / "official_fundamentals_dividend.csv"
    monkeypatch.setattr(svc, "OFFICIAL_REPORTS", {
        "dividend": {
            "label": "Official dividend distribution reference",
            "path": dividend,
            "source": "twse_tpex_openapi_dividend",
        },
    })
    monkeypatch.setattr(svc, "_sleep", lambda _seconds: None)

    def fake_fetch(url):
        if url == svc.TWSE_DIVIDEND_URL:
            return [
                {
                    "公司代號": "2330",
                    "公司名稱": "台積電",
                    "股利年度": "114",
                    "股利所屬年(季)度": "年度",
                    "期別": "1",
                    "股東配發-盈餘分配之現金股利(元/股)": "4.00000000",
                    "股東配發-法定盈餘公積發放之現金(元/股)": "0.0",
                    "股東配發-資本公積發放之現金(元/股)": "1.00000000",
                    "股東配發-盈餘轉增資配股(元/股)": "0.20000000",
                    "股東配發-法定盈餘公積轉增資配股(元/股)": "0.0",
                    "股東配發-資本公積轉增資配股(元/股)": "0.30000000",
                }
            ]
        if url == svc.TPEX_DIVIDEND_URL:
            return [
                {
                    "公司代號": "6488",
                    "公司名稱": "環球晶",
                    "股利年度": "114",
                    "期別": "1",
                    "股東配發內容-盈餘分配之現金股利(元/股)": "1.50000000",
                    "股東配發內容-法定盈餘公積、資本公積發放之現金(元/股)": "0.20000000",
                    "股東配發內容-盈餘轉增資配股(元/股)": "0.30000000",
                    "股東配發內容-法定盈餘公積、資本公積轉增資配股(元/股)": "0.10000000",
                }
            ]
        return []

    monkeypatch.setattr(svc, "_fetch_twse_rows", fake_fetch)

    result = svc.run_official_fundamentals_reports({"reports": ["dividend"], "apply": False, "sleep": 0})

    assert result["reports"]["dividend"]["row_count"] == 2
    rows = list(csv.DictReader(dividend.open(encoding="utf-8")))
    assert rows[0]["code"] == "2330"
    assert rows[0]["cash_dividend"] == "5.00000000"
    assert rows[0]["stock_dividend"] == "0.50000000"
    assert rows[0]["source"] == "twse_openapi_dividend_t187ap45_l"
    assert rows[1]["code"] == "6488"
    assert rows[1]["source"] == "tpex_openapi_dividend_t187ap39_o"


def test_run_official_fundamentals_reports_rejects_apply(client):
    response = client.post("/api/system/fundamentals-official/reports", json={"apply": True})

    assert response.status_code == 400
    assert "report-only" in response.json()["detail"]


def test_build_official_fundamentals_coverage_audit_reads_priority_and_report_csvs(tmp_path):
    import app.services.official_fundamentals_api_service as svc

    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    _write_csv(
        priority_csv,
        ["code", "name", "priority_reason"],
        [
            {"code": "2330", "name": "台積電", "priority_reason": "目前推薦/觀察名單"},
            {"code": "6488", "name": "環球晶", "priority_reason": "目前推薦/觀察名單"},
            {"code": "9999", "name": "缺資料", "priority_reason": "目前推薦/觀察名單"},
        ],
    )
    twse_bwibbu = tmp_path / "official_fundamentals_twse_bwibbu.csv"
    income_statement = tmp_path / "official_fundamentals_income_statement.csv"
    missing_dividend = tmp_path / "official_fundamentals_dividend.csv"
    _write_csv(
        twse_bwibbu,
        ["code", "name", "pe", "source", "skip_reason"],
        [{"code": "2330", "name": "台積電", "pe": "22.5", "source": "twse", "skip_reason": ""}],
    )
    _write_csv(
        income_statement,
        ["code", "name", "revenue", "operating_profit", "net_income", "eps", "source", "skip_reason"],
        [
            {
                "code": "2330",
                "name": "台積電",
                "revenue": "839254000.00",
                "operating_profit": "411716000.00",
                "net_income": "361560000.00",
                "eps": "13.94",
                "source": "twse",
                "skip_reason": "",
            },
            {
                "code": "6488",
                "name": "環球晶",
                "revenue": "15421032.00",
                "operating_profit": "3370880.00",
                "net_income": "2586174.00",
                "eps": "5.93",
                "source": "tpex",
                "skip_reason": "",
            },
        ],
    )

    audit = svc.build_official_fundamentals_coverage_audit(
        priority_csv,
        reports={
            "twse_bwibbu": {
                "label": "TWSE BWIBBU",
                "path": twse_bwibbu,
                "source": "twse_openapi_bwibbu_all",
            },
            "income_statement": {
                "label": "Official income statement reference",
                "path": income_statement,
                "source": "twse_tpex_openapi_income_statement_ci",
            },
            "dividend": {
                "label": "Official dividend distribution reference",
                "path": missing_dividend,
                "source": "twse_tpex_openapi_dividend",
            },
        },
    )

    assert audit["target_count"] == 3
    assert audit["report_count"] == 3
    assert audit["available_cell_count"] == 3
    assert audit["coverage_pct"] == 33.3
    assert audit["missing_report_files"] == ["dividend"]
    assert audit["blocked_formal_fields"] == [
        "roe_5y_avg",
        "operating_margin_5y_avg",
        "free_cash_flow_positive_years",
        "operating_cash_flow_to_net_income",
        "debt_to_equity",
        "interest_coverage",
        "revenue_growth_5y_cagr",
        "eps_growth_5y_cagr",
        "fcf_yield",
        "dividend_years",
    ]
    assert audit["reports"]["twse_bwibbu"]["available_count"] == 1
    assert audit["reports"]["income_statement"]["available_count"] == 2
    assert audit["reports"]["dividend"]["status"] == "missing_file"
    by_code = {row["code"]: row for row in audit["codes"]}
    assert by_code["2330"]["available_report_count"] == 2
    assert by_code["2330"]["reports"]["twse_bwibbu"]["present_fields"] == ["pe"]
    assert by_code["6488"]["reports"]["twse_bwibbu"]["status"] == "missing_row"
    assert by_code["6488"]["reports"]["income_statement"]["present_fields"] == [
        "revenue",
        "operating_profit",
        "net_income",
        "eps",
    ]
    assert by_code["9999"]["available_report_count"] == 0


def test_build_quality_momentum_lite_guard_coverage_is_read_only_reference_summary(tmp_path):
    import app.services.official_fundamentals_api_service as svc

    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    _write_csv(
        priority_csv,
        ["code", "name", "priority_reason"],
        [
            {"code": "2330", "name": "台積電", "priority_reason": "目前推薦/觀察名單"},
            {"code": "6488", "name": "環球晶", "priority_reason": "目前推薦/觀察名單"},
        ],
    )
    twse_bwibbu = tmp_path / "official_fundamentals_twse_bwibbu.csv"
    tpex_daily_pe = tmp_path / "official_fundamentals_tpex_daily_pe.csv"
    profitability = tmp_path / "official_fundamentals_profitability.csv"
    balance_sheet = tmp_path / "official_fundamentals_balance_sheet.csv"
    monthly_revenue = tmp_path / "official_fundamentals_twse_monthly_revenue.csv"
    income_statement = tmp_path / "official_fundamentals_income_statement.csv"

    _write_csv(twse_bwibbu, ["code", "name", "pe", "source", "skip_reason"], [
        {"code": "2330", "name": "台積電", "pe": "22.5", "source": "twse", "skip_reason": ""},
    ])
    _write_csv(tpex_daily_pe, ["code", "name", "pe", "source", "skip_reason"], [
        {"code": "6488", "name": "環球晶", "pe": "18.2", "source": "tpex", "skip_reason": ""},
    ])
    _write_csv(profitability, ["code", "name", "operating_margin", "source", "skip_reason"], [
        {"code": "2330", "name": "台積電", "operating_margin": "49.20", "source": "twse", "skip_reason": ""},
    ])
    _write_csv(balance_sheet, ["code", "name", "liabilities", "equity", "source", "skip_reason"], [
        {"code": "2330", "name": "台積電", "liabilities": "2713508871", "equity": "4216921181", "source": "twse", "skip_reason": ""},
        {"code": "6488", "name": "環球晶", "liabilities": "", "equity": "129828345", "source": "tpex", "skip_reason": "liabilities_missing"},
    ])
    _write_csv(monthly_revenue, ["code", "name", "cumulative_revenue_yoy_pct", "source", "skip_reason"], [
        {"code": "2330", "name": "台積電", "cumulative_revenue_yoy_pct": "42.6", "source": "twse", "skip_reason": ""},
    ])
    _write_csv(income_statement, ["code", "name", "revenue", "eps", "source", "skip_reason"], [
        {"code": "6488", "name": "環球晶", "revenue": "15421032", "eps": "5.93", "source": "tpex", "skip_reason": ""},
    ])

    result = svc.build_quality_momentum_lite_guard_coverage(
        priority_csv,
        reports={
            "twse_bwibbu": {"path": twse_bwibbu},
            "tpex_daily_pe": {"path": tpex_daily_pe},
            "profitability": {"path": profitability},
            "balance_sheet": {"path": balance_sheet},
            "twse_monthly_revenue": {"path": monthly_revenue},
            "income_statement": {"path": income_statement},
        },
    )

    assert result["target_count"] == 2
    assert result["guard_count"] == 5
    assert result["coverage_pct"] == 60.0
    assert result["formal_apply_fields"] == ["pe"]
    assert result["reference_only_fields"] == [
        "operating_margin_reference",
        "debt_to_equity_inputs",
        "revenue_growth_reference",
        "eps_reference",
    ]
    assert result["warnings"] == [
        "Only pe is a direct official apply field; other lite guard references must stay report-only until formulas and history depth are validated."
    ]

    by_code = {row["code"]: row for row in result["codes"]}
    assert by_code["2330"]["available_guard_count"] == 4
    assert by_code["2330"]["guards"]["pe"]["status"] == "available"
    assert by_code["2330"]["guards"]["pe"]["source_report"] == "twse_bwibbu"
    assert by_code["2330"]["guards"]["debt_to_equity_inputs"]["present_fields"] == ["liabilities", "equity"]
    assert by_code["6488"]["available_guard_count"] == 2
    assert by_code["6488"]["guards"]["debt_to_equity_inputs"]["status"] == "missing_values"
    assert by_code["6488"]["guards"]["eps_reference"]["status"] == "available"
