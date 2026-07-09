"""
price_source.py — 各 region 的行情資料來源 adapter 介面（scaffold）。

目的：確立「不同市場的行情從哪裡來」的統一 seam，讓之後接美股（Finnhub 等）與
逐步收斂台股流程時有一致介面，而**本輪不改動已驗證的台股抓取行為**。

- 介面：`PriceSource`（region / label / is_available / fetch_ohlcv）。
- 台股 `TwsePriceSource`：資料由既有 `scripts/backfill_ohlcv_twse.py` 的 TWSE/TPEX
  流程產生；本 adapter 為 seam，**本輪不接管抓取**（scripts 非 package，也刻意不
  將既有流程路由進來，以免改變行為）。`is_available()` 為 True 代表台股資料流可用。
- 美股 `UsPriceSourceStub`：stub，尚未接真資料；`fetch_ohlcv` 會丟
  `PriceSourceUnavailable`，需先設定 Finnhub（或其他來源）API key 才能實作。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.services.markets import SUPPORTED_MARKETS


class PriceSourceError(RuntimeError):
    """行情來源相關錯誤基底。"""


class PriceSourceUnavailable(PriceSourceError):
    """來源尚未就緒（例如美股尚未接、缺 API key）。"""


@runtime_checkable
class PriceSource(Protocol):
    region: str
    label: str

    def is_available(self) -> bool: ...

    def fetch_ohlcv(self, code: str, months: int = 12) -> list[dict]: ...


class TwsePriceSource:
    """台股來源 seam：資料由既有 backfill pipeline 產生，adapter 尚未接管抓取。"""

    region = "TW"
    label = "TWSE/TPEX（既有 backfill pipeline）"
    entrypoint = "scripts/backfill_ohlcv_twse.py"

    def is_available(self) -> bool:
        return True

    def fetch_ohlcv(self, code: str, months: int = 12) -> list[dict]:
        raise PriceSourceError(
            "台股 OHLCV 由既有 scripts/backfill_ohlcv_twse.py 流程負責；"
            "adapter 本輪為 seam，尚未接管抓取（不改既有行為）。"
        )


class UsPriceSourceStub:
    """美股來源 stub：尚未接真資料，需 Finnhub（或其他來源）API key。"""

    region = "US"
    label = "US（stub，未接真資料）"

    def is_available(self) -> bool:
        return False

    def fetch_ohlcv(self, code: str, months: int = 12) -> list[dict]:
        raise PriceSourceUnavailable(
            "美股行情來源尚未實作；需先設定 Finnhub（或其他來源）API key。"
        )


_REGISTRY: dict[str, PriceSource] = {
    "TW": TwsePriceSource(),
    "US": UsPriceSourceStub(),
}


def get_price_source(region: str) -> PriceSource:
    """取得指定 region 的行情來源 adapter；未知 region 丟 PriceSourceError。"""
    src = _REGISTRY.get(region)
    if src is None:
        raise PriceSourceError(
            f"未知的 region：{region!r}（支援：{list(SUPPORTED_MARKETS)}）"
        )
    return src


def available_regions() -> list[str]:
    """目前已接真資料流、可用的 region 清單（scaffold 期間只有 TW）。"""
    return [region for region, src in _REGISTRY.items() if src.is_available()]
