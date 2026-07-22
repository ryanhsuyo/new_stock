"""盤前風險中心：用本機隔夜行情與人工事件筆記產生可解釋風險提示。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.us_market_service import get_us_data_freshness
from app.storage.market_note_store import load_market_notes
from app.storage.us_market_store import load_us_ohlcv


_BENCHMARKS = (
    {"code": "QQQ", "label": "NASDAQ 100（QQQ）", "watch": -1.5, "severe": -3.0, "watch_points": 2, "severe_points": 4},
    {"code": "TSM", "label": "台積電 ADR（TSM）", "watch": -2.0, "severe": -4.0, "watch_points": 2, "severe_points": 4},
    {"code": "SPY", "label": "S&P 500（SPY）", "watch": -1.2, "severe": -2.5, "watch_points": 1, "severe_points": 3},
)

_OFFICIAL_SOURCES = (
    {"label": "公開資訊觀測站即時重大訊息", "url": "https://mops.twse.com.tw/mops/web/t120sb02_q10", "scope": "台灣上市櫃公司重大訊息"},
    {"label": "台積電投資人行事曆", "url": "https://investor.tsmc.com/chinese/financial-calendar", "scope": "法說、月營收與財務事件"},
    {"label": "Federal Reserve FOMC Calendar", "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", "scope": "利率決議與會議紀要"},
    {"label": "U.S. BLS Release Calendar", "url": "https://www.bls.gov/schedule/news_release/", "scope": "CPI、PPI、就業等美國數據"},
)


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _benchmark_signal(spec: dict[str, Any], rows: list[dict]) -> dict[str, Any]:
    base = {
        "key": spec["code"].lower(),
        "code": spec["code"],
        "label": spec["label"],
        "data_as_of": None,
        "change_pct": None,
        "status": "missing",
        "points": 0,
        "reason": f"{spec['label']} 缺少連續兩個交易日資料。",
    }
    if len(rows) < 2:
        return base
    previous = _to_float(rows[-2].get("close"))
    latest = _to_float(rows[-1].get("close"))
    if previous is None or latest is None or previous <= 0:
        return base
    change = round((latest / previous - 1) * 100, 2)
    base["data_as_of"] = str(rows[-1].get("date") or "") or None
    base["change_pct"] = change
    if change <= spec["severe"]:
        base.update(status="severe", points=spec["severe_points"], reason=f"{spec['label']} 單日 {change:.2f}%，達極端風險門檻。")
    elif change <= spec["watch"]:
        base.update(status="warning", points=spec["watch_points"], reason=f"{spec['label']} 單日 {change:.2f}%，進入盤前警戒。")
    else:
        base.update(status="ok", reason=f"{spec['label']} 單日 {change:.2f}%，未觸發跌幅門檻。")
    return base


def _latest_event_signal(reference_date: str | None) -> tuple[dict[str, Any] | None, int]:
    notes = sorted(load_market_notes(), key=lambda item: str(item.get("date") or ""), reverse=True)
    if not notes:
        return None, 0
    note = notes[0]
    note_date = str(note.get("date") or "")
    is_stale = True
    try:
        reference = datetime.strptime(str(reference_date or ""), "%Y-%m-%d").date()
        noted = datetime.strptime(note_date, "%Y-%m-%d").date()
        is_stale = abs((reference - noted).days) > 3
    except ValueError:
        pass
    risk = str(note.get("risk_level") or "neutral").strip().lower()
    severe = risk in {"extreme", "high", "critical", "risk"}
    warning = severe or risk in {"warn", "warning", "caution", "defensive"}
    points = 0 if is_stale else 4 if severe else 2 if warning else 0
    return {
        "date": note_date or None,
        "title": str(note.get("title") or "人工市場筆記"),
        "headline": str(note.get("headline") or ""),
        "risk_level": risk,
        "source": str(note.get("source") or "manual_api"),
        "status": "stale" if is_stale else "severe" if severe else "warning" if warning else "info",
        "is_stale": is_stale,
        "points": points,
    }, points


def _classification(score: int) -> tuple[str, str, int | None, bool]:
    if score >= 8:
        return "extreme", "極端風險", 30, False
    if score >= 4:
        return "defensive", "防守", 50, False
    if score >= 2:
        return "watch", "警戒", 70, True
    return "normal", "正常", 100, True


def assess_historical_pre_market_risk(fill_date: str, ohlcv: dict[str, list[dict]]) -> dict[str, Any]:
    """用台股成交日前已完成的美股日 K 評估風險；嚴禁使用 date >= fill_date。"""
    selected: dict[str, list[dict]] = {}
    for spec in _BENCHMARKS:
        rows = [row for row in ohlcv.get(spec["code"], []) if str(row.get("date") or "") < fill_date]
        selected[spec["code"]] = rows
    signals = [_benchmark_signal(spec, selected[spec["code"]]) for spec in _BENCHMARKS]
    score = sum(int(item["points"]) for item in signals)
    dates = [str(item["data_as_of"]) for item in signals if item.get("data_as_of")]
    enough = sum(item["change_pct"] is not None for item in signals) >= 2
    data_as_of = max(dates) if dates else None
    fresh = False
    try:
        fresh = 0 < (datetime.strptime(fill_date, "%Y-%m-%d").date() - datetime.strptime(str(data_as_of), "%Y-%m-%d").date()).days <= 4
    except ValueError:
        pass
    if not enough or not fresh:
        return {"level": "unknown", "level_label": "待確認", "score": score, "data_as_of": data_as_of, "signals": signals}
    level, label, _, _ = _classification(score)
    return {"level": level, "level_label": label, "score": score, "data_as_of": data_as_of, "signals": signals}


def get_pre_market_risk_report() -> dict[str, Any]:
    ohlcv = load_us_ohlcv()
    signals = [_benchmark_signal(spec, ohlcv.get(spec["code"], [])) for spec in _BENCHMARKS]
    freshness = get_us_data_freshness()
    event, event_points = _latest_event_signal(freshness.get("expected_trading_day"))
    score = sum(int(item["points"]) for item in signals) + event_points
    enough_benchmarks = sum(item["change_pct"] is not None for item in signals) >= 2
    stale = bool(freshness.get("stale"))

    if stale or not enough_benchmarks:
        level, label, max_exposure, can_open = "unknown", "待確認", None, False
        reason = "隔夜行情已過期，請先更新美股資料。" if stale else "至少需要兩個隔夜基準的連續行情才能分級。"
    else:
        level, label, max_exposure, can_open = _classification(score)
        reason = {
            "normal": "目前可用的隔夜行情與事件證據未形成明顯共振。",
            "watch": "已有單一或輕度風險訊號，降低追價與新倉規模。",
            "defensive": "多項風險訊號共振，暫停一般新倉並降低曝險。",
            "extreme": "權值／科技市場出現極端壓力，維持防守並等待開盤波動收斂。",
        }[level]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "level_label": label,
        "score": score,
        "headline": reason,
        "data_as_of": freshness.get("last_updated"),
        "data_freshness": freshness,
        "can_open_new_positions": can_open,
        "max_exposure_pct": max_exposure,
        "signals": signals,
        "latest_event": event,
        "guidance": {
            "new_positions": "暫停一般新倉" if not can_open else "可依原策略，但遵守部位上限",
            "opening_rule": "極端或未知狀態先等開盤 30 分鐘，再用當日市場廣度重新判斷。" if level in {"extreme", "unknown"} else "不因新聞標題追價，仍需價格與量能確認。",
            "max_exposure_pct": max_exposure,
        },
        "official_sources": list(_OFFICIAL_SOURCES),
        "limitations": [
            "這是風險提示，不是崩盤預測或買賣建議。",
            "第一版未自動抓取新聞全文；事件證據來自人工市場筆記，官方連結供交叉確認。",
            "美股 EOD 行情若過期，系統會回傳待確認而不是假裝正常。",
        ],
    }
