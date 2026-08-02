"""保存美股每日觀察分桶，讓這些訊號日後驗得回來。

美股沒有台股那種每日訊號流程，分桶只存在於報告產生的那一瞬間。不存下來，
「當時看到什麼」隔天就消失了，證據狀態也就永遠是樣本 0。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.storage.atomic_write import atomic_write_text

_BACKEND = Path(__file__).resolve().parents[2]
_OUT = _BACKEND / "out"
SNAPSHOT_DIR_NAME = "us_signal_snapshots"

# 只有這一桶代表「當天真的可以記一筆」；其餘桶保存但不計分
TRACKABLE_BUCKET = "enter"


def _snapshot_filename(as_of: str) -> str:
    safe = str(as_of).strip()
    if not safe or "/" in safe or "\\" in safe or ".." in safe:
        raise ValueError("美股快照 as_of 不合法")
    return f"us_signal_snapshot_{safe}.json"


def build_us_signal_snapshot(
    rows: list[Any],
    trend_gate: dict[str, Any],
    wbottom_gate: dict[str, Any],
    as_of: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    items = [{
        "code": row.code,
        "label": row.label,
        "bucket": row.bucket,
        "group": row.group,
        "action": row.action,
        "strategy": row.strategy,
        "close": row.close,
        "trigger": row.trigger,
        "trigger_note": row.trigger_note,
        "invalidation": row.invalidation,
        "target": row.target,
        "reward_risk": row.reward_risk,
        "reason": row.reason,
    } for row in rows]
    return {
        "as_of": as_of,
        "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        "market_gates": {
            "trend_bias": trend_gate.get("bias"),
            "trend_active": bool(trend_gate.get("active")),
            "wbottom_active": bool(wbottom_gate.get("active")),
        },
        "item_count": len(items),
        "trackable_count": sum(1 for item in items if item["bucket"] == TRACKABLE_BUCKET),
        "items": items,
    }


def write_us_signal_snapshot(
    snapshot: dict[str, Any], out_dir: Path | None = None
) -> Path:
    """同一資料日重複執行覆寫既有快照，不新增第二份。"""
    out_dir = out_dir or _OUT
    snapshot_dir = out_dir / SNAPSHOT_DIR_NAME
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / _snapshot_filename(snapshot["as_of"])
    atomic_write_text(path, json.dumps(snapshot, ensure_ascii=False, indent=2))
    return path
