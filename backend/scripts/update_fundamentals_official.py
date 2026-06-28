#!/usr/bin/env python3
"""用官方 OpenAPI 安全補 fundamentals priority CSV。

第一版只使用 TWSE BWIBBU_ALL，並只映射可直接對應的 `pe`。
其餘官方欄位會列在報告裡，不硬塞進基本面評分欄位。
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
    TPEX_DAILY_PE_URL,
    TWSE_BWIBBU_URL,
    TWSE_MONTHLY_REVENUE_URL,
    apply_twse_official_values_to_priority_csv,
    build_tpex_daily_pe_report_rows,
    build_twse_bwibbu_report_rows,
    build_twse_monthly_revenue_report_rows,
)
from app.services.fundamental_service import get_priority_fill_csv_path  # noqa: E402

DEFAULT_OFFICIAL_REPORT_PATH = _BACKEND / "out" / "official_fundamentals_twse_bwibbu.csv"
DEFAULT_MONTHLY_REVENUE_REPORT_PATH = _BACKEND / "out" / "official_fundamentals_twse_monthly_revenue.csv"
DEFAULT_TPEX_DAILY_PE_REPORT_PATH = _BACKEND / "out" / "official_fundamentals_tpex_daily_pe.csv"


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
    validation = result.get("validation") or {}
    return 0 if validation.get("valid") else 1


def main() -> None:
    raise SystemExit(run_update(parse_args()))


if __name__ == "__main__":
    main()
