"""
test_us_market.py — 美股 Phase 1：Finnhub 來源、universe / status 服務、US 端點。

不打真實網路：Finnhub 呼叫一律 monkeypatch `_get_json`。
缺 key 的行為（明確錯誤 / 不可用）也涵蓋，且不使整體測試失敗。
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import us_market_service
from app.services.price_source import (
    FinnhubPriceSource,
    PriceSourceRateLimited,
    PriceSourceUnavailable,
    StooqPriceSource,
)
from app.storage import us_market_store

client = TestClient(app)


# ── Finnhub 來源：缺 key 行為 ─────────────────────────────────────────────────

def test_finnhub_unavailable_and_clear_error_without_key(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    src = FinnhubPriceSource()
    assert src.is_available() is False
    with pytest.raises(PriceSourceUnavailable) as exc:
        src.fetch_ohlcv("AAPL")
    assert "FINNHUB_API_KEY" in str(exc.value)


def test_finnhub_available_with_key():
    src = FinnhubPriceSource(api_key="test-key")
    assert src.is_available() is True


# ── Finnhub 來源：解析與錯誤（mock _get_json）────────────────────────────────

def test_fetch_ohlcv_parses_candles(monkeypatch):
    src = FinnhubPriceSource(api_key="test-key")
    monkeypatch.setattr(src, "_get_json", lambda path, params: {
        "s": "ok",
        "t": [1_700_000_000, 1_700_086_400],
        "o": [10.0, 11.0], "h": [12.0, 13.0], "l": [9.0, 10.5],
        "c": [11.0, 12.5], "v": [1000, 2000],
    })
    rows = src.fetch_ohlcv("AAPL", months=1)
    assert len(rows) == 2
    assert rows[0]["code"] == "AAPL"
    assert set(rows[0]) == {"date", "code", "open", "high", "low", "close", "volume"}
    assert rows[0]["close"] == 11.0 and rows[0]["volume"] == 1000


def test_fetch_ohlcv_no_data_returns_empty(monkeypatch):
    src = FinnhubPriceSource(api_key="test-key")
    monkeypatch.setattr(src, "_get_json", lambda path, params: {"s": "no_data"})
    assert src.fetch_ohlcv("AAPL") == []


def test_fetch_quote_builds_single_row(monkeypatch):
    src = FinnhubPriceSource(api_key="test-key")
    monkeypatch.setattr(src, "_get_json", lambda path, params: {
        "c": 190.5, "h": 191.0, "l": 188.0, "o": 189.0, "pc": 188.5, "t": 1_700_000_000,
    })
    row = src.fetch_quote("AAPL")
    assert row["code"] == "AAPL" and row["close"] == 190.5


def test_rate_limited_type_exists():
    # 型別存在、可被 backfill 捕捉
    assert issubclass(PriceSourceRateLimited, Exception)


# ── Stooq 來源（US Phase 1 主源，免 key；mock _http_get_text）─────────────────

_STOOQ_CSV = (
    "Date,Open,High,Low,Close,Volume\n"
    "2026-07-08,185.00,187.50,184.20,186.10,52000000\n"
    "2026-07-09,186.20,188.00,185.50,187.40,48000000\n"
)


def test_stooq_available_without_key():
    src = StooqPriceSource()
    assert src.region == "US"
    assert src.is_available() is True


def test_stooq_fetch_ohlcv_parses_and_uses_us_suffix(monkeypatch):
    src = StooqPriceSource()
    seen = {}

    def fake_get(url):
        seen["url"] = url
        return _STOOQ_CSV

    monkeypatch.setattr(src, "_http_get_text", fake_get)
    rows = src.fetch_ohlcv("AAPL", months=1)
    assert "s=aapl.us" in seen["url"] and "i=d" in seen["url"]
    assert len(rows) == 2
    assert rows[0]["code"] == "AAPL" and rows[0]["date"] == "2026-07-08"
    assert rows[1]["close"] == 187.4 and rows[1]["volume"] == 48000000
    assert set(rows[0]) == {"date", "code", "open", "high", "low", "close", "volume"}


def test_stooq_no_data_returns_empty(monkeypatch):
    src = StooqPriceSource()
    monkeypatch.setattr(src, "_http_get_text", lambda url: "No data")
    assert src.fetch_ohlcv("ZZZZ") == []


def test_stooq_rate_limit_detected(monkeypatch):
    src = StooqPriceSource()
    monkeypatch.setattr(src, "_http_get_text", lambda url: "Exceeded the daily hits limit")
    with pytest.raises(PriceSourceRateLimited):
        src.fetch_ohlcv("AAPL")


def test_stooq_skips_bad_value_rows(monkeypatch):
    src = StooqPriceSource()
    csv = "Date,Open,High,Low,Close,Volume\n2026-07-08,N/D,N/D,N/D,N/D,N/D\n2026-07-09,1,2,0.5,1.5,10\n"
    monkeypatch.setattr(src, "_http_get_text", lambda url: csv)
    rows = src.fetch_ohlcv("AAPL")
    assert len(rows) == 1 and rows[0]["date"] == "2026-07-09"


# ── us_market_store：合併去重 ─────────────────────────────────────────────────

def test_merge_write_dedupes_code_date(tmp_path, monkeypatch):
    csv_path = tmp_path / "ohlcv_us.csv"
    monkeypatch.setattr(us_market_store, "OHLCV_US_PATH", csv_path)
    rows = [
        {"date": "2026-07-01", "code": "AAPL", "open": 1, "high": 2, "low": 0, "close": 1.5, "volume": 10},
        {"date": "2026-07-01", "code": "AAPL", "open": 9, "high": 9, "low": 9, "close": 9, "volume": 99},  # 覆蓋同 (code,date)
        {"date": "2026-07-02", "code": "AAPL", "open": 2, "high": 3, "low": 1, "close": 2.5, "volume": 20},
    ]
    total = us_market_store.merge_write_us_ohlcv(rows)
    assert total == 2  # 去重後 2 筆
    loaded = us_market_store.load_us_ohlcv()
    assert loaded["AAPL"][0]["close"] == "9"  # 後者覆蓋前者


# ── us_market_service：universe / status ─────────────────────────────────────

def test_us_universe_all_us_region_and_no_data_when_no_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(us_market_store, "OHLCV_US_PATH", tmp_path / "missing.csv")
    universe = us_market_service.get_us_universe()
    assert len(universe) >= 1
    for item in universe:
        assert item["region"] == "US"
        assert item["has_data"] is False
        assert item["data_status"] == "no_data"
        assert item["last_close"] is None


def test_us_status_source_configured_true_via_stooq(tmp_path, monkeypatch):
    # US Phase 1 主源 Stooq 免 key → source_configured 恆為 True
    monkeypatch.setattr(us_market_store, "OHLCV_US_PATH", tmp_path / "missing.csv")
    status = us_market_service.get_us_market_status()
    assert status["region"] == "US"
    assert status["source_configured"] is True
    assert status["source_label"] == "Stooq（美股）"
    assert status["tickers_with_data"] == 0
    assert status["universe_size"] >= 1


# ── HTTP 端點 ─────────────────────────────────────────────────────────────────

def test_us_universe_endpoint_schema():
    res = client.get("/api/markets/us/universe")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    for item in items:
        assert item["region"] == "US"
        for key in ("code", "name", "has_data", "row_count", "last_data_as_of", "last_close", "data_status"):
            assert key in item


def test_us_status_endpoint_schema():
    res = client.get("/api/markets/us/status")
    assert res.status_code == 200
    body = res.json()
    for key in ("region", "source_configured", "universe_size", "tickers_with_data", "last_data_as_of"):
        assert key in body
    assert body["region"] == "US"
