from app.services.fundamental_guard_service import evaluate_fundamental_guard


def test_returns_data_missing_when_no_fundamentals():
    result = evaluate_fundamental_guard("2330", None)

    assert result["fundamental_tag"] == "fundamental_guard_v1"
    assert result["fundamental_data_ok"] is False
    assert result["fundamental_flag"] is False
    assert result["fundamental_score"] is None
    assert "fundamentals" in result["fundamental_data_missing_reason"]


def test_returns_data_missing_when_required_fields_are_null():
    fundamentals = {
        "roe_5y_avg": None,
        "operating_margin_5y_avg": None,
        "free_cash_flow_positive_years": None,
        "operating_cash_flow_to_net_income": None,
        "debt_to_equity": None,
        "interest_coverage": None,
        "revenue_growth_5y_cagr": None,
        "eps_growth_5y_cagr": None,
        "pe": None,
        "fcf_yield": None,
        "dividend_years": None,
    }

    result = evaluate_fundamental_guard("2330", fundamentals)

    assert result["fundamental_data_ok"] is False
    assert result["fundamental_flag"] is False
    assert result["fundamental_score"] is None
    assert "roe_5y_avg" in result["fundamental_data_missing_reason"]


def test_scores_when_at_least_three_metric_groups_are_available():
    fundamentals = {
        "roe_5y_avg": 22.0,
        "operating_margin_5y_avg": 28.0,
        "free_cash_flow_positive_years": 5,
        "operating_cash_flow_to_net_income": 1.2,
        "debt_to_equity": 35.0,
        "interest_coverage": 18.0,
        "revenue_growth_5y_cagr": None,
        "eps_growth_5y_cagr": None,
        "pe": 18.0,
        "fcf_yield": 5.5,
        "dividend_years": None,
    }

    result = evaluate_fundamental_guard("2330", fundamentals)

    assert result["fundamental_data_ok"] is True
    assert result["fundamental_score"] is not None
    assert result["fundamental_data_completeness_pct"] == 72.7
    assert set(result["fundamental_scored_groups"]) == {"quality", "safety", "value"}
    assert result["fundamental_growth_score"] is None
    assert "revenue_growth_5y_cagr" in result["fundamental_data_missing_reason"]


def test_stays_data_missing_when_less_than_three_metric_groups_are_available():
    fundamentals = {
        "roe_5y_avg": 22.0,
        "operating_margin_5y_avg": 28.0,
        "free_cash_flow_positive_years": 5,
        "operating_cash_flow_to_net_income": 1.2,
        "debt_to_equity": 35.0,
        "interest_coverage": 18.0,
        "revenue_growth_5y_cagr": None,
        "eps_growth_5y_cagr": None,
        "pe": None,
        "fcf_yield": None,
        "dividend_years": None,
    }

    result = evaluate_fundamental_guard("2330", fundamentals)

    assert result["fundamental_data_ok"] is False
    assert result["fundamental_score"] is None
    assert "至少 3 組" in result["fundamental_data_missing_reason"]


def test_scores_high_quality_reasonable_value_company():
    fundamentals = {
        "roe_5y_avg": 22.0,
        "operating_margin_5y_avg": 28.0,
        "free_cash_flow_positive_years": 5,
        "operating_cash_flow_to_net_income": 1.2,
        "debt_to_equity": 35.0,
        "interest_coverage": 18.0,
        "revenue_growth_5y_cagr": 8.0,
        "eps_growth_5y_cagr": 10.0,
        "pe": 18.0,
        "fcf_yield": 5.5,
        "dividend_years": 10,
    }

    result = evaluate_fundamental_guard("2330", fundamentals)

    assert result["fundamental_data_ok"] is True
    assert result["fundamental_flag"] is True
    assert result["fundamental_score"] >= 75
    assert result["fundamental_signal"] == "quality_value_watch"
    assert result["fundamental_quality_score"] >= 70
    assert result["fundamental_value_score"] >= 60
    assert "自由現金流" in result["fundamental_reason"]
