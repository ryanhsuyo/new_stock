import json
import csv
import subprocess
import sys
from pathlib import Path


_BACKEND = Path(__file__).resolve().parent.parent
_SCRIPT = _BACKEND / "scripts" / "update_fundamentals_official.py"


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
