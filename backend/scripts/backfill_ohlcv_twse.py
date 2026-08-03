#!/usr/bin/env python3
"""
backfill_ohlcv_twse.py — 回補 TWSE 上市 / TPEX 上櫃股票日 OHLCV 歷史資料

用法：
    python3 backend/scripts/backfill_ohlcv_twse.py
    python3 backend/scripts/backfill_ohlcv_twse.py --months 12
    python3 backend/scripts/backfill_ohlcv_twse.py --months 6 --leaders data/leaders.json
    python3 backend/scripts/backfill_ohlcv_twse.py --months 12 --out data/ohlcv.csv

說明：
    1. 讀取 leaders.json，遞迴 flatten 取出所有股票代碼
    2. 對每個代碼，每個月份獨立容錯：先向 TWSE 請求；失敗或無資料則 fallback 至 TPEX
    3. 寫入 data/ohlcv.csv（若已存在則 merge，以 (code, date) 去重、排序）

輸出欄位（符合 daily_signals.py 格式）：
    date,code,open,high,low,close,volume
    日期格式：YYYY-MM-DD
"""

import argparse
import csv
import json
import ssl
import sys
import time
from datetime import date, timedelta
from pathlib import Path
import urllib.request
import urllib.error
import urllib.parse

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.storage.atomic_write import atomic_write_csv  # noqa: E402

_SSL_CTX = ssl.create_default_context()
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------------------------
# 常數
# ---------------------------------------------------------------------------

TWSE_API = (
    "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    "?response=json&date={date}&stockNo={code}"
)
TPEX_API = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"
TWSE_INDEX_HIST_API = (
    "https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST"
    "?response=json&date={date}"
)
TWSE_INDEX_VOLUME_API = (
    "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"
    "?response=json&date={date}"
)
TPEX_INDEX_API = "https://www.tpex.org.tw/openapi/v1/tpex_index"
TPEX_INDEX_VOLUME_API = "https://www.tpex.org.tw/openapi/v1/tpex_daily_trading_index"
SLEEP_BETWEEN_REQUESTS = 1.2   # 秒，避免被交易所封鎖
SLEEP_BETWEEN_STOCKS   = 0.5   # 換股票時額外等待
REQUEST_TIMEOUT        = 15    # 每次 HTTP request 逾時（秒）
MAX_RETRIES            = 2     # 每個 request 最多重試次數（不含第一次）
RETRY_SLEEP            = 0.5   # 重試前等待（秒）

CSV_FIELDS = ["date", "code", "open", "high", "low", "close", "volume"]

_BACKEND      = Path(__file__).resolve().parent.parent
_NAMES_PATH   = _BACKEND / "data" / "stock_names.json"
_MARKETS_PATH = _BACKEND / "data" / "stock_markets.json"


# ---------------------------------------------------------------------------
# 月份清單產生
# ---------------------------------------------------------------------------

def _months_to_fetch(
    months_back: int,
    include_current_month: bool = False,
    today: date | None = None,
) -> list[tuple[int, int]]:
    """
    回傳要查詢的 (year, month) 清單，由近到遠，共 months_back 個月。

    include_current_month=False（預設）：
        從「上個月」開始往前算，避免抓到尚未完整的當月資料。
        今天 2026-05-03, months_back=3 → [(2026,4), (2026,3), (2026,2)]

    include_current_month=True：
        從當月開始往前算。
        今天 2026-05-03, months_back=3 → [(2026,5), (2026,4), (2026,3)]
    """
    if today is None:
        today = date.today()

    if include_current_month:
        y, m = today.year, today.month
    else:
        y, m = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)

    result: list[tuple[int, int]] = []
    for _ in range(months_back):
        result.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return result


# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------

class FetchError(Exception):
    """網路 / 解析失敗，已嘗試 MAX_RETRIES 次後放棄。"""


# ---------------------------------------------------------------------------
# HTTP helpers（含 retry）
# ---------------------------------------------------------------------------

def _http_get_json(url: str) -> dict:
    """GET JSON，失敗自動重試，超過次數後 raise FetchError。"""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ohlcv-backfill/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=_SSL_CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_SLEEP)
    raise FetchError(str(last_exc)) from last_exc


