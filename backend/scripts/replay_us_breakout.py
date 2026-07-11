#!/usr/bin/env python3
"""
replay_us_breakout.py — 老王美股版突破策略回放（evaluation-only）。

用法：
    cd backend
    python3.11 scripts/replay_us_breakout.py                        # 預設 2021-09-01 起
    python3.11 scripts/replay_us_breakout.py --start 2021-09-01 --end 2026-06-30

行為：
    - 讀既有 backend/data/ohlcv_us.csv（不打網路）。
    - walk-forward 回放（見 us_breakout_replay_service；參數凍結、不調參）。
    - 輸出 backend/out/us_breakout_replay_<start>_<end>.json / .csv（gitignored）。
    - **非推薦、非買賣建議、不下單。**
"""

import argparse
import csv
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.us_breakout_replay_service import run_breakout_replay  # noqa: E402

OUT_DIR = _BACKEND / "out"
CSV_FIELDS = ["code", "category", "signal_date", "entry_date", "entry_price",
              "exit_date", "exit_price", "exit_reason", "holding_trading_days",
              "return_pct", "mfe_pct", "mae_pct", "unresolved"]


def main() -> int:
    parser = argparse.ArgumentParser(description="us_wang_breakout walk-forward 回放（evaluation-only）")
    parser.add_argument("--start", default="2021-09-01", help="訊號區間起日")
    parser.add_argument("--end", default=None, help="訊號區間迄日（預設資料最後一天）")
    args = parser.parse_args()

    result = run_breakout_replay(args.start, args.end)
    end = result["config"]["signal_window"][1]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"us_breakout_replay_{args.start}_{end}"
    (OUT_DIR / f"{stem}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT_DIR / f"{stem}.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for t in result["trades"]:
            writer.writerow({k: t.get(k, "") for k in CSV_FIELDS})

    print(f"[WRITE] {OUT_DIR / (stem + '.json')}")
    print(f"[WRITE] {OUT_DIR / (stem + '.csv')}")
    s = result["summary"]
    print(f"\n=== {result['config']['strategy']} {args.start}..{end} ===")
    for k, v in s.items():
        print(f"  {k}: {v}")
    print("\n=== 年度 ===")
    for y, st in result["yearly"].items():
        print(f"  {y}: {st}")
    print(f"\n大盤濾網擋掉訊號：{result['market_filter']['blocked_signals']} 次")
    print("[NOTE] evaluation-only：非推薦、非買賣建議、不下單；限制見 JSON limitations。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
