"""
test_market_store.py — market_store 單元測試

覆蓋：
  load_stock_markets():
    - 檔案不存在 → 回傳 {}
    - 正常讀取 → 回傳 dict
    - 損壞 JSON → 回傳 {}

  save_stock_markets():
    - 寫入後可正確讀回

  derive_market():
    - ETF 代號（0 開頭）→ "ETF"（無論 exchange）
    - exchange=TWSE, 非 ETF → "TWSE"
    - exchange=TPEX → "TPEX"
    - exchange=None, 1/2 前綴 → "TWSE"（heuristic）
    - exchange=None, 3/6/8 前綴 → "TPEX"（heuristic）
    - 已知例外代碼（3711/3231/3481/5880）→ exchange 優先於 heuristic
"""

import json
from pathlib import Path

import pytest

from app.storage.market_store import (
    MARKETS_PATH,
    derive_market,
    load_stock_markets,
    save_stock_markets,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_markets(tmp_path, monkeypatch):
    """把 MARKETS_PATH 導向臨時目錄。"""
    import app.storage.market_store as ms
    monkeypatch.setattr(ms, "MARKETS_PATH", tmp_path / "stock_markets.json")
    monkeypatch.setattr(ms, "_DATA", tmp_path)
    return tmp_path / "stock_markets.json"


# ---------------------------------------------------------------------------
# load_stock_markets
# ---------------------------------------------------------------------------

class TestLoadStockMarkets:

    def test_missing_file_returns_empty(self, tmp_markets):
        result = load_stock_markets()
        assert result == {}

    def test_reads_valid_json(self, tmp_markets):
        tmp_markets.write_text(
            json.dumps({"2330": "TWSE", "3491": "TPEX"}), encoding="utf-8"
        )
        result = load_stock_markets()
        assert result == {"2330": "TWSE", "3491": "TPEX"}

    def test_corrupted_json_returns_empty(self, tmp_markets):
        tmp_markets.write_text("{ bad json", encoding="utf-8")
        result = load_stock_markets()
        assert result == {}


# ---------------------------------------------------------------------------
# save_stock_markets
# ---------------------------------------------------------------------------

class TestSaveStockMarkets:

    def test_save_and_reload(self, tmp_markets):
        data = {"2330": "TWSE", "3491": "TPEX", "0050": "TWSE"}
        save_stock_markets(data)
        assert load_stock_markets() == data

    def test_file_is_sorted_by_code(self, tmp_markets):
        save_stock_markets({"3491": "TPEX", "2330": "TWSE", "0050": "TWSE"})
        raw = json.loads(tmp_markets.read_text(encoding="utf-8"))
        assert list(raw.keys()) == sorted(raw.keys())


# ---------------------------------------------------------------------------
# derive_market
# ---------------------------------------------------------------------------

class TestDeriveMarket:

    # ETF：代號以 "0" 開頭，一律回傳 ETF
    def test_etf_0050(self):
        assert derive_market("0050", "TWSE") == "ETF"

    def test_etf_00878(self):
        assert derive_market("00878", "TWSE") == "ETF"

    def test_etf_006208(self):
        assert derive_market("006208", "TWSE") == "ETF"

    def test_etf_exchange_none_still_etf(self):
        assert derive_market("0056", None) == "ETF"

    # exchange 已知：直接使用
    def test_twse_exchange(self):
        assert derive_market("2330", "TWSE") == "TWSE"

    def test_tpex_exchange(self):
        assert derive_market("3491", "TPEX") == "TPEX"

    # 已知例外：exchange 比 heuristic 更準確
    def test_3711_with_twse_exchange(self):
        """3711 日月光投控以 3 開頭但為 TWSE，exchange 提供正確答案。"""
        assert derive_market("3711", "TWSE") == "TWSE"

    def test_3231_with_twse_exchange(self):
        """3231 緯創以 3 開頭但為 TWSE。"""
        assert derive_market("3231", "TWSE") == "TWSE"

    def test_3481_with_twse_exchange(self):
        """3481 群創以 3 開頭但為 TWSE。"""
        assert derive_market("3481", "TWSE") == "TWSE"

    def test_5880_with_twse_exchange(self):
        """5880 合庫金以 5 開頭但為 TWSE。"""
        assert derive_market("5880", "TWSE") == "TWSE"

    # heuristic fallback（exchange 未知）
    def test_heuristic_1xxx_twse(self):
        assert derive_market("1301", None) == "TWSE"

    def test_heuristic_2xxx_twse(self):
        assert derive_market("2454", None) == "TWSE"

    def test_heuristic_6xxx_tpex(self):
        assert derive_market("6125", None) == "TPEX"

    def test_heuristic_8xxx_tpex(self):
        assert derive_market("8046", None) == "TPEX"

    def test_heuristic_3xxx_tpex(self):
        """exchange 未知時 3xxx 推斷 TPEX（近似，3711/3231/3481 為例外）。"""
        assert derive_market("3034", None) == "TPEX"
