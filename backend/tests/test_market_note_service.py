import json

import pytest

import app.storage.market_note_store as store
from app.services.market_note_service import list_market_notes, upsert_market_note


def test_upsert_market_note_creates_file_and_sorts_desc(tmp_path, monkeypatch):
    notes_path = tmp_path / "market_notes.json"
    monkeypatch.setattr(store, "MARKET_NOTES_PATH", notes_path)

    first = upsert_market_note({
        "date": "2026-05-19",
        "title": "5/19 盤後筆記",
        "risk_level": "risk",
        "headline": "TSE/OTC 轉弱，先降追價。",
    })
    second = upsert_market_note({
        "date": "2026-05-20",
        "title": "5/20 盤後筆記",
        "risk_level": "caution",
        "headline": "盤中仍觀察 MA10。",
    })

    notes = json.loads(notes_path.read_text(encoding="utf-8"))
    assert first["replaced"] is False
    assert second["replaced"] is False
    assert second["signals_rerun_required"] is True
    assert second["next_step"] == "POST /api/stocks/signals/run"
    assert [note["date"] for note in notes] == ["2026-05-20", "2026-05-19"]


def test_upsert_market_note_replaces_same_date(tmp_path, monkeypatch):
    notes_path = tmp_path / "market_notes.json"
    notes_path.write_text(
        json.dumps([
            {"date": "2026-05-19", "title": "舊標題", "risk_level": "risk", "headline": "舊內容"}
        ], ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(store, "MARKET_NOTES_PATH", notes_path)

    result = upsert_market_note({
        "date": "2026-05-19",
        "title": "新標題",
        "risk_level": "caution",
        "headline": "新內容",
        "market_actions": ["看 MA10"],
    })

    notes = list_market_notes()
    assert result["replaced"] is True
    assert len(notes) == 1
    assert notes[0]["title"] == "新標題"
    assert notes[0]["market_actions"] == ["看 MA10"]


@pytest.mark.parametrize("payload", [
    {"date": "2026/05/20", "title": "筆記", "headline": "內容"},
    {"date": "2026-05-20", "title": "", "headline": "內容"},
    {"date": "2026-05-20", "title": "筆記", "headline": ""},
])
def test_upsert_market_note_rejects_invalid_required_fields(tmp_path, monkeypatch, payload):
    notes_path = tmp_path / "market_notes.json"
    monkeypatch.setattr(store, "MARKET_NOTES_PATH", notes_path)

    with pytest.raises(ValueError):
        upsert_market_note(payload)

    assert not notes_path.exists()
