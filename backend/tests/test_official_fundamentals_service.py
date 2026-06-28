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
