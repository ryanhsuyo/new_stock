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
import re
from pathlib import Path

from app.storage.atomic_write import atomic_write_csv

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_CODE_RE = re.compile(r"[A-Z][A-Z0-9.\-]*")


def _valid_key(key: tuple[str, str]) -> bool:
    """ticker 必須以字母開頭、日期必須是 YYYY-MM-DD；擋掉截斷寫入的殘值。"""
    code, date = key
    return bool(_CODE_RE.fullmatch(code) and _DATE_RE.fullmatch(date))


_DATA = Path(__file__).resolve().parent.parent.parent / "data"
US_LEADERS_PATH = _DATA / "us_leaders.json"
OHLCV_US_PATH = _DATA / "ohlcv_us.csv"

CSV_FIELDS = ["date", "code", "open", "high", "low", "close", "volume"]


def load_us_leaders() -> list[dict]:
    """回傳 [{"code", "name", "category"}, ...]；檔案不存在或損壞時回傳 []。

    `category` 為觀察用分類（如 "Mega-cap Tech"）；缺欄位時回傳 ""。
    """
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
            category = str(item.get("category") or "").strip()
            out.append({"code": code, "name": str(item.get("name") or code), "category": category})
        elif isinstance(item, str) and item.strip():
            code = item.strip().upper()
            out.append({"code": code, "name": code, "category": ""})
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
                    # 只檢查非空不夠：截斷寫入留下的殘值兩欄都非空，會被當成真資料
                    # 一路傳承下去（曾有一筆 code=143.46…／date=7138672 存活數月）
                    if _valid_key(key):
                        merged[key] = {k: row.get(k, "") for k in CSV_FIELDS}
        except OSError:
            pass

    for row in new_rows:
        key = (str(row.get("code") or "").strip().upper(), str(row.get("date") or ""))
        if not _valid_key(key):
            continue
        merged[key] = {k: row.get(k, "") for k in CSV_FIELDS}

    ordered = sorted(merged.values(), key=lambda r: (r["code"], r["date"]))
    atomic_write_csv(OHLCV_US_PATH, CSV_FIELDS, ordered)
    return len(ordered)
