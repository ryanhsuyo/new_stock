"""
產生 2026-05 起的台股 / 美股策略交易檢討報告。

用途：
- 彙整 trades.json 的實際進出與損益。
- 以買進日 / 賣出日的 analysis_service 回推當時策略計畫與風險原因。
- 補目前台股 / 美股觀察策略狀態，避免把「實際交易」與「回放觀察」混在一起。

輸出：
- backend/out/strategy_trade_report_2026-05-01.md
- backend/out/strategy_trade_report_tw_2026-05-01.md
- backend/out/strategy_trade_report_us_2026-05-01.md
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.analysis_service import analyse_stock
from app.services.trade_service import calculate_trade_amounts
from app.services.us_market_service import get_us_market_status
from app.services.us_strategy_service import get_us_trend_follow
from app.services.us_wbottom_service import get_us_wbottom

DATA = ROOT / "data"
OUT = ROOT / "out"
START_DATE = "2026-05-01"
COMBINED_REPORT_PATH = OUT / "strategy_trade_report_2026-05-01.md"
TW_REPORT_PATH = OUT / "strategy_trade_report_tw_2026-05-01.md"
TW_AUDIT_REPORT_PATH = OUT / "strategy_trade_audit_tw_2026-05-01.md"
US_REPORT_PATH = OUT / "strategy_trade_report_us_2026-05-01.md"


@dataclass
class EntryPlan:
    as_of: str
    close: float | None
    signal: str
    strategy: str
    entry_price_low: float | None
    entry_price_high: float | None
    stop_price: float | None
    target_price: float | None
    daily_action: str
    daily_action_label: str
    daily_action_reason: str
    reason: str


@dataclass
class Lot:
    stock_id: str
    name: str
    entry_date: str
    entry_price: float
    shares: int
    remaining: int
    net_cost: float
    note: str
    plan: EntryPlan


@dataclass
class ClosedTrade:
    stock_id: str
    name: str
    entry_dates: list[str]
    entry_prices: list[float]
    shares: int
    avg_entry_price: float
    suggested_entries: list[str]
    entry_assessments: list[str]
    planned_stops: list[float | None]
    planned_targets: list[float | None]
    strategy: str
    entry_reason: str
    exit_date: str
    exit_price: float
    exit_reason: str
    realized_pnl: float
    realized_return_pct: float


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt_num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:,.{digits}f}".rstrip("0").rstrip(".")


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.0f}"


def _gap_pct(close: float | None, level: float | None) -> str:
    """價位離現價多遠。裸價位看不出遠近，必須換成百分比才讀得懂。"""
    if not close or level is None:
        return "—"
    return f"{(level - close) / close * 100:+.1f}%"


def _price_with_gap(close: float | None, level: float | None) -> str:
    gap = _gap_pct(close, level)
    return _fmt_num(level) if gap == "—" else f"{_fmt_num(level)}（{gap}）"


def _reward_risk(close: float | None, target: float | None, stop: float | None) -> str:
    """報酬風險比：上檔空間 ÷ 下檔失效距離。低於 1 代表現在追進划不來。"""
    if not close or target is None or stop is None:
        return "—"
    upside, downside = target - close, close - stop
    if upside <= 0 or downside <= 0:
        return "已無空間" if upside <= 0 else "—"
    return f"1 : {upside / downside:.1f}"


def _short(text: str, limit: int = 72) -> str:
    text = " ".join((text or "").replace("\n", " ").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


@lru_cache(maxsize=1)
def _tw_ohlcv_map() -> dict[tuple[str, str], dict[str, float]]:
    path = DATA / "ohlcv.csv"
    if not path.exists():
        return {}
    result: dict[tuple[str, str], dict[str, float]] = {}
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                result[(row["code"], row["date"])] = {
                    "low": float(row["low"]),
                    "high": float(row["high"]),
                    "close": float(row["close"]),
                }
            except (KeyError, TypeError, ValueError):
                continue
    return result


@lru_cache(maxsize=None)
def _previous_data_date(code: str, trade_date: str) -> str | None:
    dates = sorted(
        row_date
        for row_code, row_date in _tw_ohlcv_map()
        if row_code == code and row_date < trade_date
    )
    return dates[-1] if dates else None


def _safe_analysis(code: str, as_of: str) -> Any | None:
    try:
        return analyse_stock(code, as_of_date=as_of)
    except Exception as exc:
        print(f"[WARN] analyse_stock failed: {code} {as_of}: {exc}")
        return None


def _strategy_from_analysis(a: Any | None) -> str:
    if a is None:
        return "其他（無法判定）"
    tags = list(getattr(a, "strategy_tags", []) or [])
    if getattr(a, "old_wang_flag", False):
        tag = getattr(a, "old_wang_tag", None)
        return f"老王{f'（{tag}）' if tag else ''}"
    if "steady_momentum" in tags:
        return "其他（穩健動能）"
    return "其他（核心技術）"


def _entry_plan(code: str, trade_date: str) -> EntryPlan:
    decision_date = _previous_data_date(code, trade_date) or trade_date
    a = _safe_analysis(code, decision_date)
    if a is None:
        return EntryPlan(
            decision_date, None, "unknown", "其他（無法判定）", None, None,
            None, None, "", "", "", "分析失敗",
        )
    reasons = getattr(a, "reasons", []) or []
    risk_notes = getattr(a, "risk_notes", []) or []
    reason = "；".join([*(reasons[:2]), *(risk_notes[:1])])
    if not reason:
        reason = getattr(a, "price_plan_note", "") or getattr(a, "no_buy_reason", "")
    return EntryPlan(
        as_of=getattr(a, "as_of", trade_date),
        close=getattr(a, "close", None),
        signal=getattr(a, "signal", "unknown"),
        strategy=_strategy_from_analysis(a),
        entry_price_low=getattr(a, "entry_price_low", None),
        entry_price_high=getattr(a, "entry_price_high", None),
        stop_price=getattr(a, "stop_price", None),
        target_price=getattr(a, "target_price", None),
        daily_action=getattr(a, "daily_action", ""),
        daily_action_label=getattr(a, "daily_action_label", ""),
        daily_action_reason=getattr(a, "daily_action_reason", ""),
        reason=reason,
    )


def _entry_zone(plan: EntryPlan) -> str:
    if plan.entry_price_low is None and plan.entry_price_high is None:
        return "—"
    if plan.entry_price_low is None:
        return f"≤ {_fmt_num(plan.entry_price_high)}"
    if plan.entry_price_high is None:
        return f"≥ {_fmt_num(plan.entry_price_low)}"
    return f"{_fmt_num(plan.entry_price_low)}–{_fmt_num(plan.entry_price_high)}"


def _entry_assessment(plan: EntryPlan, actual_price: float) -> str:
    problems: list[str] = []
    if plan.target_price is not None and actual_price >= plan.target_price:
        problems.append(
            f"實際價 {_fmt_num(actual_price)} 已達/高於止盈 {_fmt_num(plan.target_price)}"
        )
    if plan.stop_price is not None and actual_price <= plan.stop_price:
        problems.append(
            f"實際價 {_fmt_num(actual_price)} 已達/低於停損 {_fmt_num(plan.stop_price)}"
        )
    if plan.daily_action not in {"enter", "probe"}:
        action = plan.daily_action_label or plan.daily_action or "非進場"
        problems.append(f"當日動作為「{action}」而非進場")
    if plan.entry_price_low is not None and actual_price < plan.entry_price_low:
        problems.append(f"低於建議下緣 {_fmt_num(plan.entry_price_low)}")
    if plan.entry_price_high is not None and actual_price > plan.entry_price_high:
        problems.append(f"高於建議上緣 {_fmt_num(plan.entry_price_high)}")
    if problems:
        return "不合規：" + "；".join(problems)
    return "合規：實際價位於建議區，且當日為進場動作"


def _exit_reason(code: str, sell_date: str, note: str) -> str:
    if note.strip():
        return note.strip()
    decision_date = _previous_data_date(code, sell_date) or sell_date
    a = _safe_analysis(code, decision_date)
    if a is None:
        return "交易紀錄未填；當日分析失敗，無法回推原因"
    no_buy = getattr(a, "no_buy_reason", "") or ""
    risk_notes = getattr(a, "risk_notes", []) or []
    signal = getattr(a, "signal", "unknown")
    reason = no_buy or "；".join(risk_notes[:2]) or getattr(a, "price_plan_note", "")
    return f"交易紀錄未填；依 {decision_date} 收盤分析推論：{signal}，{reason}"


def _trade_net(t: dict) -> float:
    if t.get("net_amount") is not None:
        return float(t["net_amount"])
    return float(calculate_trade_amounts(t["trade_type"], float(t["price"]), int(t["shares"]))["net_amount"])


def build_closed_trades(trades: list[dict]) -> tuple[list[ClosedTrade], list[Lot]]:
    lots_by_code: dict[str, deque[Lot]] = defaultdict(deque)
    closed: list[ClosedTrade] = []
    scoped = [
        t for t in trades
        if t.get("created_at", "") >= f"{START_DATE}T" or t.get("date", "") >= START_DATE
    ]
    scoped.sort(key=lambda t: (t.get("date", ""), t.get("created_at", ""), t.get("id", "")))

    for t in scoped:
        code = str(t["stock_id"])
        shares = int(t["shares"])
        price = float(t["price"])
        if t["trade_type"] == "buy":
            net = _trade_net(t)
            lots_by_code[code].append(
                Lot(
                    stock_id=code,
                    name=t.get("name") or code,
                    entry_date=t["date"],
                    entry_price=price,
                    shares=shares,
                    remaining=shares,
                    net_cost=net,
                    note=t.get("note") or "",
                    plan=_entry_plan(code, t["date"]),
                )
            )
            continue

        remaining_to_sell = shares
        consumed: list[tuple[Lot, int, float]] = []
        while remaining_to_sell > 0 and lots_by_code[code]:
            lot = lots_by_code[code][0]
            take = min(remaining_to_sell, lot.remaining)
            cost_share = lot.net_cost / lot.shares
            consumed.append((lot, take, cost_share * take))
            lot.remaining -= take
            remaining_to_sell -= take
            if lot.remaining == 0:
                lots_by_code[code].popleft()

        if remaining_to_sell > 0:
            print(f"[WARN] sell exceeds lots: {code} {t['date']} remaining={remaining_to_sell}")
        if not consumed:
            continue

        sell_net = _trade_net(t)
        sold_shares = sum(x[1] for x in consumed)
        cost = sum(x[2] for x in consumed)
        allocated_net = sell_net * (sold_shares / shares)
        pnl = allocated_net - cost
        gross_entry = sum(lot.entry_price * take for lot, take, _ in consumed)
        avg_entry = gross_entry / sold_shares
        entry_reasons = []
        strategies = []
        for lot, _take, _cost in consumed:
            tag = lot.note or f"{lot.plan.signal}: {lot.plan.reason}"
            entry_reasons.append(tag)
            strategies.append(lot.plan.strategy)
        closed.append(
            ClosedTrade(
                stock_id=code,
                name=consumed[0][0].name,
                entry_dates=[f"{lot.entry_date}({take})" for lot, take, _ in consumed],
                entry_prices=[lot.entry_price for lot, _take, _ in consumed],
                shares=sold_shares,
                avg_entry_price=avg_entry,
                suggested_entries=[
                    f"訊號 {lot.plan.as_of}: {_entry_zone(lot.plan)}" for lot, _take, _ in consumed
                ],
                entry_assessments=[
                    f"{lot.entry_date}: {_entry_assessment(lot.plan, lot.entry_price)}"
                    for lot, _take, _ in consumed
                ],
                planned_stops=[lot.plan.stop_price for lot, _take, _ in consumed],
                planned_targets=[lot.plan.target_price for lot, _take, _ in consumed],
                strategy=", ".join(dict.fromkeys(strategies)),
                entry_reason=" | ".join(dict.fromkeys(entry_reasons)),
                exit_date=t["date"],
                exit_price=price,
                exit_reason=_exit_reason(code, t["date"], t.get("note") or ""),
                realized_pnl=pnl,
                realized_return_pct=(pnl / cost * 100) if cost else 0.0,
            )
        )

    open_lots = [lot for lots in lots_by_code.values() for lot in lots if lot.remaining > 0]
    return closed, open_lots


def _latest_tw_actions(limit: int = 12) -> tuple[list[dict], list[dict], list[dict]]:
    path = OUT / "universe_report.csv"
    if not path.exists():
        return [], [], []
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    entries = [
        r for r in rows
        if r.get("daily_action") in {"enter", "probe", "watch"} and r.get("internal_signal") in {"ready_to_enter", "entry_confirmed", "watchlist"}
    ]
    exits = [r for r in rows if r.get("daily_action") in {"exit", "reduce"} or r.get("internal_signal") in {"exit_warning", "invalidated"}]
    blockers = [r for r in rows if r.get("old_wang_market_filter") == "block"]

    def score_key(r: dict) -> tuple[int, float]:
        try:
            priority = int(float(r.get("daily_priority") or 0))
        except ValueError:
            priority = 0
        try:
            score = float(r.get("score") or 0)
        except ValueError:
            score = 0
        return priority, score

    return (
        sorted(entries, key=score_key, reverse=True)[:limit],
        sorted(exits, key=score_key, reverse=True)[:limit],
        blockers[:3],
    )


def _tw_report_freshness() -> dict:
    """檢查日報使用的逐股資料日是否全部等於 summary as-of。"""
    summary = _load_json(OUT / "summary.json", {})
    expected = str(summary.get("as_of") or "")
    path = OUT / "universe_report.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8"))) if path.exists() else []
    stale = [
        {
            "code": str(row.get("code") or ""),
            "name": str(row.get("name") or row.get("code") or ""),
            "data_as_of": str(row.get("data_as_of") or ""),
        }
        for row in rows
        if not row.get("data_as_of") or (expected and row.get("data_as_of") != expected)
    ]
    return {
        "expected_as_of": expected or None,
        "row_count": len(rows),
        "stale_count": len(stale),
        "stale_items": stale,
        "is_complete": bool(rows) and not stale,
    }


def _trade_price_warnings(trades: list[dict], tolerance_pct: float = 1.0) -> list[list[str]]:
    ohlcv_map = _tw_ohlcv_map()
    warnings = []
    for t in trades:
        code = str(t.get("stock_id", ""))
        trade_date = str(t.get("date", ""))
        day = ohlcv_map.get((code, trade_date))
        if day is None:
            continue
        price = float(t.get("price") or 0)
        low = day["low"]
        high = day["high"]
        close = day["close"]
        if low <= 0 or high <= 0 or price <= 0:
            continue
        lower_bound = low * (1 - tolerance_pct / 100)
        upper_bound = high * (1 + tolerance_pct / 100)
        if price < lower_bound or price > upper_bound:
            anchor = low if price < low else high
            diff_pct = (price / anchor - 1) * 100
            warnings.append([
                f"{t.get('name') or code} {code}",
                trade_date,
                t.get("trade_type", ""),
                _fmt_num(price),
                f"{_fmt_num(low)}–{_fmt_num(high)}",
                _fmt_num(close),
                f"{diff_pct:+.1f}%",
                "交易價落在當日高低區間外，請確認輸入價格 / 日期 / 單位 / 除權息尺度",
            ])
    return warnings


def _read_replay_summary(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("summary") or data.get("results", {}).get("summary") or data


def _current_us_status(as_of: str | None = None) -> tuple[dict, dict, dict]:
    try:
        status = get_us_market_status()
    except Exception as exc:
        status = {"error": str(exc)}
    try:
        trend = get_us_trend_follow(as_of=as_of) if as_of else get_us_trend_follow()
    except Exception as exc:
        trend = {"error": str(exc), "candidates": [], "excluded": []}
    try:
        wbottom = get_us_wbottom(as_of=as_of) if as_of else get_us_wbottom()
    except Exception as exc:
        wbottom = {"error": str(exc), "patterns": []}
    return status, trend, wbottom


def _split_market_trades(trades: list[dict]) -> tuple[list[dict], list[dict]]:
    leaders = _load_json(DATA / "us_leaders.json", {})
    us_codes = {
        str(item.get("code", "")).upper()
        for item in leaders.get("stocks", [])
        if item.get("code")
    }
    tw: list[dict] = []
    us: list[dict] = []
    for trade in trades:
        code = str(trade.get("stock_id", "")).upper()
        if code in us_codes or (code and not code.isdigit()):
            us.append(trade)
        else:
            tw.append(trade)
    return tw, us


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_無資料_\n"
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    out.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(out) + "\n"


def _tw_closed_rows(closed: list[ClosedTrade]) -> list[list[str]]:
    rows: list[list[str]] = []
    for trade in closed:
        actual_entries = [
            f"{entry_date}: {_fmt_num(price)}"
            for entry_date, price in zip(trade.entry_dates, trade.entry_prices)
        ]
        if len(actual_entries) > 1:
            actual_entries.append(f"加權均價 {_fmt_num(trade.avg_entry_price)}")
        rows.append([
            f"{trade.name} {trade.stock_id}",
            ", ".join(trade.entry_dates),
            " / ".join(trade.suggested_entries),
            " / ".join(actual_entries),
            " / ".join(_fmt_num(x) for x in trade.planned_stops),
            " / ".join(_fmt_num(x) for x in trade.planned_targets),
            trade.exit_date,
            _fmt_num(trade.exit_price),
            _short(trade.exit_reason, 92),
            _fmt_money(trade.realized_pnl),
            f"{trade.realized_return_pct:+.2f}%",
            _short(trade.strategy, 58),
        ])
    return rows


def _tw_entry_check_rows(trades: list[dict]) -> list[list[str]]:
    rows: list[list[str]] = []
    scoped = [
        trade for trade in trades
        if trade.get("trade_type") == "buy"
        and (
            trade.get("created_at", "") >= f"{START_DATE}T"
            or trade.get("date", "") >= START_DATE
        )
    ]
    scoped.sort(key=lambda trade: (trade.get("date", ""), trade.get("created_at", "")))
    for trade in scoped:
        plan = _entry_plan(str(trade["stock_id"]), str(trade["date"]))
        actual = float(trade["price"])
        rows.append([
            f"{trade.get('name') or trade['stock_id']} {trade['stock_id']}",
            str(trade["date"]),
            plan.as_of,
            f"{plan.daily_action_label or plan.daily_action or '—'} / {plan.signal}",
            _fmt_num(plan.close),
            _entry_zone(plan),
            _fmt_num(actual),
            _fmt_num(plan.stop_price),
            _fmt_num(plan.target_price),
            _short(_entry_assessment(plan, actual), 112),
            plan.strategy,
        ])
    return rows


_TW_SIGNAL_LABELS = {
    "entry_confirmed": "進場條件成立",
    "ready_to_enter": "準備進場",
    "watchlist": "持續觀察",
    "exit_warning": "出場警示",
    "invalidated": "條件失效",
}
_TW_MARKET_FILTER_LABELS = {
    "allow": "可依策略觀察",
    "watch": "保守觀察",
    "block": "風險模式",
}


def _tw_signal_label(value: object) -> str:
    raw = str(value or "").strip()
    return _TW_SIGNAL_LABELS.get(raw, raw.replace("_", " ") if raw else "—")


def _tw_current_rows() -> tuple[list[list[str]], list[list[str]], str]:
    entries, exits, blockers = _latest_tw_actions()
    entry_rows = [[
        f"{row.get('name')} {row.get('code')}",
        row.get("daily_action_label") or row.get("daily_action") or "—",
        _tw_signal_label(row.get("internal_signal")),
        _fmt_num(float(row["close"])) if row.get("close") else "—",
        f"{row.get('entry_price_low') or '—'}–{row.get('entry_price_high') or '—'}",
        row.get("stop_price") or "—",
        row.get("target_price") or "—",
        _short(row.get("daily_action_reason") or row.get("no_buy_reason") or "", 78),
    ] for row in entries]
    exit_rows = [[
        f"{row.get('name')} {row.get('code')}",
        row.get("daily_action_label") or row.get("daily_action") or "—",
        _tw_signal_label(row.get("internal_signal")),
        _fmt_num(float(row["close"])) if row.get("close") else "—",
        row.get("support_price") or "—",
        _short(row.get("daily_action_reason") or row.get("no_buy_reason") or "", 88),
    ] for row in exits]
    raw_market_filter = blockers[0].get("old_wang_market_filter", "—") if blockers else "—"
    market_filter = _TW_MARKET_FILTER_LABELS.get(str(raw_market_filter), str(raw_market_filter))
    return entry_rows, exit_rows, market_filter


def build_tw_audit_report(trades: list[dict]) -> str:
    closed, open_lots = build_closed_trades(trades)
    total_pnl = sum(trade.realized_pnl for trade in closed)
    wins = sum(1 for trade in closed if trade.realized_pnl > 0)
    price_warnings = _trade_price_warnings(trades)
    entry_checks = _tw_entry_check_rows(trades)
    compliant_count = sum(1 for row in entry_checks if row[9].startswith("合規："))
    entry_rows, exit_rows, market_filter = _tw_current_rows()
    summary = _load_json(OUT / "summary.json", {})

    lines = [
        "# 台股歷史交易稽核（2026-05 起）",
        "",
        f"- 產生日期：{date.today().isoformat()}",
        f"- 訊號資料日：{summary.get('as_of', '—')}",
        f"- 範圍：交易建立日或交易日 >= {START_DATE}；因此旺宏雖標示 04-30，仍因 05-07 才建立紀錄而納入。",
        "- 損益口徑：買進成本含手續費；賣出收入扣手續費與證交稅。已有 net_amount 沿用原紀錄，缺值才依目前設定補算。",
        "- 本報告是復盤用途，不是下單指令。",
        "",
        "## 結論",
        "",
        (
            f"- 共 {len(closed)} 組已平倉，勝率 {wins}/{len(closed) if closed else 0}，"
            f"{'暫估' if price_warnings else '已實現'}損益 {_fmt_money(total_pnl)} 元。"
        ),
        f"- 待確認交易資料：{len(price_warnings)} 筆；未歸零前不得把暫估損益當成正式實績。",
        f"- 進場紀錄合規檢核：{compliant_count}/{len(entry_checks)} 筆符合當日系統進場動作與價格計畫；其餘不可直接算成策略照單執行績效。",
        f"- 最新老王大盤濾網：`{market_filter}`；為 block 時，短波段新多單應降權。",
        "- 推論公式可重現，但多筆實際成交價與當日 OHLCV / 前一交易日建議區不一致，所以『策略計算正確』不等於『交易紀錄可直接信任』。",
        "",
        "## 旺宏專項判斷",
        "",
        "- 舊報告用 2026-04-30 收盤後重算的計畫（建議 138–147.86、止盈 171.5）去對照同日成交 174，造成『進場價高於止盈』。這是報告的時間基準錯誤，不是策略故意設計虧損。",
        "- 可在 04-30 交易前取得的最新計畫應是 04-29 收盤：訊號 `watchlist`、動作「等回測」、建議 136.12–145.84、停損 136.12、目標 190.25。",
        "- 實際成交 174 雖未高於前一日目標 190.25，仍遠高於建議上緣 145.84，而且當日不是確認進場，所以仍判定不合規。",
        "- 修正後所有建議價、停損與止盈一律取前一交易日收盤快照，避免把當天尚未完成的 K 棒偷放進進場判斷。",
        "",
        "## 實際進出與損益",
        "",
        _md_table(
            ["股票", "進場日期", "建議進場價", "實際進場價", "預計停損", "預計止盈", "出場日", "出場價", "出場原因", "損益", "報酬", "策略"],
            _tw_closed_rows(closed),
        ),
        "",
        "## 逐筆進場合規檢核",
        "",
        _md_table(
            ["股票", "進場日", "訊號基準日", "基準日動作 / 訊號", "基準日收盤", "建議區", "實際價", "停損", "止盈", "檢核", "策略"],
            entry_checks,
        ),
        "",
        "## 交易價資料品質警示",
        "",
        "下列交易價落在同日 OHLCV 高低區間外（保留 1% 容差）。這可能是輸入錯價、日期錯位、單位或除權息尺度問題；校正前，相關損益與策略歸因只能視為暫估。",
        "",
        _md_table(["股票", "日期", "類型", "交易價", "當日低–高", "收盤", "距區間", "判斷"], price_warnings),
        "",
        "## 尚未平倉",
        "",
    ]
    if open_lots:
        lines.append(_md_table(
            ["股票", "進場日", "建議進場價", "實際進場價", "剩餘股數", "預計停損", "預計止盈", "策略", "檢核"],
            [[
                f"{lot.name} {lot.stock_id}", lot.entry_date, _entry_zone(lot.plan),
                _fmt_num(lot.entry_price), str(lot.remaining), _fmt_num(lot.plan.stop_price),
                _fmt_num(lot.plan.target_price), lot.plan.strategy,
                _short(_entry_assessment(lot.plan, lot.entry_price), 100),
            ] for lot in open_lots],
        ))
    else:
        lines.append("_目前範圍內沒有未平倉台股部位。_\n")

    lines.extend([
        "",
        "## 方法限制",
        "",
        "1. 進場計畫與推論出場原因都使用交易日前一個資料日的收盤快照，避免同日 K 棒造成未來資料洩漏。",
        "2. 出場 note 多數未填；報告中的出場原因只是以前一交易日訊號回推，不等於使用者當時主觀理由。",
        "3. 旺宏交易日是 04-30、建立日是 05-07；納入本報告是因系統自 5 月開始記錄，而非宣稱 5 月才買進。",
        "4. 同一賣出一次清掉多批進場時，損益以整個持倉週期彙總；建議價 / 停損 / 止盈依各批進場日分列。",
        "5. 本報告不修正 trades.json；資料警示需回到交易紀錄確認後才可消除。",
        "",
    ])
    return "\n".join(lines)


def build_tw_report(trades: list[dict]) -> str:
    closed, open_lots = build_closed_trades(trades)
    total_pnl = sum(trade.realized_pnl for trade in closed)
    price_warnings = _trade_price_warnings(trades)
    entry_rows, exit_rows, market_filter = _tw_current_rows()
    summary = _load_json(OUT / "summary.json", {})
    freshness = _tw_report_freshness()
    data_complete = bool(freshness["is_complete"])
    if not data_complete:
        entry_rows = []
        exit_rows = []
    pnl_label = "暫估損益" if price_warnings else "已實現損益"
    stale_preview = "、".join(
        f"{item['name']} {item['code']}（{item['data_as_of'] or '無日期'}）"
        for item in freshness["stale_items"][:8]
    )

    lines = [
        "# 台股每日行動報告",
        "",
        f"- 產生日期：{date.today().isoformat()}",
        f"- 訊號資料日：{summary.get('as_of', '—')}",
        "- 本報告只保留今天需要處理的項目；歷史交易細節另見 `strategy_trade_audit_tw_2026-05-01.md`。",
        "- 研究與復盤用途，不是下單指令。",
        "",
        "## 今日結論",
        "",
        f"- 大盤條件：{market_filter}；風險模式時不新增短波段多單。",
        (
            f"- 可小試／觀察 {len(entry_rows)} 檔；降風險／暫不進場 {len(exit_rows)} 檔。"
            if data_complete
            else f"- **逐股資料日尚未對齊，今日動作清單暫停輸出。待確認 {freshness['stale_count']} 檔：{stale_preview or '無可讀逐股資料'}。**"
        ),
        f"- 目前未平倉 {len(open_lots)} 筆；歷史 {pnl_label} {_fmt_money(total_pnl)} 元。",
        (
            f"- **資料警示：{len(price_warnings)} 筆成交價待確認，績效目前只能視為暫估。**"
            if price_warnings
            else "- 交易價資料檢查未發現 OHLCV 區間外異常。"
        ),
        "",
        "## 今日可能進場／觀察",
        "",
        _md_table(
            ["股票", "動作", "訊號", "收盤", "建議區", "停損", "止盈", "原因"],
            entry_rows,
        ) if entry_rows else (
            "_逐股資料日未完全一致，暫不產生今日候選。_\n"
            if not data_complete else "_今日沒有符合條件的新候選。_\n"
        ),
        "",
        "## 今日降風險／暫不進場",
        "",
        _md_table(["股票", "動作", "訊號", "收盤", "支撐", "原因"], exit_rows)
        if exit_rows else (
            "_逐股資料日未完全一致，暫不產生今日降風險清單。_\n"
            if not data_complete else "_今日沒有新增降風險項目。_\n"
        ),
        "",
        "## 目前持倉",
        "",
    ]
    if open_lots:
        lines.append(_md_table(
            ["股票", "進場日", "實際進場價", "剩餘股數", "停損", "止盈", "策略"],
            [[
                f"{lot.name} {lot.stock_id}",
                lot.entry_date,
                _fmt_num(lot.entry_price),
                str(lot.remaining),
                _fmt_num(lot.plan.stop_price),
                _fmt_num(lot.plan.target_price),
                lot.plan.strategy,
            ] for lot in open_lots],
        ))
    else:
        lines.append("_目前沒有未平倉台股部位。_\n")
    return "\n".join(lines)


def _us_replay_rows() -> list[list[str]]:
    trend_summary = _read_replay_summary(OUT / "us_strategy_replay_2026-06-15_2026-06-30.json")
    wbottom_summary = _read_replay_summary(OUT / "us_wbottom_replay_2021-09-01_2026-07-10.json")
    breakout_summary = _read_replay_summary(OUT / "us_breakout_replay_2021-09-01_2026-07-10.json")
    candidate = trend_summary.get("candidate_exit", {}) if isinstance(trend_summary, dict) else {}
    protect = trend_summary.get("trend_protect_exit", {}) if isinstance(trend_summary, dict) else {}
    return [
        ["趨勢延續｜敏感出場", "2026/06/15–06/30", str(candidate.get("completed_trades", "—")), f"{candidate.get('win_rate_pct', '—')}%", f"{candidate.get('avg_return_pct', '—')}%", "否", "退出過度敏感，不採用"],
        ["趨勢延續｜保護線", "2026/06/15–06/30", str(protect.get("completed_trades", "—")), f"{protect.get('win_rate_pct', '—')}%", f"{protect.get('avg_return_pct', '—')}%", "否", "結構較合理；樣本仍太少"],
        ["W 底突破", "2021/09/01–2026/07/10", str(wbottom_summary.get("n", wbottom_summary.get("completed_trades", "—"))), f"{wbottom_summary.get('win_rate_pct', '—')}%", f"{wbottom_summary.get('avg_pct', '—')}%", "否", "勝率較高；空頭年度偏弱"],
        ["突破策略｜偏差檢查", "2021/09/01–2026/07/10", str(breakout_summary.get("n", breakout_summary.get("completed_trades", "—"))), f"{breakout_summary.get('win_rate_pct', '—')}%", f"{breakout_summary.get('avg_pct', '—')}%", "否", "扣除生存者偏差後優勢消失"],
    ]

_BIAS_LABELS = {"bullish": "偏多", "bearish": "偏空", "mixed": "多空不明", "unknown": "未知"}

NEAR_TRIGGER_PCT = 0.08
FAR_TRIGGER_PCT = 0.15

# 觀望不是一種狀態，而是四種不同的等待理由；混成一桶就看不出今天該盯誰。
BUCKET_ENTER = "enter"
BUCKET_WATCH = "watch"
BUCKET_IGNORE = "ignore"
BUCKET_DEAD = "dead"


def _bias_label(bias: Any) -> str:
    return _BIAS_LABELS.get(bias, str(bias or "未知"))


def _neckline_distance(pattern: dict) -> float:
    close, neckline = pattern.get("close"), pattern.get("neckline")
    if not close or neckline is None:
        return float("inf")
    return (neckline - close) / close


def _invalidation_reason(pattern: dict) -> str:
    """說明它「現在為什麼失效」，不是重複當初突破的理由。"""
    close, low = pattern.get("close"), pattern.get("pattern_low")
    breakout = pattern.get("breakout_date")
    prefix = f"{breakout} 突破後回落，" if breakout else ""
    if not close or low is None:
        return f"{prefix}型態條件已破壞".lstrip("，")
    drop = (low - close) / low * 100
    return f"{prefix}收盤 {_fmt_num(close)} 跌破型態低 {_fmt_num(low)}（低 {drop:.1f}%），不再追蹤"


@dataclass
class UsWatchRow:
    bucket: str
    code: str
    label: str
    action: str
    strategy: str
    close: float | None
    trigger: str
    invalidation: str
    target: str
    reward_risk: str
    reason: str

    def cells(self) -> list[str]:
        return [
            self.label, self.action, self.strategy, _fmt_num(self.close),
            self.trigger, self.invalidation, self.target, self.reward_risk,
        ]


def _trend_watch_row(item: dict, gate_bias: str) -> UsWatchRow:
    code = str(item.get("code", "")).upper()
    close = item.get("close")
    ma20, ma60 = item.get("ma20"), item.get("ma60")
    fresh = gate_bias == "bullish" and item.get("state") == "candidate"
    return UsWatchRow(
        bucket=BUCKET_ENTER if fresh else BUCKET_WATCH,
        code=code,
        label=f"{item.get('name') or code} {code}",
        action="可紙上追蹤：次一交易日開盤" if fresh else "等待：SPY / QQQ 同步轉多",
        strategy="趨勢延續",
        close=close,
        trigger=f"收盤維持 MA20 {_fmt_num(ma20)} 之上（緩衝 {_gap_pct(close, ma20)}）",
        invalidation=f"連 2 日跌破 MA20 {_fmt_num(ma20)}，或跌破 MA60 {_fmt_num(ma60)}（{_gap_pct(close, ma60)}）",
        target="趨勢延續，不設固定目標",
        reward_risk="不適用（無固定目標）",
        reason=_short("；".join(item.get("reasons", [])[:2]), 96),
    )


def _wbottom_watch_row(item: dict, gate_active: bool) -> UsWatchRow:
    code = str(item.get("code", "")).upper()
    close = item.get("close")
    state = item.get("state")
    distance = _neckline_distance(item)

    if state == "breakout_today" and gate_active:
        bucket, action = BUCKET_ENTER, "可紙上追蹤：次一交易日開盤"
    elif state == "breakout_today":
        bucket, action = BUCKET_WATCH, "等待：大盤濾網重新開啟"
    elif state == "breakout_in_progress":
        bucket, action = BUCKET_WATCH, "只追蹤：原始次日觸發已過，不追價"
    elif state == "invalidated":
        bucket, action = BUCKET_DEAD, "已失效：移出追蹤"
    elif distance <= NEAR_TRIGGER_PCT:
        bucket, action = BUCKET_WATCH, f"等突破：離頸線 {_gap_pct(close, item.get('neckline'))}"
    elif distance <= FAR_TRIGGER_PCT:
        bucket, action = BUCKET_IGNORE, f"暫不看：離頸線 {_gap_pct(close, item.get('neckline'))}"
    else:
        bucket, action = BUCKET_IGNORE, f"距離仍遠：離頸線 {_gap_pct(close, item.get('neckline'))}"

    if state == "invalidated":
        # 型態已死，觸發價 / 目標 / 報酬風險比都不再有意義，留著只會被誤讀成還能追
        trigger, target, reward_risk = "—", "—", "—"
        invalidation = f"已跌破型態低 {_fmt_num(item.get('pattern_low'))}"
        reason = _invalidation_reason(item)
    else:
        trigger = f"頸線 {_price_with_gap(close, item.get('neckline'))}"
        invalidation = f"收盤跌破型態低 {_price_with_gap(close, item.get('pattern_low'))}"
        target = _price_with_gap(close, item.get("target_price"))
        reward_risk = _reward_risk(close, item.get("target_price"), item.get("pattern_low"))
        reason = _short("；".join(item.get("reasons", [])[:1]), 96)

    return UsWatchRow(
        bucket=bucket,
        code=code,
        label=f"{item.get('name') or code} {code}",
        action=action,
        strategy="W 底突破",
        close=close,
        trigger=trigger,
        invalidation=invalidation,
        target=target,
        reward_risk=reward_risk,
        reason=reason,
    )


def _us_watch_rows(trend: dict, wbottom: dict) -> list[UsWatchRow]:
    """把兩個策略的所有標的攤成一張清單並分桶；同一檔只能出現在一個桶。"""
    rows: list[UsWatchRow] = []
    seen: set[str] = set()
    gate_bias = (trend.get("market_gate") or {}).get("bias", "unknown")
    gate_active = bool((wbottom.get("market_gate") or {}).get("active"))

    for item in trend.get("candidates", []):
        code = str(item.get("code", "")).upper()
        if not code or code in seen:
            continue
        seen.add(code)
        rows.append(_trend_watch_row(item, gate_bias))

    patterns = sorted(wbottom.get("patterns", []), key=_neckline_distance)
    for item in patterns:
        code = str(item.get("code", "")).upper()
        if not code or code in seen:
            continue
        seen.add(code)
        rows.append(_wbottom_watch_row(item, gate_active))

    return rows


def _bucket(rows: list[UsWatchRow], bucket: str) -> list[UsWatchRow]:
    return [row for row in rows if row.bucket == bucket]


US_WATCH_HEADERS = [
    "股票", "今日動作", "策略", "收盤", "觸發 / 守線", "失效條件", "觀察目標", "報酬風險比",
]


def _us_bucket_section(rows: list[UsWatchRow], empty_note: str) -> str:
    if not rows:
        return f"_{empty_note}_\n"
    table = _md_table(US_WATCH_HEADERS, [row.cells() for row in rows])
    notes = "\n".join(f"{i}. {row.label}：{row.reason}" for i, row in enumerate(rows, start=1))
    return f"{table}\n**依據**\n\n{notes}\n"


def _us_daily_decision(trend: dict, wbottom: dict, actionable_count: int) -> str:
    trend_gate = trend.get("market_gate") or {}
    wbottom_gate = wbottom.get("market_gate") or {}
    if actionable_count > 0:
        return f"今日有 {actionable_count} 檔當日新訊號可進入紙上追蹤；仍須依各列保護線管理。"
    if not trend_gate.get("active") and not wbottom_gate.get("active"):
        return (
            f"今日不新增紙上追蹤：趨勢濾網＝{_bias_label(trend_gate.get('bias'))}、"
            "W 底濾網關閉；既有型態只追蹤、不追價。"
        )
    return "今日沒有當日新訊號；等待新的趨勢候選或 W 底突破，不以舊訊號補進場。"


def build_us_report(trades: list[dict], as_of: str | None = None) -> str:
    status, trend, wbottom = _current_us_status(as_of=as_of)
    rows = _us_watch_rows(trend, wbottom)
    enter_rows = _bucket(rows, BUCKET_ENTER)
    watch_rows = _bucket(rows, BUCKET_WATCH)
    ignore_rows = _bucket(rows, BUCKET_IGNORE)
    dead_rows = _bucket(rows, BUCKET_DEAD)
    daily_decision = _us_daily_decision(trend, wbottom, len(enter_rows))
    trend_gate = trend.get("market_gate") or {}
    wbottom_gate = wbottom.get("market_gate") or {}

    if trades:
        actual_note = (
            f"發現 {len(trades)} 筆疑似美股交易，但目前 trades.json 沒有市場 / 幣別 / 美股費率欄位，"
            "為避免用台股證交稅錯算，未產生虛假的美股損益。"
        )
    else:
        actual_note = "目前 trades.json 沒有任何美股實際買賣紀錄，所以沒有已實現損益可算。"

    lines = [
        "# 美股每日觀察報告",
        "",
        f"- 產生日期：{date.today().isoformat()}",
        f"- 美股資料日：{trend.get('as_of') or status.get('last_data_as_of', '—')}",
        "- 美股只有觀察策略，沒有正式推薦桶、沒有自動下單；「紙上追蹤」是記錄用途，不是買進指令。",
        "- 研究與復盤用途，不是下單指令。",
        "",
        "## 今日結論",
        "",
        f"- 大盤條件：趨勢濾網 {_bias_label(trend_gate.get('bias'))}"
        f"（{'開啟' if trend_gate.get('active') else '關閉'}）"
        f"、W 底濾網 {'開啟' if wbottom_gate.get('active') else '關閉'}；兩者都關閉時不新增紙上追蹤。",
        f"- 可紙上追蹤 {len(enter_rows)} 檔；觀望 {len(watch_rows)} 檔；"
        f"今日不必看 {len(ignore_rows)} 檔；已失效 {len(dead_rows)} 檔"
        f"（合計 {len(rows)} 檔，涵蓋全部追蹤標的）。",
        f"- 目前未平倉 0 筆；美股無已實現損益。{actual_note}",
        f"- **{daily_decision}**",
        "",
        "## 今日可紙上追蹤",
        "",
        "- 只有訊號是當日新鮮、且大盤濾網開啟時才會進這一桶。這是觀察紀錄，不是買進指令。",
        "",
        _us_bucket_section(enter_rows, "今日沒有符合條件的新候選。"),
        "",
        "## 今日觀望",
        "",
        "- 條件還差一步：可能是等大盤轉多、等突破頸線，或是已突破但錯過原始觸發日、不該追價。",
        "- 括號裡的百分比是「離現價多遠」。報酬風險比 = 上檔空間 ÷ 下檔失效距離，低於 1 : 1 表示現在追進不划算。",
        "",
        _us_bucket_section(watch_rows, "今日沒有觀望名單。"),
        "",
        "## 今日不必看",
        "",
        f"- 離觸發價超過 {int(NEAR_TRIGGER_PCT * 100)}%，今天盯它沒有意義；留著只為了下次接近時能追溯。",
        "",
        _us_bucket_section(ignore_rows, "今日沒有需要冷處理的型態。"),
        "",
        "## 已失效 / 狀態變化",
        "",
        "- 曾經追蹤、現在條件已破壞的型態。不列出來就會以為它還在觀察名單裡。",
        "",
        _us_bucket_section(dead_rows, "本期沒有型態失效。"),
        "",
        "## 回放摘要（模擬，不能當進場依據）",
        "",
        "- 下面每一列都是歷史模擬。**勝率高不等於策略有效**——偏差檢查那列就是同一套規則扣掉生存者偏差後的結果。",
        "- 回放績效不能填進『實際進場價 / 實際損益』欄，否則會把模擬結果偽裝成真實交易。",
        "",
        _md_table(
            ["策略", "期間", "完成筆數", "勝率", "平均報酬", "能否作為進場依據", "判斷"],
            _us_replay_rows(),
        ),
        "",
        "## 方法限制",
        "",
        "1. 美股 trades 尚無市場、幣別與券商費率欄位；在補齊契約前不能沿用台股 0.3% 證交稅計算。",
        "2. 趨勢延續策略只是觀察排序，沒有正式進出場價；W 底的頸線 / 型態低 / 量幅目標也只是型態觀察點。",
        "3. 回放使用歷史 OHLCV 與固定規則，受滑價、股息、存活者偏差與樣本期影響，不能視為帳戶實績。",
        "4. 若要建立真正的美股實績表，需先讓交易紀錄保存 market / currency / fee / tax / strategy_snapshot。",
        "",
    ]
    return "\n".join(lines)


def build_combined_report(tw_report: str, us_report: str) -> str:
    return "\n".join([
        "# New Stock 策略報告（2026-05 起）",
        "",
        f"- 產生日期：{date.today().isoformat()}",
        "- 內容分為台股實際交易復盤與美股觀察策略，兩者不混算績效。",
        "- 本報告是研究與驗收用途，不是下單指令。",
        "",
        tw_report,
        "",
        "---",
        "",
        us_report,
        "",
    ])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="產生 New Stock 台股／美股策略報告")
    parser.add_argument(
        "--market",
        choices=("all", "tw", "us"),
        default="all",
        help="只產生指定市場報告；all 保留手動產生合併報告的相容行為",
    )
    parser.add_argument(
        "--as-of",
        help="固定歷史資料日（YYYY-MM-DD）；只供重播驗收，不影響排程預設最新資料",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    OUT.mkdir(exist_ok=True)
    trades = _load_json(DATA / "trades.json", [])
    tw_trades, us_trades = _split_market_trades(trades)
    if args.market == "tw":
        TW_REPORT_PATH.write_text(build_tw_report(tw_trades), encoding="utf-8")
        TW_AUDIT_REPORT_PATH.write_text(build_tw_audit_report(tw_trades), encoding="utf-8")
        print(TW_REPORT_PATH)
        print(TW_AUDIT_REPORT_PATH)
        return 0
    if args.market == "us":
        US_REPORT_PATH.write_text(build_us_report(us_trades, as_of=args.as_of), encoding="utf-8")
        print(US_REPORT_PATH)
        return 0

    tw_report = build_tw_report(tw_trades)
    tw_audit_report = build_tw_audit_report(tw_trades)
    us_report = build_us_report(us_trades, as_of=args.as_of)
    COMBINED_REPORT_PATH.write_text(
        build_combined_report(tw_report, us_report),
        encoding="utf-8",
    )
    TW_REPORT_PATH.write_text(tw_report, encoding="utf-8")
    TW_AUDIT_REPORT_PATH.write_text(tw_audit_report, encoding="utf-8")
    US_REPORT_PATH.write_text(us_report, encoding="utf-8")
    for path in (COMBINED_REPORT_PATH, TW_REPORT_PATH, TW_AUDIT_REPORT_PATH, US_REPORT_PATH):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
