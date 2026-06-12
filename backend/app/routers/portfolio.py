from fastapi import APIRouter, Query

from app.models.analysis import HoldingAnalysis, PortfolioSummary
from app.models.trade import Position
from app.services.holdings_service import analyse_holdings, compute_raw_positions, get_portfolio_summary
from app.services.trade_service import calculate_positions
from app.storage.json_store import load_trades

router = APIRouter()


@router.get("/portfolio", response_model=list[Position])
def get_portfolio() -> list[Position]:
    return calculate_positions(load_trades())


@router.get("/portfolio/positions")
def get_portfolio_positions(
    as_of: str | None = Query(default=None, description="基準日 YYYY-MM-DD，預設今日"),
) -> list[dict]:
    """
    從 trades.json 推算目前持股（純持股結果，不含技術分析）。

    每筆包含 stock_id / name / shares / avg_cost。
    trades.json 為空時回傳 []，不報錯。
    """
    trades = load_trades()
    positions = compute_raw_positions(trades)
    return [
        {
            "stock_id": sid,
            "name": info["name"],
            "shares": info["shares"],
            "avg_cost": info["avg_cost"],
        }
        for sid, info in positions.items()
    ]


@router.get("/portfolio/analysis", response_model=list[HoldingAnalysis])
def get_portfolio_analysis(
    as_of: str | None = Query(default=None, description="基準日 YYYY-MM-DD，預設今日"),
) -> list[HoldingAnalysis]:
    """
    從 trades.json 推算持股，對所有持股執行技術分析。

    每筆結果包含：
    - signal（hold / take_profit_warning / exit_warning / invalidated）
    - score / reasons / risk_notes / pattern
    - 未實現損益 / 報酬率（由 trades.json 均價計算）

    trades.json 不存在或為空時回傳 []，不拋 500。
    依訊號嚴重程度排序（exit_warning 排最前）。
    """
    return analyse_holdings(as_of_date=as_of)


@router.get("/portfolio/summary", response_model=PortfolioSummary)
def get_portfolio_summary_endpoint(
    as_of: str | None = Query(default=None, description="基準日 YYYY-MM-DD，預設今日"),
) -> PortfolioSummary:
    """
    投組總覽摘要。

    包含：
    - 持股檔數、總成本、總市值、總未實現損益
    - 各 signal 數量（hold / take_profit_warning / exit_warning / invalidated）

    trades.json 為空時回傳全零摘要，不報錯。
    """
    return get_portfolio_summary(as_of_date=as_of)
