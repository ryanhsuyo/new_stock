"""
本地 JSON 儲存層。
未來若要改接 PostgreSQL / SQLite，只需替換此模組，
上層 service 與 router 不需異動。
"""
import json
from pathlib import Path
from datetime import datetime

from app.models.trade import TradeRecord
from app.storage.atomic_write import atomic_write_text

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_TRADES_FILE = _DATA_DIR / "trades.json"


def _ensure_file() -> None:
    _DATA_DIR.mkdir(exist_ok=True)
    if not _TRADES_FILE.exists():
        atomic_write_text(_TRADES_FILE, "[]")


def load_trades() -> list[TradeRecord]:
    _ensure_file()
    raw: list[dict] = json.loads(_TRADES_FILE.read_text(encoding="utf-8"))
    return [TradeRecord(**item) for item in raw]


def backup_trades() -> Path | None:
    _ensure_file()
    if not _TRADES_FILE.exists():
        return None
    backup_dir = _DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    backup_path = backup_dir / f"trades_{timestamp}.json"
    atomic_write_text(backup_path, _TRADES_FILE.read_text(encoding="utf-8"))
    return backup_path


def _backup_dir() -> Path:
    return _DATA_DIR / "backups"


def _resolve_trade_backup(filename: str) -> Path:
    if "/" in filename or "\\" in filename or not filename.startswith("trades_") or not filename.endswith(".json"):
        raise ValueError("備份檔名不合法")
    path = (_backup_dir() / filename).resolve()
    backup_root = _backup_dir().resolve()
    if backup_root not in path.parents:
        raise ValueError("備份檔名不合法")
    return path


def list_trade_backups() -> list[dict]:
    backup_dir = _backup_dir()
    if not backup_dir.exists():
        return []

    backups: list[dict] = []
    for path in sorted(backup_dir.glob("trades_*.json"), reverse=True):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            trade_count = len(raw) if isinstance(raw, list) else 0
        except Exception:
            trade_count = 0
        stat = path.stat()
        backups.append({
            "filename": path.name,
            "path": str(path),
            "size_bytes": stat.st_size,
            "trade_count": trade_count,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return backups


def restore_trades_from_backup(filename: str) -> dict:
    path = _resolve_trade_backup(filename)
    if not path.exists():
        raise FileNotFoundError(f"找不到交易備份：{filename}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("備份內容不是交易紀錄陣列")

    trades = [TradeRecord(**item) for item in raw]
    current_backup = backup_trades()
    save_trades(trades)
    return {
        "restored_from": filename,
        "restored_count": len(trades),
        "backup_path": str(current_backup) if current_backup else None,
    }


def save_trades(trades: list[TradeRecord]) -> None:
    _ensure_file()
    atomic_write_text(
        _TRADES_FILE,
        json.dumps([t.model_dump() for t in trades], ensure_ascii=False, indent=2),
    )
