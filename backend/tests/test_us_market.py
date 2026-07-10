"""
test_us_market.py — 美股 Phase 1：Finnhub 來源、universe / status 服務、US 端點。

不打真實網路：Finnhub 呼叫一律 monkeypatch `_get_json`。
缺 key 的行為（明確錯誤 / 不可用）也涵蓋，且不使整體測試失敗。
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import us_market_service
from app.services.price_source import (
    FinnhubPriceSource,
    PriceSourceError,
    PriceSourceRateLimited,
    PriceSourceUnavailable,
    StooqPriceSource,
    YahooFinancePriceSource,
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


# ── Stooq：已停用（需瀏覽器 JS 驗證）─────────────────────────────────────────

def test_stooq_now_unavailable():
    src = StooqPriceSource()
    assert src.region == "US"
    assert src.is_available() is False
    with pytest.raises(PriceSourceUnavailable):
        src.fetch_ohlcv("AAPL")


# ── Yahoo Finance（US 主源，免 key；mock _get_json）──────────────────────────

def _yahoo_chart(ts, o, h, l, c, v):
    return {"chart": {"error": None, "result": [{
        "timestamp": ts,
        "indicators": {"quote": [{"open": o, "high": h, "low": l, "close": c, "volume": v}]},
    }]}}


def test_yahoo_available_without_key():
    src = YahooFinancePriceSource()
    assert src.region == "US"
    assert src.is_available() is True


def test_yahoo_fetch_ohlcv_parses_and_uses_plain_ticker(monkeypatch):
    src = YahooFinancePriceSource()
    seen = {}

    def fake_get(url):
        seen["url"] = url
        return _yahoo_chart(
            [1_700_000_000, 1_700_086_400],
            [10.0, 11.0], [12.0, 13.0], [9.0, 10.5], [11.0, 12.5], [1000, 2000],
        )

    monkeypatch.setattr(src, "_get_json", fake_get)
    rows = src.fetch_ohlcv("AAPL", months=1)
    assert "/chart/AAPL?" in seen["url"] and "interval=1d" in seen["url"]
    assert len(rows) == 2
    assert rows[0]["code"] == "AAPL"
    assert rows[1]["close"] == 12.5 and rows[1]["volume"] == 2000
    assert set(rows[0]) == {"date", "code", "open", "high", "low", "close", "volume"}


def test_yahoo_skips_null_close_rows(monkeypatch):
    src = YahooFinancePriceSource()
    monkeypatch.setattr(src, "_get_json", lambda url: _yahoo_chart(
        [1_700_000_000, 1_700_086_400],
        [10.0, 11.0], [12.0, 13.0], [9.0, 10.5], [None, 12.5], [1000, 2000],
    ))
    rows = src.fetch_ohlcv("AAPL")
    assert len(rows) == 1 and rows[0]["close"] == 12.5


def test_yahoo_empty_result_returns_empty(monkeypatch):
    src = YahooFinancePriceSource()
    monkeypatch.setattr(src, "_get_json", lambda url: {"chart": {"error": None, "result": []}})
    assert src.fetch_ohlcv("AAPL") == []


def test_yahoo_error_raises(monkeypatch):
    src = YahooFinancePriceSource()
    monkeypatch.setattr(src, "_get_json", lambda url: {"chart": {"error": {"code": "Not Found"}, "result": None}})
    with pytest.raises(PriceSourceError):
        src.fetch_ohlcv("ZZZZ")


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


def test_us_status_source_configured_true_via_yahoo(tmp_path, monkeypatch):
    # US 主源 Yahoo 免 key → source_configured 恆為 True
    monkeypatch.setattr(us_market_store, "OHLCV_US_PATH", tmp_path / "missing.csv")
    status = us_market_service.get_us_market_status()
    assert status["region"] == "US"
    assert status["source_configured"] is True
    assert status["source_label"] == "Yahoo Finance（美股，非官方、免 key）"
    assert status["tickers_with_data"] == 0
    assert status["universe_size"] >= 1


def _write_us_ohlcv(path, rows_by_code: dict[str, int]):
    """寫最小 ohlcv_us.csv：{code: n_rows}。價格線性上升即可（本測試只看筆數）。"""
    start = date(2026, 1, 1)
    lines = ["date,code,open,high,low,close,volume"]
    for code, n in rows_by_code.items():
        for i in range(n):
            d = (start + timedelta(days=i)).isoformat()
            px = 100 + i
            lines.append(f"{d},{code},{px},{px + 1},{px - 1},{px},1000")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_us_status_no_data_all_tickers_missing(tmp_path, monkeypatch):
    # ohlcv_us.csv 不存在 → 全部 missing、無 insufficient、min_row_count=None
    monkeypatch.setattr(us_market_store, "OHLCV_US_PATH", tmp_path / "missing.csv")
    status = us_market_service.get_us_market_status()
    assert status["tickers_with_data"] == 0
    assert status["missing_tickers"] == sorted(status["missing_tickers"])
    assert len(status["missing_tickers"]) == status["universe_size"]
    assert status["insufficient_tickers"] == []
    assert status["min_row_count"] is None


def test_us_status_missing_and_insufficient_are_disjoint(tmp_path, monkeypatch):
    # AAPL 充足（>=60）、MSFT 有資料但不足（<60）、其餘完全無資料。
    csv_path = tmp_path / "ohlcv_us.csv"
    _write_us_ohlcv(csv_path, {"AAPL": 65, "MSFT": 30})
    monkeypatch.setattr(us_market_store, "OHLCV_US_PATH", csv_path)

    status = us_market_service.get_us_market_status()
    assert status["tickers_with_data"] == 2
    assert "MSFT" in status["insufficient_tickers"]          # 30 < MIN_SIGNAL_ROWS
    assert "AAPL" not in status["insufficient_tickers"]      # 65 充足
    assert "AAPL" not in status["missing_tickers"]           # 有資料 → 不在 missing
    assert "MSFT" not in status["missing_tickers"]           # 有資料（但不足）→ 不在 missing
    # missing 與 insufficient 不重疊（一個是「沒資料」、一個是「有資料但不足」）
    assert not (set(status["missing_tickers"]) & set(status["insufficient_tickers"]))
    assert status["min_row_count"] == 30                     # 目前有資料 ticker 的最小筆數
    # insufficient 門檻引用 watch signal 常數，非另寫死
    assert us_market_service.MIN_SIGNAL_ROWS == 60


# ── HTTP 端點 ─────────────────────────────────────────────────────────────────

def test_us_universe_endpoint_schema():
    res = client.get("/api/markets/us/universe")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    for item in items:
        assert item["region"] == "US"
        for key in ("code", "name", "category", "has_data", "row_count", "last_data_as_of", "last_close", "data_status"):
            assert key in item


def test_us_universe_expanded_with_categories(tmp_path, monkeypatch):
    # 第一版 universe 擴充：約 20–30 檔、每檔帶觀察用 category（非推薦分類）。
    monkeypatch.setattr(us_market_store, "OHLCV_US_PATH", tmp_path / "missing.csv")
    universe = us_market_service.get_us_universe()
    assert 20 <= len(universe) <= 40
    assert all(isinstance(u.get("category"), str) and u["category"] for u in universe)
    # 分類至少涵蓋 ETF 基準與大型科技（觀察分組）
    cats = {u["category"] for u in universe}
    assert "ETF / Benchmark" in cats
    codes = {u["code"] for u in universe}
    assert {"SPY", "QQQ", "NVDA", "AVGO", "PLTR"}.issubset(codes)


def test_us_status_endpoint_schema():
    res = client.get("/api/markets/us/status")
    assert res.status_code == 200
    body = res.json()
    for key in ("region", "source_configured", "universe_size", "tickers_with_data",
                "missing_tickers", "insufficient_tickers", "min_row_count", "last_data_as_of",
                "expected_trading_day", "days_since_last", "is_stale"):
        assert key in body
    assert body["region"] == "US"
    assert isinstance(body["missing_tickers"], list)
    assert isinstance(body["insufficient_tickers"], list)


# ── 資料新鮮度（compute_us_freshness，固定 today 求確定性）──────────────────────

def _first_monday() -> date:
    d = date(2026, 7, 6)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


def test_freshness_missing_is_stale():
    mon = _first_monday()
    f = us_market_service.compute_us_freshness(None, today=mon)
    assert f["is_stale"] is True
    assert f["days_since_last"] is None
    assert f["expected_trading_day"] == mon.isoformat()


def test_freshness_up_to_date_not_stale():
    mon = _first_monday()
    f = us_market_service.compute_us_freshness(mon.isoformat(), today=mon)
    assert f["days_since_last"] == 0 and f["is_stale"] is False


def test_freshness_one_trading_day_behind_tolerated():
    mon = _first_monday()
    fri = mon - timedelta(days=3)  # 前一交易日（週五，跨週末）
    f = us_market_service.compute_us_freshness(fri.isoformat(), today=mon)
    assert f["days_since_last"] == 1 and f["is_stale"] is False


def test_freshness_two_trading_days_behind_is_stale():
    mon = _first_monday()
    thu = mon - timedelta(days=4)  # 週四
    f = us_market_service.compute_us_freshness(thu.isoformat(), today=mon)
    assert f["days_since_last"] == 2 and f["is_stale"] is True


def test_freshness_weekend_today_uses_previous_trading_day():
    mon = _first_monday()
    sat = mon - timedelta(days=2)  # 週六 → 預期最新交易日為前一週五
    fri = mon - timedelta(days=3)
    f = us_market_service.compute_us_freshness(None, today=sat)
    assert f["expected_trading_day"] == fri.isoformat()
