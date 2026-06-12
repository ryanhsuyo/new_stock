#!/usr/bin/env python3
"""
update_chips.py — 更新籌碼摘要到 backend/data/chips.json

資料來源：
- TWSE T86 三大法人買賣超：外資 / 投信，單位轉為「張」
- TDCC 集保戶股權分散表：散戶 / 大戶持股比例，單位為「%」

注意：
- 散戶用「100 張以下」持股比例代理。
- 大戶用「400 張以上」持股比例代理。
- TPEX 三大法人 endpoint 版型較多，第一版先寫入 TWSE 與 TDCC 能穩定取得的資料。
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import time
from datetime import date
from pathlib import Path
from typing import Any

import requests

BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / "data"
OHLCV_PATH = DATA / "ohlcv.csv"
CHIPS_PATH = DATA / "chips.json"
MARKETS_PATH = DATA / "stock_markets.json"

TWSE_T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEX_3I_URLS = [
    "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_download.php",
    "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_result.php",
]
TDCC_URLS = [
    "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5",
    "https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5",
]

# TDCC 持股分級：1-9 約為 100 張以下；12 以上約為 400 張以上。
RETAIL_LEVELS = {str(i) for i in range(1, 10)}
MAJOR_LEVELS = {str(i) for i in range(12, 18)}


def _clean_number(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().replace(",", "")
    if text in {"", "--", "-"}:
        return 0.0
    return float(text)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _latest_ohlcv_date() -> str | None:
    if not OHLCV_PATH.exists():
        return None
    latest: str | None = None
    with OHLCV_PATH.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = row.get("date")
            if d and (latest is None or d > latest):
                latest = d
    return latest


def _fetch_twse_t86(as_of: str, codes: set[str]) -> dict[str, dict]:
    ymd = as_of.replace("-", "")
    params = {
        "date": ymd,
        "selectType": "ALLBUT0999",
        "response": "json",
        "_": str(int(time.time() * 1000)),
    }
    res = requests.get(TWSE_T86_URL, params=params, timeout=20)
    res.raise_for_status()
    payload = res.json()
    fields = payload.get("fields") or []
    rows = payload.get("data") or []
    if not fields or not rows:
        print(f"[TWSE] no data: stat={payload.get('stat')} date={as_of}")
        return {}

    out: dict[str, dict] = {}
    for raw in rows:
        row = dict(zip(fields, raw))
        code = str(row.get("證券代號", "")).strip()
        if code not in codes:
            continue
        foreign_net_shares = _clean_number(row.get("外陸資買賣超股數(不含外資自營商)"))
        trust_net_shares = _clean_number(row.get("投信買賣超股數"))
        out[code] = {
            "data_as_of": as_of,
            "foreign_net_buy": round(foreign_net_shares / 1000, 2),
            "investment_trust_net_buy": round(trust_net_shares / 1000, 2),
        }
    print(f"[TWSE] loaded institutional chips for {len(out)} codes date={as_of}")
    return out


def _roc_date(as_of: str) -> str:
    y, m, d = as_of.split("-")
    return f"{int(y) - 1911}/{m}/{d}"


def _first_value(row: dict, names: tuple[str, ...]) -> Any:
    for name in names:
        if name in row:
            return row.get(name)
    for key, value in row.items():
        normalized = str(key).replace(" ", "").replace("\ufeff", "")
        for name in names:
            if name.replace(" ", "") in normalized:
                return value
    return None


def _fetch_tpex_3insti(as_of: str, codes: set[str]) -> dict[str, dict]:
    if not codes:
        return {}

    params_variants = [
        {"l": "zh-tw", "d": _roc_date(as_of), "se": "EW", "t": "D"},
        {"l": "zh-tw", "date": _roc_date(as_of), "type": "Daily", "response": "csv"},
    ]
    headers = {"User-Agent": "Mozilla/5.0 new_stock_chip_updater"}
    out: dict[str, dict] = {}

    for url in TPEX_3I_URLS:
        for params in params_variants:
            try:
                res = requests.get(url, params=params, headers=headers, timeout=25)
                res.raise_for_status()
            except requests.RequestException as exc:
                print(f"[TPEX] skip url={url} params={params} error={exc}")
                continue

            text = res.content.decode("utf-8-sig", errors="replace")
            if "證券代號" not in text and "代號" not in text:
                text = res.content.decode("big5", errors="replace")
            if "證券代號" not in text and "代號" not in text:
                continue

            lines = [line for line in text.splitlines() if "," in line]
            header_idx = next(
                (i for i, line in enumerate(lines) if "證券代號" in line or line.startswith("代號")),
                None,
            )
            if header_idx is None:
                continue
            reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
            for row in reader:
                code = str(_first_value(row, ("證券代號", "代號")) or "").strip()
                if code not in codes:
                    continue
                foreign_net = _clean_number(_first_value(row, (
                    "外資及陸資買賣超股數",
                    "外資及陸資買賣超",
                    "外資買賣超股數",
                    "外資買賣超",
                )))
                trust_net = _clean_number(_first_value(row, (
                    "投信買賣超股數",
                    "投信買賣超",
                )))
                # TPEx CSV 常見單位為股；若數值看起來已是張，除以 1000 會過小，因此保守用量級判斷。
                foreign_lots = foreign_net / 1000 if abs(foreign_net) > 100_000 else foreign_net
                trust_lots = trust_net / 1000 if abs(trust_net) > 100_000 else trust_net
                out[code] = {
                    "data_as_of": as_of,
                    "foreign_net_buy": round(foreign_lots, 2),
                    "investment_trust_net_buy": round(trust_lots, 2),
                }
            if out:
                print(f"[TPEX] loaded institutional chips for {len(out)} codes date={as_of}")
                return out

    print(f"[TPEX] no institutional chips loaded date={as_of}")
    return {}


def _fetch_tdcc_holder_distribution(codes: set[str]) -> dict[str, dict]:
    last_error: Exception | None = None
    res = None
    headers = {"User-Agent": "Mozilla/5.0 new_stock_chip_updater"}
    for url in TDCC_URLS:
        try:
            res = requests.get(url, timeout=40, headers=headers, allow_redirects=True)
            res.raise_for_status()
            break
        except requests.RequestException as exc:
            last_error = exc
            res = None
            print(f"[TDCC] skip url={url} error={exc}")
    if res is None:
        print(f"[TDCC] no holder distribution loaded: {last_error}")
        return {}

    text = res.content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    latest_dates: list[str] = []
    by_date_code: dict[str, dict[str, dict[str, float]]] = {}
    for row in reader:
        d = (row.get("資料日期") or "").strip()
        code = (row.get("證券代號") or "").strip()
        level = (row.get("持股分級") or "").strip()
        pct = _clean_number(row.get("占集保庫存數比例%") or row.get("佔集保庫存數比例%"))
        if code not in codes or not d:
            continue
        if d not in by_date_code:
            by_date_code[d] = {}
            latest_dates = sorted(by_date_code.keys())[-2:]
            by_date_code = {k: by_date_code[k] for k in latest_dates}
        item = by_date_code[d].setdefault(code, {"retail": 0.0, "major": 0.0})
        if level in RETAIL_LEVELS:
            item["retail"] += pct
        if level in MAJOR_LEVELS:
            item["major"] += pct

    if not latest_dates:
        print("[TDCC] no matching holder rows")
        return {}

    latest_date = latest_dates[-1]
    previous_date = latest_dates[-2] if len(latest_dates) >= 2 else None
    by_code = by_date_code.get(latest_date, {})
    prev_by_code = by_date_code.get(previous_date, {}) if previous_date else {}

    out: dict[str, dict] = {}
    for code, item in by_code.items():
        prev = prev_by_code.get(code, {})
        retail = round(item["retail"], 2)
        major = round(item["major"], 2)
        out[code] = {
            "holder_data_as_of": latest_date,
            "retail_net_buy": retail,
            "major_investor_net_buy": major,
            "retail_pct_change": round(retail - prev["retail"], 2) if prev else None,
            "major_pct_change": round(major - prev["major"], 2) if prev else None,
        }
    print(f"[TDCC] loaded holder distribution for {len(out)} codes date={latest_date}")
    return out


def update_chips(as_of: str | None = None) -> dict[str, dict]:
    as_of = as_of or _latest_ohlcv_date() or date.today().isoformat()
    markets = _load_json(MARKETS_PATH)
    all_codes = set(markets.keys())
    twse_codes = {code for code, market in markets.items() if market == "TWSE"}
    tpex_codes = {code for code, market in markets.items() if market == "TPEX"}
    if not twse_codes:
        twse_codes = all_codes

    existing = _load_json(CHIPS_PATH)
    chips: dict[str, dict] = {str(code): dict(item) for code, item in existing.items() if isinstance(item, dict)}

    twse = _fetch_twse_t86(as_of, twse_codes)
    time.sleep(0.8)
    tpex = _fetch_tpex_3insti(as_of, tpex_codes)
    time.sleep(0.8)
    tdcc = _fetch_tdcc_holder_distribution(all_codes)

    for code in sorted(all_codes):
        merged = chips.setdefault(code, {})
        if code in twse:
            merged.update(twse[code])
        if code in tpex:
            merged.update(tpex[code])
        if code in tdcc:
            merged.update(tdcc[code])

    DATA.mkdir(parents=True, exist_ok=True)
    CHIPS_PATH.write_text(
        json.dumps(chips, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"[WRITE] {CHIPS_PATH} codes={len(chips)}")
    return chips


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD，預設使用 ohlcv.csv 最新日期")
    args = parser.parse_args()
    update_chips(args.as_of)


if __name__ == "__main__":
    main()
