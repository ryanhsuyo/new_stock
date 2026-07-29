"""Read-only storage for manually verified official market events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "official_market_events.json"


def load_official_market_events(path: Path = DEFAULT_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {"verified_at": None, "verification_note": "", "events": []}
    if not isinstance(payload, dict):
        return {"verified_at": None, "verification_note": "", "events": []}
    events = payload.get("events")
    return {
        "verified_at": payload.get("verified_at"),
        "verification_note": str(payload.get("verification_note") or ""),
        "events": [item for item in events if isinstance(item, dict)] if isinstance(events, list) else [],
    }
