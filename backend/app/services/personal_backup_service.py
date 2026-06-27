from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.storage.atomic_write import atomic_write_text

_BACKEND = Path(__file__).resolve().parents[2]
_DATA_DIR = _BACKEND / "data"
_BACKUP_ROOT = _DATA_DIR / "backups" / "personal"
_RESTORE_CONFIRM = "RESTORE_PERSONAL_DATA"

PERSONAL_DATA_FILES: tuple[tuple[str, str], ...] = (
    ("trades", "trades.json"),
    ("decision_journal", "decision_journal.json"),
    ("watchlists", "watchlists.json"),
    ("market_notes", "market_notes.json"),
    ("settings", "settings.json"),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _backup_id(now: datetime | None = None) -> str:
    return f"personal_{(now or datetime.now()).strftime('%Y%m%dT%H%M%S%f')}"


def _assert_safe_backup_id(backup_id: str) -> None:
    if (
        not backup_id.startswith("personal_")
        or "/" in backup_id
        or "\\" in backup_id
        or ".." in backup_id
    ):
        raise ValueError("備份 ID 不合法")


def _resolve_backup_dir(backup_id: str, *, backup_root: Path | None = None) -> Path:
    _assert_safe_backup_id(backup_id)
    backup_root = backup_root or _BACKUP_ROOT
    root = backup_root.resolve()
    path = (backup_root / backup_id).resolve()
    if root != path and root not in path.parents:
        raise ValueError("備份 ID 不合法")
    return path


def _manifest_path(backup_dir: Path) -> Path:
    return backup_dir / "manifest.json"


def _load_manifest(backup_id: str, *, backup_root: Path | None = None) -> dict[str, Any]:
    backup_root = backup_root or _BACKUP_ROOT
    backup_dir = _resolve_backup_dir(backup_id, backup_root=backup_root)
    manifest_path = _manifest_path(backup_dir)
    if not manifest_path.exists():
        raise FileNotFoundError(f"找不到個人資料備份：{backup_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != "personal_data":
        raise ValueError("備份 manifest 類型不正確")
    return manifest


def create_personal_backup(
    *,
    data_dir: Path | None = None,
    backup_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    data_dir = data_dir or _DATA_DIR
    backup_root = backup_root or _BACKUP_ROOT
    data_dir.mkdir(parents=True, exist_ok=True)
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_id = _backup_id(now)
    backup_dir = _resolve_backup_dir(backup_id, backup_root=backup_root)
    backup_dir.mkdir(parents=True, exist_ok=False)

    files: list[dict[str, Any]] = []
    for key, filename in PERSONAL_DATA_FILES:
        source = data_dir / filename
        item: dict[str, Any] = {
            "key": key,
            "source": f"data/{filename}",
            "backup_path": filename,
            "exists": source.exists(),
            "size_bytes": 0,
            "sha256": None,
        }
        if source.exists():
            text = source.read_text(encoding="utf-8")
            target = backup_dir / filename
            atomic_write_text(target, text)
            item["size_bytes"] = target.stat().st_size
            item["sha256"] = _sha256(target)
        files.append(item)

    manifest = {
        "backup_id": backup_id,
        "created_at": (now or datetime.now()).isoformat(timespec="seconds"),
        "kind": "personal_data",
        "file_count": sum(1 for item in files if item["exists"]),
        "missing_count": sum(1 for item in files if not item["exists"]),
        "files": files,
    }
    atomic_write_text(_manifest_path(backup_dir), json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def list_personal_backups(*, backup_root: Path | None = None) -> list[dict[str, Any]]:
    backup_root = backup_root or _BACKUP_ROOT
    if not backup_root.exists():
        return []
    backups: list[dict[str, Any]] = []
    for manifest_path in sorted(backup_root.glob("personal_*/manifest.json"), reverse=True):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        stat = manifest_path.parent.stat()
        backups.append({
            "backup_id": manifest.get("backup_id") or manifest_path.parent.name,
            "created_at": manifest.get("created_at"),
            "file_count": int(manifest.get("file_count") or 0),
            "missing_count": int(manifest.get("missing_count") or 0),
            "path": str(manifest_path.parent),
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    return backups


def preview_personal_restore(
    backup_id: str,
    *,
    data_dir: Path | None = None,
    backup_root: Path | None = None,
) -> dict[str, Any]:
    data_dir = data_dir or _DATA_DIR
    backup_root = backup_root or _BACKUP_ROOT
    manifest = _load_manifest(backup_id, backup_root=backup_root)
    backup_dir = _resolve_backup_dir(backup_id, backup_root=backup_root)
    files: list[dict[str, Any]] = []
    can_restore = True

    for item in manifest.get("files") or []:
        filename = Path(str(item.get("backup_path") or "")).name
        target = data_dir / filename
        backup_file = backup_dir / filename
        exists_in_backup = bool(item.get("exists"))
        checksum_ok = True
        action = "skip_missing"

        if exists_in_backup:
            if not backup_file.exists():
                checksum_ok = False
                can_restore = False
                action = "blocked_missing_backup_file"
            else:
                expected = item.get("sha256")
                actual = _sha256(backup_file)
                checksum_ok = expected == actual
                if not checksum_ok:
                    can_restore = False
                    action = "blocked_checksum_mismatch"
                else:
                    action = "overwrite" if target.exists() else "create"

        files.append({
            "key": item.get("key"),
            "target": f"data/{filename}",
            "action": action,
            "exists_in_backup": exists_in_backup,
            "target_exists": target.exists(),
            "checksum_ok": checksum_ok,
            "sha256": item.get("sha256"),
            "current_sha256": _sha256(target) if target.exists() else None,
        })

    return {
        "backup_id": backup_id,
        "dry_run": True,
        "can_restore": can_restore,
        "restore_confirmation": _RESTORE_CONFIRM,
        "files": files,
    }


def restore_personal_backup(
    backup_id: str,
    *,
    confirm: str | None,
    data_dir: Path | None = None,
    backup_root: Path | None = None,
) -> dict[str, Any]:
    data_dir = data_dir or _DATA_DIR
    backup_root = backup_root or _BACKUP_ROOT
    if confirm != _RESTORE_CONFIRM:
        raise ValueError("正式還原必須提供 confirm=RESTORE_PERSONAL_DATA")

    preview = preview_personal_restore(backup_id, data_dir=data_dir, backup_root=backup_root)
    if not preview["can_restore"]:
        raise ValueError("備份檢查未通過，請先查看 restore preview")

    pre_restore = create_personal_backup(data_dir=data_dir, backup_root=backup_root)
    backup_dir = _resolve_backup_dir(backup_id, backup_root=backup_root)
    restored_files: list[str] = []

    for item in preview["files"]:
        if item["action"] not in {"create", "overwrite"}:
            continue
        filename = Path(str(item["target"]).replace("data/", "", 1)).name
        source = backup_dir / filename
        target = data_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, source.read_text(encoding="utf-8"))
        restored_files.append(f"data/{filename}")

    return {
        "backup_id": backup_id,
        "restored": True,
        "restored_files": restored_files,
        "restored_count": len(restored_files),
        "pre_restore_backup_id": pre_restore["backup_id"],
        "pre_restore_backup_path": str(_resolve_backup_dir(pre_restore["backup_id"], backup_root=backup_root)),
    }