def _http_post_json(url: str, body: bytes, headers: dict) -> dict:
    """POST JSON，失敗自動重試，超過次數後 raise FetchError。"""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=_SSL_CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_SLEEP)
    raise FetchError(str(last_exc)) from last_exc


def _roc_date_to_iso(value: str) -> str:
    parts = value.strip().split("/")
    western_year = int(parts[0]) + 1911
    return f"{western_year}-{parts[1]}-{parts[2]}"


def _compact_roc_date_to_iso(value: str) -> str:
    raw = value.strip()
    if len(raw) == 8:
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    if len(raw) == 7:
        western_year = int(raw[:3]) + 1911
        return f"{western_year}-{raw[3:5]}-{raw[5:7]}"
    raise ValueError(f"unsupported compact date: {value}")


def _to_float(value: str) -> float:
    return float(value.replace(",", "").strip())


def _to_int(value: str) -> int:
    return int(value.replace(",", "").strip())


# ---------------------------------------------------------------------------
# stock_names.json
# ---------------------------------------------------------------------------

def _load_names() -> dict[str, str]:
    if not _NAMES_PATH.exists():
        return {}
    try:
        return json.loads(_NAMES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_names(names: dict[str, str]) -> None:
    _NAMES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _NAMES_PATH.write_text(
        json.dumps(names, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_markets() -> dict[str, str]:
    if not _MARKETS_PATH.exists():
        return {}
    try:
        return json.loads(_MARKETS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_markets(markets: dict[str, str]) -> None:
    _MARKETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MARKETS_PATH.write_text(
        json.dumps(markets, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# leaders.json 解析
# ---------------------------------------------------------------------------

def flatten_codes(obj) -> list[str]:
    """遞迴 flatten：dict / list / str 都支援。"""
    codes: list[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            codes.extend(flatten_codes(v))
    elif isinstance(obj, list):
        for item in obj:
            codes.extend(flatten_codes(item))
    elif isinstance(obj, str):
        codes.append(obj.strip())
    return codes


def load_leaders(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    codes = flatten_codes(data)
    seen: set[str] = set()
    unique: list[str] = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


# ---------------------------------------------------------------------------
# TWSE API
# ---------------------------------------------------------------------------

def fetch_month(code: str, year: int, month: int) -> tuple[list[dict], str | None]:
    """
    向 TWSE 請求某月的日 OHLCV。
    回傳 (rows, name)；TWSE 有回應但無資料時 rows 為空。
    網路 / 解析失敗時 raise FetchError（已重試 MAX_RETRIES 次）。
    """
    date_str = f"{year}{month:02d}01"
    url = TWSE_API.format(date=date_str, code=code)

    payload = _http_get_json(url)   # raise FetchError on persistent network failure

    if payload.get("stat") != "OK" or not payload.get("data"):
        return [], None

    # 從 title 提取名稱，格式："114年04月 2330 台積電  各日成交資訊"
    name: str | None = None
    title_parts = payload.get("title", "").split()
    if len(title_parts) >= 3:
        name = title_parts[2]

    rows: list[dict] = []
    for record in payload["data"]:
        if len(record) < 7:
            continue
        roc_date, volume_str, _, open_str, high_str, low_str, close_str = record[:7]

        if "--" in (open_str, high_str, low_str, close_str):
            continue

        try:
            parts = roc_date.strip().split("/")
            western_year = int(parts[0]) + 1911
            iso_date = f"{western_year}-{parts[1]}-{parts[2]}"
        except (ValueError, IndexError):
            continue

        def to_float(s: str) -> float:
            return float(s.replace(",", "").strip())

        try:
            rows.append({
                "date":   iso_date,
                "code":   code,
                "open":   to_float(open_str),
                "high":   to_float(high_str),
                "low":    to_float(low_str),
                "close":  to_float(close_str),
                "volume": int(volume_str.replace(",", "").strip()),
            })
        except ValueError:
            continue

    return rows, name


# ---------------------------------------------------------------------------
# TPEX API
# ---------------------------------------------------------------------------

def _parse_tpex_response(code: str, payload: dict) -> tuple[list[dict], str | None]:
    """
    解析 TPEX POST API 回應（/www/zh-tw/afterTrading/tradingStock）。

    欄位順序：日期, 成交張數, 成交仟元, 開盤, 最高, 最低, 收盤, 漲跌, 筆數
    成交量單位為「張」（1 張 = 1000 股），× 1000 後與 TWSE 單位一致。
    """
    tables = payload.get("tables") or []
    aa_data = (tables[0].get("data") or []) if tables else []
    name: str | None = payload.get("name") or None

    def to_float(s: str) -> float:
        return float(s.replace(",", "").strip())

    rows: list[dict] = []
    for record in aa_data:
        if len(record) < 7:
            continue
        roc_date = record[0]
        volume_lots_str = record[1]
        open_str, high_str, low_str, close_str = record[3], record[4], record[5], record[6]

        if "--" in (open_str, high_str, low_str, close_str):
            continue

        try:
            parts = roc_date.strip().split("/")
            western_year = int(parts[0]) + 1911
            iso_date = f"{western_year}-{parts[1]}-{parts[2]}"
        except (ValueError, IndexError):
            continue

        try:
            rows.append({
                "date":   iso_date,
                "code":   code,
                "open":   to_float(open_str),
                "high":   to_float(high_str),
                "low":    to_float(low_str),
                "close":  to_float(close_str),
                "volume": int(volume_lots_str.replace(",", "").strip()) * 1000,
            })
        except ValueError:
            continue

    return rows, name


def fetch_tpex_month(code: str, year: int, month: int) -> tuple[list[dict], str | None]:
    """
    向 TPEX 請求某月的日 OHLCV（POST）。
    回傳 (rows, name)；TPEX 有回應但無資料時 rows 為空。
    網路 / 解析失敗時 raise FetchError。
    """
    post_body = urllib.parse.urlencode({
        "code": code,
        "date": f"{year}/{month:02d}/01",
        "response": "json",
    }).encode("utf-8")
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ohlcv-backfill/1.0)",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    payload = _http_post_json(TPEX_API, post_body, headers)   # raise FetchError on failure

    if payload.get("stat") != "ok":
        return [], None

    return _parse_tpex_response(code, payload)


# ---------------------------------------------------------------------------
# 市場指數 API（TSE / OTC）
# ---------------------------------------------------------------------------

def _parse_twse_index_month(hist_payload: dict, volume_payload: dict) -> list[dict]:
    """
    合併 TWSE 加權指數 OHLC 與市場成交量。

    OHLC 來源：MI_5MINS_HIST
    成交量來源：FMTQIK 的「成交股數」
    """
    if hist_payload.get("stat") != "OK" or volume_payload.get("stat") != "OK":
        return []

    volume_by_date: dict[str, int] = {}
    for record in volume_payload.get("data") or []:
        if len(record) < 2:
            continue
        try:
            volume_by_date[_roc_date_to_iso(record[0])] = _to_int(record[1])
        except (ValueError, IndexError):
            continue

    rows: list[dict] = []
    for record in hist_payload.get("data") or []:
        if len(record) < 5:
            continue
        try:
            iso_date = _roc_date_to_iso(record[0])
            rows.append({
                "date": iso_date,
                "code": "TSE",
                "open": _to_float(record[1]),
                "high": _to_float(record[2]),
                "low": _to_float(record[3]),
                "close": _to_float(record[4]),
                "volume": volume_by_date.get(iso_date, 0),
            })
        except ValueError:
            continue
    return rows


def fetch_twse_index_month(year: int, month: int) -> list[dict]:
    date_str = f"{year}{month:02d}01"
    hist_payload = _http_get_json(TWSE_INDEX_HIST_API.format(date=date_str))
    volume_payload = _http_get_json(TWSE_INDEX_VOLUME_API.format(date=date_str))
    return _parse_twse_index_month(hist_payload, volume_payload)


def _parse_tpex_index_current(index_payload: list[dict], trading_payload: list[dict]) -> list[dict]:
    """
    合併 TPEX 櫃買指數 OHLC 與成交量。

    OHLC 來源：/openapi/v1/tpex_index
    成交量來源：/openapi/v1/tpex_daily_trading_index 的 TradeVolume
    """
    volume_by_date: dict[str, int] = {}
    for record in trading_payload:
        try:
            volume_by_date[_compact_roc_date_to_iso(str(record.get("Date", "")))] = _to_int(str(record.get("TradeVolume", "0")))
        except ValueError:
            continue

    rows: list[dict] = []
    for record in index_payload:
        try:
            iso_date = _compact_roc_date_to_iso(str(record.get("Date", "")))
            rows.append({
                "date": iso_date,
                "code": "OTC",
                "open": _to_float(str(record.get("Open", ""))),
                "high": _to_float(str(record.get("High", ""))),
                "low": _to_float(str(record.get("Low", ""))),
                "close": _to_float(str(record.get("Close", ""))),
                "volume": volume_by_date.get(iso_date, 0),
            })
        except ValueError:
            continue
    return rows


def fetch_tpex_index_current() -> list[dict]:
    index_payload = _http_get_json(TPEX_INDEX_API)
    trading_payload = _http_get_json(TPEX_INDEX_VOLUME_API)
    if not isinstance(index_payload, list) or not isinstance(trading_payload, list):
        return []
    return _parse_tpex_index_current(index_payload, trading_payload)


def fetch_market_indices(
    months_back: int,
    include_current_month: bool = False,
    _today: date | None = None,
) -> list[dict]:
    rows: list[dict] = []
    targets = _months_to_fetch(months_back, include_current_month, _today)

    for year, month in targets:
        try:
            monthly = fetch_twse_index_month(year, month)
            rows.extend(monthly)
            print(f"  [TSE {year}/{month:02d}] OK，取得 {len(monthly)} 筆")
        except FetchError as exc:
            print(f"  [TSE {year}/{month:02d}] error → skip index month: {exc}")
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    try:
        tpex_rows = fetch_tpex_index_current()
        rows.extend(tpex_rows)
        print(f"  [OTC current] OK，取得 {len(tpex_rows)} 筆")
    except FetchError as exc:
        print(f"  [OTC current] error → skip index: {exc}")

    return rows


# ---------------------------------------------------------------------------
# 主要抓資料邏輯（per-month 獨立容錯 + fallback）
# ---------------------------------------------------------------------------

def fetch_stock(
    code: str,
    months_back: int,
    include_current_month: bool = False,
    _today: date | None = None,
) -> tuple[list[dict], str, str | None]:
    """
    回補某支股票最近 months_back 個月。
    include_current_month=False（預設）：排除當月，從上個月開始。
    每個月份獨立容錯：先嘗試 TWSE；失敗或無資料則 fallback 至 TPEX。
    單月失敗不影響其他月份。
    回傳 (rows, market, name)：market = "TWSE" | "TPEX" | "UNKNOWN"

    Log 規則：
      - TWSE 有資料：不印 per-month（正常路徑）
      - TWSE 無資料（正常 OTC 股票）：不印 per-month，靜默 fallback TPEX
      - TWSE error：印 "[code YY/MM] TWSE error → fallback TPEX"
      - TPEX 成功（在 TWSE error 之後）：印 "[code YY/MM] OK [TPEX]，取得 N 筆"
      - 兩邊都失敗：印 "[code YY/MM] TWSE X, TPEX Y → skip month"
    """
    targets = _months_to_fetch(months_back, include_current_month, _today)
    stock_name: str | None = None
    all_rows: list[dict] = []
    twse_months = 0
    tpex_months = 0

    for year, month in targets:
        tag = f"[{code} {year}/{month:02d}]"

        # --- Try TWSE ---
        twse_rows: list[dict] = []
        twse_name: str | None = None
        twse_error: str | None = None
        try:
            twse_rows, twse_name = fetch_month(code, year, month)
        except FetchError as exc:
            twse_error = str(exc)

        if twse_rows:
            all_rows.extend(twse_rows)
            twse_months += 1
            if twse_name and stock_name is None:
                stock_name = twse_name
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            continue

        # TWSE empty or failed → fallback TPEX
        if twse_error:
            print(f"  {tag} TWSE error → fallback TPEX", flush=True)

        time.sleep(SLEEP_BETWEEN_REQUESTS)

        tpex_rows: list[dict] = []
        tpex_name: str | None = None
        tpex_error: str | None = None
        try:
            tpex_rows, tpex_name = fetch_tpex_month(code, year, month)
        except FetchError as exc:
            tpex_error = str(exc)

        if tpex_rows:
            all_rows.extend(tpex_rows)
            tpex_months += 1
            if tpex_name and stock_name is None:
                stock_name = tpex_name
            if twse_error:
                print(f"  {tag} OK [TPEX]，取得 {len(tpex_rows)} 筆")
        else:
            twse_label = "error" if twse_error else "無資料"
            tpex_label = "error" if tpex_error else "無資料"
            print(f"  {tag} TWSE {twse_label}, TPEX {tpex_label} → skip month")

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    if not all_rows:
        return [], "UNKNOWN", None

    if tpex_months > 0 and tpex_months >= twse_months:
        market = "TPEX"
    elif twse_months > 0:
        market = "TWSE"
    else:
        market = "UNKNOWN"

    return all_rows, market, stock_name


def retry_skipped_stocks(
    skipped_codes: list[str],
    months_back: int,
    include_current_month: bool = False,
) -> dict:
    """
    Retry codes that were skipped by the first pass.

    TWSE can temporarily return an empty / non-OK STOCK_DAY response for a
    small subset of listed symbols while the same month is already available
    for other symbols. A same-run second pass avoids leaving tracked stocks
    partially stale when the endpoint becomes consistent minutes later.
    """
    result = {
        "rows": [],
        "names": {},
        "markets": {},
        "twse_count": 0,
        "tpex_count": 0,
        "skipped": [],
    }
    if not skipped_codes:
        return result

    print()
    print(f"[RETRY] 第一輪跳過 {len(skipped_codes)} 支，進行同次二次修復 ...")

    total = len(skipped_codes)
    for idx, code in enumerate(skipped_codes, start=1):
        print(f"[RETRY {idx:>3}/{total}] {code} ...", flush=True)
        rows, market, name = fetch_stock(code, months_back, include_current_month)

        if not rows:
            print(f"  STILL SKIP（TWSE / TPEX 均無資料）")
            result["skipped"].append(code)
        else:
            label = f"  {name}" if name else ""
            print(f"  RECOVERED [{market}]，取得 {len(rows)} 筆{label}")
            result["rows"].extend(rows)
            if name:
                result["names"][code] = name
            if market in ("TWSE", "TPEX"):
                result["markets"][code] = market
                if market == "TWSE":
                    result["twse_count"] += 1
                else:
                    result["tpex_count"] += 1

        time.sleep(SLEEP_BETWEEN_STOCKS)

    return result


# ---------------------------------------------------------------------------
# CSV 讀寫與 merge
# ---------------------------------------------------------------------------

def load_existing_csv(path: Path) -> dict[tuple[str, str], dict]:
    """載入既有 CSV，以 (code, date) 為 key。"""
    existing: dict[tuple[str, str], dict] = {}
    if not path.exists():
        return existing
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["code"], row["date"])
            existing[key] = row
    return existing


def merge_and_save(path: Path, new_rows: list[dict]) -> tuple[int, int]:
    """
    Merge new_rows 進既有 CSV。
    回傳 (新增筆數, 總筆數)。
    """
    existing = load_existing_csv(path)
    added = 0
    for row in new_rows:
        key = (row["code"], row["date"])
        if key not in existing:
            existing[key] = {k: row[k] for k in CSV_FIELDS}
            added += 1

    sorted_rows = sorted(existing.values(), key=lambda r: (r["code"], r["date"]))

    # 全檔重寫必須原子化：中途被中斷會留下截斷的檔，殘值可能通過下次合併的檢查
    atomic_write_csv(path, CSV_FIELDS, sorted_rows)

    return added, len(sorted_rows)


# ---------------------------------------------------------------------------
# 主程式
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="回補 TWSE 上市 / TPEX 上櫃股票日 OHLCV 至 data/ohlcv.csv"
    )
    parser.add_argument("--months",  type=int,  default=12,                        metavar="N",    help="回補幾個月（預設 12）")
    parser.add_argument("--leaders", type=Path, default=_BACKEND / "data" / "leaders.json", metavar="PATH", help="leaders.json 路徑")
    parser.add_argument("--out",     type=Path, default=_BACKEND / "data" / "ohlcv.csv",    metavar="PATH", help="輸出 CSV 路徑")
    parser.add_argument("--include-current-month", action="store_true", default=False,
                        help="包含當月資料（預設排除，避免抓到未完整月份）")
    parser.add_argument("--skip-market-indices", action="store_true", default=False,
                        help="不回補 TSE/OTC 大盤指數資料")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.leaders.exists():
        print(f"[ERROR] 找不到 {args.leaders}，請先建立 leaders.json", file=sys.stderr)
        sys.exit(1)

    codes = load_leaders(args.leaders)
    months_list = _months_to_fetch(args.months, args.include_current_month)
    months_str = ", ".join(f"{y}/{m:02d}" for y, m in months_list)
    current_tag = "（含當月）" if args.include_current_month else "（排除當月）"

    print(f"[INFO] 從 {args.leaders} 讀到 {len(codes)} 支股票：{', '.join(codes)}")
    print(f"[INFO] 回補 {args.months} 個月{current_tag}（timeout={REQUEST_TIMEOUT}s, retry={MAX_RETRIES}）")
    print(f"[INFO] 查詢月份：{months_str}")
    print(f"[INFO] 輸出至 {args.out}")
    print()

    twse_count = 0
    tpex_count = 0
    skipped: list[str] = []
    all_new_rows: list[dict] = []
    names_collected: dict[str, str] = {}
    markets_collected: dict[str, str] = {}   # code → "TWSE" | "TPEX"
    total_codes = len(codes)

    for idx, code in enumerate(codes, start=1):
        print(f"[{idx:>3}/{total_codes}] {code} ...", flush=True)
        rows, market, name = fetch_stock(code, args.months, args.include_current_month)

        if not rows:
            print(f"  SKIP（TWSE / TPEX 均無資料）")
            skipped.append(code)
        else:
            label = f"  {name}" if name else ""
            print(f"  OK [{market}]，取得 {len(rows)} 筆{label}")
            all_new_rows.extend(rows)
            if name:
                names_collected[code] = name
            if market in ("TWSE", "TPEX"):
                markets_collected[code] = market
                if market == "TWSE":
                    twse_count += 1
                else:
                    tpex_count += 1

        time.sleep(SLEEP_BETWEEN_STOCKS)

    if skipped:
        retry_result = retry_skipped_stocks(skipped, args.months, args.include_current_month)
        skipped = retry_result["skipped"]
        all_new_rows.extend(retry_result["rows"])
        names_collected.update(retry_result["names"])
        markets_collected.update(retry_result["markets"])
        twse_count += retry_result["twse_count"]
        tpex_count += retry_result["tpex_count"]

    if not args.skip_market_indices:
        print()
        print("[INDEX] 回補市場指數 TSE / OTC ...")
        index_rows = fetch_market_indices(args.months, args.include_current_month)
        if index_rows:
            all_new_rows.extend(index_rows)
            names_collected.update({"TSE": "加權指數", "OTC": "櫃買指數"})
            markets_collected.update({"TSE": "TWSE", "OTC": "TPEX"})
        else:
            print("  SKIP（市場指數無資料）")

    # --- 寫入 CSV ---
    print()
    added, total = merge_and_save(args.out, all_new_rows)
    print(f"[INFO] 已寫入 {args.out}：新增 {added} 筆，總計 {total} 筆")

    # --- 更新股票名稱 ---
    if names_collected:
        existing_names = _load_names()
        existing_names.update(names_collected)
        _save_names(existing_names)
        print(f"[INFO] 已更新 {_NAMES_PATH}：本次新增/更新 {len(names_collected)} 支名稱")

    # --- 更新股票市場（TWSE / TPEX）---
    if markets_collected:
        existing_markets = _load_markets()
        existing_markets.update(markets_collected)
        _save_markets(existing_markets)
        print(f"[INFO] 已更新 {_MARKETS_PATH}：本次新增/更新 {len(markets_collected)} 支市場資訊")

    print(f"[INFO] 市場分佈：TWSE {twse_count} 支 / TPEX {tpex_count} 支 / 跳過 {len(skipped)} 支")

    if skipped:
        print()
        print(f"[SKIP] 以下 {len(skipped)} 支股票 TWSE / TPEX 均無資料：")
        for c in skipped:
            print(f"       - {c}")

    print()
    print("[DONE]")


if __name__ == "__main__":
    main()
