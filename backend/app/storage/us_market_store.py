"""
us_market_store.py — 美股資料存取層（與台股完全分離）。

- `us_leaders.json`：小型 US universe（追蹤 ticker + 名稱），為 repo 內 curated 檔。
- `ohlcv_us.csv`：美股日 OHLCV，**獨立於台股 `ohlcv.csv`**，由 `scripts/backfill_ohlcv_us.py`
  產生 / 更新（generated，gitignored）。欄位與台股一致：date,code,open,high,low,close,volume。

刻意不動台股任何檔案，避免回歸。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent.parent / "data"
US_LEADERS_PATH = _DATA / "us_leaders.json"
OHLCV_US_PATH = _DATA / "ohlcv_us.csv"

CSV_FIELDS = ["date", "code", "open", "high", "low", "close", "volume"]


def load_us_leaders() -> list[dict]:
    """回傳 [{"code", "name"}, ...]；檔案不存在或損壞時回傳 []。"""
    if not US_LEADERS_PATH.exists():
        return []
    try:
        raw = json.loads(US_LEADERS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    stocks = raw.get("stocks", []) if isinstance(raw, dict) else raw
    out: list[dict] = []
    for item in stocks or []:
        if isinstance(item, dict) and item.get("code"):
            code = str(item["code"]).strip().upper()
            out.append({"code": code, "name": str(item.get("name") or code)})
        elif isinstance(item, str) and item.strip():
            code = item.strip().upper()
            out.append({"code": code, "name": code})
    return out


def load_us_ohlcv() -> dict[str, list[dict]]:
    """讀 ohlcv_us.csv，回傳 {code: [rows...]}（各 code 依日期排序）。無檔回 {}。"""
    if not OHLCV_US_PATH.exists():
        return {}
    by_code: dict[str, list[dict]] = {}
    try:
        with OHLCV_US_PATH.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                code = (row.get("code") or "").strip().upper()
                if not code or not row.get("date"):
                    continue
                by_code.setdefault(code, []).append(row)
    except OSError:
        return {}
    for rows in by_code.values():
        rows.sort(key=lambda r: r["date"])
    return by_code


def merge_write_us_ohlcv(new_rows: list[dict]) -> int:
    """
    合併新資料到 ohlcv_us.csv：以 (code, date) 去重，排序後寫回。
    回傳寫入後的總筆數。不觸碰台股 ohlcv.csv。
    """
    merged: dict[tuple[str, str], dict] = {}

    if OHLCV_US_PATH.exists():
        try:
            with OHLCV_US_PATH.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    key = ((row.get("code") or "").strip().upper(), row.get("date") or "")
                    if key[0] and key[1]:
                        merged[key] = {k: row.get(k, "") for k in CSV_FIELDS}
        except OSError:
            pass

    for row in new_rows:
        code = str(row.get("code") or "").strip().upper()
        date = str(row.get("date") or "")
        if not code or not date:
            continue
        merged[(code, date)] = {k: row.get(k, "") for k in CSV_FIELDS}

    ordered = sorted(merged.values(), key=lambda r: (r["code"], r["date"]))
    OHLCV_US_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OHLCV_US_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(ordered)
    return len(ordered)
