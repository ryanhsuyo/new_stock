"""
stock_names 動態名稱查詢測試

覆蓋：
  - _stock_name() 從 stock_names.json 正確讀取名稱
  - 名稱不存在時 fallback 為 code，不出現 "code (code)" 格式
  - name_store.load_stock_names() / save_stock_names() 讀寫正確
"""

import json
import pytest


# ---------------------------------------------------------------------------
# name_store 讀寫
# ---------------------------------------------------------------------------

class TestNameStore:

    def test_load_returns_empty_when_file_missing(self, tmp_path, monkeypatch):
        import app.storage.name_store as ns
        monkeypatch.setattr(ns, "NAMES_PATH", tmp_path / "stock_names.json")
        assert ns.load_stock_names() == {}

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        import app.storage.name_store as ns
        monkeypatch.setattr(ns, "NAMES_PATH", tmp_path / "stock_names.json")
        ns.save_stock_names({"2330": "台積電", "0050": "元大台灣50"})
        result = ns.load_stock_names()
        assert result["2330"] == "台積電"
        assert result["0050"] == "元大台灣50"

    def test_load_returns_empty_on_corrupt_file(self, tmp_path, monkeypatch):
        import app.storage.name_store as ns
        bad = tmp_path / "stock_names.json"
        bad.write_text("not valid json", encoding="utf-8")
        monkeypatch.setattr(ns, "NAMES_PATH", bad)
        assert ns.load_stock_names() == {}


# ---------------------------------------------------------------------------
# signals_service._stock_name() 動態查詢
# ---------------------------------------------------------------------------

class TestStockNameLookup:

    def _patch_names(self, monkeypatch, tmp_path, names: dict):
        """將 name_store.NAMES_PATH 導向 tmp_path 並寫入指定 names。"""
        import app.storage.name_store as ns
        import app.services.signals_service as svc
        path = tmp_path / "stock_names.json"
        path.write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(ns, "NAMES_PATH", path)
        svc._name_cache = None  # 強制重新載入

    def test_known_code_returns_name(self, monkeypatch, tmp_path):
        import app.services.signals_service as svc
        self._patch_names(monkeypatch, tmp_path, {"2330": "台積電"})
        assert svc._stock_name("2330") == "台積電"

    def test_unknown_code_returns_code_only(self, monkeypatch, tmp_path):
        """fallback 應回傳 code 本身，不出現 'code (code)' 格式。"""
        import app.services.signals_service as svc
        self._patch_names(monkeypatch, tmp_path, {})
        result = svc._stock_name("9999")
        assert result == "9999"
        assert result.count("9999") == 1

    def test_cache_refreshed_after_file_update(self, monkeypatch, tmp_path):
        """模擬 backfill 更新檔案後，run_daily_signals 重載快取。"""
        import app.storage.name_store as ns
        import app.services.signals_service as svc
        path = tmp_path / "stock_names.json"
        path.write_text('{"2330": "台積電"}', encoding="utf-8")
        monkeypatch.setattr(ns, "NAMES_PATH", path)
        svc._name_cache = None

        assert svc._stock_name("2330") == "台積電"

        # 模擬 backfill 後新股加入
        path.write_text('{"2330": "台積電", "9998": "新股票"}', encoding="utf-8")
        svc._reload_name_cache()

        assert svc._stock_name("9998") == "新股票"

    def test_initial_seed_file_has_expected_codes(self):
        """確認 stock_names.json 種子檔包含 leaders.json 所有代碼。"""
        from pathlib import Path
        import json
        names_path = Path(__file__).resolve().parent.parent / "data" / "stock_names.json"
        assert names_path.exists(), "stock_names.json 種子檔不存在"
        names = json.loads(names_path.read_text(encoding="utf-8"))
        expected = ["2330", "2454", "0050", "2881", "2603"]
        for code in expected:
            assert code in names, f"{code} 應在 stock_names.json"
