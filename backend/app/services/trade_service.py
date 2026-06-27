"""
交易商業邏輯：持倉計算、損益計算、統計。
使用加權平均成本法（WAC）計算損益。
"""
import uuid
from datetime import date, datetime
from typing import Any

from app.models.trade import Position, Stats, TradeImportItem, TradeRecord
from app.services.stock_service import get_all_current_prices
from app.storage.json_store import (
    backup_trades,
    list_trade_backups,
    load_trades,
    restore_trades_from_backup,
    save_trades,
)
from app.storage.name_store import load_stock_names
from app.storage.settings_store import load_trading_settings


_AMOUNT_FIELDS = ("gross_amount", "fee", "tax", "net_amount")


def calculate_trade_amounts(
    trade_type: str,
    price: float,
    shares: int,
    settings: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    台股交易金額估算。

    預設：
    - 買賣手續費 0.1425%
    - 賣出證交稅 0.3%
    - 可由 backend/data/settings.json 調整券商折扣與最低手續費
    """
    settings = settings if settings is not None else load_trading_settings()
    gross = round(price * shares)
    raw_fee = gross * settings["brokerage_fee_rate"] * settings["brokerage_discount"]
    fee = round(raw_fee)
    if gross > 0 and settings["min_brokerage_fee"] > 0:
        fee = max(fee, round(settings["min_brokerage_fee"]))
    tax = round(gross * settings["sell_transaction_tax_rate"]) if trade_type == "sell" else 0
    net = gross + fee if trade_type == "buy" else gross - fee - tax
    return {
        "gross_amount": float(gross),
        "fee": float(fee),
        "tax": float(tax),
        "net_amount": float(net),
    }


def trade_net_amount(t: TradeRecord) -> float:
    if t.net_amount is not None:
        return t.net_amount
    return calculate_trade_amounts(t.trade_type, t.price, t.shares)["net_amount"]


def normalize_trade_names(trades: list[TradeRecord], names: dict[str, str] | None = None) -> tuple[list[TradeRecord], int]:
    """
    用 stock_names.json 修正交易紀錄中的股票名稱。
    回傳新的交易清單與實際修正筆數；不直接寫檔，讓 storage/script 決定是否持久化。
    """
    stock_names = names if names is not None else load_stock_names()
    normalized: list[TradeRecord] = []
    changed = 0

    for trade in trades:
        canonical_name = stock_names.get(trade.stock_id)
        if canonical_name and trade.name != canonical_name:
            normalized.append(trade.model_copy(update={"name": canonical_name}))
            changed += 1
        else:
            normalized.append(trade)

    return normalized, changed


def _coerce_import_trades(trades: list[TradeImportItem | TradeRecord]) -> list[TradeRecord]:
    records, _ = _coerce_import_trades_with_warnings(trades)
    return records


def _coerce_import_trades_with_warnings(trades: list[TradeImportItem | TradeRecord]) -> tuple[list[TradeRecord], list[str]]:
    stock_names = load_stock_names()
    now = datetime.now().isoformat()
    records: list[TradeRecord] = []
    filled = {
        "id": 0,
        "created_at": 0,
        "name": 0,
        "amounts": 0,
    }
    for item in trades:
        data: dict[str, Any] = item.model_dump()
        stock_id = str(data.get("stock_id") or "").strip().upper()
        if not data.get("id"):
            filled["id"] += 1
        if not data.get("created_at"):
            filled["created_at"] += 1
        if not str(data.get("name") or "").strip():
            filled["name"] += 1
        if any(data.get(field) is None for field in _AMOUNT_FIELDS):
            filled["amounts"] += 1
        name = str(data.get("name") or "").strip() or stock_names.get(stock_id) or stock_id
        records.append(
            TradeRecord(
                id=data.get("id") or str(uuid.uuid4()),
                stock_id=stock_id,
                name=name,
                trade_type=data["trade_type"],
                date=data["date"],
                price=data["price"],
                shares=data["shares"],
                gross_amount=data.get("gross_amount"),
                fee=data.get("fee"),
                tax=data.get("tax"),
                net_amount=data.get("net_amount"),
                note=data.get("note") or "",
                created_at=data.get("created_at") or now,
            )
        )
    warnings = []
    if filled["id"]:
        warnings.append(f"自動補齊 id {filled['id']} 筆")
    if filled["created_at"]:
        warnings.append(f"自動補齊 created_at {filled['created_at']} 筆")
    if filled["name"]:
        warnings.append(f"自動補齊 name {filled['name']} 筆")
    if filled["amounts"]:
        warnings.append(f"自動補齊金額欄位 {filled['amounts']} 筆")
    return records, warnings


def _validate_import_trades(trades: list[TradeImportItem | TradeRecord]) -> None:
    records = _coerce_import_trades(trades)
    errors = _collect_import_errors(records)
    if errors:
        raise ValueError(errors[0])


def _collect_import_errors(trades: list[TradeRecord]) -> list[str]:
    errors: list[str] = []
    if not trades:
        return ["交易紀錄不可為空，若要清空請使用明確清空流程"]

    seen_ids: set[str] = set()
    holdings: dict[str, int] = {}
    for index, trade in enumerate(trades, start=1):
        if trade.id in seen_ids:
            errors.append(f"第 {index} 筆交易 id 重複：{trade.id}")
        seen_ids.add(trade.id)

        sid = trade.stock_id.strip().upper()
        if not sid:
            errors.append(f"第 {index} 筆交易缺少股票代碼")
        if trade.price <= 0:
            errors.append(f"第 {index} 筆交易價格必須大於 0")
        if trade.shares <= 0:
            errors.append(f"第 {index} 筆交易股數必須大於 0")

        if trade.trade_type == "buy":
            if trade.shares > 0:
                holdings[sid] = holdings.get(sid, 0) + trade.shares
        else:
            available = holdings.get(sid, 0)
            if available < trade.shares:
                errors.append(
                    f"第 {index} 筆 {sid} 可賣出股數不足，目前累計持有 {available} 股"
                )
            elif trade.shares > 0:
                holdings[sid] = available - trade.shares
    return errors


def _normalize_import_trades(trades: list[TradeRecord]) -> list[TradeRecord]:
    normalized: list[TradeRecord] = []
    for trade in trades:
        amounts = calculate_trade_amounts(trade.trade_type, trade.price, trade.shares)
        normalized.append(
            trade.model_copy(
                update={
                    "stock_id": trade.stock_id.strip().upper(),
                    "name": trade.name.strip() or trade.stock_id.strip().upper(),
                    "gross_amount": trade.gross_amount
                    if trade.gross_amount is not None
                    else amounts["gross_amount"],
                    "fee": trade.fee
                    if trade.fee is not None
                    else amounts["fee"],
                    "tax": trade.tax
                    if trade.tax is not None
                    else amounts["tax"],
                    "net_amount": trade.net_amount
                    if trade.net_amount is not None
                    else amounts["net_amount"],
                }
            )
        )
    return normalized


def import_trades(trades: list[TradeImportItem | TradeRecord], *, backup: bool = True) -> dict:
    records, warnings = _coerce_import_trades_with_warnings(trades)
    errors = _collect_import_errors(records)
    if errors:
        raise ValueError(errors[0])
    normalized = _normalize_import_trades(records)
    backup_path = backup_trades() if backup else None
    save_trades(normalized)
    return {
        "imported_count": len(normalized),
        "buy_count": sum(1 for trade in normalized if trade.trade_type == "buy"),
        "sell_count": sum(1 for trade in normalized if trade.trade_type == "sell"),
        "backup_path": str(backup_path) if backup_path else None,
        "warnings": warnings,
        "positions_preview": [],
    }


def preview_import_trades(trades: list[TradeImportItem | TradeRecord]) -> dict:
    records, warnings = _coerce_import_trades_with_warnings(trades)
    errors = _collect_import_errors(records)
    if errors:
        raise ValueError(errors[0])
    normalized = _normalize_import_trades(records)
    positions = calculate_positions(normalized)
    return {
        "imported_count": len(normalized),
        "buy_count": sum(1 for trade in normalized if trade.trade_type == "buy"),
        "sell_count": sum(1 for trade in normalized if trade.trade_type == "sell"),
        "backup_path": None,
        "warnings": warnings,
        "positions_preview": [position.model_dump() for position in positions],
    }


def validate_import_trades(trades: list[TradeImportItem | TradeRecord]) -> dict:
    records, warnings = _coerce_import_trades_with_warnings(trades)
    errors = _collect_import_errors(records)
    if errors:
        return {
            "valid": False,
            "error_count": len(errors),
            "errors": errors,
            "imported_count": len(records),
            "buy_count": sum(1 for trade in records if trade.trade_type == "buy"),
            "sell_count": sum(1 for trade in records if trade.trade_type == "sell"),
            "positions_preview": [],
            "warnings": warnings,
        }

    normalized = _normalize_import_trades(records)
    positions = calculate_positions(normalized)
    return {
        "valid": True,
        "error_count": 0,
        "errors": [],
        "imported_count": len(normalized),
        "buy_count": sum(1 for trade in normalized if trade.trade_type == "buy"),
        "sell_count": sum(1 for trade in normalized if trade.trade_type == "sell"),
        "positions_preview": [position.model_dump() for position in positions],
        "warnings": warnings,
    }


def clear_trades(*, confirm: str, backup: bool = True) -> dict:
    if confirm != "CLEAR_TRADES":
        raise ValueError("確認字串錯誤；若要清空交易紀錄，confirm 必須為 CLEAR_TRADES")

    current = load_trades()
    backup_path = backup_trades() if backup else None
    save_trades([])
    return {
        "cleared_count": len(current),
        "backup_path": str(backup_path) if backup_path else None,
        "warnings": [],
    }


def get_trade_backups() -> list[dict]:
    return list_trade_backups()


def restore_trades_backup(*, filename: str, confirm: str) -> dict:
    if confirm != "RESTORE_TRADES":
        raise ValueError("確認字串錯誤；若要還原交易備份，confirm 必須為 RESTORE_TRADES")
    result = restore_trades_from_backup(filename)
    return {**result, "warnings": []}


def calculate_positions(trades: list[TradeRecord]) -> list[Position]:
    """
    依所有交易紀錄計算目前持倉。
    - 買入成本以加權平均計算
    - 若持股數歸零則不顯示
    """
    buy_stats: dict[str, dict] = {}   # stock_id → {name, shares, cost}
    sold_shares: dict[str, int] = {}  # stock_id → total sold shares

    for t in trades:
        sid = t.stock_id
        if t.trade_type == "buy":
            if sid not in buy_stats:
                buy_stats[sid] = {"name": t.name, "shares": 0, "cost": 0.0}
            buy_stats[sid]["shares"] += t.shares
            buy_stats[sid]["cost"] += trade_net_amount(t)
        else:
            sold_shares[sid] = sold_shares.get(sid, 0) + t.shares

    current_prices = get_all_current_prices()
    stock_names = load_stock_names()
    positions: list[Position] = []

    for sid, bs in buy_stats.items():
        remaining = bs["shares"] - sold_shares.get(sid, 0)
        if remaining <= 0:
            continue

        avg_cost = bs["cost"] / bs["shares"]
        current_price = current_prices.get(sid, avg_cost)  # 無最新收盤價則以成本代替
        total_cost = avg_cost * remaining
        current_value = calculate_trade_amounts("sell", current_price, remaining)["net_amount"]
        unrealized_pnl = current_value - total_cost
        return_rate = unrealized_pnl / total_cost * 100 if total_cost else 0.0

        positions.append(
            Position(
                stock_id=sid,
                name=stock_names.get(sid) or bs["name"],
                total_shares=remaining,
                avg_cost=round(avg_cost, 2),
                total_cost=round(total_cost, 2),
                current_price=round(current_price, 2),
                current_value=round(current_value, 2),
                unrealized_pnl=round(unrealized_pnl, 2),
                return_rate=round(return_rate, 2),
            )
        )

    return positions


def calculate_stats(trades: list[TradeRecord], period: str) -> Stats:
    """
    計算統計資料。
    - period="monthly"：只統計本月買賣筆數與已實現損益
    - period="all"：統計所有紀錄
    - 未實現損益：固定為目前所有持倉合計（不受 period 篩選影響）
    - 已實現損益計算：賣出價 vs 歷史加權平均成本
    """
    # 全量 buy_stats 用於計算 avg_cost（不受 period 限制，確保成本準確）
    buy_stats: dict[str, dict] = {}
    for t in trades:
        if t.trade_type == "buy":
            sid = t.stock_id
            if sid not in buy_stats:
                buy_stats[sid] = {"shares": 0, "cost": 0.0}
            buy_stats[sid]["shares"] += t.shares
            buy_stats[sid]["cost"] += trade_net_amount(t)

    # 依 period 篩選
    if period == "monthly":
        month_prefix = date.today().strftime("%Y-%m")
        scoped = [t for t in trades if t.date.startswith(month_prefix)]
    else:
        scoped = trades

    buy_count = sum(1 for t in scoped if t.trade_type == "buy")
    sell_count = sum(1 for t in scoped if t.trade_type == "sell")

    realized_pnl = 0.0
    winning_sells = 0

    for t in scoped:
        if t.trade_type == "sell":
            sid = t.stock_id
            if sid in buy_stats and buy_stats[sid]["shares"] > 0:
                avg_cost = buy_stats[sid]["cost"] / buy_stats[sid]["shares"]
                pnl = trade_net_amount(t) - avg_cost * t.shares
                realized_pnl += pnl
                if pnl > 0:
                    winning_sells += 1

    unrealized_pnl = sum(p.unrealized_pnl for p in calculate_positions(trades))
    win_rate = winning_sells / sell_count * 100 if sell_count > 0 else 0.0

    return Stats(
        period=period,  # type: ignore[arg-type]
        buy_count=buy_count,
        sell_count=sell_count,
        realized_pnl=round(realized_pnl, 2),
        unrealized_pnl=round(unrealized_pnl, 2),
        win_rate=round(win_rate, 1),
    )
