"""
test_markets_scaffold.py — 市場（region）維度與 price source adapter scaffold。

驗證：
- region 分類：既有台股（數字代碼）皆為 TW；美股 ticker（英文字母）為 US。
- price source 註冊表：TW 可用、US 為未就緒 stub。
- get_universe() 每筆帶 region 欄位，且既有資料一律 TW（不影響台股主流程）。
"""

import pytest

from app.services import markets, price_source, signals_service


# ── region 分類 ──────────────────────────────────────────────────────────────

def test_supported_markets_tw_enabled_us_not_yet():
    assert markets.SUPPORTED_MARKETS["TW"].enabled is True
    assert markets.SUPPORTED_MARKETS["US"].enabled is False
    assert markets.is_market_enabled("TW") is True
    assert markets.is_market_enabled("US") is False


@pytest.mark.parametrize("code", ["2330", "0050", "006208", "6285", "3711"])
def test_taiwan_numeric_codes_are_tw(code):
    assert markets.classify_region(code) == "TW"


@pytest.mark.parametrize("code", ["AAPL", "MSFT", "TSLA", "F"])
def test_us_tickers_are_us(code):
    assert markets.classify_region(code) == "US"


# ── price source adapter ─────────────────────────────────────────────────────

def test_tw_source_available_but_not_taking_over_fetch():
    tw = price_source.get_price_source("TW")
    assert tw.region == "TW"
    assert tw.is_available() is True
    # 本輪 TW adapter 為 seam，尚未接管抓取
    with pytest.raises(price_source.PriceSourceError):
        tw.fetch_ohlcv("2330")


def test_us_source_is_stooq_and_available_without_key():
    # US Phase 1 主源為 Stooq，免 API key
    us = price_source.get_price_source("US")
    assert us.region == "US"
    assert us.is_available() is True
    assert isinstance(us, price_source.StooqPriceSource)


def test_available_regions_include_us_via_stooq():
    assert price_source.available_regions() == ["TW", "US"]


def test_unknown_region_raises():
    with pytest.raises(price_source.PriceSourceError):
        price_source.get_price_source("JP")


# ── universe 帶 region 欄位 ───────────────────────────────────────────────────

def test_get_universe_items_carry_region_tw():
    universe = signals_service.get_universe()
    # 環境可能無資料檔；有資料時每筆都要帶 region，且既有台股皆為 TW
    for item in universe:
        assert "region" in item
        assert item["region"] == "TW"
