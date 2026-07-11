"""
us_strategy_service.py — 美股觀察策略：us_trend_follow（大盤守門的趨勢延續觀察）。

**非推薦、非買賣建議、非下單。** 輸出只有觀察語言（candidate / watch / avoid /
overheated）與排序 rank；**不產出 0–100 分數、不給進場價 / 停損價**。

在 Phase 2 指標（us_analysis_service）之上做跨檔收斂：
  - 大盤守門（SPY/QQQ 相對 MA60，複用 us_watch_signal_service._market_context）：
    bearish / unknown 時誠實回空 candidates（關門本身就是資訊）。
  - 入選 / 排除規則全部只用既有欄位（close / MA20 / MA60 / RSI14 / 20 日漲跌幅 /
    dist_ma20 / category），不引入新指標。
  - 每筆（含 excluded）都有 reasons；candidate 另有 risk_notes。

**不套用台股 old_wang / steady_momentum；不改台股主流程。**
過熱門檻引用 us_analysis_service 既有常數；資料量門檻引用 us_watch_signal_service
的 MIN_SIGNAL_ROWS——避免同一規則在第三處重複寫死（CLAUDE.md §10）。
"""

from __future__ import annotations

from app.services.us_analysis_service import (
    OVERHEATED_DIST_MA20,
    OVERHEATED_RSI,
    get_us_analysis,
)
from app.services.us_watch_signal_service import MIN_SIGNAL_ROWS, _market_context

STRATEGY = "us_trend_follow"
STRATEGY_LABEL = "趨勢延續（大盤守門）"

# 策略自有門檻（單一來源，只在此檔定義）
RSI_MIN = 50.0            # 有動能
RSI_MAX = 68.0            # 未逼近過熱（70 為既有 OVERHEATED_RSI）
DIST_MA20_MAX = 8.0       # 防追高：站上 MA20 但乖離 ≤ +8%
ETF_CATEGORY = "ETF / Benchmark"   # ETF 是大盤量尺，不列個股候選

# 大盤守門文案：bearish / unknown 一律關門並明講「不是故障，是規則」
_GATE_NOTE = {
    "bullish": "SPY / QQQ 皆在 MA60 上方，策略啟用",
    "mixed":   "SPY / QQQ 分歧，candidate 降為 watch（大盤分歧）",
    "bearish": "大盤在 MA60 下方或資料不足，本策略今日不產生觀察對象",
    "unknown": "大盤在 MA60 下方或資料不足，本策略今日不產生觀察對象",
}


