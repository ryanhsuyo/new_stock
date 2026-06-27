"""Deterministic accounting primitives for the core daily-signal backtester."""

import csv
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from app.services import signals_service
from app.services.signals_service import CORE_STRATEGY_ID, MIN_ROWS
from app.services.trade_service import calculate_trade_amounts
from app.storage.atomic_write import atomic_write_text
from app.storage.settings_store import load_trading_settings


ENTRY_STATES = {"entry_confirmed", "ready_to_enter"}
EXIT_STATES = {"exit_warning", "invalidated"}
TRADE_FIELDS = (
    "signal_date",
    "fill_date",
    "side",
    "trigger_state",
    "reason",
    "raw_open",
    "fill_price",
    "shares",
    "gross_amount",
    "fee",
    "tax",
    "net_cash_flow",
    "realized_pnl",
    "holding_days",
)


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 1_000_000.0
    slippage_bps: float = 10.0
    lot_size: int = 1
    minimum_history: int = MIN_ROWS
    force_close: bool = False


SignalCallback = Callable[[list[dict], list[dict], bool], dict]


def _validate_config(config: BacktestConfig) -> None:
    if config.initial_cash <= 0:
        raise ValueError("initial_cash must be positive")
    if config.slippage_bps < 0:
        raise ValueError("slippage_bps must be non-negative")
    if not isinstance(config.lot_size, int) or config.lot_size <= 0:
        raise ValueError("lot_size must be a positive integer")
    if not isinstance(config.minimum_history, int) or config.minimum_history < MIN_ROWS:
        raise ValueError(f"minimum_history must be at least {MIN_ROWS}")


def _validate_rows(rows: list[dict]) -> None:
    if not rows:
        raise ValueError("rows must not be empty")

    previous_date: date | None = None
    for row in rows:
        raw_date = str(row.get("date") or "")
        try:
            row_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ValueError(f"invalid date: {raw_date}") from exc
        if previous_date is not None and row_date <= previous_date:
            raise ValueError(f"date must be strictly increasing: {raw_date}")
        previous_date = row_date

        values: dict[str, float] = {}
        for field in ("open", "high", "low", "close"):
            value = row.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"invalid {field} on {raw_date}")
            values[field] = float(value)
        volume = row.get("volume")
        if not isinstance(volume, (int, float)) or isinstance(volume, bool) or volume < 0:
            raise ValueError(f"invalid volume on {raw_date}")
        if values["high"] < max(values["open"], values["low"], values["close"]):
            raise ValueError(f"invalid OHLC high on {raw_date}")
        if values["low"] > min(values["open"], values["high"], values["close"]):
            raise ValueError(f"invalid OHLC low on {raw_date}")


def _apply_slippage(price: float, side: str, slippage_bps: float) -> float:
    if side == "buy":
        return price * (1 + slippage_bps / 10_000)
    if side == "sell":
        return price * (1 - slippage_bps / 10_000)
    raise ValueError(f"unsupported side: {side}")


