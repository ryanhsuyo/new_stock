"""US-only background update orchestration; never touches Taiwan data."""

from __future__ import annotations

import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from app.storage.us_update_store import load_us_update_status, save_us_update_status

_LOCK = threading.Lock()
_BACKEND = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _BACKEND / "scripts" / "backfill_ohlcv_us.py"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _run_us_backfill(months: int) -> tuple[bool, str]:
    result = subprocess.run([sys.executable, str(_SCRIPT), "--months", str(months)], capture_output=True, text=True, encoding="utf-8")
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    return result.returncode == 0, output


def _worker(months: int) -> None:
    try:
        ok, output = _run_us_backfill(months)
        save_us_update_status({"status": "success" if ok else "failed", "started_at": load_us_update_status().get("started_at"), "finished_at": _now(), "error": None if ok else (output[-2000:] or "US backfill failed"), "months": months})
    except Exception as exc:  # background boundary: persist unexpected failures
        save_us_update_status({"status": "failed", "started_at": load_us_update_status().get("started_at"), "finished_at": _now(), "error": str(exc), "months": months})
    finally:
        _LOCK.release()


def trigger_us_background_update(months: int = 1) -> dict:
    if months < 1 or months > 60:
        raise ValueError("months 必須介於 1 與 60")
    if not _LOCK.acquire(blocking=False):
        raise RuntimeError("美股資料更新已在執行中")
    status = {"status": "running", "started_at": _now(), "finished_at": None, "error": None, "months": months}
    save_us_update_status(status)
    threading.Thread(target=_worker, args=(months,), daemon=True).start()
    return status


def get_us_update_status() -> dict:
    return load_us_update_status()
