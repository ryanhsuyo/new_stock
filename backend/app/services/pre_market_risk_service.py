"""盤前風險中心：用本機隔夜行情與人工事件筆記產生可解釋風險提示。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.services.us_market_service import get_us_data_freshness
from app.storage.market_note_store import load_market_notes
from app.storage.official_market_event_store import load_official_market_events
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
_TAIPEI = ZoneInfo("Asia/Taipei")


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
    return "normal", "未觸發額外防守", 100, True


def _official_event_summary(now: datetime | None = None) -> dict[str, Any]:
    current = (now or datetime.now(_TAIPEI)).astimezone(_TAIPEI)
    payload = load_official_market_events()
    verified_at = str(payload.get("verified_at") or "")
    verification_age_days: int | None = None
    try:
        verified = datetime.strptime(verified_at, "%Y-%m-%d").date()
        verification_age_days = max(0, (current.date() - verified).days)
    except ValueError:
        pass

    window_end = current + timedelta(days=14)
    events: list[dict[str, Any]] = []
    for raw in payload.get("events") or []:
        try:
            scheduled = datetime.fromisoformat(str(raw.get("scheduled_at") or "")).astimezone(_TAIPEI)
        except (TypeError, ValueError):
            continue
        if scheduled < current or scheduled > window_end:
            continue
        events.append({
            "id": str(raw.get("id") or ""),
            "title": str(raw.get("title") or "官方事件"),
            "category": str(raw.get("category") or "other"),
            "importance": str(raw.get("importance") or "medium"),
            "scheduled_at": scheduled.isoformat(timespec="minutes"),
            "date_label": "今日" if scheduled.date() == current.date() else scheduled.strftime("%m/%d"),
            "time_label": scheduled.strftime("%H:%M"),
            "original_time": str(raw.get("original_time") or ""),
            "source_label": str(raw.get("source_label") or "官方來源"),
            "source_url": str(raw.get("source_url") or ""),
        })
    events.sort(key=lambda item: item["scheduled_at"])
    return {
        "verified_at": verified_at or None,
        "verification_age_days": verification_age_days,
        "is_stale": verification_age_days is None or verification_age_days > 7,
        "verification_note": str(payload.get("verification_note") or ""),
        "window_days": 14,
        "event_count": len(events),
        "events": events,
        "scoring_note": "官方事件只做時間提醒，不直接加入風險分數。",
    }


_RISK_SEVERITY = {"normal": 0, "watch": 1, "defensive": 2, "extreme": 3}
_RISK_LABELS = {"normal": "未觸發額外防守", "watch": "警戒", "defensive": "防守", "extreme": "極端風險"}

# 缺幾項輸入 → 至少要落在哪一級。回放可以在 unknown 時停手，production 每天都要出報告，
# 所以改成推估；但推估只能往保守方向，缺資料不得產生比較安全的結論。
_DEGRADED_FLOOR = {0: "defensive", 1: "watch"}


def _more_severe(left: str, right: str) -> str:
    return left if _RISK_SEVERITY.get(left, 0) >= _RISK_SEVERITY.get(right, 0) else right


def estimate_pre_market_risk(signals: list[dict[str, Any]], score: int) -> dict[str, Any]:
    """輸入不完整時推出一個等級，而不是停在 unknown。

    已知分數是真實分數的下界（缺漏項只可能加分、不會扣分），所以 level(已知分數)
    是「可得資料所支持」的最寬鬆結果；推估值不得比它更寬鬆。
    """
    usable = [s for s in signals if s.get("change_pct") is not None]
    missing = [str(s.get("code")) for s in signals if s.get("change_pct") is None]
    supported_level, _label, _exposure, _ok = _classification(score)
    floor = _DEGRADED_FLOOR.get(len(usable), "normal")
    level = _more_severe(supported_level, floor)
    return {
        "level": level,
        "level_label": _RISK_LABELS.get(level, level),
        "score": score,
        "degraded": True,
        "usable_count": len(usable),
        "missing_inputs": missing,
        "supported_level": supported_level,
        "reason": (
            f"盤前輸入只有 {len(usable)} 項可用（缺 {'、'.join(missing) or '無'}），"
            f"以可得資料推估為「{_RISK_LABELS.get(level, level)}」；缺資料不下修風險。"
        ),
    }


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
            "normal": "目前可用的隔夜行情與人工事件筆記未觸發防守門檻；這不代表今日不會大跌。",
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
        "official_event_summary": _official_event_summary(),
        "guidance": {
            "new_positions": (
                "暫停一般新倉"
                if not can_open
                else "未觸發額外防守；仍依策略、停損與部位上限"
            ),
            "opening_rule": (
                "極端或未知狀態先等開盤 30 分鐘，再用當日市場廣度重新判斷。"
                if level in {"extreme", "unknown"}
                else "開盤跳空、盤中市場廣度或突發新聞仍可能改變風險；不因盤前未觸發就放寬停損。"
            ),
            "max_exposure_pct": max_exposure,
        },
        "official_sources": list(_OFFICIAL_SOURCES),
        "limitations": [
            "這是風險提示，不是崩盤預測或買賣建議。",
            "第一版未自動抓取新聞全文；事件證據來自人工市場筆記，官方連結供交叉確認。",
            "未觸發只代表目前已納入的資料沒有越過門檻，不代表市場安全或排除盤中突發事件。",
            "美股 EOD 行情若過期，系統會回傳待確認而不是假裝正常。",
        ],
    }
