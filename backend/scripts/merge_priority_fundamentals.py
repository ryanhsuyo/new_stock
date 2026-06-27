#!/usr/bin/env python3
"""預覽或合併基本面避雷 priority fundamentals CSV。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

from app.services.fundamental_service import (  # noqa: E402
    merge_priority_fill_csv,
    write_fundamentals_report,
)

_CONFIRM = "MERGE_PRIORITY_FUNDAMENTALS"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="預覽或正式合併 backend/out/fundamentals_priority_fill.csv"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="正式合併 priority CSV 到 fundamentals.csv，並匯入 fundamentals.json",
    )
    parser.add_argument(
        "--confirm",
        default=None,
        help=f"正式合併確認字串，需為 {_CONFIRM}",
    )
    return parser.parse_args(argv)


def _print_result(result: dict) -> None:
    mode = "預覽" if result.get("dry_run") else "正式合併"
    allowed = "可合併" if result.get("merge_allowed") else "不可合併"
    print(f"基本面避雷 priority CSV {mode}")
    print(f"  狀態          : {allowed}")
    print(f"  更新檔數 / 欄位: {result.get('updated_code_count', 0)} / {result.get('updated_field_count', 0)}")
    print(f"  完整 / 部分 / 空白: {len(result.get('complete_codes') or [])} / {len(result.get('partial_codes') or [])} / {len(result.get('empty_codes') or [])}")
    print(f"  警告數        : {result.get('warning_count', 0)}")

    preview = result.get("fundamental_preview") or []
    if preview:
        print("  基本面避雷預覽:")
        for item in preview[:10]:
            code = item.get("code")
            name = item.get("name") or code
            score = item.get("fundamental_score")
            signal = item.get("fundamental_signal") or ""
            print(f"    {code} {name} score={score} {signal}".rstrip())

    if result.get("json_path"):
        print(f"  已更新 JSON   : {result['json_path']}")

    next_action = result.get("next_action_label") or ""
    if result.get("signals_refresh_required"):
        next_action = "python3 scripts/run_signals.py"
    if next_action:
        print(f"  下一步        : {next_action}")


def run_merge(args: argparse.Namespace) -> int:
    try:
        result = merge_priority_fill_csv(
            dry_run=not args.apply,
            confirm=args.confirm,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    _print_result(result)
    if args.apply and result.get("signals_refresh_required"):
        report_path = write_fundamentals_report()
        print(f"  已更新報告    : {report_path}")
        print("  驗收          : 重跑 signals 後，doctor 的基本面避雷覆蓋率應上升。")
    return 0


def main() -> None:
    raise SystemExit(run_merge(parse_args()))


if __name__ == "__main__":
    main()
