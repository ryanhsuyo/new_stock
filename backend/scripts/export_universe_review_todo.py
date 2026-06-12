#!/usr/bin/env python3
"""匯出候選股報表待補復盤 Markdown。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

from app.services.decision_journal_service import write_universe_report_review_markdown  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="依 universe_report.csv 匯出尚未建立 source=universe_report 決策日誌的可行動股票"
    )
    parser.add_argument("--date", default=None, help="資料日 YYYY-MM-DD；預設使用 universe_report 的 data_as_of")
    parser.add_argument("--limit", type=int, default=None, help="最多輸出幾檔；預設輸出全部")
    return parser.parse_args(argv)


def run_export(args: argparse.Namespace) -> int:
    path = write_universe_report_review_markdown(as_of=args.date, limit=args.limit)
    print(f"已匯出候選股復盤待辦：{path}")
    print("提醒：此檔只供人工復盤，不會自動建立決策日誌或修改交易紀錄。")
    return 0


def main() -> None:
    raise SystemExit(run_export(parse_args()))


if __name__ == "__main__":
    main()
