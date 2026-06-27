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


def test_personal_backup_cli_create_and_list(monkeypatch, tmp_path, capsys):
    from scripts import personal_backup

    data_dir, _backup_root = _patch_backup_paths(monkeypatch, tmp_path)
    _write_json(data_dir / "trades.json", [{"id": "t1"}])

    assert personal_backup.main(["create"]) == 0
    create_out = capsys.readouterr().out
    assert "created personal_" in create_out
    assert "included=1 missing=4" in create_out

    assert personal_backup.main(["list"]) == 0
    list_out = capsys.readouterr().out
    assert "personal_" in list_out
    assert "files=1" in list_out


def test_personal_backup_cli_preview_restore(monkeypatch, tmp_path, capsys):
    from app.services.personal_backup_service import create_personal_backup
    from scripts import personal_backup

    data_dir, backup_root = _patch_backup_paths(monkeypatch, tmp_path)
    _write_json(data_dir / "trades.json", [{"id": "backup"}])
    backup_id = create_personal_backup(data_dir=data_dir, backup_root=backup_root)["backup_id"]
    _write_json(data_dir / "trades.json", [{"id": "current"}])

    assert personal_backup.main(["preview-restore", backup_id]) == 0
    out = capsys.readouterr().out
    assert f"preview {backup_id} can_restore=True" in out
    assert "restore confirm: RESTORE_PERSONAL_DATA" in out
    assert json.loads((data_dir / "trades.json").read_text(encoding="utf-8")) == [{"id": "current"}]


def test_personal_backup_cli_restore_requires_confirm(monkeypatch, tmp_path, capsys):
    from app.services.personal_backup_service import create_personal_backup
    from scripts import personal_backup

    data_dir, backup_root = _patch_backup_paths(monkeypatch, tmp_path)
    _write_json(data_dir / "trades.json", [{"id": "backup"}])
    backup_id = create_personal_backup(data_dir=data_dir, backup_root=backup_root)["backup_id"]

    assert personal_backup.main(["restore", backup_id]) == 2
    err = capsys.readouterr().err
    assert "RESTORE_PERSONAL_DATA" in err


def test_personal_backup_cli_restore(monkeypatch, tmp_path, capsys):
    from app.services.personal_backup_service import create_personal_backup
    from scripts import personal_backup

    data_dir, backup_root = _patch_backup_paths(monkeypatch, tmp_path)
    _write_json(data_dir / "trades.json", [{"id": "backup"}])
    backup_id = create_personal_backup(data_dir=data_dir, backup_root=backup_root)["backup_id"]
    _write_json(data_dir / "trades.json", [{"id": "current"}])

    assert personal_backup.main(["restore", backup_id, "--confirm", "RESTORE_PERSONAL_DATA"]) == 0
    out = capsys.readouterr().out
    assert f"restored {backup_id}" in out
    assert "pre_restore_backup_id=personal_" in out
    assert json.loads((data_dir / "trades.json").read_text(encoding="utf-8")) == [{"id": "backup"}]
