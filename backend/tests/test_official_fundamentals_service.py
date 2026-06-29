import csv

from app.services import official_fundamentals_service as svc


def _priority_csv(path):
    fieldnames = [
        "code",
        "name",
        "priority_reason",
        "missing_count",
        "missing_fields",
        "missing_field_labels",
        "fill_format_note",
        "example_values",
        *svc.REQUIRED_FIELDS,
    ]
    rows = [
        {
            "code": "2330",
            "name": "台積電",
            "priority_reason": "目前推薦/觀察名單",
            "missing_count": "11",
            "missing_fields": "all",
            "missing_field_labels": "全部",
            "fill_format_note": "note",
            "example_values": "examples",
            **{field: "" for field in svc.REQUIRED_FIELDS},
        },
        {
            "code": "6488",
            "name": "環球晶",
            "priority_reason": "目前推薦/觀察名單",
            "missing_count": "11",
            "missing_fields": "all",
            "missing_field_labels": "全部",
            "fill_format_note": "note",
            "example_values": "examples",
            **{field: "" for field in svc.REQUIRED_FIELDS},
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_apply_twse_official_values_dry_run_keeps_priority_csv_unchanged(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    _priority_csv(priority_csv)
    before = priority_csv.read_text(encoding="utf-8")

    result = svc.apply_twse_official_values_to_priority_csv(
        priority_csv,
        [
            {"Code": "2330", "Name": "台積電", "PEratio": "22.5", "DividendYield": "1.8", "PBratio": "5.2"},
        ],
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["updated_code_count"] == 1
    assert result["updated_field_count"] == 1
    assert result["updated_codes"] == ["2330"]
    assert result["skipped"][0]["code"] == "6488"
    assert result["skipped"][0]["reason"] == "twse_b_wibbu_missing"
    assert priority_csv.read_text(encoding="utf-8") == before


def test_apply_twse_official_values_apply_updates_only_mapped_fields(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    _priority_csv(priority_csv)

    result = svc.apply_twse_official_values_to_priority_csv(
        priority_csv,
        [
            {"Code": "2330", "Name": "台積電", "PEratio": "22.5", "DividendYield": "1.8", "PBratio": "5.2"},
        ],
        dry_run=False,
    )

    with priority_csv.open(encoding="utf-8", newline="") as f:
        rows = {row["code"]: row for row in csv.DictReader(f)}

    assert result["dry_run"] is False
    assert rows["2330"]["pe"] == "22.5"
    assert rows["2330"]["roe_5y_avg"] == ""
    assert rows["2330"]["fcf_yield"] == ""
    assert rows["6488"]["pe"] == ""
    assert result["unmapped_official_fields"] == ["DividendYield", "PBratio"]


def test_apply_twse_official_values_skips_blank_pe(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    _priority_csv(priority_csv)

    result = svc.apply_twse_official_values_to_priority_csv(
        priority_csv,
        [
            {"Code": "2330", "Name": "台積電", "PEratio": "", "DividendYield": "1.8", "PBratio": "5.2"},
        ],
        dry_run=False,
    )

    assert result["updated_code_count"] == 0
    assert result["skipped"][0] == {"code": "2330", "reason": "twse_pe_missing_or_empty"}


def test_build_twse_bwibbu_report_rows_keeps_unmapped_official_fields():
    rows = svc.build_twse_bwibbu_report_rows(
        [
            {"Code": "2330", "Name": "台積電", "PEratio": "22.5", "DividendYield": "1.8", "PBratio": "5.2"},
            {"Code": "1101", "Name": "台泥", "PEratio": "", "DividendYield": "3.1", "PBratio": "1.4"},
        ],
    )

    assert rows == [
        {
            "code": "2330",
            "name": "台積電",
            "pe": "22.5",
            "dividend_yield": "1.8",
            "pb_ratio": "5.2",
            "source": "twse_openapi_bwibbu_all",
            "skip_reason": "",
        },
        {
            "code": "1101",
            "name": "台泥",
            "pe": "",
            "dividend_yield": "3.1",
            "pb_ratio": "1.4",
            "source": "twse_openapi_bwibbu_all",
            "skip_reason": "twse_pe_missing_or_empty",
        },
    ]


def test_build_twse_monthly_revenue_report_rows_maps_official_yoy_fields():
    rows = svc.build_twse_monthly_revenue_report_rows(
        [
            {
                "資料年月": "11505",
                "公司代號": "2330",
                "公司名稱": "台積電",
                "營業收入-當月營收": "320516000",
                "營業收入-去年同月增減(%)": "39.6",
                "累計營業收入-當月累計營收": "1515233000",
                "累計營業收入-前期比較增減(%)": "42.6",
                "備註": "-",
            },
            {
                "資料年月": "11505",
                "公司代號": "1101",
                "公司名稱": "台泥",
                "營業收入-當月營收": "12612013",
                "營業收入-去年同月增減(%)": "",
                "累計營業收入-當月累計營收": "58084626",
                "累計營業收入-前期比較增減(%)": "-3.63",
                "備註": "尚未公告",
            },
        ],
    )

    assert rows == [
        {
            "code": "2330",
            "name": "台積電",
            "revenue_year_month": "11505",
            "monthly_revenue": "320516000",
            "monthly_revenue_yoy_pct": "39.6",
            "cumulative_revenue": "1515233000",
            "cumulative_revenue_yoy_pct": "42.6",
            "source": "twse_openapi_monthly_revenue_t187ap05_l",
            "note": "-",
            "skip_reason": "",
        },
        {
            "code": "1101",
            "name": "台泥",
            "revenue_year_month": "11505",
            "monthly_revenue": "12612013",
            "monthly_revenue_yoy_pct": "",
            "cumulative_revenue": "58084626",
            "cumulative_revenue_yoy_pct": "-3.63",
            "source": "twse_openapi_monthly_revenue_t187ap05_l",
            "note": "尚未公告",
            "skip_reason": "twse_monthly_revenue_yoy_missing",
        },
    ]


def test_build_tpex_daily_pe_report_rows_maps_official_pe_fields():
    rows = svc.build_tpex_daily_pe_report_rows(
        {
            "date": "20260626",
            "tables": [
                {
                    "fields": ["股票代號", "公司名稱", "本益比", "每股股利", "股利年度", "殖利率(%)", "股價淨值比", "財報年/季"],
                    "data": [
                        ["6488", "環球晶        ", "18.25", "9.00000000", 114, "2.20", "1.55", "115Q1"],
                        ["1569", "濱川          ", "N/A", "0.00000000", 114, "0.00", "2.11", "115Q1"],
                    ],
                }
            ],
        }
    )

    assert rows == [
        {
            "code": "6488",
            "name": "環球晶",
            "pe": "18.25",
            "dividend_per_share": "9.00000000",
            "dividend_year": "114",
            "dividend_yield": "2.20",
            "pb_ratio": "1.55",
            "financial_period": "115Q1",
            "source": "tpex_after_trading_pe_qry_date",
            "source_date": "20260626",
            "skip_reason": "",
        },
        {
            "code": "1569",
            "name": "濱川",
            "pe": "",
            "dividend_per_share": "0.00000000",
            "dividend_year": "114",
            "dividend_yield": "0.00",
            "pb_ratio": "2.11",
            "financial_period": "115Q1",
            "source": "tpex_after_trading_pe_qry_date",
            "source_date": "20260626",
            "skip_reason": "tpex_pe_missing_or_na",
        },
    ]


def test_build_official_profitability_report_rows_normalizes_twse_and_tpex_rows():
    rows = svc.build_official_profitability_report_rows(
        twse_rows=[
            {
                "公司代號": "2330",
                "公司名稱": "台積電",
                "年度": "114",
                "季別": "1",
                "營業利益率(%)": "49.20",
                "稅前純益率(%)": "52.10",
                "稅後純益率(%)": "41.30",
            },
            {
                "公司代號": "1101",
                "公司名稱": "台泥",
                "年度": "114",
                "季別": "1",
                "營業利益率(%)": "",
                "稅前純益率(%)": "8.10",
                "稅後純益率(%)": "6.30",
            },
        ],
        tpex_rows=[
            {
                "公司代號": "6488",
                "公司名稱": "環球晶",
                "年度": "114",
                "季別": "1",
                "營業利益率(%)": "24.50",
                "稅前純益率(%)": "28.60",
                "稅後純益率(%)": "21.40",
            },
        ],
    )

    assert rows == [
        {
            "code": "2330",
            "name": "台積電",
            "year": "114",
            "quarter": "1",
            "operating_margin": "49.20",
            "pre_tax_margin": "52.10",
            "after_tax_margin": "41.30",
            "source": "twse_openapi_profitability_t187ap17_l",
            "skip_reason": "",
        },
        {
            "code": "1101",
            "name": "台泥",
            "year": "114",
            "quarter": "1",
            "operating_margin": "",
            "pre_tax_margin": "8.10",
            "after_tax_margin": "6.30",
            "source": "twse_openapi_profitability_t187ap17_l",
            "skip_reason": "operating_margin_missing",
        },
        {
            "code": "6488",
            "name": "環球晶",
            "year": "114",
            "quarter": "1",
            "operating_margin": "24.50",
            "pre_tax_margin": "28.60",
            "after_tax_margin": "21.40",
            "source": "tpex_openapi_profitability_187ap17_o",
            "skip_reason": "",
        },
    ]


def test_build_official_balance_sheet_report_rows_normalizes_general_industry_rows():
    rows = svc.build_official_balance_sheet_report_rows(
        twse_rows=[
            {
                "公司代號": "2330",
                "公司名稱": "台積電",
                "年度": "115",
                "季別": "1",
                "資產總額": "6930430052.00",
                "負債總額": "2713508871.00",
                "權益總額": "4216921181.00",
            },
            {
                "公司代號": "1101",
                "公司名稱": "台泥",
                "年度": "115",
                "季別": "1",
                "資產總額": "",
                "負債總額": "292869670.00",
                "權益總額": "304745616.00",
            },
        ],
        tpex_rows=[
            {
                "SecuritiesCompanyCode": "6488",
                "CompanyName": "環球晶",
                "年度": "115",
                "季別": "1",
                "資產總計": "223698757.00",
                "負債總計": "93870412.00",
                "權益總計": "129828345.00",
            },
        ],
    )

    assert rows == [
        {
            "code": "2330",
            "name": "台積電",
            "year": "115",
            "quarter": "1",
            "total_assets": "6930430052.00",
            "liabilities": "2713508871.00",
            "equity": "4216921181.00",
            "source": "twse_openapi_balance_sheet_t187ap07_l_ci",
            "skip_reason": "",
        },
        {
            "code": "1101",
            "name": "台泥",
            "year": "115",
            "quarter": "1",
            "total_assets": "",
            "liabilities": "292869670.00",
            "equity": "304745616.00",
            "source": "twse_openapi_balance_sheet_t187ap07_l_ci",
            "skip_reason": "total_assets_missing",
        },
        {
            "code": "6488",
            "name": "環球晶",
            "year": "115",
            "quarter": "1",
            "total_assets": "223698757.00",
            "liabilities": "93870412.00",
            "equity": "129828345.00",
            "source": "tpex_openapi_balance_sheet_t187ap07_o_ci",
            "skip_reason": "",
        },
    ]


def test_build_official_income_statement_report_rows_normalizes_general_industry_rows():
    rows = svc.build_official_income_statement_report_rows(
        twse_rows=[
            {
                "公司代號": "2330",
                "公司名稱": "台積電",
                "年度": "115",
                "季別": "1",
                "營業收入": "839254000.00",
                "營業利益（損失）": "411716000.00",
                "本期淨利（淨損）": "361560000.00",
                "基本每股盈餘（元）": "13.94",
            },
            {
                "公司代號": "1101",
                "公司名稱": "台泥",
                "年度": "115",
                "季別": "1",
                "營業收入": "",
                "營業利益（損失）": "2792191.00",
                "本期淨利（淨損）": "1204739.00",
                "基本每股盈餘（元）": "0.10",
            },
        ],
        tpex_rows=[
            {
                "SecuritiesCompanyCode": "6488",
                "CompanyName": "環球晶",
                "Year": "115",
                "Season": "1",
                "營業收入": "15421032.00",
                "營業利益（損失）": "3370880.00",
                "本期淨利（淨損）": "2586174.00",
                "基本每股盈餘（元）": "5.93",
            },
        ],
    )

    assert rows == [
        {
            "code": "2330",
            "name": "台積電",
            "year": "115",
            "quarter": "1",
            "revenue": "839254000.00",
            "operating_profit": "411716000.00",
            "net_income": "361560000.00",
            "eps": "13.94",
            "source": "twse_openapi_income_statement_t187ap06_l_ci",
            "skip_reason": "",
        },
        {
            "code": "1101",
            "name": "台泥",
            "year": "115",
            "quarter": "1",
            "revenue": "",
            "operating_profit": "2792191.00",
            "net_income": "1204739.00",
            "eps": "0.10",
            "source": "twse_openapi_income_statement_t187ap06_l_ci",
            "skip_reason": "revenue_missing",
        },
        {
            "code": "6488",
            "name": "環球晶",
            "year": "115",
            "quarter": "1",
            "revenue": "15421032.00",
            "operating_profit": "3370880.00",
            "net_income": "2586174.00",
            "eps": "5.93",
            "source": "tpex_openapi_income_statement_t187ap06_o_ci",
            "skip_reason": "",
        },
    ]


def test_build_official_dividend_report_rows_normalizes_twse_and_tpex_rows():
    rows = svc.build_official_dividend_report_rows(
        twse_rows=[
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
            },
            {
                "公司代號": "1101",
                "公司名稱": "台泥",
                "股利年度": "114",
                "股利所屬年(季)度": "年度",
                "期別": "1",
                "股東配發-盈餘分配之現金股利(元/股)": "",
                "股東配發-法定盈餘公積發放之現金(元/股)": "",
                "股東配發-資本公積發放之現金(元/股)": "",
                "股東配發-盈餘轉增資配股(元/股)": "0.0",
                "股東配發-法定盈餘公積轉增資配股(元/股)": "0.0",
                "股東配發-資本公積轉增資配股(元/股)": "0.0",
            },
        ],
        tpex_rows=[
            {
                "公司代號": "6488",
                "公司名稱": "環球晶",
                "股利年度": "114",
                "期別": "1",
                "股東配發內容-盈餘分配之現金股利(元/股)": "1.50000000",
                "股東配發內容-法定盈餘公積、資本公積發放之現金(元/股)": "0.20000000",
                "股東配發內容-盈餘轉增資配股(元/股)": "0.30000000",
                "股東配發內容-法定盈餘公積、資本公積轉增資配股(元/股)": "0.10000000",
            },
        ],
    )

    assert rows == [
        {
            "code": "2330",
            "name": "台積電",
            "dividend_year": "114",
            "period": "年度",
            "cash_dividend": "5.00000000",
            "stock_dividend": "0.50000000",
            "source": "twse_openapi_dividend_t187ap45_l",
            "skip_reason": "",
        },
        {
            "code": "1101",
            "name": "台泥",
            "dividend_year": "114",
            "period": "年度",
            "cash_dividend": "",
            "stock_dividend": "0.0",
            "source": "twse_openapi_dividend_t187ap45_l",
            "skip_reason": "cash_dividend_missing",
        },
        {
            "code": "6488",
            "name": "環球晶",
            "dividend_year": "114",
            "period": "1",
            "cash_dividend": "1.70000000",
            "stock_dividend": "0.40000000",
            "source": "tpex_openapi_dividend_t187ap39_o",
            "skip_reason": "",
        },
    ]
