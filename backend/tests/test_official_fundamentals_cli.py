import json
import csv
import subprocess
import sys
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
_SCRIPT = _BACKEND / "scripts" / "update_fundamentals_official.py"


def _write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_update_fundamentals_official_help_exits_0():
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        cwd=_BACKEND,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "官方基本面" in result.stdout


def test_update_fundamentals_official_with_fixture_dry_run(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values,"
        "roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,"
        "debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years\n"
        "2330,台積電,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    fixture = tmp_path / "bwibbu.json"
    fixture.write_text(
        json.dumps([{"Code": "2330", "Name": "台積電", "PEratio": "22.5", "DividendYield": "1.8", "PBratio": "5.2"}]),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--priority-csv",
            str(priority_csv),
            "--fixture",
            str(fixture),
        ],
        cwd=_BACKEND,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "官方基本面 priority 更新 dry-run" in result.stdout
    assert "更新檔數 / 欄位: 1 / 1" in result.stdout
    assert "2330" in result.stdout
    assert "22.5" not in priority_csv.read_text(encoding="utf-8")


def test_update_fundamentals_official_writes_reference_report_from_fixture(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values,"
        "roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,"
        "debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years\n"
        "2330,台積電,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    fixture = tmp_path / "bwibbu.json"
    fixture.write_text(
        json.dumps([{"Code": "2330", "Name": "台積電", "PEratio": "22.5", "DividendYield": "1.8", "PBratio": "5.2"}]),
        encoding="utf-8",
    )
    report_csv = tmp_path / "official_report.csv"

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--priority-csv",
            str(priority_csv),
            "--fixture",
            str(fixture),
            "--write-report",
            str(report_csv),
        ],
        cwd=_BACKEND,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "官方暫存報告" in result.stdout
    with report_csv.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows == [
        {
            "code": "2330",
            "name": "台積電",
            "pe": "22.5",
            "dividend_yield": "1.8",
            "pb_ratio": "5.2",
            "source": "twse_openapi_bwibbu_all",
            "skip_reason": "",
        }
    ]


def test_update_fundamentals_official_writes_monthly_revenue_report_from_fixture(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values,"
        "roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,"
        "debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years\n"
        "2330,台積電,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    bwibbu_fixture = tmp_path / "bwibbu.json"
    bwibbu_fixture.write_text(
        json.dumps([{"Code": "2330", "Name": "台積電", "PEratio": "22.5"}]),
        encoding="utf-8",
    )
    monthly_fixture = tmp_path / "monthly_revenue.json"
    monthly_fixture.write_text(
        json.dumps(
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
                }
            ]
        ),
        encoding="utf-8",
    )
    monthly_report = tmp_path / "official_monthly_revenue.csv"

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--priority-csv",
            str(priority_csv),
            "--fixture",
            str(bwibbu_fixture),
            "--monthly-revenue-fixture",
            str(monthly_fixture),
            "--write-monthly-revenue-report",
            str(monthly_report),
        ],
        cwd=_BACKEND,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "月營收暫存報告" in result.stdout
    with monthly_report.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
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
        }
    ]


