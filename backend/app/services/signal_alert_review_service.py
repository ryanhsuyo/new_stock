from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app.storage.atomic_write import atomic_write_text
from app.services.signal_alert_service import ALERTS_FILENAME, load_signal_alerts

_BACKEND = Path(__file__).resolve().parents[2]
_OUT = _BACKEND / "out"
_DATA = _BACKEND / "data"
REVIEWS_FILENAME = "signal_alert_reviews.json"


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _canonical_alerts_payload(alerts: dict[str, Any]) -> dict[str, Any]:
    normalized_alerts = []
    for item in alerts.get("alerts") or []:
        if not isinstance(item, dict):
            continue
        normalized_alerts.append({
            key: item.get(key)
            for key in sorted(item.keys())
            if key not in {"generated_at"}
        })
    normalized_alerts.sort(
        key=lambda item: (
            str(item.get("severity") or ""),
            str(item.get("outcome") or ""),
            str(item.get("code") or ""),
            json.dumps(item, ensure_ascii=False, sort_keys=True),
        )
    )
    return {
        "as_of": alerts.get("as_of"),
        "previous_as_of": alerts.get("previous_as_of"),
        "rules_version": alerts.get("rules_version"),
        "rules_metadata": alerts.get("rules_metadata") or {},
        "alert_count": int(alerts.get("alert_count") or 0),
        "severity_counts": alerts.get("severity_counts") or {},
        "alerts": normalized_alerts,
    }


def signal_alert_fingerprint(alerts: dict[str, Any] | None) -> str | None:
    if not alerts:
        return None
    payload = _canonical_alerts_payload(alerts)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _reviews_path(out_dir: Path | None = None) -> Path:
    if out_dir is None or out_dir == _OUT:
        return _DATA / REVIEWS_FILENAME
    return out_dir / REVIEWS_FILENAME


def _load_reviews(out_dir: Path | None = None) -> dict[str, Any]:
    path = _reviews_path(out_dir)
    if not path.exists():
        return {"reviews": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"reviews": []}
    return data if isinstance(data, dict) else {"reviews": []}


def _find_review(reviews: dict[str, Any], fingerprint: str | None) -> dict[str, Any] | None:
    if not fingerprint:
        return None
    for review in reviews.get("reviews") or []:
        if isinstance(review, dict) and review.get("fingerprint") == fingerprint:
            return review
    return None


def _refresh_daily_check_safely() -> None:
    try:
        scripts_dir = _BACKEND / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        from app.services.today_scan_service import load_today_scan_report
        from daily_check import build_daily_summary, load_summary_for_daily_check, write_daily_summary
        from doctor import build_doctor_report

        report = build_doctor_report(_BACKEND)
        summary = build_daily_summary(
            report,
            limit=3,
            signal_alerts=load_signal_alerts(_BACKEND / "out"),
            signal_alert_review=get_signal_alert_review_status(out_dir=_BACKEND / "out"),
            today_scan=load_today_scan_report(_BACKEND / "out"),
            signals_summary=load_summary_for_daily_check(_BACKEND),
            include_official_coverage=True,
        )
        write_daily_summary(summary, _BACKEND)
    except Exception:
        # The review ledger is the source of truth; Daily Check can be regenerated later.
        pass


def get_signal_alert_review_status(
    alerts: dict[str, Any] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    out_dir = out_dir or _OUT
    alerts = alerts if alerts is not None else load_signal_alerts(out_dir)
    alert_count = int((alerts or {}).get("alert_count") or 0)
    fingerprint = signal_alert_fingerprint(alerts)
    reviews = _load_reviews(out_dir)
    matched = _find_review(reviews, fingerprint)
    latest_review = (reviews.get("reviews") or [])[-1] if reviews.get("reviews") else None
    reviewed = bool(matched)
    return {
        "alerts_file": f"backend/out/{ALERTS_FILENAME}",
        "reviews_file": (
            f"backend/data/{REVIEWS_FILENAME}"
            if out_dir == _OUT
            else str(_reviews_path(out_dir))
        ),
        "review_required": alert_count > 0 and not reviewed,
        "reviewed": reviewed,
        "current_fingerprint": fingerprint,
        "latest_reviewed_fingerprint": (latest_review or {}).get("fingerprint") if isinstance(latest_review, dict) else None,
        "alert_count": alert_count,
        "as_of": (alerts or {}).get("as_of"),
        "previous_as_of": (alerts or {}).get("previous_as_of"),
        "severity_counts": (alerts or {}).get("severity_counts") or {},
        "reviewed_at": (matched or {}).get("reviewed_at"),
        "reviewer": (matched or {}).get("reviewer"),
        "note": (matched or {}).get("note"),
    }


def acknowledge_current_signal_alerts(
    reviewer: str = "manual",
    note: str | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    out_dir = out_dir or _OUT
    alerts = load_signal_alerts(out_dir)
    alert_count = int((alerts or {}).get("alert_count") or 0)
    fingerprint = signal_alert_fingerprint(alerts)
    if not alerts or not fingerprint or alert_count <= 0:
        return get_signal_alert_review_status(alerts, out_dir)

    reviews = _load_reviews(out_dir)
    existing = _find_review(reviews, fingerprint)
    if existing is None:
        existing = {
            "fingerprint": fingerprint,
            "as_of": alerts.get("as_of"),
            "previous_as_of": alerts.get("previous_as_of"),
            "alert_count": alert_count,
            "severity_counts": alerts.get("severity_counts") or {},
        }
        reviews.setdefault("reviews", []).append(existing)

    existing["reviewed_at"] = _utc_now_iso()
    existing["reviewer"] = reviewer or "manual"
    existing["note"] = note or None
    path = _reviews_path(out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(reviews, ensure_ascii=False, indent=2))
    _refresh_daily_check_safely()
    return get_signal_alert_review_status(alerts, out_dir)
