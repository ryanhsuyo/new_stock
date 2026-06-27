"""
fundamental_guard_service.py — 基本面避雷品質價值指標 V1。

此服務只做基本面品質/價值評估，不參與短線 BUY/SELL 判斷。
若沒有 fundamentals.json 或單檔資料不足，必須明確回傳 data_missing，
避免用技術線型假裝基本面避雷分數。
"""

FUNDAMENTAL_GUARD_TAG = "fundamental_guard_v1"
FUNDAMENTAL_GUARD_NAME = "基本面避雷品質價值指標V1"
REQUIRED_FIELDS = (
    "roe_5y_avg",
    "operating_margin_5y_avg",
    "free_cash_flow_positive_years",
    "operating_cash_flow_to_net_income",
    "debt_to_equity",
    "interest_coverage",
    "revenue_growth_5y_cagr",
    "eps_growth_5y_cagr",
    "pe",
    "fcf_yield",
    "dividend_years",
)
METRIC_GROUPS = {
    "quality": (
        "roe_5y_avg",
        "operating_margin_5y_avg",
        "free_cash_flow_positive_years",
        "operating_cash_flow_to_net_income",
    ),
    "safety": (
        "debt_to_equity",
        "interest_coverage",
    ),
    "value": (
        "pe",
        "fcf_yield",
    ),
    "growth": (
        "revenue_growth_5y_cagr",
        "eps_growth_5y_cagr",
        "dividend_years",
    ),
}
GROUP_WEIGHTS = {
    "quality": 0.35,
    "safety": 0.25,
    "value": 0.20,
    "growth": 0.20,
}
MIN_SCORABLE_GROUPS = 3


