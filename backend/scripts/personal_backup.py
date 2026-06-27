#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import personal_backup_service as backup_service  # noqa: E402


def _print_files(files: list[dict]) -> None:
    for item in files:
        label = item.get("target") or item.get("source") or item.get("backup_path")
        action = item.get("action") or ("include" if item.get("exists") else "missing")
        checksum = " checksum_ok" if item.get("checksum_ok") is True else ""
        print(f"  - {label}: {action}{checksum}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="個人資料備份 / dry-run 還原工具")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("create", help="建立個人資料備份")
    sub.add_parser("list", help="列出個人資料備份")

    preview = sub.add_parser("preview-restore", help="dry-run 預覽還原，不寫入檔案")
    preview.add_argument("backup_id")

    restore = sub.add_parser("restore", help="正式還原個人資料")
    restore.add_argument("backup_id")
    restore.add_argument("--confirm", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "create":
            result = backup_service.create_personal_backup()
            print(f"created {result['backup_id']}")
            print(f"included={result['file_count']} missing={result['missing_count']}")
            _print_files(result["files"])
            return 0

        if args.command == "list":
            backups = backup_service.list_personal_backups()
            if not backups:
                print("no personal backups")
                return 0
            for item in backups:
                print(
                    f"{item['backup_id']} created_at={item.get('created_at') or '-'} "
                    f"files={item.get('file_count', 0)} missing={item.get('missing_count', 0)}"
                )
            return 0

        if args.command == "preview-restore":
            preview = backup_service.preview_personal_restore(args.backup_id)
            print(f"preview {preview['backup_id']} can_restore={preview['can_restore']}")
            print(f"restore confirm: {preview['restore_confirmation']}")
            _print_files(preview["files"])
            return 0 if preview["can_restore"] else 2

        if args.command == "restore":
            result = backup_service.restore_personal_backup(args.backup_id, confirm=args.confirm)
            print(f"restored {result['backup_id']}")
            print(f"restored_count={result['restored_count']}")
            print(f"pre_restore_backup_id={result['pre_restore_backup_id']}")
            return 0
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"unknown command: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
