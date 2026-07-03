from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.storage.atomic_write import atomic_write_text

_BACKEND = Path(__file__).resolve().parents[2]
_OUT = _BACKEND / "out"
SNAPSHOT_DIR_NAME = "signal_snapshots"
REVIEW_FILENAME = "signal_snapshot_review.json"


def _snapshot_filename(as_of: str) -> str:
    safe = str(as_of).strip()
    if not safe or "/" in safe or "\\" in safe or ".." in safe:
        raise ValueError("snapshot as_of 不合法")
    return f"signal_snapshot_{safe}.json"


def _compact_signal(sig: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": sig.get("code"),
        "name": sig.get("name"),
        "close": sig.get("close"),
        "internal_signal": sig.get("internal_signal"),
        "signal": sig.get("signal"),
        "daily_action": sig.get("daily_action"),
        "daily_action_label": sig.get("daily_action_label"),
        "daily_action_reason": sig.get("daily_action_reason"),
        "daily_key_price": sig.get("daily_key_price"),
        "daily_invalidation": sig.get("daily_invalidation"),
        "price_plan_note": sig.get("price_plan_note"),
        "support_source": sig.get("support_source"),
        "resistance_source": sig.get("resistance_source"),
        "entry_source": sig.get("entry_source"),
        "stop_source": sig.get("stop_source"),
        "target_source": sig.get("target_source"),
        "old_wang_flag": sig.get("old_wang_flag"),
        "old_wang_score": sig.get("old_wang_score"),
        "steady_momentum_flag": sig.get("steady_momentum_flag"),
        "steady_momentum_score": sig.get("steady_momentum_score"),
        "holding_shares": sig.get("holding_shares"),
        "holding_position_pct": sig.get("holding_position_pct"),
    }


def build_signal_snapshot(summary: dict[str, Any]) -> dict[str, Any]:
    as_of = str(summary.get("as_of") or "")
    if not as_of:
        raise ValueError("summary 缺少 as_of，無法建立 signal snapshot")
    items = [_compact_signal(sig) for sig in summary.get("signals") or []]
    return {
        "as_of": as_of,
        "generated_at": summary.get("generated_at"),
        "rules_version": summary.get("rules_version"),
        "rules_metadata": summary.get("rules_metadata") or {},
        "batch_id": summary.get("batch_id"),
        "lineage": summary.get("lineage"),
        "universe_size": summary.get("universe_size"),
        "data_ok_count": summary.get("data_ok_count"),
        "data_missing_count": summary.get("data_missing_count"),
        "item_count": len(items),
        "items": items,
    }


def write_signal_snapshot(summary: dict[str, Any], out_dir: Path | None = None) -> Path:
    out_dir = out_dir or _OUT
    snapshot = build_signal_snapshot(summary)
    snapshot_dir = out_dir / SNAPSHOT_DIR_NAME
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / _snapshot_filename(snapshot["as_of"])
    atomic_write_text(path, json.dumps(snapshot, ensure_ascii=False, indent=2))
    return path


def _load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_previous_snapshot(as_of: str, out_dir: Path | None = None) -> dict[str, Any] | None:
    out_dir = out_dir or _OUT
    snapshot_dir = out_dir / SNAPSHOT_DIR_NAME
    if not snapshot_dir.exists():
        return None
    candidates: list[tuple[str, Path]] = []
    for path in snapshot_dir.glob("signal_snapshot_*.json"):
        try:
            snapshot_as_of = str(_load_snapshot(path).get("as_of") or "")
        except Exception:
            continue
        if snapshot_as_of and snapshot_as_of < as_of:
            candidates.append((snapshot_as_of, path))
    if not candidates:
        return None
    _prev_as_of, prev_path = sorted(candidates, key=lambda item: item[0])[-1]
    return _load_snapshot(prev_path)


def _review_outcome(prev: dict[str, Any], current: dict[str, Any] | None) -> tuple[str, str]:
    if current is None:
        return "missing_current", "前次快照有計畫，但本次訊號清單缺少此股票。"

    prev_action = str(prev.get("daily_action") or "")
    current_action = str(current.get("daily_action") or "")
    current_signal = str(current.get("internal_signal") or "")
    risk_actions = {"reduce", "exit", "avoid"}
    constructive_actions = {"enter", "wait_pullback", "hold", "long_watch"}

    if prev_action in {"enter", "wait_pullback", "hold", "long_watch"} and (
        current_action in risk_actions or current_signal in {"exit_warning", "invalidated", "DATA_MISSING"}
    ):
        return "risk_triggered", "前次快照計畫轉為風險或暫不進場，需復盤失效條件。"

    if prev_action in {"reduce", "exit"} and current_action in constructive_actions:
        return "risk_eased", "前次快照風險計畫已轉為較健康狀態，可重新評估。"

    if prev_action != current_action:
        return "action_changed", f"前次快照動作由 {prev_action or '未知'} 變為 {current_action or '未知'}。"

    return "unchanged", "前次快照動作未改變，依原計畫追蹤。"


def build_signal_snapshot_review(summary: dict[str, Any], previous_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    current_snapshot = build_signal_snapshot(summary)
    if not previous_snapshot:
        return {
            "as_of": current_snapshot["as_of"],
            "previous_as_of": None,
            "generated_at": summary.get("generated_at"),
            "rules_version": summary.get("rules_version"),
            "rules_metadata": summary.get("rules_metadata") or {},
            "status": "no_previous_snapshot",
            "outcome_counts": {},
            "items": [],
        }

    current_by_code = {str(item.get("code")): item for item in current_snapshot["items"] if item.get("code")}
    items: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for prev in previous_snapshot.get("items") or []:
        code = str(prev.get("code") or "")
        if not code:
            continue
        current = current_by_code.get(code)
        outcome, reason = _review_outcome(prev, current)
        counts[outcome] += 1
        items.append({
            "code": code,
            "name": prev.get("name") or (current or {}).get("name"),
            "previous_action": prev.get("daily_action"),
            "previous_label": prev.get("daily_action_label"),
            "previous_close": prev.get("close"),
            "previous_key_price": prev.get("daily_key_price"),
            "previous_invalidation": prev.get("daily_invalidation"),
            "current_action": (current or {}).get("daily_action"),
            "current_label": (current or {}).get("daily_action_label"),
            "current_close": (current or {}).get("close"),
            "current_signal": (current or {}).get("internal_signal"),
            "outcome": outcome,
            "reason": reason,
        })

    return {
        "as_of": current_snapshot["as_of"],
        "previous_as_of": previous_snapshot.get("as_of"),
        "generated_at": summary.get("generated_at"),
        "rules_version": summary.get("rules_version"),
        "rules_metadata": summary.get("rules_metadata") or {},
        "status": "reviewed",
        "outcome_counts": dict(counts),
        "items": items,
    }


def write_signal_snapshot_review(summary: dict[str, Any], out_dir: Path | None = None) -> Path:
    out_dir = out_dir or _OUT
    as_of = str(summary.get("as_of") or "")
    previous = find_previous_snapshot(as_of, out_dir)
    review = build_signal_snapshot_review(summary, previous)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / REVIEW_FILENAME
    atomic_write_text(path, json.dumps(review, ensure_ascii=False, indent=2))
    return path


def write_snapshot_and_review(summary: dict[str, Any], out_dir: Path | None = None) -> dict[str, Path]:
    out_dir = out_dir or _OUT
    review_path = write_signal_snapshot_review(summary, out_dir)
    snapshot_path = write_signal_snapshot(summary, out_dir)
    return {"review_path": review_path, "snapshot_path": snapshot_path}
