from app.services.buffett_service import evaluate_buffett_indicator


def test_returns_data_missing_when_no_fundamentals():
    result = evaluate_buffett_indicator("2330", None)

    assert result["buffett_tag"] == "buffett_quality_value_v1"
    assert result["buffett_data_ok"] is False
    assert result["buffett_flag"] is False
    assert result["buffett_score"] is None
    assert "fundamentals" in result["buffett_data_missing_reason"]


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

    result = evaluate_buffett_indicator("2330", fundamentals)

    assert result["buffett_data_ok"] is False
    assert result["buffett_flag"] is False
    assert result["buffett_score"] is None
    assert "roe_5y_avg" in result["buffett_data_missing_reason"]


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

    result = evaluate_buffett_indicator("2330", fundamentals)

    assert result["buffett_data_ok"] is True
    assert result["buffett_score"] is not None
    assert result["buffett_data_completeness_pct"] == 72.7
    assert set(result["buffett_scored_groups"]) == {"quality", "safety", "value"}
    assert result["buffett_growth_score"] is None
    assert "revenue_growth_5y_cagr" in result["buffett_data_missing_reason"]


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

    result = evaluate_buffett_indicator("2330", fundamentals)

    assert result["buffett_data_ok"] is False
    assert result["buffett_score"] is None
    assert "至少 3 組" in result["buffett_data_missing_reason"]


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

    result = evaluate_buffett_indicator("2330", fundamentals)

    assert result["buffett_data_ok"] is True
    assert result["buffett_flag"] is True
    assert result["buffett_score"] >= 75
    assert result["buffett_signal"] == "quality_value_watch"
    assert result["buffett_quality_score"] >= 70
    assert result["buffett_value_score"] >= 60
    assert "自由現金流" in result["buffett_reason"]
