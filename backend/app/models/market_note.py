from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class MarketNoteInput(BaseModel):
    date: str = Field(..., description="筆記日期 YYYY-MM-DD")
    title: str
    risk_level: str = "neutral"
    source: str = "manual_api"
    headline: str
    position_guidance: str | None = None
    market_actions: list[str] = Field(default_factory=list)
    index_notes: list[str] = Field(default_factory=list)
    stock_notes: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        datetime.strptime(value, "%Y-%m-%d")
        return value

    @field_validator("title", "headline")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required text cannot be empty")
        return value.strip()
