"""
normalize_trade_names.py — 將 trades.json 內的股票名稱同步為 stock_names.json 的正式名稱。

用途：
  python3 scripts/normalize_trade_names.py

只修正 name 欄位，不改交易日期、價格、股數、note。
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.trade_service import normalize_trade_names
from app.storage.json_store import load_trades, save_trades
from app.storage.name_store import load_stock_names


def main() -> None:
    trades = load_trades()
    names = load_stock_names()

    normalized, changed = normalize_trade_names(trades, names)
    if changed:
        save_trades(normalized)

    print(f"交易名稱正規化完成：總筆數={len(trades)}，修正={changed}")


if __name__ == "__main__":
    main()
