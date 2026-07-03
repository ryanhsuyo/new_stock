from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.storage.atomic_write import atomic_write_text

_BACKEND = Path(__file__).resolve().parents[2]
_OUT = _BACKEND / "out"
ALERTS_FILENAME = "signal_alerts.json"

_OUTCOME_META = {
    "risk_triggered": ("block", "持股/候選轉風險"),
    "missing_current": ("warn", "前日計畫缺少本日資料"),
    "action_changed": ("warn", "前次快照以來動作變更"),
    "risk_eased": ("info", "風險解除觀察"),
}

_OUTCOME_ACTIONS = {
    "risk_triggered": {
        "action_label": "先復盤風險",
        "next_action": "檢查前次進場/持股失效條件、目前訊號與停損價，必要時列入今日風險處理。",
        "review_focus": [
            "previous_action",
            "current_action",
            "previous_key_price",
            "previous_invalidation",
            "current_signal",
        ],
    },
    "missing_current": {
        "action_label": "補資料",
        "next_action": "確認本日 universe_report 是否缺少該股票；若是資料缺口，先補日線後重跑訊號。",
        "review_focus": ["previous_action", "previous_key_price", "previous_invalidation"],
    },
    "action_changed": {
        "action_label": "比對動作",
        "next_action": "比對前次與本次 daily_action，確認是否只是正常狀態切換，或需要補決策日誌。",
        "review_focus": ["previous_action", "current_action", "previous_label", "current_label"],
    },
    "risk_eased": {
        "action_label": "重新評估",
        "next_action": "風險已緩和；重新檢查進場區間、量能與大盤濾網，不直接視為買進訊號。",
        "review_focus": ["previous_action", "current_action", "current_signal"],
    },
}


def _alert_from_review_item(item: dict[str, Any]) -> dict[str, Any] | None:
    outcome = str(item.get("outcome") or "")
    if outcome == "unchanged":
        return None
    meta = _OUTCOME_META.get(outcome)
    if meta is None:
        return None
    severity, title = meta
    code = str(item.get("code") or "")
    name = str(item.get("name") or code)
    action = _OUTCOME_ACTIONS.get(outcome, {})
    return {
        "code": code,
        "name": name,
        "severity": severity,
        "outcome": outcome,
        "title": title,
        "message": item.get("reason") or title,
        "action_label": action.get("action_label") or "查看警示",
        "next_action": action.get("next_action") or "查看前次與本次訊號差異，再決定是否需要復盤。",
        "review_focus": list(action.get("review_focus") or []),
        "previous_action": item.get("previous_action"),
        "previous_label": item.get("previous_label"),
        "previous_close": item.get("previous_close"),
        "previous_key_price": item.get("previous_key_price"),
        "previous_invalidation": item.get("previous_invalidation"),
        "current_action": item.get("current_action"),
        "current_label": item.get("current_label"),
        "current_close": item.get("current_close"),
        "current_signal": item.get("current_signal"),
    }


def build_signal_alerts(review: dict[str, Any]) -> dict[str, Any]:
    status = str(review.get("status") or "unknown")
    as_of = review.get("as_of")
    previous_as_of = review.get("previous_as_of")
    window_label = (
        f"{previous_as_of} 至 {as_of}"
        if previous_as_of and as_of
        else "前次快照以來"
    )
    alerts = [
        alert
        for item in review.get("items") or []
        if (alert := _alert_from_review_item(item)) is not None
    ]
    severity_counts = Counter(str(alert.get("severity") or "unknown") for alert in alerts)
    if status == "no_previous_snapshot":
        message = "尚無前次 signal snapshot，今日不產生快照變化警示。"
    elif alerts:
        message = f"偵測到 {len(alerts)} 筆訊號快照變化警示（{window_label}）。"
    else:
        message = f"訊號快照無需處理的新警示（{window_label}）。"

    return {
        "as_of": as_of,
        "previous_as_of": previous_as_of,
        "snapshot_window_label": window_label,
        "generated_at": review.get("generated_at"),
        "rules_version": review.get("rules_version"),
        "rules_metadata": review.get("rules_metadata") or {},
        "status": status,
        "alert_count": len(alerts),
        "severity_counts": dict(severity_counts),
        "alerts": alerts,
        "message": message,
    }


def write_signal_alerts(review: dict[str, Any], out_dir: Path | None = None) -> Path:
    out_dir = out_dir or _OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ALERTS_FILENAME
    payload = build_signal_alerts(review)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def load_signal_alerts(out_dir: Path | None = None) -> dict[str, Any] | None:
    out_dir = out_dir or _OUT
    path = out_dir / ALERTS_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
