def test_us_update_status_store_defaults_and_roundtrips(tmp_path, monkeypatch):
    import app.storage.us_update_store as store
    monkeypatch.setattr(store, "US_UPDATE_STATUS_PATH", tmp_path / "us_update_status.json")
    assert store.load_us_update_status()["status"] == "idle"
    store.save_us_update_status({"status": "success", "months": 1})
    assert store.load_us_update_status()["months"] == 1


def test_trigger_us_update_validates_months():
    from app.services.us_update_service import trigger_us_background_update
    for value in (0, 61):
        try:
            trigger_us_background_update(value)
        except ValueError as exc:
            assert "1 與 60" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_us_update_endpoints(client, monkeypatch):
    import app.routers.markets as router
    monkeypatch.setattr(router, "get_us_update_status", lambda: {"status": "idle"})
    monkeypatch.setattr(router, "trigger_us_background_update", lambda months: {"status": "running", "months": months})
    assert client.get("/api/markets/us/update-status").json()["status"] == "idle"
    response = client.post("/api/markets/us/update-now?months=12")
    assert response.status_code == 200
    assert response.json() == {"status": "running", "months": 12}


def test_us_update_endpoint_returns_conflict(client, monkeypatch):
    import app.routers.markets as router
    monkeypatch.setattr(router, "trigger_us_background_update", lambda months: (_ for _ in ()).throw(RuntimeError("美股資料更新已在執行中")))
    assert client.post("/api/markets/us/update-now").status_code == 409


def test_us_backfill_command_only_targets_us_script(monkeypatch):
    import app.services.us_update_service as service
    seen = {}
    class Result:
        returncode = 0
        stdout = "ok"
        stderr = ""
    def fake_run(command, **kwargs):
        seen["command"] = command
        return Result()
    monkeypatch.setattr(service.subprocess, "run", fake_run)
    ok, _ = service._run_us_backfill(1)
    assert ok is True
    command = " ".join(str(part) for part in seen["command"])
    assert "backfill_ohlcv_us.py" in command
    assert "backfill_ohlcv_twse.py" not in command
