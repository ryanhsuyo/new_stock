import json
from pathlib import Path

from app.models.decision_journal import DecisionJournalEntry
from app.storage.atomic_write import atomic_write_text

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
DECISION_JOURNAL_PATH = _DATA_DIR / "decision_journal.json"


def _ensure_file() -> None:
    _DATA_DIR.mkdir(exist_ok=True)
    if not DECISION_JOURNAL_PATH.exists():
        atomic_write_text(DECISION_JOURNAL_PATH, "[]")


def load_decision_journal() -> list[DecisionJournalEntry]:
    _ensure_file()
    raw = json.loads(DECISION_JOURNAL_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("decision_journal.json 必須是陣列")
    return [DecisionJournalEntry(**item) for item in raw]


def save_decision_journal(entries: list[DecisionJournalEntry]) -> None:
    _ensure_file()
    atomic_write_text(
        DECISION_JOURNAL_PATH,
        json.dumps([entry.model_dump() for entry in entries], ensure_ascii=False, indent=2),
    )
