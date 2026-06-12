import json


def test_add_stock_to_tracking_appends_manual_group_and_appears_in_universe(client, tmp_path, monkeypatch):
    import app.services.analysis_service as analysis_svc
    import app.services.signals_service as signals_svc
    import app.storage.leaders_store as leaders_store
    import app.storage.name_store as name_store

    leaders_path = tmp_path / "leaders.json"
    names_path = tmp_path / "stock_names.json"
    leaders_path.write_text(json.dumps({"AI半導體": ["2330"]}, ensure_ascii=False), encoding="utf-8")
    names_path.write_text(json.dumps({"2330": "台積電"}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(leaders_store, "LEADERS_PATH", leaders_path)
    monkeypatch.setattr(name_store, "NAMES_PATH", names_path)
    monkeypatch.setattr(signals_svc, "LEADERS_PATH", leaders_path)
    monkeypatch.setattr(analysis_svc, "LEADERS_PATH", leaders_path)
    signals_svc._reload_name_cache()

    response = client.post("/api/stocks/9999/tracking", json={"name": "測試股"})

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "9999"
    assert body["name"] == "測試股"
    assert body["group"] == "手動追蹤"
    assert body["added"] is True
    assert body["next_action_command"] == "python3 scripts/daily_update.py --months 12"
    assert body["next_action_copy_command"].endswith(
        "backend\npython3 scripts/daily_update.py --months 12"
    )

    saved = json.loads(leaders_path.read_text(encoding="utf-8"))
    assert saved["AI半導體"] == ["2330"]
    assert saved["手動追蹤"] == ["9999"]
    assert json.loads(names_path.read_text(encoding="utf-8"))["9999"] == "測試股"

    universe = client.get("/api/stocks/universe").json()
    added = next(item for item in universe if item["code"] == "9999")
    assert added["name"] == "測試股"
    assert added["data_status"] == "no_data"


def test_add_stock_to_tracking_is_idempotent(client, tmp_path, monkeypatch):
    import app.services.analysis_service as analysis_svc
    import app.services.signals_service as signals_svc
    import app.storage.leaders_store as leaders_store
    import app.storage.name_store as name_store

    leaders_path = tmp_path / "leaders.json"
    names_path = tmp_path / "stock_names.json"
    leaders_path.write_text(
        json.dumps({"AI半導體": ["2330"], "手動追蹤": ["9999"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    names_path.write_text(json.dumps({"9999": "測試股"}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(leaders_store, "LEADERS_PATH", leaders_path)
    monkeypatch.setattr(name_store, "NAMES_PATH", names_path)
    monkeypatch.setattr(signals_svc, "LEADERS_PATH", leaders_path)
    monkeypatch.setattr(analysis_svc, "LEADERS_PATH", leaders_path)
    signals_svc._reload_name_cache()

    response = client.post("/api/stocks/9999/tracking", json={"name": "測試股"})

    assert response.status_code == 200
    body = response.json()
    assert body["added"] is False
    saved = json.loads(leaders_path.read_text(encoding="utf-8"))
    assert saved["手動追蹤"].count("9999") == 1
