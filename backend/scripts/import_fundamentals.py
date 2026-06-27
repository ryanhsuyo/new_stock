#!/usr/bin/env python3
"""將 backend/data/fundamentals.csv 匯入為 fundamentals.json。"""

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

from app.storage.fundamental_store import (  # noqa: E402
    FUNDAMENTALS_CSV_PATH,
    FUNDAMENTALS_PATH,
    format_csv_validation_error,
    load_fundamentals_from_csv,
    merge_priority_csv_into_fundamentals,
    save_fundamentals,
    validate_fundamentals_csv,
    validate_priority_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="將 fundamentals.csv 轉成基本面避雷使用的 fundamentals.json"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=FUNDAMENTALS_CSV_PATH,
        help="輸入 CSV 路徑（預設 backend/data/fundamentals.csv）",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=FUNDAMENTALS_PATH,
        help="輸出 JSON 路徑（預設 backend/data/fundamentals.json）",
    )
    parser.add_argument(
        "--merge-priority-csv",
        type=Path,
        default=None,
        metavar="PATH",
        help="先將 fundamentals_priority_fill.csv 合併回 fundamentals.csv，再匯入 JSON",
    )
    parser.add_argument(
        "--validate-priority-csv",
        type=Path,
        default=None,
        metavar="PATH",
        help="驗證 fundamentals_priority_fill.csv 格式，不寫入任何檔案",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="搭配 --merge-priority-csv 時只預覽更新數量，不寫回 CSV / JSON",
    )
    return parser.parse_args()


def print_validation_report(report: dict) -> None:
    status = "OK" if report["valid"] else "FAILED"
    print(f"priority CSV 驗證: {status}")
    print(
        f"rows={report['row_count']} "
        f"filled_codes={report['filled_code_count']} "
        f"filled_fields={report['filled_field_count']}"
    )
    if report["duplicate_codes"]:
        print(f"duplicate_codes={','.join(report['duplicate_codes'])}")
    if report["missing_code_rows"]:
        rows = ",".join(str(row) for row in report["missing_code_rows"])
        print(f"missing_code_rows={rows}")
    for error in report["errors"][:20]:
        print(
            "error: "
            f"row={error['row_number']} "
            f"code={error['code']} "
            f"field={error['field']} "
            f"value={error['value']} "
            f"message={error['message']}"
        )


def main() -> None:
    args = parse_args()
    if args.validate_priority_csv:
        report = validate_priority_csv(args.validate_priority_csv)
        print_validation_report(report)
        if not report["valid"]:
            raise SystemExit(1)
        if not args.merge_priority_csv:
            return

    if args.merge_priority_csv:
        try:
            result = merge_priority_csv_into_fundamentals(
                args.merge_priority_csv,
                fundamentals_path=args.csv,
                dry_run=args.dry_run,
            )
        except ValueError as exc:
            print(f"priority CSV 驗證失敗: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        verb = "預計合併" if args.dry_run else "已合併"
        print(
            f"{verb}優先填表 "
            f"{result['updated_code_count']} 檔 / {result['updated_field_count']} 欄位 -> {args.csv}"
        )
        if args.dry_run:
            return
    validation = validate_fundamentals_csv(args.csv)
    if not validation["valid"]:
        print(format_csv_validation_error(validation, label="fundamentals.csv"), file=sys.stderr)
        raise SystemExit(1)

    data = load_fundamentals_from_csv(args.csv)
    save_fundamentals(data, path=args.out)
    print(f"已匯入 {len(data)} 檔基本面資料 -> {args.out}")


if __name__ == "__main__":
    main()
