"""
price_source.py — 各 region 的行情資料來源 adapter。

目的：確立「不同市場的行情從哪裡來」的統一 seam。

- 介面：`PriceSource`（region / label / is_available / fetch_ohlcv）。
- 台股 `TwsePriceSource`：資料由既有 `scripts/backfill_ohlcv_twse.py` 的 TWSE/TPEX
  流程產生；本 adapter 為 seam，**尚未接管抓取**（`fetch_ohlcv` 刻意丟錯），台股
  行為不變。`test_markets_scaffold.py` 對此有斷言，勿順手修掉。
- 美股（US Phase 1 主資料源）`YahooFinancePriceSource`：Yahoo Finance chart endpoint，
  **免 API key、非官方、best-effort**（`is_available()=True`）。無 SLA、可能變動 / 被限流。
- 美股 `StooqPriceSource`：**已停用**（Stooq 改為需瀏覽器 JS 驗證，回 HTML 而非 CSV；
  `is_available()=False`）。**不繞過驗證**；保留類別供歷史 / fallback 參考。
- 美股 optional `FinnhubPriceSource`：官方 API（免金鑰時 `is_available()=False`），
  **不在 US registry**，保留供之後接 quote / 即時 / 基本面（免費層歷史 candle 需付費）。

不新增第三方依賴：HTTP 一律走標準庫 `urllib`（與既有 backfill 一致）。
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable

from app.config import resolve_finnhub_api_key
from app.services.markets import SUPPORTED_MARKETS


class PriceSourceError(RuntimeError):
    """行情來源相關錯誤基底。"""


class PriceSourceUnavailable(PriceSourceError):
    """來源尚未就緒（例如美股未設定 API key）。"""


class PriceSourceRateLimited(PriceSourceError):
    """被資料源限流（HTTP 429）。"""


@runtime_checkable
class PriceSource(Protocol):
    region: str
    label: str

    def is_available(self) -> bool: ...

    def fetch_ohlcv(self, code: str, months: int = 12) -> list[dict]: ...


# ── 台股：既有 backfill pipeline 的 seam（不接管抓取）──────────────────────────

class TwsePriceSource:
    region = "TW"
    label = "TWSE/TPEX（既有 backfill pipeline）"
    entrypoint = "scripts/backfill_ohlcv_twse.py"

    def is_available(self) -> bool:
        return True

    def fetch_ohlcv(self, code: str, months: int = 12) -> list[dict]:
        raise PriceSourceError(
            "台股 OHLCV 由既有 scripts/backfill_ohlcv_twse.py 流程負責；"
            "adapter 為 seam，尚未接管抓取（不改既有行為）。"
        )


# ── 美股：Finnhub ─────────────────────────────────────────────────────────────

_FINNHUB_BASE = "https://finnhub.io/api/v1"
_TIMEOUT = 15

# SSL context：與既有 scripts/backfill_ohlcv_twse.py 一致（certifi 優先，缺則退回不驗證）
_SSL_CTX = ssl.create_default_context()
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode = ssl.CERT_NONE


class FinnhubPriceSource:
    """
    美股行情來源（Finnhub）。

    - 缺 `FINNHUB_API_KEY`：`is_available()=False`，`fetch_ohlcv` / `fetch_quote`
      丟 `PriceSourceUnavailable`（訊息明確），完全不影響台股。
    - `fetch_ohlcv`：GET /stock/candle（日 K）。注意 Finnhub 免費方案已將 candle 列為
      付費端點，免費 key 會得到 403；此時請改用 `fetch_quote`（免費）逐日累積。
    - `fetch_quote`：GET /quote（免費），回傳當前 OHLC 快照。
    """

    region = "US"
    label = "Finnhub（美股）"

    def __init__(self, api_key: str | None = None):
        # 傳入 None 時延後到呼叫當下讀環境變數，讓測試能 monkeypatch
        self._api_key = api_key

    def _key(self) -> str:
        return (self._api_key if self._api_key is not None else resolve_finnhub_api_key())

    def is_available(self) -> bool:
        return bool(self._key())

    def _require_key(self) -> str:
        key = self._key()
        if not key:
            raise PriceSourceUnavailable(
                "美股資料源尚未設定：請設定環境變數 FINNHUB_API_KEY 後再試。"
            )
        return key

    def _get_json(self, path: str, params: dict) -> dict:
        query = urllib.parse.urlencode(params)
        url = f"{_FINNHUB_BASE}{path}?{query}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "new_stock-us-backfill/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_SSL_CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise PriceSourceError("Finnhub API key 無效或未授權（401）。") from exc
            if exc.code == 403:
                raise PriceSourceError(
                    "此 Finnhub 端點需付費方案（403）；免費方案請改用 /quote。"
                ) from exc
            if exc.code == 429:
                raise PriceSourceRateLimited(
                    "Finnhub 限流（429），請稍後再試或降低頻率。"
                ) from exc
            raise PriceSourceError(f"Finnhub HTTP {exc.code}。") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise PriceSourceError(f"連線 Finnhub 失敗：{exc}") from exc
        except json.JSONDecodeError as exc:
            raise PriceSourceError("Finnhub 回應非合法 JSON。") from exc

    def fetch_ohlcv(self, code: str, months: int = 12) -> list[dict]:
        key = self._require_key()
        symbol = code.strip().upper()
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=max(1, months) * 31)
        data = self._get_json(
            "/stock/candle",
            {
                "symbol": symbol,
                "resolution": "D",
                "from": int(start.timestamp()),
                "to": int(now.timestamp()),
                "token": key,
            },
        )
        if data.get("s") != "ok":
            return []
        rows: list[dict] = []
        times = data.get("t", []) or []
        for i, ts in enumerate(times):
            date = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
            rows.append({
                "date":   date,
                "code":   symbol,
                "open":   _num(data.get("o", []), i),
                "high":   _num(data.get("h", []), i),
                "low":    _num(data.get("l", []), i),
                "close":  _num(data.get("c", []), i),
                "volume": _int(data.get("v", []), i),
            })
        return rows

    def fetch_quote(self, code: str) -> dict:
        """免費端點：回傳單日 OHLC 快照（今日日期）。"""
        key = self._require_key()
        symbol = code.strip().upper()
        data = self._get_json("/quote", {"symbol": symbol, "token": key})
        if not data or data.get("c") in (None, 0):
            return {}
        ts = data.get("t") or int(datetime.now(timezone.utc).timestamp())
        date = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        return {
            "date":   date,
            "code":   symbol,
            "open":   float(data.get("o") or data.get("c")),
            "high":   float(data.get("h") or data.get("c")),
            "low":    float(data.get("l") or data.get("c")),
            "close":  float(data.get("c")),
            "volume": 0,
        }


def _num(seq, i) -> float:
    try:
        return float(seq[i])
    except (IndexError, TypeError, ValueError):
        return 0.0


def _int(seq, i) -> int:
    try:
        return int(seq[i])
    except (IndexError, TypeError, ValueError):
        return 0


# ── 美股：Stooq（已停用）─────────────────────────────────────────────────────
# Stooq 已改為需瀏覽器 JS 驗證（回傳 "This site requires JavaScript to verify your
# browser" 的 HTML，而非 CSV），不適合程式化抓取。**不繞過驗證**，直接標記 unavailable。


class StooqPriceSource:
    """Stooq：已停用（需瀏覽器 JS 驗證，無法程式化抓 CSV）。保留類別供歷史 / fallback 參考。"""

    region = "US"
    label = "Stooq（美股，已停用）"

    def is_available(self) -> bool:
        return False

    def fetch_ohlcv(self, code: str, months: int = 12) -> list[dict]:
        raise PriceSourceUnavailable(
            "Stooq 已改為需瀏覽器 JS 驗證，不適合程式化抓取；US 主源已改用 Yahoo Finance。"
        )


# ── 美股 Phase 1 主資料源：Yahoo Finance chart（免 key、非官方、best-effort）─────

_YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"


class YahooFinancePriceSource:
    """
    Yahoo Finance chart endpoint（美股，**免 API key、非官方、best-effort**）。

    - `is_available()=True`（無金鑰門檻）。
    - `fetch_ohlcv`：GET `/v8/finance/chart/{ticker}?interval=1d&period1&period2`，把
      timestamp + indicators.quote 轉成既有 OHLCV 格式；缺值列（null）跳過。
    - 非官方端點、無 SLA：可能變動或被限流；節流、少量 ticker、個人用途。
    """

    region = "US"
    label = "Yahoo Finance（美股，非官方、免 key）"

    def is_available(self) -> bool:
        return True

    def _get_json(self, url: str) -> dict:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; new_stock-us/1.0)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_SSL_CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise PriceSourceRateLimited("Yahoo 限流（429），請稍後再試。") from exc
            raise PriceSourceError(f"Yahoo HTTP {exc.code}。") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise PriceSourceError(f"連線 Yahoo 失敗：{exc}") from exc
        except json.JSONDecodeError as exc:
            raise PriceSourceError("Yahoo 回應非合法 JSON。") from exc

    def fetch_ohlcv(self, code: str, months: int = 12) -> list[dict]:
        symbol = code.strip().upper()
        now = datetime.now(timezone.utc)
        p1 = int((now - timedelta(days=max(1, months) * 31)).timestamp())
        p2 = int(now.timestamp())
        url = f"{_YAHOO_BASE}{symbol}?interval=1d&period1={p1}&period2={p2}"
        data = self._get_json(url)
        return _parse_yahoo_chart(data, symbol)


def _parse_yahoo_chart(data: dict, code: str) -> list[dict]:
    chart = (data or {}).get("chart") or {}
    if chart.get("error"):
        raise PriceSourceError(f"Yahoo 回傳錯誤：{chart['error']}")
    results = chart.get("result") or []
    if not results:
        return []
    res = results[0]
    timestamps = res.get("timestamp") or []
    quote = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    rows: list[dict] = []
    for i, ts in enumerate(timestamps):
        close = _at(closes, i)
        if close is None:            # 缺這天資料（停牌 / null）→ 跳過
            continue
        rows.append({
            "date":   datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
            "code":   code,
            "open":   _at(opens, i) if _at(opens, i) is not None else close,
            "high":   _at(highs, i) if _at(highs, i) is not None else close,
            "low":    _at(lows, i) if _at(lows, i) is not None else close,
            "close":  close,
            "volume": int(_at(volumes, i) or 0),
        })
    return rows


def _at(seq, i) -> float | None:
    try:
        v = seq[i]
        return float(v) if v is not None else None
    except (IndexError, TypeError, ValueError):
        return None


# ── registry ─────────────────────────────────────────────────────────────────
# US 主資料源 = Yahoo Finance（免 key、非官方、best-effort）。
# Stooq 已停用（需瀏覽器 JS 驗證）。Finnhub 保留為 future optional（官方、需 key），皆不註冊為 US 主源。

_REGISTRY: dict[str, PriceSource] = {
    "TW": TwsePriceSource(),
    "US": YahooFinancePriceSource(),
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
    """目前資料源就緒、可用的 region 清單（US 需設定 FINNHUB_API_KEY）。"""
    return [region for region, src in _REGISTRY.items() if src.is_available()]
