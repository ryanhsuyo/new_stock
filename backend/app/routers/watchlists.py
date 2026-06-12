"""
watchlists.py — 觀察清單路由

GET    /watchlists                       取得所有群組
POST   /watchlists                       建立群組
DELETE /watchlists/{group}               刪除群組
POST   /watchlists/{group}/stocks        加入股票
DELETE /watchlists/{group}/stocks/{code} 移除股票
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.storage.watchlist_store import (
    add_stock,
    create_group,
    delete_group,
    get_all_groups,
    remove_stock,
)

router = APIRouter()


# ── Request models ─────────────────────────────────────────────────────────────

class CreateGroupRequest(BaseModel):
    name: str


class AddStockRequest(BaseModel):
    code: str
    name: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/watchlists")
def list_watchlists() -> list[dict]:
    """取得所有觀察清單群組（含各群組的股票列表）。"""
    return get_all_groups()


@router.post("/watchlists", status_code=201)
def create_watchlist(req: CreateGroupRequest) -> dict:
    """建立新群組。群組名稱已存在時回傳 409。"""
    try:
        return create_group(req.name.strip())
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/watchlists/{group}")
def delete_watchlist(group: str) -> dict:
    """刪除整個群組（含群組內所有股票）。"""
    try:
        delete_group(group)
        return {"deleted": group}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/watchlists/{group}/stocks")
def add_to_watchlist(group: str, req: AddStockRequest) -> dict:
    """
    將股票加入指定群組。冪等：若股票已在群組中，靜默跳過。
    群組不存在時回傳 404。
    """
    try:
        return add_stock(group, req.code.strip(), req.name.strip())
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/watchlists/{group}/stocks/{code}")
def remove_from_watchlist(group: str, code: str) -> dict:
    """從群組中移除指定股票。群組不存在時回傳 404。"""
    try:
        return remove_stock(group, code)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
