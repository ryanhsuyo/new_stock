from __future__ import annotations

from typing import Literal
from pydantic import BaseModel


# ── 儲存單位：一筆買賣紀錄 ──────────────────────────────────────────────────
class TradeRecord(BaseModel):
    id: str
    stock_id: str
    name: str
    trade_type: Literal["buy", "sell"]
    date: str          # YYYY-MM-DD
    price: float
    shares: int
    gross_amount: float | None = None  # price * shares
    fee: float | None = None           # 券商手續費
    tax: float | None = None           # 證交稅；買進為 0
    net_amount: float | None = None    # 買進=含手續費成本；賣出=扣費稅後收入
    note: str = ""
    created_at: str    # ISO datetime


# ── API 請求體 ────────────────────────────────────────────────────────────────
class BuyRequest(BaseModel):
    stock_id: str
    name: str
    date: str
    price: float
    shares: int
    note: str = ""


class SellRequest(BaseModel):
    stock_id: str
    date: str
    price: float
    shares: int
    note: str = ""


class TradeUpdateRequest(BaseModel):
    date: str
    price: float
    shares: int
    note: str = ""


class TradeIntegrityItem(BaseModel):
    trade_id: str
    status: Literal["ok", "warning", "unverified"]
    reason: str
    day_low: float | None = None
    day_high: float | None = None
    day_close: float | None = None
    difference_pct: float | None = None


class TradeIntegrityReport(BaseModel):
    checked_count: int
    warning_count: int
    unverified_count: int
    performance_status: Literal["verified", "provisional"]
    items: list[TradeIntegrityItem]


class TradeImportItem(BaseModel):
    id: str | None = None
    stock_id: str
    name: str | None = None
    trade_type: Literal["buy", "sell"]
    date: str
    price: float
    shares: int
    gross_amount: float | None = None
    fee: float | None = None
    tax: float | None = None
    net_amount: float | None = None
    note: str = ""
    created_at: str | None = None


class TradeImportRequest(BaseModel):
    trades: list[TradeImportItem]
    mode: Literal["replace"] = "replace"
    backup: bool = True


class TradeImportResult(BaseModel):
    imported_count: int
    buy_count: int
    sell_count: int
    backup_path: str | None = None
    warnings: list[str] = []
    positions_preview: list[Position] = []


class TradeImportValidationResult(BaseModel):
    valid: bool
    error_count: int
    errors: list[str] = []
    imported_count: int = 0
    buy_count: int = 0
    sell_count: int = 0
    positions_preview: list[Position] = []
    warnings: list[str] = []


class TradeClearRequest(BaseModel):
    confirm: str
    backup: bool = True


class TradeClearResult(BaseModel):
    cleared_count: int
    backup_path: str | None = None
    warnings: list[str] = []


class TradeBackupInfo(BaseModel):
    filename: str
    path: str
    size_bytes: int
    trade_count: int
    modified_at: str


class TradeRestoreRequest(BaseModel):
    filename: str
    confirm: str


class TradeRestoreResult(BaseModel):
    restored_from: str
    restored_count: int
    backup_path: str | None = None
    warnings: list[str] = []


# ── 計算結果（不儲存，每次動態算出）─────────────────────────────────────────
class Position(BaseModel):
    stock_id: str
    name: str
    total_shares: int
    avg_cost: float        # 加權平均成本
    total_cost: float      # 剩餘持股總成本
    current_price: float
    current_value: float
    unrealized_pnl: float  # 未實現損益
    return_rate: float     # 報酬率 %


class Stats(BaseModel):
    period: Literal["monthly", "all"]
    buy_count: int
    sell_count: int
    realized_pnl: float    # 已實現損益
    unrealized_pnl: float  # 未實現損益（當前所有持倉合計）
    win_rate: float        # 勝率 % （已結清交易中獲利比例）
