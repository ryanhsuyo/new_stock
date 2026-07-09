#!/usr/bin/env python3
"""
backfill_ohlcv_us.py — 回補美股日 OHLCV 至 backend/data/ohlcv_us.csv（獨立於台股）。

用法：
    cd backend
    export FINNHUB_API_KEY=xxxx          # 不進 git
    python3 scripts/backfill_ohlcv_us.py               # 回補最近 12 個月
    python3 scripts/backfill_ohlcv_us.py --months 1
    python3 scripts/backfill_ohlcv_us.py --quote-only  # 只用免費 quote 端點（單日快照）

行為：
    - 讀 backend/data/us_leaders.json（US universe）。
    - 每檔先試 Finnhub /stock/candle（歷史日 K）；若該端點需付費（403）自動 fallback
      到免費 /quote（單日快照）。可用 --quote-only 強制走 quote。
    - 節流（每檔間 sleep），(code,date) 去重、排序後寫回 ohlcv_us.csv。
    - **不寫台股 ohlcv.csv**；缺 FINNHUB_API_KEY 時給明確錯誤並非 0 退出。
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
    FinnhubPriceSource,
    PriceSourceError,
    PriceSourceRateLimited,
    PriceSourceUnavailable,
)
from app.storage.us_market_store import (  # noqa: E402
    OHLCV_US_PATH,
    load_us_leaders,
    merge_write_us_ohlcv,
)

THROTTLE_SECONDS = 1.2   # Finnhub 免費層約 60 req/min


def main() -> int:
    parser = argparse.ArgumentParser(
        description="回補美股日 OHLCV 至 backend/data/ohlcv_us.csv（Finnhub）"
    )
    parser.add_argument("--months", type=int, default=12, help="回補月數（candle 模式）")
    parser.add_argument(
        "--quote-only",
        action="store_true",
        help="只用免費 /quote 端點（單日快照，適合免費 key）",
    )
    args = parser.parse_args()

    source = FinnhubPriceSource()
    if not source.is_available():
        print(
            "[ERROR] 未設定 FINNHUB_API_KEY。\n"
            "        請先 `export FINNHUB_API_KEY=<你的 key>`（不要寫進 repo）再重跑。",
            file=sys.stderr,
        )
        return 2

    leaders = load_us_leaders()
    if not leaders:
        print("[ERROR] us_leaders.json 為空或不存在。", file=sys.stderr)
        return 2

    all_rows: list[dict] = []
    ok, skipped = 0, 0
    for i, item in enumerate(leaders):
        code = item["code"]
        try:
            rows = _fetch_one(source, code, args.months, args.quote_only)
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
        except (PriceSourceUnavailable, PriceSourceError) as exc:
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


def _fetch_one(source: FinnhubPriceSource, code: str, months: int, quote_only: bool) -> list[dict]:
    if quote_only:
        row = source.fetch_quote(code)
        return [row] if row else []
    try:
        return source.fetch_ohlcv(code, months=months)
    except PriceSourceError as exc:
        # candle 端點需付費（403）→ fallback 到免費 quote 單日快照
        if "403" in str(exc) or "付費" in str(exc):
            row = source.fetch_quote(code)
            return [row] if row else []
        raise


def _existing_count() -> int:
    if not OHLCV_US_PATH.exists():
        return 0
    with OHLCV_US_PATH.open(encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)


if __name__ == "__main__":
    raise SystemExit(main())
