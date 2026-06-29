#!/usr/bin/env python3
"""用官方 OpenAPI 安全補 fundamentals priority CSV。

正式 apply 目前只允許 TWSE BWIBBU_ALL 直接對應的 `pe`。
其他官方來源一律先寫 neutral report-only CSV，不硬塞進基本面評分欄位。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.official_fundamentals_service import (  # noqa: E402
    TPEX_BALANCE_SHEET_CI_URL,
    TPEX_DAILY_PE_URL,
    TPEX_DIVIDEND_URL,
    TPEX_INCOME_STATEMENT_CI_URL,
    TPEX_PROFITABILITY_URL,
    TWSE_BALANCE_SHEET_CI_URL,
    TWSE_BWIBBU_URL,
    TWSE_DIVIDEND_URL,
    TWSE_INCOME_STATEMENT_CI_URL,
    TWSE_MONTHLY_REVENUE_URL,
    TWSE_PROFITABILITY_URL,
    apply_twse_official_values_to_priority_csv,
    build_official_balance_sheet_report_rows,
    build_official_dividend_report_rows,
    build_official_income_statement_report_rows,
    build_official_profitability_report_rows,
    build_tpex_daily_pe_report_rows,
    build_twse_bwibbu_report_rows,
    build_twse_monthly_revenue_report_rows,
)
from app.services.official_fundamentals_api_service import (  # noqa: E402
    OFFICIAL_REPORTS,
    build_official_fundamentals_coverage_audit,
)
from app.services.fundamental_service import get_priority_fill_csv_path  # noqa: E402

DEFAULT_OFFICIAL_REPORT_PATH = _BACKEND / "out" / "official_fundamentals_twse_bwibbu.csv"
DEFAULT_MONTHLY_REVENUE_REPORT_PATH = _BACKEND / "out" / "official_fundamentals_twse_monthly_revenue.csv"
DEFAULT_TPEX_DAILY_PE_REPORT_PATH = _BACKEND / "out" / "official_fundamentals_tpex_daily_pe.csv"
DEFAULT_PROFITABILITY_REPORT_PATH = _BACKEND / "out" / "official_fundamentals_profitability.csv"
DEFAULT_BALANCE_SHEET_REPORT_PATH = _BACKEND / "out" / "official_fundamentals_balance_sheet.csv"
DEFAULT_INCOME_STATEMENT_REPORT_PATH = _BACKEND / "out" / "official_fundamentals_income_statement.csv"
DEFAULT_DIVIDEND_REPORT_PATH = _BACKEND / "out" / "official_fundamentals_dividend.csv"
DEFAULT_COVERAGE_AUDIT_PATH = _BACKEND / "out" / "official_fundamentals_coverage_audit.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="官方基本面資料更新 fundamentals priority CSV")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="正式寫入 priority CSV；預設只 dry-run 預覽",
    )
    parser.add_argument(
        "--priority-csv",
        type=Path,
        default=None,
        help="fundamentals_priority_fill.csv 路徑；預設 backend/out/fundamentals_priority_fill.csv",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="測試用 TWSE BWIBBU JSON 檔；提供時不打網路",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="官方 API 請求前節流秒數，預設 1 秒",
    )
    parser.add_argument(
        "--write-report",
        nargs="?",
        const=DEFAULT_OFFICIAL_REPORT_PATH,
        type=Path,
        default=None,
        help="寫出官方暫存報告 CSV；未指定路徑時寫到 backend/out/official_fundamentals_twse_bwibbu.csv",
    )
    parser.add_argument(
        "--monthly-revenue-fixture",
        type=Path,
        default=None,
        help="測試用 TWSE 月營收 JSON 檔；提供時不打月營收網路",
    )
    parser.add_argument(
        "--write-monthly-revenue-report",
        nargs="?",
        const=DEFAULT_MONTHLY_REVENUE_REPORT_PATH,
        type=Path,
        default=None,
        help="寫出 TWSE 官方月營收暫存報告 CSV；未指定路徑時寫到 backend/out/official_fundamentals_twse_monthly_revenue.csv",
    )
    parser.add_argument(
        "--tpex-daily-pe-date",
        default=None,
        help="TPEx PE/PB/殖利率資料日期，格式 YYYY/MM/DD；預設使用 TPEx 端點預設日期",
    )
    parser.add_argument(
        "--tpex-daily-pe-fixture",
        type=Path,
        default=None,
        help="測試用 TPEx PE/PB JSON 檔；提供時不打 TPEx 網路",
    )
    parser.add_argument(
        "--write-tpex-daily-pe-report",
        nargs="?",
        const=DEFAULT_TPEX_DAILY_PE_REPORT_PATH,
        type=Path,
        default=None,
        help="寫出 TPEx 官方 PE/PB/殖利率暫存報告 CSV；未指定路徑時寫到 backend/out/official_fundamentals_tpex_daily_pe.csv",
    )
    parser.add_argument(
        "--twse-profitability-fixture",
        type=Path,
        default=None,
        help="測試用 TWSE 營益分析 JSON 檔；提供時不打 TWSE 營益分析網路",
    )
    parser.add_argument(
        "--tpex-profitability-fixture",
        type=Path,
        default=None,
        help="測試用 TPEx 營益分析 JSON 檔；提供時不打 TPEx 營益分析網路",
    )
    parser.add_argument(
        "--write-profitability-report",
        nargs="?",
        const=DEFAULT_PROFITABILITY_REPORT_PATH,
        type=Path,
        default=None,
        help="寫出 TWSE/TPEx 官方營益分析暫存報告 CSV；未指定路徑時寫到 backend/out/official_fundamentals_profitability.csv",
    )
    parser.add_argument(
        "--twse-balance-sheet-fixture",
        type=Path,
        default=None,
        help="測試用 TWSE 一般業資產負債表 JSON 檔；提供時不打 TWSE 資產負債表網路",
    )
    parser.add_argument(
        "--tpex-balance-sheet-fixture",
        type=Path,
        default=None,
        help="測試用 TPEx 一般業資產負債表 JSON 檔；提供時不打 TPEx 資產負債表網路",
    )
    parser.add_argument(
        "--write-balance-sheet-report",
        nargs="?",
        const=DEFAULT_BALANCE_SHEET_REPORT_PATH,
        type=Path,
        default=None,
        help="寫出 TWSE/TPEx 官方一般業資產負債表暫存報告 CSV；未指定路徑時寫到 backend/out/official_fundamentals_balance_sheet.csv",
    )
    parser.add_argument(
        "--twse-income-statement-fixture",
        type=Path,
        default=None,
        help="測試用 TWSE 一般業損益表 JSON 檔；提供時不打 TWSE 損益表網路",
    )
    parser.add_argument(
        "--tpex-income-statement-fixture",
        type=Path,
        default=None,
        help="測試用 TPEx 一般業損益表 JSON 檔；提供時不打 TPEx 損益表網路",
    )
    parser.add_argument(
        "--write-income-statement-report",
        nargs="?",
        const=DEFAULT_INCOME_STATEMENT_REPORT_PATH,
        type=Path,
        default=None,
        help="寫出 TWSE/TPEx 官方一般業損益表暫存報告 CSV；未指定路徑時寫到 backend/out/official_fundamentals_income_statement.csv",
    )
    parser.add_argument(
        "--twse-dividend-fixture",
        type=Path,
        default=None,
        help="測試用 TWSE 股利分派 JSON 檔；提供時不打 TWSE 股利網路",
    )
    parser.add_argument(
        "--tpex-dividend-fixture",
        type=Path,
        default=None,
        help="測試用 TPEx 股利分派 JSON 檔；提供時不打 TPEx 股利網路",
    )
    parser.add_argument(
        "--write-dividend-report",
        nargs="?",
        const=DEFAULT_DIVIDEND_REPORT_PATH,
        type=Path,
        default=None,
        help="寫出 TWSE/TPEx 官方股利分派暫存報告 CSV；未指定路徑時寫到 backend/out/official_fundamentals_dividend.csv",
    )
    parser.add_argument(
        "--official-report-dir",
        type=Path,
        default=None,
        help="官方 report-only CSV 目錄；覆蓋率稽核測試用，預設 backend/out",
    )
    parser.add_argument(
        "--write-coverage-audit",
        nargs="?",
        const=DEFAULT_COVERAGE_AUDIT_PATH,
        type=Path,
        default=None,
        help="寫出官方 report-only 覆蓋率稽核 JSON；不打網路、不寫 priority CSV",
    )
    return parser.parse_args(argv)


def _load_fixture(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("fixture 必須是 JSON array")
    return [item for item in raw if isinstance(item, dict)]


def _fetch_twse_bwibbu(sleep_seconds: float) -> list[dict[str, Any]]:
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    response = requests.get(TWSE_BWIBBU_URL, timeout=20)
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        raise ValueError("TWSE BWIBBU 回應不是 JSON array")
    return [item for item in raw if isinstance(item, dict)]


def _fetch_twse_monthly_revenue(sleep_seconds: float) -> list[dict[str, Any]]:
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    response = requests.get(TWSE_MONTHLY_REVENUE_URL, timeout=20)
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        raise ValueError("TWSE 月營收回應不是 JSON array")
    return [item for item in raw if isinstance(item, dict)]


def _fetch_twse_profitability(sleep_seconds: float) -> list[dict[str, Any]]:
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    response = requests.get(TWSE_PROFITABILITY_URL, timeout=20)
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        raise ValueError("TWSE 營益分析回應不是 JSON array")
    return [item for item in raw if isinstance(item, dict)]


def _fetch_tpex_profitability(sleep_seconds: float) -> list[dict[str, Any]]:
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    response = requests.get(TPEX_PROFITABILITY_URL, timeout=20)
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        raise ValueError("TPEx 營益分析回應不是 JSON array")
    return [item for item in raw if isinstance(item, dict)]


def _fetch_twse_balance_sheet(sleep_seconds: float) -> list[dict[str, Any]]:
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    response = requests.get(TWSE_BALANCE_SHEET_CI_URL, timeout=20)
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        raise ValueError("TWSE 資產負債表回應不是 JSON array")
    return [item for item in raw if isinstance(item, dict)]


def _fetch_tpex_balance_sheet(sleep_seconds: float) -> list[dict[str, Any]]:
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    response = requests.get(TPEX_BALANCE_SHEET_CI_URL, timeout=20)
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        raise ValueError("TPEx 資產負債表回應不是 JSON array")
    return [item for item in raw if isinstance(item, dict)]


def _fetch_twse_income_statement(sleep_seconds: float) -> list[dict[str, Any]]:
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    response = requests.get(TWSE_INCOME_STATEMENT_CI_URL, timeout=20)
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        raise ValueError("TWSE 損益表回應不是 JSON array")
    return [item for item in raw if isinstance(item, dict)]


def _fetch_tpex_income_statement(sleep_seconds: float) -> list[dict[str, Any]]:
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    response = requests.get(TPEX_INCOME_STATEMENT_CI_URL, timeout=20)
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        raise ValueError("TPEx 損益表回應不是 JSON array")
    return [item for item in raw if isinstance(item, dict)]


def _fetch_twse_dividend(sleep_seconds: float) -> list[dict[str, Any]]:
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    response = requests.get(TWSE_DIVIDEND_URL, timeout=20)
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        raise ValueError("TWSE 股利分派回應不是 JSON array")
    return [item for item in raw if isinstance(item, dict)]


def _fetch_tpex_dividend(sleep_seconds: float) -> list[dict[str, Any]]:
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    response = requests.get(TPEX_DIVIDEND_URL, timeout=20)
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        raise ValueError("TPEx 股利分派回應不是 JSON array")
    return [item for item in raw if isinstance(item, dict)]


def _fetch_tpex_daily_pe(sleep_seconds: float, date: str | None) -> dict[str, Any]:
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    response = requests.post(
        TPEX_DAILY_PE_URL,
        data={"date": date or "", "cate": "", "response": "json"},
        timeout=20,
    )
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, dict):
        raise ValueError("TPEx PE/PB 回應不是 JSON object")
    if raw.get("stat") != "ok":
        raise ValueError("TPEx PE/PB 回應失敗: " + str(raw.get("stat")))
    return raw


def _write_official_report(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = ["code", "name", "pe", "dividend_yield", "pb_ratio", "source", "skip_reason"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_monthly_revenue_report(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "code",
        "name",
        "revenue_year_month",
        "monthly_revenue",
        "monthly_revenue_yoy_pct",
        "cumulative_revenue",
        "cumulative_revenue_yoy_pct",
        "source",
        "note",
        "skip_reason",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_tpex_daily_pe_report(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "code",
        "name",
        "pe",
        "dividend_per_share",
        "dividend_year",
        "dividend_yield",
        "pb_ratio",
        "financial_period",
        "source",
        "source_date",
        "skip_reason",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_profitability_report(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "code",
        "name",
        "year",
        "quarter",
        "operating_margin",
        "pre_tax_margin",
        "after_tax_margin",
        "source",
        "skip_reason",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_balance_sheet_report(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "code",
        "name",
        "year",
        "quarter",
        "total_assets",
        "liabilities",
        "equity",
        "source",
        "skip_reason",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_income_statement_report(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "code",
        "name",
        "year",
        "quarter",
        "revenue",
        "operating_profit",
        "net_income",
        "eps",
        "source",
        "skip_reason",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_dividend_report(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "code",
        "name",
        "dividend_year",
        "period",
        "cash_dividend",
        "stock_dividend",
        "source",
        "skip_reason",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _reports_for_dir(report_dir: Path) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for key, meta in OFFICIAL_REPORTS.items():
        default_name = Path(meta["path"]).name
        reports[key] = {
            **meta,
            "path": report_dir / default_name,
        }
    return reports


def _print_result(result: dict[str, Any]) -> None:
    mode = "apply" if not result.get("dry_run") else "dry-run"
    print(f"官方基本面 priority 更新 {mode}")
    print(f"  來源          : {result.get('source')}")
    print(f"  來源列數      : {result.get('source_row_count', 0)}")
    print(f"  更新檔數 / 欄位: {result.get('updated_code_count', 0)} / {result.get('updated_field_count', 0)}")
    print(f"  更新代碼      : {', '.join(result.get('updated_codes') or []) or '-'}")
    print(f"  略過數        : {result.get('skipped_count', 0)}")
    skipped = result.get("skipped") or []
    if skipped:
        first = skipped[0]
        print(f"  第一筆略過    : {first.get('code')} {first.get('reason')}")
    unmapped = result.get("unmapped_official_fields") or []
    if unmapped:
        print(f"  未映射官方欄位: {', '.join(unmapped)}")
    validation = result.get("validation") or {}
    print(
        "  priority 驗證 : "
        f"valid={validation.get('valid')} "
        f"complete={validation.get('complete_code_count', 0)} "
        f"partial={len(validation.get('partial_codes') or [])}"
    )
    print(f"  下一步        : {result.get('next_action_label')}")


def run_update(args: argparse.Namespace) -> int:
    priority_csv = args.priority_csv or get_priority_fill_csv_path()
    try:
        if args.write_coverage_audit:
            report_dir = args.official_report_dir or (_BACKEND / "out")
            audit = build_official_fundamentals_coverage_audit(
                priority_csv,
                reports=_reports_for_dir(report_dir),
            )
            args.write_coverage_audit.parent.mkdir(parents=True, exist_ok=True)
            args.write_coverage_audit.write_text(
                json.dumps(audit, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(
                "官方覆蓋率稽核: "
                f"{args.write_coverage_audit} "
                f"targets={audit.get('target_count', 0)} "
                f"coverage={audit.get('coverage_pct', 0)}%"
            )
            return 0
        rows = _load_fixture(args.fixture) if args.fixture else _fetch_twse_bwibbu(args.sleep)
        result = apply_twse_official_values_to_priority_csv(
            priority_csv,
            rows,
            dry_run=not args.apply,
        )
        if args.write_report:
            report_rows = build_twse_bwibbu_report_rows(rows)
            _write_official_report(args.write_report, report_rows)
            result["official_report_path"] = str(args.write_report)
        if args.write_monthly_revenue_report:
            monthly_rows = (
                _load_fixture(args.monthly_revenue_fixture)
                if args.monthly_revenue_fixture
                else _fetch_twse_monthly_revenue(args.sleep)
            )
            monthly_report_rows = build_twse_monthly_revenue_report_rows(monthly_rows)
            _write_monthly_revenue_report(args.write_monthly_revenue_report, monthly_report_rows)
            result["monthly_revenue_report_path"] = str(args.write_monthly_revenue_report)
            result["monthly_revenue_report_row_count"] = len(monthly_report_rows)
        if args.write_tpex_daily_pe_report:
            tpex_payload = (
                json.loads(args.tpex_daily_pe_fixture.read_text(encoding="utf-8"))
                if args.tpex_daily_pe_fixture
                else _fetch_tpex_daily_pe(args.sleep, args.tpex_daily_pe_date)
            )
            if not isinstance(tpex_payload, dict):
                raise ValueError("TPEx PE/PB fixture 必須是 JSON object")
            tpex_report_rows = build_tpex_daily_pe_report_rows(tpex_payload)
            _write_tpex_daily_pe_report(args.write_tpex_daily_pe_report, tpex_report_rows)
            result["tpex_daily_pe_report_path"] = str(args.write_tpex_daily_pe_report)
            result["tpex_daily_pe_report_row_count"] = len(tpex_report_rows)
        if args.write_profitability_report:
            twse_profitability_rows = (
                _load_fixture(args.twse_profitability_fixture)
                if args.twse_profitability_fixture
                else _fetch_twse_profitability(args.sleep)
            )
            tpex_profitability_rows = (
                _load_fixture(args.tpex_profitability_fixture)
                if args.tpex_profitability_fixture
                else _fetch_tpex_profitability(args.sleep)
            )
            profitability_report_rows = build_official_profitability_report_rows(
                twse_rows=twse_profitability_rows,
                tpex_rows=tpex_profitability_rows,
            )
            _write_profitability_report(args.write_profitability_report, profitability_report_rows)
            result["profitability_report_path"] = str(args.write_profitability_report)
            result["profitability_report_row_count"] = len(profitability_report_rows)
        if args.write_balance_sheet_report:
            twse_balance_sheet_rows = (
                _load_fixture(args.twse_balance_sheet_fixture)
                if args.twse_balance_sheet_fixture
                else _fetch_twse_balance_sheet(args.sleep)
            )
            tpex_balance_sheet_rows = (
                _load_fixture(args.tpex_balance_sheet_fixture)
                if args.tpex_balance_sheet_fixture
                else _fetch_tpex_balance_sheet(args.sleep)
            )
            balance_sheet_report_rows = build_official_balance_sheet_report_rows(
                twse_rows=twse_balance_sheet_rows,
                tpex_rows=tpex_balance_sheet_rows,
            )
            _write_balance_sheet_report(args.write_balance_sheet_report, balance_sheet_report_rows)
            result["balance_sheet_report_path"] = str(args.write_balance_sheet_report)
            result["balance_sheet_report_row_count"] = len(balance_sheet_report_rows)
        if args.write_income_statement_report:
            twse_income_statement_rows = (
                _load_fixture(args.twse_income_statement_fixture)
                if args.twse_income_statement_fixture
                else _fetch_twse_income_statement(args.sleep)
            )
            tpex_income_statement_rows = (
                _load_fixture(args.tpex_income_statement_fixture)
                if args.tpex_income_statement_fixture
                else _fetch_tpex_income_statement(args.sleep)
            )
            income_statement_report_rows = build_official_income_statement_report_rows(
                twse_rows=twse_income_statement_rows,
                tpex_rows=tpex_income_statement_rows,
            )
            _write_income_statement_report(args.write_income_statement_report, income_statement_report_rows)
            result["income_statement_report_path"] = str(args.write_income_statement_report)
            result["income_statement_report_row_count"] = len(income_statement_report_rows)
        if args.write_dividend_report:
            twse_dividend_rows = (
                _load_fixture(args.twse_dividend_fixture)
                if args.twse_dividend_fixture
                else _fetch_twse_dividend(args.sleep)
            )
            tpex_dividend_rows = (
                _load_fixture(args.tpex_dividend_fixture)
                if args.tpex_dividend_fixture
                else _fetch_tpex_dividend(args.sleep)
            )
            dividend_report_rows = build_official_dividend_report_rows(
                twse_rows=twse_dividend_rows,
                tpex_rows=tpex_dividend_rows,
            )
            _write_dividend_report(args.write_dividend_report, dividend_report_rows)
            result["dividend_report_path"] = str(args.write_dividend_report)
            result["dividend_report_row_count"] = len(dividend_report_rows)
    except (OSError, ValueError, requests.RequestException) as exc:
        print(f"官方基本面更新失敗：{exc}", file=sys.stderr)
        return 1

    _print_result(result)
    if result.get("official_report_path"):
        print(f"  官方暫存報告  : {result.get('official_report_path')}")
    if result.get("monthly_revenue_report_path"):
        print(
            "  月營收暫存報告: "
            f"{result.get('monthly_revenue_report_path')} "
            f"rows={result.get('monthly_revenue_report_row_count', 0)}"
        )
    if result.get("tpex_daily_pe_report_path"):
        print(
            "  TPEx PE暫存報告: "
            f"{result.get('tpex_daily_pe_report_path')} "
            f"rows={result.get('tpex_daily_pe_report_row_count', 0)}"
        )
    if result.get("profitability_report_path"):
        print(
            "  營益分析暫存報告: "
            f"{result.get('profitability_report_path')} "
            f"rows={result.get('profitability_report_row_count', 0)}"
        )
    if result.get("balance_sheet_report_path"):
        print(
            "  資產負債表暫存報告: "
            f"{result.get('balance_sheet_report_path')} "
            f"rows={result.get('balance_sheet_report_row_count', 0)}"
        )
    if result.get("income_statement_report_path"):
        print(
            "  損益表暫存報告: "
            f"{result.get('income_statement_report_path')} "
            f"rows={result.get('income_statement_report_row_count', 0)}"
        )
    if result.get("dividend_report_path"):
        print(
            "  股利分派暫存報告: "
            f"{result.get('dividend_report_path')} "
            f"rows={result.get('dividend_report_row_count', 0)}"
        )
    validation = result.get("validation") or {}
    return 0 if validation.get("valid") else 1


def main() -> None:
    raise SystemExit(run_update(parse_args()))


if __name__ == "__main__":
    main()
