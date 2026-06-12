import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.models.trade import (
    BuyRequest,
    SellRequest,
    TradeBackupInfo,
    TradeClearRequest,
    TradeClearResult,
    TradeImportRequest,
    TradeImportResult,
    TradeImportValidationResult,
    TradeRestoreRequest,
    TradeRestoreResult,
    TradeRecord,
)
from app.services.trade_service import (
    calculate_positions,
    calculate_trade_amounts,
    clear_trades,
    get_trade_backups,
    import_trades,
    preview_import_trades,
    restore_trades_backup,
    validate_import_trades,
)
from app.storage.json_store import load_trades, save_trades

router = APIRouter()


@router.get("/trades", response_model=list[TradeRecord])
def list_trades() -> list[TradeRecord]:
    return load_trades()


@router.get("/trades/backups", response_model=list[TradeBackupInfo])
def list_trade_backup_files() -> list[dict]:
    return get_trade_backups()


@router.post("/trades/backups/restore", response_model=TradeRestoreResult)
def restore_trade_backup_file(req: TradeRestoreRequest) -> dict:
    try:
        return restore_trades_backup(filename=req.filename, confirm=req.confirm)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/trades/import", response_model=TradeImportResult)
def import_trade_records(req: TradeImportRequest) -> dict:
    try:
        return import_trades(req.trades, backup=req.backup)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/trades/import/preview", response_model=TradeImportResult)
def preview_import_trade_records(req: TradeImportRequest) -> dict:
    try:
        return preview_import_trades(req.trades)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/trades/import/validate", response_model=TradeImportValidationResult)
def validate_import_trade_records(req: TradeImportRequest) -> dict:
    return validate_import_trades(req.trades)


@router.post("/trades/clear", response_model=TradeClearResult)
def clear_trade_records(req: TradeClearRequest) -> dict:
    try:
        return clear_trades(confirm=req.confirm, backup=req.backup)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/trades/buy", response_model=TradeRecord, status_code=201)
def buy_stock(req: BuyRequest) -> TradeRecord:
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="買入股數必須大於 0")
    if req.price <= 0:
        raise HTTPException(status_code=400, detail="買入價格必須大於 0")

    trades = load_trades()
    record = TradeRecord(
        id=str(uuid.uuid4()),
        stock_id=req.stock_id.strip().upper(),
        name=req.name.strip(),
        trade_type="buy",
        date=req.date,
        price=req.price,
        shares=req.shares,
        **calculate_trade_amounts("buy", req.price, req.shares),
        note=req.note,
        created_at=datetime.now().isoformat(),
    )
    trades.append(record)
    save_trades(trades)
    return record


@router.post("/trades/sell", response_model=TradeRecord, status_code=201)
def sell_stock(req: SellRequest) -> TradeRecord:
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="賣出股數必須大於 0")
    if req.price <= 0:
        raise HTTPException(status_code=400, detail="賣出價格必須大於 0")

    trades = load_trades()

    # 驗證持股是否足夠
    positions = calculate_positions(trades)
    sid = req.stock_id.strip().upper()
    pos = next((p for p in positions if p.stock_id == sid), None)
    available = pos.total_shares if pos else 0
    if available < req.shares:
        raise HTTPException(
            status_code=400,
            detail=f"可賣出股數不足，目前持有 {available} 股",
        )

    # 從買入紀錄取得股票名稱
    name = next((t.name for t in trades if t.stock_id == sid), sid)

    record = TradeRecord(
        id=str(uuid.uuid4()),
        stock_id=sid,
        name=name,
        trade_type="sell",
        date=req.date,
        price=req.price,
        shares=req.shares,
        **calculate_trade_amounts("sell", req.price, req.shares),
        note=req.note,
        created_at=datetime.now().isoformat(),
    )
    trades.append(record)
    save_trades(trades)
    return record
