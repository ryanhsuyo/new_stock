"""
market_note_service.py — 人工盤後筆記整理與 upsert。
"""

from datetime import datetime

from app.storage.market_note_store import load_market_notes, save_market_notes


def list_market_notes() -> list[dict]:
    notes = load_market_notes()
    return sorted(notes, key=lambda item: str(item.get("date", "")), reverse=True)


def upsert_market_note(note: dict) -> dict:
    normalized = _normalize_note(note)
    notes = load_market_notes()
    replaced = False
    result: list[dict] = []

    for existing in notes:
        if str(existing.get("date", "")) == normalized["date"]:
            if not replaced:
                result.append(normalized)
                replaced = True
            continue
        result.append(existing)

    if not replaced:
        result.append(normalized)

    result = sorted(result, key=lambda item: str(item.get("date", "")), reverse=True)
    save_market_notes(result)
    return {
        "saved": normalized,
        "count": len(result),
        "replaced": replaced,
        "signals_rerun_required": True,
        "next_step": "POST /api/stocks/signals/run",
    }


def _normalize_note(note: dict) -> dict:
    list_fields = ("market_actions", "index_notes", "stock_notes", "rules")
    normalized = {
        "date": str(note.get("date", "")).strip(),
        "title": str(note.get("title", "")).strip(),
        "risk_level": str(note.get("risk_level", "neutral")).strip() or "neutral",
        "source": str(note.get("source", "manual_api")).strip() or "manual_api",
        "headline": str(note.get("headline", "")).strip(),
    }
    if note.get("position_guidance"):
        normalized["position_guidance"] = str(note.get("position_guidance", "")).strip()
    for field in list_fields:
        values = note.get(field)
        if values is None:
            continue
        if isinstance(values, list):
            normalized[field] = [str(value).strip() for value in values if str(value).strip()]
        else:
            normalized[field] = [str(values).strip()] if str(values).strip() else []
    _validate_note(normalized)
    return normalized


def _validate_note(note: dict) -> None:
    try:
        datetime.strptime(str(note.get("date", "")), "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc
    if not str(note.get("title", "")).strip():
        raise ValueError("title is required")
    if not str(note.get("headline", "")).strip():
        raise ValueError("headline is required")
