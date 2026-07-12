#!/usr/bin/env python3
"""
replay_us_wbottom.py — W 底突破 + 量幅目標（us_wbottom_target）回放（evaluation-only）。

用法：
    cd backend
    python3.11 scripts/replay_us_wbottom.py                       # 預設 2021-09-01 起
    python3.11 scripts/replay_us_wbottom.py --start 2021-09-01 --end 2026-06-30

行為：
    - 讀既有 backend/data/ohlcv_us.csv（不打網路）。
    - walk-forward 回放（見 us_wbottom_service；參數凍結、不調參；
      偵測邏輯與 production 觀察輸出共用 find_w_breakout，單一規則來源）。
    - 輸出 backend/out/us_wbottom_replay_<start>_<end>.json / .csv（gitignored）。
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

from app.services.us_wbottom_service import run_wbottom_replay  # noqa: E402

OUT_DIR = _BACKEND / "out"
CSV_FIELDS = ["code", "category", "signal_date", "entry_date", "entry_price",
              "target_price", "pattern_low", "exit_date", "exit_price", "exit_reason",
              "holding_trading_days", "return_pct", "unresolved"]


def main() -> int:
    parser = argparse.ArgumentParser(description="us_wbottom_target walk-forward 回放（evaluation-only）")
    parser.add_argument("--start", default="2021-09-01", help="訊號區間起日")
    parser.add_argument("--end", default=None, help="訊號區間迄日（預設資料最後一天）")
    args = parser.parse_args()

    result = run_wbottom_replay(args.start, args.end)
    end = result["config"]["signal_window"][1]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"us_wbottom_replay_{args.start}_{end}"
    (OUT_DIR / f"{stem}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with (OUT_DIR / f"{stem}.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for t in result["trades"]:
            writer.writerow({k: t.get(k, "") for k in CSV_FIELDS})

    print(f"[WRITE] {OUT_DIR / (stem + '.json')}")
    print(f"[WRITE] {OUT_DIR / (stem + '.csv')}")
    print(f"\n=== {result['config']['strategy']} {args.start}..{end} ===")
    for k, v in result["summary"].items():
        print(f"  {k}: {v}")
    print("\n=== 年度 ===")
    for y, st in result["yearly"].items():
        print(f"  {y}: {st}")
    print("[NOTE] evaluation-only：非推薦、非買賣建議、不下單；限制見 JSON limitations。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
