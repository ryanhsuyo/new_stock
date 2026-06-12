"""
holdings_service.py — 持股技術分析服務

從 trades.json 自動推算持股，對每檔呼叫 analyse_stock，
計算未實現損益，組合成 HoldingAnalysis 列表。

公開介面
--------
    compute_raw_positions(trades)          → dict[str, dict]
    analyse_holdings(as_of_date)           → list[HoldingAnalysis]
    get_portfolio_summary(as_of_date)      → PortfolioSummary

設計原則
--------
- trades.json 為持股唯一來源（不再讀 positions.json）
- trades.json 不存在或為空 → 回傳 [] / 空摘要，不拋例外
- 回傳依訊號嚴重程度排序（exit_warning 排最前）
"""

from app.models.analysis import HoldingAnalysis, PortfolioSummary
from app.models.trade import TradeRecord
from app.services.analysis_service import analyse_stock
from app.services.trade_service import calculate_trade_amounts, trade_net_amount
from app.storage.json_store import load_trades
from app.storage.name_store import load_stock_names

_URGENCY: dict[str, int] = {
    "exit_warning":        0,
    "invalidated":         1,
    "take_profit_warning": 2,
    "hold":                3,
    "watchlist":           4,
    "ready_to_enter":      5,
    "entry_confirmed":     6,
    "DATA_MISSING":        7,
}


def compute_raw_positions(trades: list[TradeRecord]) -> dict[str, dict]:
    """
    從交易紀錄推算目前持股（不需要行情價格）。

    Returns
    -------
    dict[str, dict]
        {stock_id: {"name": str, "shares": int, "avg_cost": float}}
        只含持股數量 > 0 的項目。
    """
    buy_stats: dict[str, dict] = {}
    sold_shares: dict[str, int] = {}
    stock_names = load_stock_names()

    for t in trades:
        sid = t.stock_id
        if t.trade_type == "buy":
            if sid not in buy_stats:
                buy_stats[sid] = {"name": t.name, "shares": 0, "cost": 0.0}
            buy_stats[sid]["shares"] += t.shares
            buy_stats[sid]["cost"] += trade_net_amount(t)
        else:
            sold_shares[sid] = sold_shares.get(sid, 0) + t.shares

    result: dict[str, dict] = {}
    for sid, bs in buy_stats.items():
        remaining = bs["shares"] - sold_shares.get(sid, 0)
        if remaining > 0:
            result[sid] = {
                "name": stock_names.get(sid) or bs["name"],
                "shares": remaining,
                "avg_cost": round(bs["cost"] / bs["shares"], 2),
            }
    return result


def analyse_holdings(as_of_date: str | None = None) -> list[HoldingAnalysis]:
    """
    從 trades.json 推算持股，對每檔執行技術分析。

    Parameters
    ----------
    as_of_date : str | None
        計算基準日（YYYY-MM-DD）。None = 今日。

    Returns
    -------
    list[HoldingAnalysis]
        依訊號嚴重程度排序（exit_warning / invalidated 排前，hold 排後）。
    """
    trades = load_trades()
    holdings = compute_raw_positions(trades)

    if not holdings:
        return []

    results: list[HoldingAnalysis] = []

    for sid, info in holdings.items():
        avg_cost = info["avg_cost"]
        shares   = info["shares"]

        stock_analysis = analyse_stock(sid, as_of_date=as_of_date)

        if stock_analysis.data_ok and stock_analysis.close is not None and avg_cost > 0:
            current_net = calculate_trade_amounts("sell", stock_analysis.close, shares)["net_amount"]
            cost = avg_cost * shares
            unrealized_pnl = round(current_net - cost, 2)
            return_rate    = round(unrealized_pnl / cost * 100, 2)
        else:
            unrealized_pnl = None
            return_rate    = None

        results.append(HoldingAnalysis(
            avg_cost=avg_cost,
            shares=shares,
            unrealized_pnl=unrealized_pnl,
            return_rate=return_rate,
            analysis=stock_analysis,
        ))

    results.sort(key=lambda h: _URGENCY.get(h.analysis.signal, 99))
    return results


def get_portfolio_summary(as_of_date: str | None = None) -> PortfolioSummary:
    """
    彙總所有持股的投組摘要。

    - 總持股數、總成本、總市值、總未實現損益
    - 各 signal 數量統計
    - 若資料不足（無 close），市值以成本代替

    Returns
    -------
    PortfolioSummary
    """
    holdings = analyse_holdings(as_of_date=as_of_date)

    total_cost          = 0.0
    total_market_value  = 0.0
    total_unrealized_pnl = 0.0
    hold_count               = 0
    take_profit_warning_count = 0
    exit_warning_count        = 0
    invalidated_count         = 0

    for h in holdings:
        cost = h.avg_cost * h.shares
        total_cost += cost

        if h.analysis.close is not None:
            total_market_value += calculate_trade_amounts("sell", h.analysis.close, h.shares)["net_amount"]
        else:
            total_market_value += cost  # 無最新收盤價時以成本代替

        if h.unrealized_pnl is not None:
            total_unrealized_pnl += h.unrealized_pnl

        sig = h.analysis.signal
        if sig == "hold":
            hold_count += 1
        elif sig == "take_profit_warning":
            take_profit_warning_count += 1
        elif sig == "exit_warning":
            exit_warning_count += 1
        elif sig == "invalidated":
            invalidated_count += 1

    return PortfolioSummary(
        total_positions=len(holdings),
        total_cost=round(total_cost, 2),
        total_market_value=round(total_market_value, 2),
        total_unrealized_pnl=round(total_unrealized_pnl, 2),
        hold_count=hold_count,
        take_profit_warning_count=take_profit_warning_count,
        exit_warning_count=exit_warning_count,
        invalidated_count=invalidated_count,
    )
