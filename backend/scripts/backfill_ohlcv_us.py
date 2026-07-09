#!/usr/bin/env python3
"""
backfill_ohlcv_us.py — 回補美股日 OHLCV 至 backend/data/ohlcv_us.csv（獨立於台股）。

用法：
    cd backend
    python3 scripts/backfill_ohlcv_us.py               # 回補最近 12 個月
    python3 scripts/backfill_ohlcv_us.py --months 1

資料源：US Phase 1 主源為 Stooq（免 API key）。腳本走 `get_price_source("US")`，
與資料源實作解耦；之後若換源（例如 Finnhub）此腳本不需改。

行為：
    - 讀 backend/data/us_leaders.json（US universe）。
    - 每檔抓日 OHLCV，節流、(code,date) 去重、排序後寫回 ohlcv_us.csv。
    - **不寫台股 ohlcv.csv**。被限流時停止本次回補並提示稍後再試。
"""

import argparse
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # backend/scripts/
_BACKEND = _HERE.parent                          # backend/
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.price_source import (  # noqa: E402
    PriceSourceError,
    PriceSourceRateLimited,
    get_price_source,
)
from app.storage.us_market_store import (  # noqa: E402
    OHLCV_US_PATH,
    load_us_leaders,
    merge_write_us_ohlcv,
)

THROTTLE_SECONDS = 1.5   # Stooq 非正式來源：節流、少量、避免被擋


def main() -> int:
    parser = argparse.ArgumentParser(
        description="回補美股日 OHLCV 至 backend/data/ohlcv_us.csv（Stooq，免 key）"
    )
    parser.add_argument("--months", type=int, default=12, help="回補月數")
    args = parser.parse_args()

    source = get_price_source("US")
    if not source.is_available():
        print(f"[ERROR] 美股資料源（{getattr(source, 'label', 'US')}）尚未就緒。", file=sys.stderr)
        return 2

    leaders = load_us_leaders()
    if not leaders:
        print("[ERROR] us_leaders.json 為空或不存在。", file=sys.stderr)
        return 2

    print(f"[INFO] 資料源：{getattr(source, 'label', 'US')}；ticker 數：{len(leaders)}")

    all_rows: list[dict] = []
    ok, skipped = 0, 0
    for i, item in enumerate(leaders):
        code = item["code"]
        try:
            rows = source.fetch_ohlcv(code, months=args.months)
            if rows:
                all_rows.extend(rows)
                ok += 1
                print(f"[OK]   {code}: {len(rows)} rows")
            else:
                skipped += 1
                print(f"[SKIP] {code}: no data")
        except PriceSourceRateLimited as exc:
            print(f"[RATE] {code}: {exc} — 停止本次回補，稍後再試。", file=sys.stderr)
            break
        except PriceSourceError as exc:
            skipped += 1
            print(f"[SKIP] {code}: {exc}", file=sys.stderr)
        if i < len(leaders) - 1:
            time.sleep(THROTTLE_SECONDS)

    total = merge_write_us_ohlcv(all_rows) if all_rows else _existing_count()
    print(
        f"\n[WRITE] {OHLCV_US_PATH}  ok={ok} skipped={skipped} "
        f"new_rows={len(all_rows)} total_rows={total}"
    )
    return 0


def _existing_count() -> int:
    if not OHLCV_US_PATH.exists():
        return 0
    with OHLCV_US_PATH.open(encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)


if __name__ == "__main__":
    raise SystemExit(main())
