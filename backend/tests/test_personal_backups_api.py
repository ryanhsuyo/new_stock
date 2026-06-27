import json


def _patch_backup_paths(monkeypatch, tmp_path):
    import app.services.personal_backup_service as svc

    data_dir = tmp_path / "data"
    backup_root = tmp_path / "backups" / "personal"
    data_dir.mkdir(parents=True)
    monkeypatch.setattr(svc, "_DATA_DIR", data_dir)
    monkeypatch.setattr(svc, "_BACKUP_ROOT", backup_root)
    return data_dir, backup_root


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_personal_backup_api_create_and_list(client, monkeypatch, tmp_path):
    data_dir, _backup_root = _patch_backup_paths(monkeypatch, tmp_path)
    _write_json(data_dir / "trades.json", [{"id": "t1"}])

    create_resp = client.post("/api/system/personal-backups")
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["backup_id"].startswith("personal_")
    assert created["file_count"] == 1
    assert created["missing_count"] == 4

    list_resp = client.get("/api/system/personal-backups")
    assert list_resp.status_code == 200
    assert list_resp.json()[0]["backup_id"] == created["backup_id"]


def test_personal_backup_api_preview_is_dry_run(client, monkeypatch, tmp_path):
    data_dir, _backup_root = _patch_backup_paths(monkeypatch, tmp_path)
    _write_json(data_dir / "trades.json", [{"id": "backup"}])
    backup_id = client.post("/api/system/personal-backups").json()["backup_id"]
    _write_json(data_dir / "trades.json", [{"id": "current"}])

    resp = client.post("/api/system/personal-backups/restore-preview", json={"backup_id": backup_id})

    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert body["can_restore"] is True
    assert body["restore_confirmation"] == "RESTORE_PERSONAL_DATA"
    assert json.loads((data_dir / "trades.json").read_text(encoding="utf-8")) == [{"id": "current"}]


def test_personal_backup_api_restore_requires_confirm(client, monkeypatch, tmp_path):
    data_dir, _backup_root = _patch_backup_paths(monkeypatch, tmp_path)
    _write_json(data_dir / "trades.json", [{"id": "backup"}])
    backup_id = client.post("/api/system/personal-backups").json()["backup_id"]

    resp = client.post("/api/system/personal-backups/restore", json={"backup_id": backup_id})

    assert resp.status_code == 400
    assert "RESTORE_PERSONAL_DATA" in resp.json()["detail"]


def test_personal_backup_api_restore_writes_backup_and_restores(client, monkeypatch, tmp_path):
    data_dir, backup_root = _patch_backup_paths(monkeypatch, tmp_path)
    _write_json(data_dir / "trades.json", [{"id": "backup"}])
    backup_id = client.post("/api/system/personal-backups").json()["backup_id"]
    _write_json(data_dir / "trades.json", [{"id": "current"}])

    resp = client.post(
        "/api/system/personal-backups/restore",
        json={"backup_id": backup_id, "confirm": "RESTORE_PERSONAL_DATA"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["restored"] is True
    assert body["restored_files"] == ["data/trades.json"]
    assert (backup_root / body["pre_restore_backup_id"] / "trades.json").exists()
    assert json.loads((data_dir / "trades.json").read_text(encoding="utf-8")) == [{"id": "backup"}]


def test_personal_backup_api_rejects_invalid_backup_id(client, monkeypatch, tmp_path):
    _patch_backup_paths(monkeypatch, tmp_path)

    resp = client.post("/api/system/personal-backups/restore-preview", json={"backup_id": "../bad"})

    assert resp.status_code == 400
