#!/usr/bin/env python3
"""檢查 fundamentals.json 對 leaders 股票清單的覆蓋率。"""

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

from app.services.fundamental_service import (  # noqa: E402
    build_fundamentals_status,
    write_fundamentals_report,
    write_priority_fill_csv,
)
from app.storage.fundamental_store import format_csv_validation_error  # noqa: E402
from scripts.backfill_ohlcv_twse import load_leaders  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="檢查基本面避雷 fundamentals.json 缺哪些股票與欄位"
    )
    parser.add_argument(
        "--leaders",
        type=Path,
        default=_BACKEND / "data" / "leaders.json",
        help="股票清單 JSON（預設 backend/data/leaders.json）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="輸出完整 JSON 報告",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="寫出 backend/out/fundamentals_report.json",
    )
    parser.add_argument(
        "--write-priority-csv",
        action="store_true",
        help="寫出 backend/out/fundamentals_priority_fill.csv（舊補資料工作檔；外部匯入優先使用 prepare_fundamentals_priority_import.py --write-template）",
    )
    parser.add_argument(
        "--priority-limit",
        type=int,
        default=20,
        help="優先補資料 CSV 輸出幾檔（預設 20）",
    )
    return parser.parse_args()


def _print_validation_summary(label: str, validation: dict | None) -> None:
    if validation is None:
        print(f"  {label:<13}: 尚未產生")
        return

    print(
        f"  {label:<13}: "
        f"valid={validation['valid']} "
        f"rows={validation['row_count']} "
        f"filled_codes={validation['filled_code_count']} "
        f"filled_fields={validation['filled_field_count']}"
    )
    if not validation["valid"]:
        print(f"    {format_csv_validation_error(validation, label=label)}")


def _format_first_priority_issue(validation: dict | None) -> str | None:
    if not validation:
        return None
    errors = validation.get("errors") or []
    warnings = validation.get("warnings") or []
    issue = errors[0] if errors else (warnings[0] if warnings else None)
    if not issue:
        return None
    kind = "錯誤" if errors else "警告"
    row = issue.get("row_number")
    code = issue.get("code") or "未填代碼"
    field = issue.get("field") or "欄位"
    value = issue.get("value")
    message = issue.get("message") or "請確認格式"
    return f"{kind}：第 {row} 列 {code} {field}={value!r}，{message}"


def _print_priority_workflow_summary(report: dict) -> None:
    readiness = report.get("priority_fill_readiness") or {}
    guide = report.get("priority_fill_guide") or {}
    validation = report.get("priority_csv_validation") or {}
    status = readiness.get("status") or "unknown"
    next_action = guide.get("next_action_label") or readiness.get("suggested_action") or "先產生 priority CSV"
    errors = validation.get("errors") or []
    warnings = validation.get("warnings") or []

    print(f"  priority 狀態 : {status}")
    print(f"  下一步        : {next_action}")
    print(f"  錯誤 / 警告   : {len(errors)} / {len(warnings)}")
    first_issue = _format_first_priority_issue(validation)
    if first_issue:
        print(f"    {first_issue}")


def _build_report_after_requested_writes(args: argparse.Namespace, codes: list[str]) -> dict:
    report = build_fundamentals_status(codes)

    if args.write_priority_csv:
        path = write_priority_fill_csv(limit=args.priority_limit)
        print(f"已寫出 {path}", file=sys.stderr)
        report = build_fundamentals_status(codes)
    if args.write_report:
        path = write_fundamentals_report()
        print(f"已寫出 {path}", file=sys.stderr)
        report = build_fundamentals_status(codes)

    return report


def main() -> None:
    args = parse_args()
    codes = load_leaders(args.leaders)
    report = _build_report_after_requested_writes(args, codes)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("fundamentals 覆蓋率")
    print(f"  股票總數    : {report['total_codes']}")
    print(f"  完整可評分  : {report['complete_count']}")
    print(f"  欄位未補齊  : {report['incomplete_count']}")
    print(f"  整檔缺資料  : {report['missing_count']}")
    _print_validation_summary("正式 CSV", report.get("fundamentals_csv_validation"))
    _print_validation_summary("priority CSV", report.get("priority_csv_validation"))
    _print_priority_workflow_summary(report)

    if report["missing_codes"]:
        preview = ", ".join(report["missing_codes"][:20])
        print(f"  缺資料股票  : {preview}")

    if report["incomplete"]:
        print("  欄位未補齊：")
        for code, fields in list(report["incomplete"].items())[:20]:
            print(f"    {code}: {', '.join(fields)}")


if __name__ == "__main__":
    main()
