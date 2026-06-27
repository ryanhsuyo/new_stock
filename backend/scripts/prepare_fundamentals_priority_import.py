#!/usr/bin/env python3
"""把外部基本面 CSV 正規化填入 priority fundamentals CSV。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

from app.services.fundamental_service import (  # noqa: E402
    prepare_priority_fundamentals_import,
    write_priority_import_template_csv,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="預覽或寫入外部基本面 CSV 到 backend/out/fundamentals_priority_fill.csv"
    )
    parser.add_argument(
        "source_csv",
        type=Path,
        nargs="?",
        help="外部整理好的 CSV，需包含 code / stock_id / 代號 其中一欄",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="正式寫入 priority CSV；預設只 dry-run 預覽",
    )
    parser.add_argument(
        "--write-template",
        action="store_true",
        help="寫出外部資料整理用的空白模板，不匯入任何數字",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="模板列出幾檔優先補資料股票（預設 20）",
    )
    return parser.parse_args(argv)


def _print_result(result: dict) -> None:
    mode = "apply" if not result.get("dry_run") else "dry-run"
    validation = result.get("validation") or {}
    print(f"基本面 priority 匯入 {mode}")
    print(f"  來源列數      : {result.get('source_row_count', 0)}")
    print(f"  更新檔數 / 欄位: {result.get('updated_code_count', 0)} / {result.get('updated_field_count', 0)}")
    print(f"  略過代碼      : {', '.join(result.get('skipped_codes') or []) or '-'}")
    print(f"  priority 驗證 : valid={validation.get('valid')} complete={validation.get('complete_code_count', 0)} partial={len(validation.get('partial_codes') or [])}")

    updated_codes = result.get("updated_codes") or []
    if updated_codes:
        print("  更新代碼      : " + ", ".join(updated_codes[:20]))

    warnings = validation.get("warnings") or []
    if warnings:
        first = warnings[0]
        print(
            "  第一個警告    : "
            f"row {first.get('row_number')} code {first.get('code')} "
            f"field {first.get('field')} {first.get('message')}"
        )

    errors = validation.get("errors") or []
    if errors:
        first = errors[0]
        print(
            "  第一個錯誤    : "
            f"row {first.get('row_number')} code {first.get('code')} "
            f"field {first.get('field')} value {first.get('value')!r} {first.get('message')}"
        )

    next_action = result.get("next_action_label")
    if next_action:
        print(f"  下一步        : {next_action}")


def run_prepare(args: argparse.Namespace) -> int:
    if args.write_template:
        path = write_priority_import_template_csv(limit=args.limit)
        print(f"已寫出外部資料模板：{path}")
        print("下一步：填入真實外部資料後，先 dry-run 匯入 priority CSV。")
        return 0

    if args.source_csv is None:
        print("請提供 source_csv，或使用 --write-template 先產生空白模板。", file=sys.stderr)
        return 1

    try:
        result = prepare_priority_fundamentals_import(
            args.source_csv,
            dry_run=not args.apply,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    _print_result(result)
    return 0 if (result.get("validation") or {}).get("valid") else 1


def main() -> None:
    raise SystemExit(run_prepare(parse_args()))


if __name__ == "__main__":
    main()
