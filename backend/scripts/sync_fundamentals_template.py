#!/usr/bin/env python3
"""依 leaders.json 同步 fundamentals.csv 欄位骨架。"""

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_BACKEND))

from app.storage.fundamental_store import FUNDAMENTALS_CSV_PATH, sync_fundamentals_csv  # noqa: E402
from scripts.backfill_ohlcv_twse import load_leaders  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把 leaders.json 中缺少的股票補進 fundamentals.csv，不覆蓋既有數值"
    )
    parser.add_argument(
        "--leaders",
        type=Path,
        default=_BACKEND / "data" / "leaders.json",
        help="股票清單 JSON（預設 backend/data/leaders.json）",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=FUNDAMENTALS_CSV_PATH,
        help="fundamentals.csv 路徑（預設 backend/data/fundamentals.csv）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    codes = load_leaders(args.leaders)
    result = sync_fundamentals_csv(codes, path=args.csv)

    print(f"已同步 fundamentals.csv -> {args.csv}")
    print(f"  總列數    : {result['total_codes']}")
    print(f"  新增列數  : {result['added_count']}")
    if result["added_codes"]:
        print(f"  新增股票  : {', '.join(result['added_codes'][:30])}")


if __name__ == "__main__":
    main()
