import json

from app.storage import fundamental_store as store


def test_load_fundamentals_from_csv_parses_numeric_fields(tmp_path):
    csv_path = tmp_path / "fundamentals.csv"
    csv_path.write_text(
        "\n".join([
            "code,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2330,22.5,28.1,5,1.2,35,18,8.2,10.5,18.3,5.6,10",
        ]),
        encoding="utf-8",
    )

    data = store.load_fundamentals_from_csv(csv_path)

    assert data["2330"]["roe_5y_avg"] == 22.5
    assert data["2330"]["free_cash_flow_positive_years"] == 5
    assert data["2330"]["dividend_years"] == 10


def test_load_fundamentals_from_csv_keeps_blank_fields_as_none(tmp_path):
    csv_path = tmp_path / "fundamentals.csv"
    csv_path.write_text(
        "\n".join([
            "code,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2337,,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )

    data = store.load_fundamentals_from_csv(csv_path)

    assert data["2337"]["roe_5y_avg"] is None
    assert data["2337"]["pe"] is None


def test_save_fundamentals_writes_json(tmp_path):
    path = tmp_path / "fundamentals.json"

    store.save_fundamentals(
        {"2330": {"roe_5y_avg": 22.5, "pe": 18.3}},
        path=path,
    )

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["2330"]["roe_5y_avg"] == 22.5


def test_check_fundamentals_reports_missing_codes_and_fields():
    fundamentals = {
        "2330": {
            "roe_5y_avg": 22.5,
            "operating_margin_5y_avg": 28.1,
            "free_cash_flow_positive_years": 5,
            "operating_cash_flow_to_net_income": 1.2,
            "debt_to_equity": 35.0,
            "interest_coverage": 18.0,
            "revenue_growth_5y_cagr": 8.2,
            "eps_growth_5y_cagr": 10.5,
            "pe": 18.3,
            "fcf_yield": 5.6,
            "dividend_years": 10,
        },
        "2337": {
            "roe_5y_avg": None,
            "operating_margin_5y_avg": None,
        },
    }

    report = store.check_fundamentals(fundamentals, ["2330", "2337", "2408"])

    assert report["total_codes"] == 3
    assert report["complete_count"] == 1
    assert report["incomplete_count"] == 1
    assert report["missing_count"] == 1
    assert report["missing_codes"] == ["2408"]
    assert "roe_5y_avg" in report["incomplete"]["2337"]


def test_sync_fundamentals_csv_adds_missing_leader_rows(tmp_path):
    csv_path = tmp_path / "fundamentals.csv"
    csv_path.write_text(
        "\n".join([
            "code,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2330,22.5,28.1,5,1.2,35,18,8.2,10.5,18.3,5.6,10",
        ]),
        encoding="utf-8",
    )

    result = store.sync_fundamentals_csv(["2330", "2408"], path=csv_path)
    data = store.load_fundamentals_from_csv(csv_path)

    assert result["added_codes"] == ["2408"]
    assert data["2408"]["roe_5y_avg"] is None


def test_sync_fundamentals_csv_preserves_existing_values(tmp_path):
    csv_path = tmp_path / "fundamentals.csv"
    csv_path.write_text(
        "\n".join([
            "code,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2330,22.5,28.1,5,1.2,35,18,8.2,10.5,18.3,5.6,10",
        ]),
        encoding="utf-8",
    )

    store.sync_fundamentals_csv(["2330", "2408"], path=csv_path)
    data = store.load_fundamentals_from_csv(csv_path)

    assert data["2330"]["roe_5y_avg"] == 22.5
    assert data["2330"]["pe"] == 18.3


def test_merge_priority_csv_updates_only_filled_fields(tmp_path):
    fundamentals_path = tmp_path / "fundamentals.csv"
    fundamentals_path.write_text(
        "\n".join([
            "code,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2408,,28.1,,,,,,,,,",
        ]),
        encoding="utf-8",
    )
    priority_path = tmp_path / "priority.csv"
    priority_path.write_text(
        "\n".join([
            "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2408,南亞科,目前推薦/觀察名單,2,roe_5y_avg,5 年平均 ROE,12.5,,5,,,,,,18.2,,7",
        ]),
        encoding="utf-8",
    )

    result = store.merge_priority_csv_into_fundamentals(priority_path, fundamentals_path)
    data = store.load_fundamentals_from_csv(fundamentals_path)

    assert result["updated_code_count"] == 1
    assert data["2408"]["roe_5y_avg"] == 12.5
    assert data["2408"]["operating_margin_5y_avg"] == 28.1
    assert data["2408"]["free_cash_flow_positive_years"] == 5
    assert data["2408"]["pe"] == 18.2
    assert data["2408"]["dividend_years"] == 7


def test_merge_priority_csv_adds_new_code(tmp_path):
    fundamentals_path = tmp_path / "fundamentals.csv"
    fundamentals_path.write_text(
        "code,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years\n",
        encoding="utf-8",
    )
    priority_path = tmp_path / "priority.csv"
    priority_path.write_text(
        "\n".join([
            "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "3711,日月光投控,目前推薦/觀察名單,1,roe_5y_avg,5 年平均 ROE,14.2,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )

    result = store.merge_priority_csv_into_fundamentals(priority_path, fundamentals_path)
    data = store.load_fundamentals_from_csv(fundamentals_path)

    assert result["added_codes"] == ["3711"]
    assert data["3711"]["roe_5y_avg"] == 14.2


def test_merge_priority_csv_dry_run_does_not_write(tmp_path):
    fundamentals_path = tmp_path / "fundamentals.csv"
    fundamentals_path.write_text(
        "\n".join([
            "code,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2408,,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )
    priority_path = tmp_path / "priority.csv"
    priority_path.write_text(
        "\n".join([
            "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2408,南亞科,目前推薦/觀察名單,1,roe_5y_avg,5 年平均 ROE,12.5,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )

    result = store.merge_priority_csv_into_fundamentals(
        priority_path,
        fundamentals_path,
        dry_run=True,
    )
    data = store.load_fundamentals_from_csv(fundamentals_path)

    assert result["dry_run"] is True
    assert result["updated_field_count"] == 1
    assert data["2408"]["roe_5y_avg"] is None


def test_validate_priority_csv_reports_invalid_numeric_value(tmp_path):
    priority_path = tmp_path / "priority.csv"
    priority_path.write_text(
        "\n".join([
            "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2408,南亞科,目前推薦/觀察名單,1,roe_5y_avg,5 年平均 ROE,abc,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )

    report = store.validate_priority_csv(priority_path)

    assert report["valid"] is False
    assert report["errors"] == [
        {
            "row_number": 2,
            "code": "2408",
            "field": "roe_5y_avg",
            "value": "abc",
            "message": "必須是數字",
        }
    ]


def test_validate_priority_csv_counts_filled_values_and_duplicates(tmp_path):
    priority_path = tmp_path / "priority.csv"
    priority_path.write_text(
        "\n".join([
            "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2408,南亞科,目前推薦/觀察名單,2,roe_5y_avg,5 年平均 ROE,12.5,,,,,,,,18.2,,",
            "2408,南亞科,目前推薦/觀察名單,1,dividend_years,連續配息年數,,,,,,,,,,,4",
            ",缺代碼,目前推薦/觀察名單,1,roe_5y_avg,5 年平均 ROE,10,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )

    report = store.validate_priority_csv(priority_path)

    assert report["valid"] is False
    assert report["row_count"] == 3
    assert report["filled_code_count"] == 1
    assert report["filled_field_count"] == 3
    assert report["duplicate_codes"] == ["2408"]
    assert report["missing_code_rows"] == [4]


def test_validate_priority_csv_reports_complete_partial_and_empty_rows(tmp_path):
    priority_path = tmp_path / "priority.csv"
    complete_values = ",".join(["20", "30", "5", "1.2", "35", "18", "8", "10", "18", "4", "10"])
    priority_path.write_text(
        "\n".join([
            "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            f"2330,台積電,目前推薦/觀察名單,11,all,全部,{complete_values}",
            "2408,南亞科,目前推薦/觀察名單,11,all,全部,12.5,,,,,,,,,,",
            "2344,華邦電,目前推薦/觀察名單,11,all,全部,,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )

    report = store.validate_priority_csv(priority_path)

    assert report["valid"] is True
    assert report["complete_code_count"] == 1
    assert report["complete_codes"] == ["2330"]
    assert report["partial_codes"] == ["2408"]
    assert report["empty_codes"] == ["2344"]
    assert report["row_statuses"][0]["status"] == "complete"
    assert report["row_statuses"][0]["filled_field_count"] == 11
    assert report["row_statuses"][1]["status"] == "partial"
    assert report["row_statuses"][1]["missing_field_count"] == 10
    assert "operating_margin_5y_avg" in report["row_statuses"][1]["missing_fields"]
    assert report["row_statuses"][2]["status"] == "empty"


def test_validate_priority_csv_warns_on_suspicious_percent_and_negative_values(tmp_path):
    priority_path = tmp_path / "priority.csv"
    priority_path.write_text(
        "\n".join([
            "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2330,台積電,目前推薦/觀察名單,11,all,全部,0.28,160,6,1.2,35,18,8,10,-3,4,10",
        ]),
        encoding="utf-8",
    )

    report = store.validate_priority_csv(priority_path)

    assert report["valid"] is True
    assert report["warnings"]
    assert {warning["field"] for warning in report["warnings"]} >= {
        "roe_5y_avg",
        "operating_margin_5y_avg",
        "free_cash_flow_positive_years",
        "pe",
    }


def test_validate_fundamentals_csv_reports_invalid_numeric_value(tmp_path):
    csv_path = tmp_path / "fundamentals.csv"
    csv_path.write_text(
        "\n".join([
            "code,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2330,twenty,28.1,5,1.2,35,18,8.2,10.5,18.3,5.6,10",
        ]),
        encoding="utf-8",
    )

    report = store.validate_fundamentals_csv(csv_path)

    assert report["valid"] is False
    assert report["errors"] == [
        {
            "row_number": 2,
            "code": "2330",
            "field": "roe_5y_avg",
            "value": "twenty",
            "message": "必須是數字",
        }
    ]
