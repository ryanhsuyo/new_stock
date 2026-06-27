import json
from datetime import datetime

import pytest


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_create_personal_backup_writes_manifest_and_checksums(tmp_path):
    from app.services.personal_backup_service import create_personal_backup

    data_dir = tmp_path / "data"
    backup_root = tmp_path / "backups"
    data_dir.mkdir()
    _write_json(data_dir / "trades.json", [{"id": "t1"}])
    _write_json(data_dir / "decision_journal.json", [{"id": "j1"}])

    result = create_personal_backup(
        data_dir=data_dir,
        backup_root=backup_root,
        now=datetime(2026, 6, 25, 3, 0, 0),
    )

    assert result["backup_id"].startswith("personal_20260625T030000")
    assert result["file_count"] == 2
    assert result["missing_count"] == 3
    manifest_path = backup_root / result["backup_id"] / "manifest.json"
    assert manifest_path.exists()
    trades = next(item for item in result["files"] if item["key"] == "trades")
    assert trades["exists"] is True
    assert trades["sha256"]
    assert (backup_root / result["backup_id"] / "trades.json").exists()


def test_list_personal_backups_returns_manifest_summaries(tmp_path):
    from app.services.personal_backup_service import create_personal_backup, list_personal_backups

    data_dir = tmp_path / "data"
    backup_root = tmp_path / "backups"
    data_dir.mkdir()
    _write_json(data_dir / "trades.json", [])

    created = create_personal_backup(data_dir=data_dir, backup_root=backup_root)

    backups = list_personal_backups(backup_root=backup_root)

    assert backups[0]["backup_id"] == created["backup_id"]
    assert backups[0]["file_count"] == 1
    assert backups[0]["missing_count"] == 4


def test_preview_personal_restore_does_not_modify_current_files(tmp_path):
    from app.services.personal_backup_service import create_personal_backup, preview_personal_restore

    data_dir = tmp_path / "data"
    backup_root = tmp_path / "backups"
    data_dir.mkdir()
    _write_json(data_dir / "trades.json", [{"id": "backup"}])
    created = create_personal_backup(data_dir=data_dir, backup_root=backup_root)
    _write_json(data_dir / "trades.json", [{"id": "current"}])

    preview = preview_personal_restore(created["backup_id"], data_dir=data_dir, backup_root=backup_root)

    assert preview["dry_run"] is True
    assert preview["can_restore"] is True
    assert preview["restore_confirmation"] == "RESTORE_PERSONAL_DATA"
    assert next(item for item in preview["files"] if item["key"] == "trades")["action"] == "overwrite"
    assert json.loads((data_dir / "trades.json").read_text(encoding="utf-8")) == [{"id": "current"}]


def test_restore_requires_confirmation(tmp_path):
    from app.services.personal_backup_service import create_personal_backup, restore_personal_backup

    data_dir = tmp_path / "data"
    backup_root = tmp_path / "backups"
    data_dir.mkdir()
    _write_json(data_dir / "trades.json", [{"id": "backup"}])
    created = create_personal_backup(data_dir=data_dir, backup_root=backup_root)

    with pytest.raises(ValueError, match="RESTORE_PERSONAL_DATA"):
        restore_personal_backup(created["backup_id"], confirm=None, data_dir=data_dir, backup_root=backup_root)


def test_restore_creates_pre_restore_backup_and_restores_files(tmp_path):
    from app.services.personal_backup_service import create_personal_backup, restore_personal_backup

    data_dir = tmp_path / "data"
    backup_root = tmp_path / "backups"
    data_dir.mkdir()
    _write_json(data_dir / "trades.json", [{"id": "backup"}])
    created = create_personal_backup(data_dir=data_dir, backup_root=backup_root)
    _write_json(data_dir / "trades.json", [{"id": "current"}])

    result = restore_personal_backup(
        created["backup_id"],
        confirm="RESTORE_PERSONAL_DATA",
        data_dir=data_dir,
        backup_root=backup_root,
    )

    assert result["restored"] is True
    assert result["restored_files"] == ["data/trades.json"]
    assert result["pre_restore_backup_id"].startswith("personal_")
    assert result["pre_restore_backup_id"] != created["backup_id"]
    pre_restore_trades = json.loads(
        (backup_root / result["pre_restore_backup_id"] / "trades.json").read_text(encoding="utf-8")
    )
    assert pre_restore_trades == [{"id": "current"}]
    assert json.loads((data_dir / "trades.json").read_text(encoding="utf-8")) == [{"id": "backup"}]


def test_invalid_backup_id_is_rejected(tmp_path):
    from app.services.personal_backup_service import preview_personal_restore

    with pytest.raises(ValueError, match="備份 ID 不合法"):
        preview_personal_restore("../trades", data_dir=tmp_path / "data", backup_root=tmp_path / "backups")