def _num(data: dict, key: str) -> float | None:
    value = data.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _clamp(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _score_quality(data: dict) -> int:
    score = 0
    roe = _num(data, "roe_5y_avg")
    margin = _num(data, "operating_margin_5y_avg")
    fcf_years = _num(data, "free_cash_flow_positive_years")
    cash_conversion = _num(data, "operating_cash_flow_to_net_income")

    if roe is not None:
        score += min(35, roe / 20 * 35)
    if margin is not None:
        score += min(25, margin / 25 * 25)
    if fcf_years is not None:
        score += min(25, fcf_years / 5 * 25)
    if cash_conversion is not None:
        score += min(15, cash_conversion / 1.0 * 15)

    return _clamp(score)


def _score_safety(data: dict) -> int:
    score = 50
    debt_to_equity = _num(data, "debt_to_equity")
    interest_coverage = _num(data, "interest_coverage")

    if debt_to_equity is not None:
        if debt_to_equity <= 40:
            score += 30
        elif debt_to_equity <= 80:
            score += 15
        else:
            score -= 20
    if interest_coverage is not None:
        if interest_coverage >= 10:
            score += 20
        elif interest_coverage >= 5:
            score += 10
        else:
            score -= 20

    return _clamp(score)


def _score_growth(data: dict) -> int:
    score = 50
    revenue_growth = _num(data, "revenue_growth_5y_cagr")
    eps_growth = _num(data, "eps_growth_5y_cagr")
    dividend_years = _num(data, "dividend_years")

    if revenue_growth is not None:
        score += min(20, revenue_growth / 10 * 20)
    if eps_growth is not None:
        score += min(20, eps_growth / 12 * 20)
    if dividend_years is not None and dividend_years >= 5:
        score += 10

    return _clamp(score)


def _score_value(data: dict) -> int:
    score = 50
    pe = _num(data, "pe")
    fcf_yield = _num(data, "fcf_yield")

    if pe is not None:
        if pe <= 15:
            score += 25
        elif pe <= 22:
            score += 15
        elif pe <= 30:
            score += 0
        else:
            score -= 20
    if fcf_yield is not None:
        if fcf_yield >= 6:
            score += 25
        elif fcf_yield >= 4:
            score += 15
        elif fcf_yield >= 2:
            score += 5
        else:
            score -= 15

    return _clamp(score)


def _missing_result(reason: str) -> dict:
    return {
        "fundamental_flag": False,
        "fundamental_tag": FUNDAMENTAL_GUARD_TAG,
        "fundamental_score": None,
        "fundamental_signal": "data_missing",
        "fundamental_reason": "",
        "fundamental_data_ok": False,
        "fundamental_data_missing_reason": reason,
        "fundamental_quality_score": None,
        "fundamental_value_score": None,
        "fundamental_safety_score": None,
        "fundamental_growth_score": None,
        "fundamental_data_completeness_pct": 0.0,
        "fundamental_missing_fields": [],
        "fundamental_scored_groups": [],
    }


def _missing_fields(fundamentals: dict) -> list[str]:
    return [
        field
        for field in REQUIRED_FIELDS
        if _num(fundamentals, field) is None
    ]


def _available_groups(fundamentals: dict) -> list[str]:
    groups: list[str] = []
    for group, fields in METRIC_GROUPS.items():
        if any(_num(fundamentals, field) is not None for field in fields):
            groups.append(group)
    return groups


def _data_completeness_pct(missing_fields: list[str]) -> float:
    present = len(REQUIRED_FIELDS) - len(missing_fields)
    return round(present / len(REQUIRED_FIELDS) * 100, 1)


def _weighted_score(scores: dict[str, int | None], groups: list[str]) -> int:
    available_weight = sum(GROUP_WEIGHTS[group] for group in groups)
    if available_weight <= 0:
        return 0
    weighted = sum((scores[group] or 0) * GROUP_WEIGHTS[group] for group in groups)
    return _clamp(weighted / available_weight)


def evaluate_fundamental_guard(code: str, fundamentals: dict | None) -> dict:
    if not fundamentals:
        return _missing_result(f"缺少 fundamentals.json 中 {code} 的基本面資料")

    missing_fields = _missing_fields(fundamentals)
    available_groups = _available_groups(fundamentals)
    completeness = _data_completeness_pct(missing_fields)
    if len(available_groups) < MIN_SCORABLE_GROUPS:
        joined = "、".join(missing_fields)
        result = _missing_result(
            f"fundamentals.json 中 {code} 至少 {MIN_SCORABLE_GROUPS} 組基本面資料才可評分；"
            f"目前可用 {len(available_groups)} 組，缺欄位：{joined}"
        )
        result["fundamental_data_completeness_pct"] = completeness
        result["fundamental_missing_fields"] = missing_fields
        result["fundamental_scored_groups"] = available_groups
        return result

    quality = _score_quality(fundamentals) if "quality" in available_groups else None
    value = _score_value(fundamentals) if "value" in available_groups else None
    safety = _score_safety(fundamentals) if "safety" in available_groups else None
    growth = _score_growth(fundamentals) if "growth" in available_groups else None
    group_scores = {
        "quality": quality,
        "safety": safety,
        "value": value,
        "growth": growth,
    }
    score = _weighted_score(group_scores, available_groups)

    quality_for_gate = quality if quality is not None else 0
    safety_for_gate = safety if safety is not None else 0
    value_for_gate = value if value is not None else 50
    flag = score >= 75 and quality_for_gate >= 70 and safety_for_gate >= 60 and value_for_gate >= 50
    if flag:
        signal = "quality_value_watch"
    elif quality_for_gate >= 70 and safety_for_gate >= 60 and value is not None and value < 50:
        signal = "quality_but_expensive"
    elif quality_for_gate < 60:
        signal = "quality_insufficient"
    else:
        signal = "watch_only"

    reason_parts = [
        f"資料完整度 {completeness}%",
    ]
    if missing_fields:
        reason_parts.append(f"缺欄位 {'、'.join(missing_fields)}")
    if quality is not None:
        reason_parts.append(f"品質分 {quality}")
    if safety is not None:
        reason_parts.append(f"安全分 {safety}")
    if value is not None:
        reason_parts.append(f"估值分 {value}")
    if growth is not None:
        reason_parts.append(f"成長分 {growth}")
    if fundamentals.get("free_cash_flow_positive_years") is not None:
        reason_parts.append(f"自由現金流為正 {fundamentals['free_cash_flow_positive_years']} 年")
    if fundamentals.get("roe_5y_avg") is not None:
        reason_parts.append(f"5年平均 ROE {fundamentals['roe_5y_avg']}%")

    return {
        "fundamental_flag": flag,
        "fundamental_tag": FUNDAMENTAL_GUARD_TAG if flag else "",
        "fundamental_score": score,
        "fundamental_signal": signal,
        "fundamental_reason": "；".join(reason_parts),
        "fundamental_data_ok": True,
        "fundamental_data_missing_reason": "、".join(missing_fields),
        "fundamental_quality_score": quality,
        "fundamental_value_score": value,
        "fundamental_safety_score": safety,
        "fundamental_growth_score": growth,
        "fundamental_data_completeness_pct": completeness,
        "fundamental_missing_fields": missing_fields,
        "fundamental_scored_groups": available_groups,
    }
