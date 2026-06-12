from pydantic import BaseModel


class DecisionJournalCreate(BaseModel):
    date: str
    code: str
    name: str
    decision: str
    reason: str
    price: float | None = None
    shares: int | None = None
    key_price: str | None = None
    invalidation: str | None = None
    source: str = "manual"


class DecisionJournalEntry(DecisionJournalCreate):
    id: str
    created_at: str
    updated_at: str | None = None
    workflow_status: str | None = None
    workflow_headline: str | None = None


class DecisionJournalSummary(BaseModel):
    date: str | None = None
    total_count: int
    by_decision: dict[str, int]
    recent_codes: list[str]


class DecisionJournalBulkCreateRequest(BaseModel):
    date: str | None = None
    limit: int | None = None


class DecisionJournalBulkCreateResult(BaseModel):
    date: str
    total_task_count: int
    created_count: int
    skipped_count: int
    skipped_codes: list[str]
    created_entries: list[DecisionJournalEntry]