def classify_trend_follow(a: dict, market_bias: str) -> dict:
    """
    純函式：單檔 analysis item + 大盤 bias → 分桶結果。
    回傳 {"bucket": "candidate" | "excluded", "state", "reasons", "risk_notes"}。
    排除判斷順序：ETF 量尺 → 資料不足 → 過熱 → 跌破 MA60 → 修復中 → 入選條件逐項。
    """
    close = a.get("last_close")
    ma20 = a.get("ma20")
    ma60 = a.get("ma60")
    rsi = a.get("rsi14")
    dist = a.get("dist_ma20_pct")
    chg = a.get("change_20d_pct")

    def excluded(state: str, reasons: list[str]) -> dict:
        return {"bucket": "excluded", "state": state, "reasons": reasons, "risk_notes": []}

    # ETF / Benchmark：量尺不是標的
    if a.get("category") == ETF_CATEGORY:
        return excluded("watch", ["ETF 作為大盤量尺，不列入個股候選"])

    # 資料不足：無法計算 ≠ 弱勢，但一律不列候選
    if (
        a.get("status") == "no_data"
        or a.get("row_count", 0) < MIN_SIGNAL_ROWS
        or close is None or ma20 is None or ma60 is None or rsi is None or dist is None
    ):
        return excluded("avoid", [f"資料不足或尚未回補（需 ≥ {MIN_SIGNAL_ROWS} 筆）"])

    # 過熱：沿用 Phase 2 既有門檻
    if rsi >= OVERHEATED_RSI or dist >= OVERHEATED_DIST_MA20:
        reasons = []
        if rsi >= OVERHEATED_RSI:
            reasons.append(f"RSI {rsi} ≥ {OVERHEATED_RSI:g}，過熱")
        if dist >= OVERHEATED_DIST_MA20:
            reasons.append(f"距 MA20 +{dist}% ≥ +{OVERHEATED_DIST_MA20:g}%，乖離過大")
        return excluded("overheated", reasons)

    # 長線偏弱
    if close < ma60:
        return excluded("avoid", [f"收盤 {close:.2f} 跌破 MA60 {ma60}，長線偏弱"])

    # 均線尚未翻多（修復中）：列 watch、非候選
    if a.get("status") == "recovering":
        return excluded("watch", ["均線尚未翻多，修復中"])

    # 入選條件逐項檢查；任一不符 → excluded(watch) 並列出未通過原因
    fails: list[str] = []
    if close <= ma20:
        fails.append(f"收盤 {close:.2f} 未站上 MA20 {ma20}（回檔中，非趨勢延續段）")
    if ma20 <= ma60:
        fails.append(f"MA20 {ma20} 未在 MA60 {ma60} 之上，均線未翻多")
    if rsi < RSI_MIN:
        fails.append(f"RSI {rsi} 低於 {RSI_MIN:g}，動能不足")
    elif rsi > RSI_MAX:
        fails.append(f"RSI {rsi} 高於 {RSI_MAX:g}，接近過熱，暫不列入（防追高）")
    if dist > DIST_MA20_MAX:
        fails.append(f"距 MA20 +{dist}% 高於 +{DIST_MA20_MAX:g}%，暫不列入（防追高）")
    if chg is None or chg <= 0:
        fails.append(f"20 日漲跌幅 {chg if chg is not None else '—'}% ≤ 0，近月未走升")
    if fails:
        return excluded("watch", fails)

    # candidate（mixed 時降為 watch）
    reasons = [
        f"收盤 {close:.2f} > MA20 {ma20} > MA60 {ma60}（多頭排列）",
        f"RSI {rsi} 介於 {RSI_MIN:g}–{RSI_MAX:g}，有動能未過熱",
        f"距 MA20 +{dist}%（≤ +{DIST_MA20_MAX:g}%，未追高）",
        f"20 日漲跌幅 +{chg}%",
    ]
    risk_notes = [
        "趨勢延續觀察，非入場建議；跌破 MA20 即離開清單",
        "盤整市清單會反覆進出（whipsaw），清單變動不代表訊號翻轉",
    ]
    state = "candidate"
    if market_bias == "mixed":
        state = "watch"
        reasons.append("大盤分歧（SPY/QQQ 不同步），candidate 降為 watch")
        risk_notes.append("大盤分歧，觀察優先度降低")
    return {"bucket": "candidate", "state": state, "reasons": reasons, "risk_notes": risk_notes}


def get_us_trend_follow() -> dict:
    """
    us_trend_follow 策略總表。bearish / unknown 時 market_gate.active=false、
    candidates=[]（原本符合條件者移入 excluded 並註明守門關閉）。
    """
    analysis = get_us_analysis()
    by_code = {x["code"]: x for x in analysis}
    bias, _detail = _market_context(by_code)
    active = bias in ("bullish", "mixed")
    dates = [x["last_data_as_of"] for x in analysis if x["last_data_as_of"]]

    picked: list[tuple[dict, dict]] = []   # (analysis item, output item)
    excluded_out: list[dict] = []
    for a in analysis:
        r = classify_trend_follow(a, bias)
        item = {
            "code":       a["code"],
            "name":       a["name"],
            "category":   a.get("category", ""),
            "close":      a["last_close"],
            "state":      r["state"],
            "reasons":    r["reasons"],
            "data_as_of": a["last_data_as_of"],
        }
        if r["bucket"] == "candidate" and active:
            item["risk_notes"] = r["risk_notes"]
            picked.append((a, item))
        elif r["bucket"] == "candidate":
            # 守門關閉：誠實移入 excluded，說明是規則關門而非個股問題
            item["state"] = "watch"
            item["reasons"] = ["符合入選條件，但大盤守門關閉，今日不列候選（見 market_gate.note）"]
            excluded_out.append(item)
        else:
            excluded_out.append(item)

    # 排序：距 MA20 由小到大（防追高排序化）→ 20 日漲跌幅由大到小 → code
    picked.sort(key=lambda t: (t[0]["dist_ma20_pct"], -t[0]["change_20d_pct"], t[0]["code"]))
    candidates = []
    for rank, (_a, item) in enumerate(picked, start=1):
        item["rank"] = rank
        candidates.append(item)

    return {
        "as_of":          max(dates) if dates else None,
        "strategy":       STRATEGY,
        "strategy_label": STRATEGY_LABEL,
        "market_gate":    {"active": active, "bias": bias, "note": _GATE_NOTE[bias]},
        "candidates":     candidates,
        "excluded":       excluded_out,
    }
