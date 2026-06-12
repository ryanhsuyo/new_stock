"""
market_store.py — stock_markets.json 的讀寫層

stock_markets.json 格式：{"code": "exchange", ...}
  exchange: "TWSE" | "TPEX"
  - 由 backfill_ohlcv_twse.py 在 backfill 結束後寫入
  - 由 signals_service.get_universe_report_json() 讀取，補充 market/exchange 欄位

market（API 對外欄位）與 exchange 的差異：
  code 以 "0" 開頭（台灣 ETF 均如此）→ market = "ETF"，exchange 仍為 "TWSE"
  其餘 exchange = "TWSE" → market = "TWSE"
  exchange = "TPEX" → market = "TPEX"
  exchange 未知 → 以代碼前綴推斷（近似）
"""

import json
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent.parent / "data"
MARKETS_PATH = _DATA / "stock_markets.json"


def load_stock_markets() -> dict[str, str]:
    """載入 stock_markets.json，回傳 {code: exchange} dict；不存在或損壞時回傳 {}。"""
    if not MARKETS_PATH.exists():
        return {}
    try:
        return json.loads(MARKETS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_stock_markets(markets: dict[str, str]) -> None:
    """寫入 stock_markets.json（按 code 排序）。"""
    _DATA.mkdir(parents=True, exist_ok=True)
    MARKETS_PATH.write_text(
        json.dumps(markets, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def derive_market(code: str, exchange: str | None) -> str:
    """
    從 exchange 推導前端篩選用的 market。

    台灣 ETF 代碼一律以 "0" 開頭（0050 / 0056 / 00878 / 006208 等），
    掛牌交易所為 TWSE，但對外以 "ETF" 分類以利篩選。

    exchange 未知時以代碼前綴做近似推斷（已知例外：3711/3231/3481 為 TWSE；5880 為 TWSE）。
    若 exchange 已存在於 stock_markets.json，則為精確值，heuristic 僅做兜底。

    Returns: "ETF" | "TWSE" | "TPEX" | "UNKNOWN"
    """
    if code.startswith("0"):
        return "ETF"
    if exchange in ("TWSE", "TPEX"):
        return exchange
    # heuristic fallback（exchange 不在 stock_markets.json 時）
    first = code[0] if code else ""
    if first in ("1", "2"):
        return "TWSE"
    if first in ("3", "4", "5", "6", "7", "8", "9"):
        return "TPEX"
    return "UNKNOWN"
