import json

from app.models.trade import TradeRecord


def _trade(
    trade_id: str,
    stock_id: str,
    trade_type: str,
    *,
    shares: int = 1000,
    price: float = 100.0,
    date: str = "2026-05-19",
) -> dict:
    return {
        "id": trade_id,
        "stock_id": stock_id,
        "name": stock_id,
        "trade_type": trade_type,
        "date": date,
        "price": price,
        "shares": shares,
        "note": "",
        "created_at": f"{date}T09:00:00",
    }


def _simple_trade(
    stock_id: str,
    trade_type: str,
    *,
    shares: int = 1000,
    price: float = 100.0,
    date: str = "2026-05-19",
    name: str | None = None,
) -> dict:
    payload = {
        "stock_id": stock_id,
        "trade_type": trade_type,
        "date": date,
        "price": price,
        "shares": shares,
    }
    if name is not None:
        payload["name"] = name
    return payload


def test_backup_trades_writes_copy_before_replace(tmp_path, monkeypatch):
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    backup_path = store.backup_trades()

    assert backup_path is not None
    assert backup_path.parent == tmp_path / "backups"
    assert json.loads(backup_path.read_text(encoding="utf-8")) == [{"id": "old"}]


def test_import_trades_rejects_empty_list_without_writing(tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    try:
        service.import_trades([], backup=True)
    except ValueError as exc:
        assert "交易紀錄不可為空" in str(exc)
    else:
        raise AssertionError("empty import should fail")

    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": "old"}]
    assert not (tmp_path / "backups").exists()


def test_import_trades_rejects_oversell_without_writing(tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    trades = [
        TradeRecord(**_trade("b1", "2330", "buy", shares=1000)),
        TradeRecord(**_trade("s1", "2330", "sell", shares=2000)),
    ]

    try:
        service.import_trades(trades, backup=True)
    except ValueError as exc:
        assert "可賣出股數不足" in str(exc)
    else:
        raise AssertionError("oversell import should fail")

    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": "old"}]
    assert not (tmp_path / "backups").exists()


def test_import_trades_backs_up_and_replaces_valid_records(tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    trades = [
        TradeRecord(**_trade("b1", "2330", "buy", shares=2000)),
        TradeRecord(**_trade("s1", "2330", "sell", shares=1000)),
    ]

    result = service.import_trades(trades, backup=True)

    assert result["imported_count"] == 2
    assert result["buy_count"] == 1
    assert result["sell_count"] == 1
    assert result["backup_path"]
    assert json.loads(path.read_text(encoding="utf-8"))[0]["id"] == "b1"
    assert json.loads(path.read_text(encoding="utf-8"))[1]["id"] == "s1"


def test_preview_import_trades_validates_and_summarizes_without_writing(tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)
    monkeypatch.setattr(service, "get_all_current_prices", lambda: {"2330": 120.0})
    monkeypatch.setattr(service, "load_stock_names", lambda: {"2330": "台積電"})

    trades = [
        TradeRecord(**_trade("b1", "2330", "buy", shares=2000, price=100.0)),
        TradeRecord(**_trade("s1", "2330", "sell", shares=1000, price=110.0)),
    ]

    result = service.preview_import_trades(trades)

    assert result["imported_count"] == 2
    assert result["buy_count"] == 1
    assert result["sell_count"] == 1
    assert result["backup_path"] is None
    assert result["positions_preview"][0]["stock_id"] == "2330"
    assert result["positions_preview"][0]["total_shares"] == 1000
    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": "old"}]
    assert not (tmp_path / "backups").exists()


def test_import_trades_api_rejects_invalid_batch(client, tmp_path, monkeypatch):
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    resp = client.post("/api/trades/import", json={
        "trades": [
            _trade("b1", "2330", "buy", shares=1000),
            _trade("s1", "2330", "sell", shares=2000),
        ]
    })

    assert resp.status_code == 400
    assert "可賣出股數不足" in resp.json()["detail"]
    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": "old"}]


def test_import_trades_api_replaces_valid_batch(client, tmp_path, monkeypatch):
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    resp = client.post("/api/trades/import", json={
        "trades": [
            _trade("b1", "2330", "buy", shares=2000),
            _trade("s1", "2330", "sell", shares=1000),
        ]
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["imported_count"] == 2
    assert body["backup_path"]
    assert json.loads(path.read_text(encoding="utf-8"))[0]["id"] == "b1"


def test_preview_import_trades_api_does_not_write_or_backup(client, tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)
    monkeypatch.setattr(service, "get_all_current_prices", lambda: {"2330": 120.0})
    monkeypatch.setattr(service, "load_stock_names", lambda: {"2330": "台積電"})

    resp = client.post("/api/trades/import/preview", json={
        "trades": [
            _trade("b1", "2330", "buy", shares=2000, price=100.0),
            _trade("s1", "2330", "sell", shares=1000, price=110.0),
        ]
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["imported_count"] == 2
    assert body["positions_preview"][0]["stock_id"] == "2330"
    assert body["positions_preview"][0]["total_shares"] == 1000
    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": "old"}]
    assert not (tmp_path / "backups").exists()


def test_preview_import_trades_api_rejects_invalid_batch_without_writing(client, tmp_path, monkeypatch):
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    resp = client.post("/api/trades/import/preview", json={
        "trades": [
            _trade("b1", "2330", "buy", shares=1000),
            _trade("s1", "2330", "sell", shares=2000),
        ]
    })

    assert resp.status_code == 400
    assert "可賣出股數不足" in resp.json()["detail"]
    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": "old"}]


def test_validate_import_trades_returns_all_errors_without_writing(tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    trades = [
        TradeRecord(**_trade("b1", "2330", "buy", shares=1000, price=-1.0)),
        TradeRecord(**_trade("b1", "2330", "buy", shares=0, price=100.0)),
        TradeRecord(**_trade("s1", "2303", "sell", shares=1000, price=20.0)),
    ]

    result = service.validate_import_trades(trades)

    assert result["valid"] is False
    assert result["error_count"] == 4
    assert any("價格必須大於 0" in error for error in result["errors"])
    assert any("id 重複" in error for error in result["errors"])
    assert any("股數必須大於 0" in error for error in result["errors"])
    assert any("可賣出股數不足" in error for error in result["errors"])
    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": "old"}]
    assert not (tmp_path / "backups").exists()


def test_validate_import_trades_returns_positions_for_valid_batch(tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)
    monkeypatch.setattr(service, "get_all_current_prices", lambda: {"2330": 120.0})
    monkeypatch.setattr(service, "load_stock_names", lambda: {"2330": "台積電"})

    trades = [
        TradeRecord(**_trade("b1", "2330", "buy", shares=2000, price=100.0)),
        TradeRecord(**_trade("s1", "2330", "sell", shares=1000, price=110.0)),
    ]

    result = service.validate_import_trades(trades)

    assert result["valid"] is True
    assert result["error_count"] == 0
    assert result["imported_count"] == 2
    assert result["positions_preview"][0]["stock_id"] == "2330"
    assert result["positions_preview"][0]["total_shares"] == 1000
    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": "old"}]


def test_validate_import_trades_api_returns_error_report_without_writing(client, tmp_path, monkeypatch):
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    resp = client.post("/api/trades/import/validate", json={
        "trades": [
            _trade("b1", "2330", "buy", shares=1000, price=-1.0),
            _trade("b1", "2330", "buy", shares=0, price=100.0),
            _trade("s1", "2303", "sell", shares=1000, price=20.0),
        ]
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert body["error_count"] == 4
    assert len(body["errors"]) == 4
    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": "old"}]


def test_validate_import_trades_api_accepts_simple_records_without_writing(client, tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)
    monkeypatch.setattr(service, "get_all_current_prices", lambda: {"2330": 120.0})
    monkeypatch.setattr(service, "load_stock_names", lambda: {"2330": "台積電"})

    resp = client.post("/api/trades/import/validate", json={
        "trades": [
            _simple_trade("2330", "buy", shares=2000, price=100.0),
            _simple_trade("2330", "sell", shares=1000, price=110.0),
        ]
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert any("自動補齊 id 2 筆" in warning for warning in body["warnings"])
    assert any("自動補齊 created_at 2 筆" in warning for warning in body["warnings"])
    assert any("自動補齊 name 2 筆" in warning for warning in body["warnings"])
    assert any("自動補齊金額欄位 2 筆" in warning for warning in body["warnings"])
    assert body["positions_preview"][0]["name"] == "台積電"
    assert body["positions_preview"][0]["total_shares"] == 1000
    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": "old"}]


def test_import_trades_api_accepts_simple_records_and_fills_required_fields(client, tmp_path, monkeypatch):
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    resp = client.post("/api/trades/import", json={
        "trades": [
            _simple_trade("2330", "buy", shares=1000, price=100.0, name="台積電"),
        ]
    })

    assert resp.status_code == 200
    body = resp.json()
    assert any("自動補齊 id 1 筆" in warning for warning in body["warnings"])
    assert any("自動補齊 created_at 1 筆" in warning for warning in body["warnings"])
    assert any("自動補齊金額欄位 1 筆" in warning for warning in body["warnings"])
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored[0]["stock_id"] == "2330"
    assert stored[0]["name"] == "台積電"
    assert stored[0]["id"]
    assert stored[0]["created_at"]
    assert stored[0]["gross_amount"] == 100000
    assert stored[0]["net_amount"] is not None


def test_preview_import_trades_api_returns_autofill_warnings_for_simple_records(client, tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text('[{"id": "old"}]', encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)
    monkeypatch.setattr(service, "get_all_current_prices", lambda: {"2330": 120.0})
    monkeypatch.setattr(service, "load_stock_names", lambda: {"2330": "台積電"})

    resp = client.post("/api/trades/import/preview", json={
        "trades": [
            _simple_trade("2330", "buy", shares=1000, price=100.0),
        ]
    })

    assert resp.status_code == 200
    body = resp.json()
    assert any("自動補齊 id 1 筆" in warning for warning in body["warnings"])
    assert any("自動補齊 created_at 1 筆" in warning for warning in body["warnings"])
    assert any("自動補齊 name 1 筆" in warning for warning in body["warnings"])
    assert any("自動補齊金額欄位 1 筆" in warning for warning in body["warnings"])
    assert json.loads(path.read_text(encoding="utf-8")) == [{"id": "old"}]


def test_clear_trades_rejects_wrong_confirmation_without_writing(tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text(json.dumps([_trade("b1", "2330", "buy")]), encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    try:
        service.clear_trades(confirm="清空", backup=True)
    except ValueError as exc:
        assert "確認字串" in str(exc)
    else:
        raise AssertionError("wrong confirmation should fail")

    assert len(json.loads(path.read_text(encoding="utf-8"))) == 1
    assert not (tmp_path / "backups").exists()


def test_clear_trades_backs_up_and_empties_records(tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text(json.dumps([_trade("b1", "2330", "buy")]), encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    result = service.clear_trades(confirm="CLEAR_TRADES", backup=True)

    assert result["cleared_count"] == 1
    assert result["backup_path"]
    assert json.loads(path.read_text(encoding="utf-8")) == []
    backups = list((tmp_path / "backups").glob("trades_*.json"))
    assert len(backups) == 1
    assert len(json.loads(backups[0].read_text(encoding="utf-8"))) == 1


def test_clear_trades_api_requires_confirmation(client, tmp_path, monkeypatch):
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text(json.dumps([_trade("b1", "2330", "buy")]), encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    resp = client.post("/api/trades/clear", json={"confirm": "wrong"})

    assert resp.status_code == 400
    assert "確認字串" in resp.json()["detail"]
    assert len(json.loads(path.read_text(encoding="utf-8"))) == 1


def test_clear_trades_api_backs_up_and_clears(client, tmp_path, monkeypatch):
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text(json.dumps([_trade("b1", "2330", "buy")]), encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    resp = client.post("/api/trades/clear", json={"confirm": "CLEAR_TRADES"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["cleared_count"] == 1
    assert body["backup_path"]
    assert json.loads(path.read_text(encoding="utf-8")) == []


def test_list_trade_backups_returns_metadata(tmp_path, monkeypatch):
    import app.storage.json_store as store

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "trades_20260520T090000000000.json").write_text(
        json.dumps([_trade("b1", "2330", "buy")]),
        encoding="utf-8",
    )
    (backup_dir / "trades_20260520T100000000000.json").write_text(
        json.dumps([_trade("b1", "2330", "buy"), _trade("s1", "2330", "sell")]),
        encoding="utf-8",
    )
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)

    backups = store.list_trade_backups()

    assert [item["filename"] for item in backups] == [
        "trades_20260520T100000000000.json",
        "trades_20260520T090000000000.json",
    ]
    assert backups[0]["trade_count"] == 2
    assert backups[0]["size_bytes"] > 0


def test_restore_trades_rejects_path_traversal_without_writing(tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text(json.dumps([_trade("current", "2330", "buy")]), encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    try:
        service.restore_trades_backup(filename="../trades_20260520T090000000000.json", confirm="RESTORE_TRADES")
    except ValueError as exc:
        assert "備份檔名不合法" in str(exc)
    else:
        raise AssertionError("path traversal should fail")

    assert json.loads(path.read_text(encoding="utf-8"))[0]["id"] == "current"


def test_restore_trades_requires_confirmation_without_writing(tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text(json.dumps([_trade("current", "2330", "buy")]), encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_name = "trades_20260520T090000000000.json"
    (backup_dir / backup_name).write_text(json.dumps([_trade("backup", "2303", "buy")]), encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    try:
        service.restore_trades_backup(filename=backup_name, confirm="wrong")
    except ValueError as exc:
        assert "確認字串" in str(exc)
    else:
        raise AssertionError("wrong confirmation should fail")

    assert json.loads(path.read_text(encoding="utf-8"))[0]["id"] == "current"


def test_restore_trades_backup_backs_up_current_and_restores_selected_file(tmp_path, monkeypatch):
    import app.services.trade_service as service
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text(json.dumps([_trade("current", "2330", "buy")]), encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_name = "trades_20260520T090000000000.json"
    (backup_dir / backup_name).write_text(json.dumps([_trade("backup", "2303", "buy")]), encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    result = service.restore_trades_backup(filename=backup_name, confirm="RESTORE_TRADES")

    assert result["restored_count"] == 1
    assert result["restored_from"] == backup_name
    assert result["backup_path"]
    assert json.loads(path.read_text(encoding="utf-8"))[0]["id"] == "backup"
    backups = sorted((tmp_path / "backups").glob("trades_*.json"))
    assert len(backups) == 2


def test_trade_backups_api_lists_and_restores(client, tmp_path, monkeypatch):
    import app.storage.json_store as store

    path = tmp_path / "trades.json"
    path.write_text(json.dumps([_trade("current", "2330", "buy")]), encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    backup_name = "trades_20260520T090000000000.json"
    (backup_dir / backup_name).write_text(json.dumps([_trade("backup", "2303", "buy")]), encoding="utf-8")
    monkeypatch.setattr(store, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "_TRADES_FILE", path)

    list_resp = client.get("/api/trades/backups")
    assert list_resp.status_code == 200
    assert list_resp.json()[0]["filename"] == backup_name

    restore_resp = client.post("/api/trades/backups/restore", json={
        "filename": backup_name,
        "confirm": "RESTORE_TRADES",
    })
    assert restore_resp.status_code == 200
    assert restore_resp.json()["restored_from"] == backup_name
    assert json.loads(path.read_text(encoding="utf-8"))[0]["id"] == "backup"
