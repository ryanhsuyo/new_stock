#!/usr/bin/env python3
"""今日規則掃描報告：讀取既有 summary / universe_report，輸出 PM 可讀分桶。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.today_scan_service import DEFAULT_SCAN_LIMIT, build_today_scan_report, write_today_scan_report  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="輸出今日規則掃描報告")
    parser.add_argument("--backend", type=Path, default=_BACKEND, help="backend 目錄")
    parser.add_argument("--json", action="store_true", help="輸出 machine-readable JSON")
    parser.add_argument("--write-report", action="store_true", help="寫入 backend/out/today_scan.json")
    parser.add_argument("--limit", type=int, default=DEFAULT_SCAN_LIMIT, help="每個分桶最多輸出幾檔")
    return parser.parse_args(argv)


def _print_items(title: str, items: list[dict[str, Any]]) -> None:
    print(f"\n{title}（{len(items)}）")
    if not items:
        print("  - 無")
        return
    for item in items:
        reason = str(item.get("reason") or "").strip()
        strategy_summary = item.get("strategy_score_summary") if isinstance(item.get("strategy_score_summary"), dict) else {}
        strategy_label = str(strategy_summary.get("summary_label") or "").strip()
        strategy_suffix = f"｜{strategy_label}" if strategy_label else ""
        suffix = f"：{reason}" if reason else ""
        print(f"  - {item.get('code')} {item.get('name')}{strategy_suffix}{suffix}")


def print_today_scan_report(report: dict[str, Any]) -> None:
    market = report.get("market_context") or {}
    data_status = report.get("data_status") or {}
    print(f"資料日：{report.get('as_of') or 'unknown'}")
    print(f"規則版：{report.get('rules_version') or 'unknown'}")
    print(
        "資料狀態："
        f"universe {data_status.get('universe_size') or 0}，"
        f"data_ok {data_status.get('data_ok_count') if data_status.get('data_ok_count') is not None else 'unknown'}，"
        f"data_missing {data_status.get('data_missing_count') if data_status.get('data_missing_count') is not None else 'unknown'}"
    )
    print(
        "大盤濾網："
        f"general={market.get('market_filter') or 'unknown'}，"
        f"old_wang={market.get('old_wang_market_filter') or 'unknown'}"
    )
    for note in report.get("notes") or []:
        print(f"提醒：{note}")

    _print_items("正式可小試", report.get("formal_entries") or [])
    _print_items("老王觀察", report.get("old_wang_candidates") or [])
    _print_items("穩健動能", report.get("steady_momentum_candidates") or [])
    _print_items("風險處理", report.get("risk_items") or [])


def run(args: argparse.Namespace) -> int:
    out_dir = args.backend / "out"
    if args.write_report:
        path = write_today_scan_report(out_dir, limit=args.limit)
        print(f"Wrote {path}")
        return 0

    report = build_today_scan_report(out_dir, limit=args.limit)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_today_scan_report(report)
    return 0


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