def _affordable_shares(
    cash: float,
    price: float,
    lot_size: int,
    trading_settings: dict[str, float],
) -> int:
    high = max(0, int(cash // price) // lot_size)
    low = 0
    while low < high:
        middle = (low + high + 1) // 2
        shares = middle * lot_size
        cost = calculate_trade_amounts(
            "buy", price, shares, settings=trading_settings
        )["net_amount"]
        if cost <= cash:
            low = middle
        else:
            high = middle - 1
    return low * lot_size


def _max_drawdown(equities: list[float]) -> float | None:
    if not equities:
        return None
    peak = equities[0]
    maximum = 0.0
    for equity in equities:
        peak = max(peak, equity)
        if peak > 0:
            maximum = max(maximum, (peak - equity) / peak * 100)
    return round(maximum, 2)


def _estimated_liquidation_value(
    price: float,
    shares: int,
    trading_settings: dict[str, float],
) -> float:
    return calculate_trade_amounts(
        "sell", price, shares, settings=trading_settings
    )["net_amount"]


def _buy_and_hold_return(
    rows: list[dict],
    config: BacktestConfig,
    trading_settings: dict[str, float],
) -> float | None:
    first_fill_index = config.minimum_history
    if first_fill_index >= len(rows):
        return None
    buy_price = _apply_slippage(
        float(rows[first_fill_index]["open"]), "buy", config.slippage_bps
    )
    shares = _affordable_shares(
        config.initial_cash,
        buy_price,
        config.lot_size,
        trading_settings,
    )
    if shares == 0:
        return None
    buy = calculate_trade_amounts(
        "buy", buy_price, shares, settings=trading_settings
    )
    cash = config.initial_cash - buy["net_amount"]
    sell_price = _apply_slippage(
        float(rows[-1]["close"]), "sell", config.slippage_bps
    )
    final_equity = cash + _estimated_liquidation_value(
        sell_price, shares, trading_settings
    )
    return round((final_equity / config.initial_cash - 1) * 100, 4)


def _empty_result(
    code: str,
    rows: list[dict],
    config: BacktestConfig,
    status: str,
) -> dict:
    return {
        "summary": {
            "status": status,
            "code": code,
            "start_date": rows[0]["date"],
            "end_date": rows[-1]["date"],
            "rules_version": CORE_STRATEGY_ID,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "config": asdict(config),
            "initial_cash": round(config.initial_cash, 2),
            "final_equity": round(config.initial_cash, 2),
            "total_return_pct": 0.0,
            "buy_and_hold_return_pct": None,
            "excess_return_pct": None,
            "max_drawdown_pct": 0.0,
            "closed_trade_count": 0,
            "win_rate_pct": None,
            "average_realized_pnl": None,
            "total_fees": 0.0,
            "total_tax": 0.0,
            "skipped_actions": {},
            "open_position": None,
            "lookahead_guard": True,
            "limitations": ["single_stock", "daily_bars", "core_only"],
        },
        "trades": [],
        "equity_curve": [],
    }


def _core_signal_callback(
    code: str,
    stock_rows: list[dict],
    benchmark_rows: list[dict],
    is_holding: bool,
) -> dict:
    if benchmark_rows:
        context = signals_service._market_context(
            {signals_service.BENCHMARK_CODE: benchmark_rows}
        )
    else:
        context = {
            "benchmark_code": signals_service.BENCHMARK_CODE,
            "benchmark_rows": [],
            "market_regime": "unknown",
            "market_filter": "neutral",
            "market_reason": "backtest benchmark unavailable; using neutral filter",
            "old_wang_market_regime": "unknown",
            "old_wang_market_filter": "neutral",
            "old_wang_market_source": "none",
            "old_wang_market_reason": "disabled in core backtest",
        }
    context.update(
        {
            "core_backtest": True,
            "fundamentals": {},
            "sector_rotation": {},
        }
    )
    positions = {
        "holdings": {code: {"shares": 1}} if is_holding else {},
    }
    signal = signals_service._compute_signal(code, stock_rows, positions, context)
    approved_fields = (
        "data_ok",
        "internal_signal",
        "data_as_of",
        "reasons",
        "risk_note",
        "no_buy_reason",
    )
    return {field: signal.get(field) for field in approved_fields}


def run_backtest(
    code: str,
    rows: list[dict],
    benchmark_rows: list[dict] | None = None,
    *,
    config: BacktestConfig | None = None,
    trading_settings: dict[str, float] | None = None,
    signal_callback: SignalCallback | None = None,
) -> dict:
    config = config or BacktestConfig()
    _validate_config(config)
    _validate_rows(rows)
    benchmark_rows = benchmark_rows or []
    if benchmark_rows:
        _validate_rows(benchmark_rows)
    trading_settings = (
        dict(trading_settings)
        if trading_settings is not None
        else load_trading_settings()
    )
    if len(rows) < config.minimum_history:
        return _empty_result(code, rows, config, "insufficient_history")
    if signal_callback is None:
        signal_callback = lambda stock, benchmark, holding: _core_signal_callback(
            code, stock, benchmark, holding
        )

    cash = float(config.initial_cash)
    position: dict | None = None
    pending: dict | None = None
    trades: list[dict] = []
    equity_curve: list[dict] = []
    skipped_actions: dict[str, int] = {}

    def skip(reason: str) -> None:
        skipped_actions[reason] = skipped_actions.get(reason, 0) + 1

    def execute(action: dict, row: dict) -> None:
        nonlocal cash, position
        side = action["side"]
        fill_price = _apply_slippage(
            float(row["open"]), side, config.slippage_bps
        )
        if side == "buy":
            shares = _affordable_shares(
                cash, fill_price, config.lot_size, trading_settings
            )
            if shares == 0:
                skip("insufficient_cash")
                return
            amounts = calculate_trade_amounts(
                "buy", fill_price, shares, settings=trading_settings
            )
            cash -= amounts["net_amount"]
            position = {
                "shares": shares,
                "entry_date": row["date"],
                "entry_cost": amounts["net_amount"],
                "entry_price": fill_price,
            }
            realized_pnl = None
            holding_days = None
            net_cash_flow = -amounts["net_amount"]
        else:
            if position is None:
                skip("already_flat")
                return
            shares = int(position["shares"])
            amounts = calculate_trade_amounts(
                "sell", fill_price, shares, settings=trading_settings
            )
            cash += amounts["net_amount"]
            realized_pnl = round(
                amounts["net_amount"] - float(position["entry_cost"]), 2
            )
            holding_days = (
                date.fromisoformat(row["date"])
                - date.fromisoformat(str(position["entry_date"]))
            ).days
            position = None
            net_cash_flow = amounts["net_amount"]

        trades.append(
            {
                "signal_date": action["signal_date"],
                "fill_date": row["date"],
                "side": side,
                "trigger_state": action["trigger_state"],
                "reason": action["reason"],
                "raw_open": round(float(row["open"]), 4),
                "fill_price": round(fill_price, 4),
                "shares": shares,
                "gross_amount": amounts["gross_amount"],
                "fee": amounts["fee"],
                "tax": amounts["tax"],
                "net_cash_flow": round(net_cash_flow, 2),
                "realized_pnl": realized_pnl,
                "holding_days": holding_days,
            }
        )

    for index, row in enumerate(rows):
        if pending is not None:
            execute(pending, row)
            pending = None

        equity = cash
        if position is not None:
            equity += _estimated_liquidation_value(
                float(row["close"]), int(position["shares"]), trading_settings
            )
        equity_curve.append({"date": row["date"], "equity": round(equity, 2)})

        if index < config.minimum_history - 1:
            continue
        stock_prefix = rows[: index + 1]
        benchmark_prefix = [
            benchmark_row
            for benchmark_row in benchmark_rows
            if benchmark_row["date"] <= row["date"]
        ]
        signal = signal_callback(
            stock_prefix, benchmark_prefix, position is not None
        )
        if signal.get("data_as_of") != row["date"]:
            raise ValueError(
                f"signal data_as_of mismatch: expected {row['date']}, "
                f"got {signal.get('data_as_of')}"
            )
        state = str(signal.get("internal_signal") or "")
        if state not in ENTRY_STATES | EXIT_STATES:
            continue
        if index + 1 >= len(rows):
            skip("no_next_bar")
            continue
        if state in ENTRY_STATES:
            if position is not None:
                skip("already_holding")
                continue
            side = "buy"
        else:
            if position is None:
                skip("already_flat")
                continue
            side = "sell"
        reasons = signal.get("reasons") or []
        pending = {
            "side": side,
            "signal_date": row["date"],
            "trigger_state": state,
            "reason": " | ".join(str(reason) for reason in reasons)
            or str(signal.get("no_buy_reason") or signal.get("risk_note") or ""),
        }

    if config.force_close and position is not None:
        final_row = dict(rows[-1])
        final_row["open"] = final_row["close"]
        execute(
            {
                "side": "sell",
                "signal_date": final_row["date"],
                "trigger_state": "forced_close",
                "reason": "force_close enabled at end of data",
            },
            final_row,
        )
        equity_curve[-1]["equity"] = round(cash, 2)

    final_equity = cash
    open_position = None
    if position is not None:
        estimated_value = _estimated_liquidation_value(
            float(rows[-1]["close"]), int(position["shares"]), trading_settings
        )
        final_equity += estimated_value
        open_position = {
            "shares": int(position["shares"]),
            "entry_date": position["entry_date"],
            "entry_price": round(float(position["entry_price"]), 4),
            "entry_cost": round(float(position["entry_cost"]), 2),
            "estimated_liquidation_value": round(estimated_value, 2),
        }

    realized = [
        float(trade["realized_pnl"])
        for trade in trades
        if trade["side"] == "sell" and trade["realized_pnl"] is not None
    ]
    buy_hold = _buy_and_hold_return(rows, config, trading_settings)
    total_return = round((final_equity / config.initial_cash - 1) * 100, 4)
    result = _empty_result(code, rows, config, "ok")
    result["trades"] = trades
    result["equity_curve"] = equity_curve
    result["summary"].update(
        {
            "final_equity": round(final_equity, 2),
            "total_return_pct": total_return,
            "buy_and_hold_return_pct": buy_hold,
            "excess_return_pct": (
                round(total_return - buy_hold, 4) if buy_hold is not None else None
            ),
            "max_drawdown_pct": _max_drawdown(
                [float(point["equity"]) for point in equity_curve]
            ),
            "closed_trade_count": len(realized),
            "win_rate_pct": (
                round(sum(value > 0 for value in realized) / len(realized) * 100, 2)
                if realized
                else None
            ),
            "average_realized_pnl": (
                round(sum(realized) / len(realized), 2) if realized else None
            ),
            "total_fees": round(sum(float(trade["fee"]) for trade in trades), 2),
            "total_tax": round(sum(float(trade["tax"]) for trade in trades), 2),
            "skipped_actions": skipped_actions,
            "open_position": open_position,
        }
    )
    return result


def write_backtest_outputs(result: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "backtest_summary.json"
    trades_path = out_dir / "backtest_trades.csv"
    atomic_write_text(
        summary_path,
        json.dumps(result["summary"], ensure_ascii=False, indent=2),
    )

    temp_path = trades_path.with_name(f".{trades_path.name}.tmp")
    try:
        with temp_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=TRADE_FIELDS)
            writer.writeheader()
            writer.writerows(result.get("trades") or [])
        temp_path.replace(trades_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return summary_path, trades_path
