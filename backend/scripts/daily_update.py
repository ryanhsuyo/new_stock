#!/usr/bin/env python3
"""
daily_update.py — 每日收盤後資料更新入口。

此 script 是日常操作用的薄包裝：
  1. 回補最近 N 個月 OHLCV（含當月）
  2. 更新輔助籌碼資料
  3. 重算 summary.json / universe_report.csv
  4. 寫入 update_status.json / update.log / daily_check.json

底層流程沿用 update_all_data.run_update_job，避免維護兩套更新邏輯。
"""

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
sys.path.insert(0, str(_HERE))

from update_all_data import _DEFAULT_LOG, run_update_job  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="每日收盤後更新 OHLCV + 籌碼 + 訊號，並寫入 backend/out/"
    )
    parser.add_argument(
        "--months",
        type=int,
        default=1,
        metavar="N",
        help="回補幾個月（預設 1；初次建資料可用 12）",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=str(_DEFAULT_LOG),
        metavar="PATH",
        help="log 輸出路徑（預設 backend/out/update.log，傳 'none' 停用）",
    )
    parser.add_argument(
        "--no-lock",
        action="store_true",
        help="略過 PID 並發保護（測試用）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_log = args.log_file.strip()
    log_file: Path | None = None if raw_log.lower() == "none" else Path(raw_log)
    exit_code = run_update_job(
        months=args.months,
        log_file=log_file,
        skip_lock=args.no_lock,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
