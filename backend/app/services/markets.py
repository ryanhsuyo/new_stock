"""
markets.py — 市場（region）維度 scaffold：TW（台股）/ US（美股）。

這是「國家 / 交易市場」層級的維度，與既有 `stock_markets.json` / `market_store`
的 exchange 欄位（TWSE / TPEX / ETF，三者都屬台股）**不同**；region 是其上一層：

    region = TW ─┬─ exchange = TWSE
                 ├─ exchange = TPEX
                 └─ (ETF 為對外分類，仍屬 TWSE)
    region = US ── (尚未接真資料)

目前美股尚未接資料（見 `price_source.UsPriceSourceStub`）；所有既有台股代碼一律
歸類為 TW，不影響現有台股主流程。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Region = Literal["TW", "US"]

DEFAULT_REGION: Region = "TW"


@dataclass(frozen=True)
class MarketInfo:
    region: Region
    label: str
    timezone: str
    # enabled=True 代表該 region 已接真資料流；US scaffold 期間為 False
    enabled: bool


SUPPORTED_MARKETS: dict[str, MarketInfo] = {
    "TW": MarketInfo("TW", "台股", "Asia/Taipei", True),
    "US": MarketInfo("US", "美股", "America/New_York", False),
}


def classify_region(code: str) -> Region:
    """
    由代碼推斷 region。

    台股代碼為數字（含 0 開頭的 ETF）；美股 ticker 為英文字母。
    目前尚無美股資料，數字代碼一律 TW；純英文字母且長度 1–5 才視為 US
    （scaffold 用；不會被任何既有台股代碼觸發）。
    """
    c = (code or "").strip().upper()
    if c and c.isalpha() and len(c) <= 5:
        return "US"
    return DEFAULT_REGION


def is_market_enabled(region: str) -> bool:
    """該 region 是否已接真資料流（US scaffold 期間為 False）。"""
    info = SUPPORTED_MARKETS.get(region)
    return bool(info and info.enabled)
