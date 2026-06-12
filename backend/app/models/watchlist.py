"""
watchlist.py — 觀察清單的 Pydantic 模型
"""
from pydantic import BaseModel


class WatchlistItem(BaseModel):
    code: str
    name: str
    added_at: str   # YYYY-MM-DD


class WatchlistGroup(BaseModel):
    name: str
    stocks: list[WatchlistItem] = []