def test_update_fundamentals_official_writes_tpex_daily_pe_report_from_fixture(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values,"
        "roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,"
        "debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years\n"
        "6488,環球晶,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    bwibbu_fixture = tmp_path / "bwibbu.json"
    bwibbu_fixture.write_text(json.dumps([]), encoding="utf-8")
    tpex_fixture = tmp_path / "tpex_pe.json"
    tpex_fixture.write_text(
        json.dumps(
            {
                "date": "20260626",
                "stat": "ok",
                "tables": [
                    {
                        "fields": ["股票代號", "公司名稱", "本益比", "每股股利", "股利年度", "殖利率(%)", "股價淨值比", "財報年/季"],
                        "data": [["6488", "環球晶        ", "18.25", "9.00000000", 114, "2.20", "1.55", "115Q1"]],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report_csv = tmp_path / "official_tpex_pe.csv"

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--priority-csv",
            str(priority_csv),
            "--fixture",
            str(bwibbu_fixture),
            "--tpex-daily-pe-fixture",
            str(tpex_fixture),
            "--write-tpex-daily-pe-report",
            str(report_csv),
        ],
        cwd=_BACKEND,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "TPEx PE暫存報告" in result.stdout
    with report_csv.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
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
        }
    ]


def test_update_fundamentals_official_apply_uses_tpex_pe_fixture(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values,"
        "roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,"
        "debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years\n"
        "6488,環球晶,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    bwibbu_fixture = tmp_path / "bwibbu.json"
    bwibbu_fixture.write_text(json.dumps([]), encoding="utf-8")
    tpex_fixture = tmp_path / "tpex_pe.json"
    tpex_fixture.write_text(
        json.dumps(
            {
                "date": "20260626",
                "stat": "ok",
                "tables": [
                    {
                        "fields": ["股票代號", "公司名稱", "本益比", "每股股利", "股利年度", "殖利率(%)", "股價淨值比", "財報年/季"],
                        "data": [["6488", "環球晶        ", "18.25", "9.00000000", 114, "2.20", "1.55", "115Q1"]],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--priority-csv",
            str(priority_csv),
            "--fixture",
            str(bwibbu_fixture),
            "--tpex-daily-pe-fixture",
            str(tpex_fixture),
            "--apply",
        ],
        cwd=_BACKEND,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "官方基本面 priority 更新 apply" in result.stdout
    assert "更新檔數 / 欄位: 1 / 1" in result.stdout
    with priority_csv.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["pe"] == "18.25"
    assert rows[0]["roe_5y_avg"] == ""
    assert rows[0]["fcf_yield"] == ""


def test_update_fundamentals_official_writes_profitability_report_from_fixtures(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values,"
        "roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,"
        "debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years\n"
        "2330,台積電,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    bwibbu_fixture = tmp_path / "bwibbu.json"
    bwibbu_fixture.write_text(json.dumps([]), encoding="utf-8")
    twse_profitability_fixture = tmp_path / "twse_profitability.json"
    twse_profitability_fixture.write_text(
        json.dumps(
            [
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
        ),
        encoding="utf-8",
    )
    tpex_profitability_fixture = tmp_path / "tpex_profitability.json"
    tpex_profitability_fixture.write_text(
        json.dumps(
            [
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
        ),
        encoding="utf-8",
    )
    report_csv = tmp_path / "official_profitability.csv"

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--priority-csv",
            str(priority_csv),
            "--fixture",
            str(bwibbu_fixture),
            "--twse-profitability-fixture",
            str(twse_profitability_fixture),
            "--tpex-profitability-fixture",
            str(tpex_profitability_fixture),
            "--write-profitability-report",
            str(report_csv),
        ],
        cwd=_BACKEND,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "營益分析暫存報告" in result.stdout
    assert "49.20" not in priority_csv.read_text(encoding="utf-8")
    with report_csv.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
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


def test_update_fundamentals_official_writes_balance_sheet_report_from_fixtures(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values,"
        "roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,"
        "debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years\n"
        "2330,台積電,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    bwibbu_fixture = tmp_path / "bwibbu.json"
    bwibbu_fixture.write_text(json.dumps([]), encoding="utf-8")
    twse_balance_sheet_fixture = tmp_path / "twse_balance_sheet.json"
    twse_balance_sheet_fixture.write_text(
        json.dumps(
            [
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
        ),
        encoding="utf-8",
    )
    tpex_balance_sheet_fixture = tmp_path / "tpex_balance_sheet.json"
    tpex_balance_sheet_fixture.write_text(
        json.dumps(
            [
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
        ),
        encoding="utf-8",
    )
    report_csv = tmp_path / "official_balance_sheet.csv"

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--priority-csv",
            str(priority_csv),
            "--fixture",
            str(bwibbu_fixture),
            "--twse-balance-sheet-fixture",
            str(twse_balance_sheet_fixture),
            "--tpex-balance-sheet-fixture",
            str(tpex_balance_sheet_fixture),
            "--write-balance-sheet-report",
            str(report_csv),
        ],
        cwd=_BACKEND,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "資產負債表暫存報告" in result.stdout
    assert "6930430052.00" not in priority_csv.read_text(encoding="utf-8")
    with report_csv.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
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


def test_update_fundamentals_official_writes_income_statement_report_from_fixtures(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values,"
        "roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,"
        "debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years\n"
        "2330,台積電,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    bwibbu_fixture = tmp_path / "bwibbu.json"
    bwibbu_fixture.write_text(json.dumps([]), encoding="utf-8")
    twse_income_statement_fixture = tmp_path / "twse_income_statement.json"
    twse_income_statement_fixture.write_text(
        json.dumps(
            [
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
        ),
        encoding="utf-8",
    )
    tpex_income_statement_fixture = tmp_path / "tpex_income_statement.json"
    tpex_income_statement_fixture.write_text(
        json.dumps(
            [
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
        ),
        encoding="utf-8",
    )
    report_csv = tmp_path / "official_income_statement.csv"

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--priority-csv",
            str(priority_csv),
            "--fixture",
            str(bwibbu_fixture),
            "--twse-income-statement-fixture",
            str(twse_income_statement_fixture),
            "--tpex-income-statement-fixture",
            str(tpex_income_statement_fixture),
            "--write-income-statement-report",
            str(report_csv),
        ],
        cwd=_BACKEND,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "損益表暫存報告" in result.stdout
    assert "839254000.00" not in priority_csv.read_text(encoding="utf-8")
    with report_csv.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
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


def test_update_fundamentals_official_writes_dividend_report_from_fixtures(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values,"
        "roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,"
        "debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years\n"
        "2330,台積電,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    bwibbu_fixture = tmp_path / "bwibbu.json"
    bwibbu_fixture.write_text(json.dumps([]), encoding="utf-8")
    twse_dividend_fixture = tmp_path / "twse_dividend.json"
    twse_dividend_fixture.write_text(
        json.dumps(
            [
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
        ),
        encoding="utf-8",
    )
    tpex_dividend_fixture = tmp_path / "tpex_dividend.json"
    tpex_dividend_fixture.write_text(
        json.dumps(
            [
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
        ),
        encoding="utf-8",
    )
    report_csv = tmp_path / "official_dividend.csv"

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--priority-csv",
            str(priority_csv),
            "--fixture",
            str(bwibbu_fixture),
            "--twse-dividend-fixture",
            str(twse_dividend_fixture),
            "--tpex-dividend-fixture",
            str(tpex_dividend_fixture),
            "--write-dividend-report",
            str(report_csv),
        ],
        cwd=_BACKEND,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "股利分派暫存報告" in result.stdout
    assert "5.00000000" not in priority_csv.read_text(encoding="utf-8")
    with report_csv.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
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


def test_update_fundamentals_official_writes_coverage_audit_without_network_or_priority_mutation(tmp_path):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values,"
        "roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,"
        "debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years\n"
        "2330,台積電,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n"
        "6488,環球晶,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    _write_csv(
        report_dir / "official_fundamentals_twse_bwibbu.csv",
        ["code", "name", "pe", "source", "skip_reason"],
        [{"code": "2330", "name": "台積電", "pe": "22.5", "source": "twse", "skip_reason": ""}],
    )
    _write_csv(
        report_dir / "official_fundamentals_income_statement.csv",
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
    audit_json = tmp_path / "official_coverage_audit.json"

    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--priority-csv",
            str(priority_csv),
            "--official-report-dir",
            str(report_dir),
            "--write-coverage-audit",
            str(audit_json),
        ],
        cwd=_BACKEND,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "官方覆蓋率稽核" in result.stdout
    assert "839254000.00" not in priority_csv.read_text(encoding="utf-8")
    audit = json.loads(audit_json.read_text(encoding="utf-8"))
    assert audit["target_count"] == 2
    assert audit["reports"]["twse_bwibbu"]["available_count"] == 1
    assert audit["reports"]["income_statement"]["available_count"] == 2
    assert audit["reports"]["dividend"]["status"] == "missing_file"
