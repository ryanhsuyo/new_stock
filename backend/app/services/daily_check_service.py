"""每日 PM 摘要報告讀取服務。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parent.parent.parent
_OUT = _BACKEND / "out"
_REFRESH_COMMAND = "python3 scripts/daily_check.py --write-report"
_REFRESH_EXPECTED_OUTPUTS = ["backend/out/daily_check.json"]


def _refresh_payload() -> dict[str, Any]:
    return {
        "snapshot_refresh_command": _REFRESH_COMMAND,
        "snapshot_refresh_copy_command": f"cd {_BACKEND}\n{_REFRESH_COMMAND}",
        "snapshot_refresh_expected_outputs": _REFRESH_EXPECTED_OUTPUTS,
    }


def _snapshot_freshness(data: dict[str, Any]) -> dict[str, Any]:
    generated_at = str(data.get("generated_at") or "")
    today = date.today().isoformat()
    if not generated_at:
        return {
            "snapshot_is_stale": True,
            "snapshot_stale_reason": "Daily Check 快照缺少產生日，請重新產生每日摘要。",
            **_refresh_payload(),
        }

    try:
        generated_date = date.fromisoformat(generated_at[:10]).isoformat()
    except ValueError:
        return {
            "snapshot_is_stale": True,
            "snapshot_stale_reason": f"Daily Check 快照產生日格式無法判讀：{generated_at}，請重新產生每日摘要。",
            **_refresh_payload(),
        }

    if generated_date < today:
        return {
            "snapshot_is_stale": True,
            "snapshot_stale_reason": f"Daily Check 快照產生於 {generated_date}，今天是 {today}，請重新產生每日摘要。",
            **_refresh_payload(),
        }

    return {
        "snapshot_is_stale": False,
        "snapshot_stale_reason": "",
        **_refresh_payload(),
    }


def get_daily_check_report() -> dict[str, Any] | None:
    """讀取 backend/out/daily_check.json；不存在或格式錯誤時回傳 None。"""
    path = _OUT / "daily_check.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return {**data, **_snapshot_freshness(data)}
