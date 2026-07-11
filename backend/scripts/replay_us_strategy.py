#!/usr/bin/env python3
"""
replay_us_strategy.py — us_trend_follow 歷史逐日回放（evaluation-only）。

用法：
    cd backend
    python3.11 scripts/replay_us_strategy.py                       # 預設 2026-06-15..2026-06-30
    python3.11 scripts/replay_us_strategy.py --start 2026-06-15 --end 2026-06-30

行為：
    - 讀既有 backend/data/ohlcv_us.csv（不重新抓資料、不打網路）。
    - walk-forward 回放（見 us_strategy_replay_service），比較兩套 evaluation-only
      退出規則（candidate_exit / trend_protect_exit）。
    - 輸出 backend/out/us_strategy_replay_<start>_<end>.json / .csv（gitignored）。
    - **非推薦、非買賣建議、不下單、不改 production 策略規則。**
"""

import argparse
import csv
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # backend/scripts/
_BACKEND = _HERE.parent                          # backend/
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.us_strategy_replay_service import run_replay  # noqa: E402

OUT_DIR = _BACKEND / "out"

CSV_FIELDS = [
    "exit_rule", "code", "category", "signal_date", "entry_date", "entry_price",
    "exit_date", "exit_price", "exit_reason", "holding_trading_days",
    "return_pct", "mfe_pct", "mae_pct", "market_bias_at_entry",
    "entry_reasons", "unresolved",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="us_trend_follow walk-forward 回放（evaluation-only）")
    parser.add_argument("--start", default="2026-06-15", help="訊號區間起日（YYYY-MM-DD）")
    parser.add_argument("--end", default="2026-06-30", help="訊號區間迄日（YYYY-MM-DD）")
    args = parser.parse_args()

    result = run_replay(args.start, args.end)
    if not result["snapshots"]:
        print(f"[ERROR] 訊號區間 {args.start}..{args.end} 無任何交易日資料（ohlcv_us.csv 未涵蓋？）",
              file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"us_strategy_replay_{args.start}_{args.end}"
    json_path = OUT_DIR / f"{stem}.json"
    csv_path = OUT_DIR / f"{stem}.csv"

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for rule, trades in result["trades"].items():
            for t in trades:
                row = {k: t.get(k, "") for k in CSV_FIELDS}
                row["exit_rule"] = rule
                row["entry_reasons"] = " | ".join(t.get("entry_reasons") or [])
                writer.writerow(row)

    print(f"[WRITE] {json_path}")
    print(f"[WRITE] {csv_path}")
    print(f"\n訊號區間 {args.start}..{args.end}（{len(result['snapshots'])} 個交易日），"
          f"資料最後日 {result['config']['data_last_date']}")
    churn = result["candidate_churn"]
    print(f"candidate churn：新增 {churn['daily_added']}、移除 {churn['daily_removed']}、"
          f"有變動天數 {churn['days_with_change']}/{churn['snapshot_days']}")
    for rule, s in result["summary"].items():
        print(f"\n=== {rule} ===")
        for k, v in s.items():
            print(f"  {k}: {v}")
    print("\n[NOTE] evaluation-only：非推薦、非買賣建議、不下單；限制見 JSON limitations。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
