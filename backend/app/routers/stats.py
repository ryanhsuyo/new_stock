from typing import Literal

from fastapi import APIRouter, Query

from app.models.trade import Stats
from app.services.trade_service import calculate_stats
from app.storage.json_store import load_trades

router = APIRouter()


@router.get("/stats", response_model=Stats)
def get_stats(
    period: Literal["monthly", "all"] = Query(default="all"),
) -> Stats:
    return calculate_stats(load_trades(), period)
