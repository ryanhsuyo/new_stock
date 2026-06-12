"""
test_watchlists.py — 觀察清單 API 與 storage 最小測試

覆蓋：
  GET  /api/stocks/universe  — schema 欄位、data_status 值域
  GET  /api/watchlists       — 空清單回 []
  POST /api/watchlists       — 建立群組
  409 重複建立
  POST /api/watchlists/{group}/stocks  — 加入股票、冪等
  DELETE /api/watchlists/{group}/stocks/{code} — 移除
  DELETE /api/watchlists/{group}       — 刪除群組
  404 群組不存在
"""

import json
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── /api/stocks/universe ──────────────────────────────────────────────────────

def test_universe_schema():
    res = client.get("/api/stocks/universe")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    for item in items:
        assert "code"            in item
        assert "name"            in item
        assert "has_data"        in item
        assert "row_count"       in item
        assert "last_data_as_of" in item
        assert "data_status"     in item
        assert item["data_status"] in ("ok", "insufficient", "no_data")
        assert isinstance(item["has_data"], bool)
        assert isinstance(item["row_count"], int)


# ── watchlist storage 單元測試（直接呼叫 store，不走 HTTP）────────────────────

def _store():
    import app.storage.watchlist_store as ws
    return ws


def test_watchlist_crud(tmp_path, monkeypatch):
    ws = _store()
    monkeypatch.setattr(ws, "_WATCHLISTS_PATH", tmp_path / "watchlists.json")

    # 初始為空
    assert ws.get_all_groups() == []

    # 建立群組
    g = ws.create_group("科技股")
    assert g["name"] == "科技股"
    assert g["stocks"] == []

    # 重複建立 → 拋 ValueError
    with pytest.raises(ValueError):
        ws.create_group("科技股")

    # 加入股票
    ws.add_stock("科技股", "2330", "台積電")
    groups = ws.get_all_groups()
    assert len(groups[0]["stocks"]) == 1
    assert groups[0]["stocks"][0]["code"] == "2330"

    # 冪等：再次加入同一股票，數量不變
    ws.add_stock("科技股", "2330", "台積電")
    assert len(ws.get_all_groups()[0]["stocks"]) == 1

    # 加入第二支股票
    ws.add_stock("科技股", "2454", "聯發科")
    assert len(ws.get_all_groups()[0]["stocks"]) == 2

    # 移除股票
    ws.remove_stock("科技股", "2330")
    assert len(ws.get_all_groups()[0]["stocks"]) == 1

    # 移除不存在群組 → 拋 KeyError
    with pytest.raises(KeyError):
        ws.remove_stock("不存在的群組", "2330")

    # 刪除群組
    ws.delete_group("科技股")
    assert ws.get_all_groups() == []

    # 刪除不存在群組 → 拋 KeyError
    with pytest.raises(KeyError):
        ws.delete_group("科技股")


# ── watchlist HTTP 端點 ────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_watchlist(tmp_path, monkeypatch):
    import app.storage.watchlist_store as ws
    path = tmp_path / "watchlists.json"
    monkeypatch.setattr(ws, "_WATCHLISTS_PATH", path)
    return path


def test_api_list_empty(tmp_watchlist):
    res = client.get("/api/watchlists")
    assert res.status_code == 200
    assert res.json() == []


def test_api_create_group(tmp_watchlist):
    res = client.post("/api/watchlists", json={"name": "觀察A"})
    assert res.status_code == 201
    assert res.json()["name"] == "觀察A"


def test_api_create_duplicate_409(tmp_watchlist):
    client.post("/api/watchlists", json={"name": "觀察A"})
    res = client.post("/api/watchlists", json={"name": "觀察A"})
    assert res.status_code == 409


def test_api_add_and_remove_stock(tmp_watchlist):
    client.post("/api/watchlists", json={"name": "觀察A"})

    # 加入
    res = client.post("/api/watchlists/觀察A/stocks", json={"code": "2330", "name": "台積電"})
    assert res.status_code == 200
    assert res.json()["stocks"][0]["code"] == "2330"

    # 移除
    res = client.delete("/api/watchlists/觀察A/stocks/2330")
    assert res.status_code == 200
    assert res.json()["stocks"] == []


def test_api_add_to_missing_group_404(tmp_watchlist):
    res = client.post("/api/watchlists/不存在群組/stocks", json={"code": "2330", "name": "台積電"})
    assert res.status_code == 404


def test_api_delete_group(tmp_watchlist):
    client.post("/api/watchlists", json={"name": "觀察A"})
    res = client.delete("/api/watchlists/觀察A")
    assert res.status_code == 200
    assert client.get("/api/watchlists").json() == []
