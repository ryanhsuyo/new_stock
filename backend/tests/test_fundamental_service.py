from app.services import fundamental_service as svc


def test_build_fundamentals_status_includes_missing_field_counts(monkeypatch):
    monkeypatch.setattr(svc, "_FUNDAMENTALS_CSV_PATH", svc._OUT / "missing_fundamentals.csv")
    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", svc._OUT / "missing_priority.csv")
    monkeypatch.setattr(svc, "_load_leader_codes", lambda: ["2330", "2408"])
    monkeypatch.setattr(svc, "_load_recommendation_priority", lambda: ["2408"])
    monkeypatch.setattr(svc, "load_stock_names", lambda: {"2408": "南亞科"})
    monkeypatch.setattr(svc, "load_fundamentals", lambda: {
        "2330": {field: 1 for field in svc.REQUIRED_FIELDS},
        "2408": {
            **{field: 1 for field in svc.REQUIRED_FIELDS},
            "roe_5y_avg": None,
            "pe": None,
        },
    })

    status = svc.build_fundamentals_status()

    assert status["complete_count"] == 1
    assert status["field_missing_counts"]["roe_5y_avg"] == 1
    assert status["field_missing_counts"]["pe"] == 1
    assert status["next_fill_targets"][0]["code"] == "2408"
    assert status["next_fill_targets"][0]["name"] == "南亞科"
    assert status["fundamentals_csv_validation"] is None
    assert status["priority_csv_validation"] is None
    workflow = status["workflow_summary"]
    assert workflow["stage"] == "generate_priority_csv"
    assert workflow["headline"] == "先產生基本面避雷優先補資料 CSV"
    assert workflow["primary_action"]["label"] == "下載補資料 CSV"
    assert workflow["primary_action"]["command"] == "GET /api/system/fundamentals-priority-fill"
    assert workflow["focus_targets"][0]["code"] == "2408"
    assert "南亞科 2408" in workflow["fill_targets_copy_text"]
    assert "5 年平均 ROE (roe_5y_avg，範例 28.5)" in workflow["fill_targets_copy_text"]
    assert "本益比 (pe，範例 22.5)" in workflow["fill_targets_copy_text"]
    assert [step["key"] for step in workflow["checklist"]] == [
        "download_priority_csv",
        "fill_required_fields",
        "preview_and_merge",
        "rerun_signals",
    ]
    assert workflow["checklist"][0]["status"] == "todo"


def test_prepare_priority_import_preview_keeps_priority_csv_unchanged(tmp_path, monkeypatch):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    import_csv = tmp_path / "import.csv"
    header = "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values," + ",".join(svc.REQUIRED_FIELDS)
    priority_csv.write_text(
        header + "\n2408,南亞科,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    import_csv.write_text(
        "\n".join([
            "stock_id,ROE 5Y,pe,dividend_years",
            "2408,18.5,22.1,7",
            "9999,10,12,3",
        ]),
        encoding="utf-8",
    )
    before = priority_csv.read_text(encoding="utf-8")
    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", priority_csv)

    result = svc.prepare_priority_fundamentals_import(import_csv, dry_run=True)

    assert result["dry_run"] is True
    assert result["updated_code_count"] == 1
    assert result["updated_field_count"] == 3
    assert result["updated_codes"] == ["2408"]
    assert result["skipped_codes"] == ["9999"]
    assert result["validation"]["valid"] is True
    assert result["validation"]["partial_codes"] == ["2408"]
    assert priority_csv.read_text(encoding="utf-8") == before


def test_prepare_priority_import_apply_updates_priority_csv(tmp_path, monkeypatch):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    import_csv = tmp_path / "import.csv"
    header = "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values," + ",".join(svc.REQUIRED_FIELDS)
    priority_csv.write_text(
        header + "\n2408,南亞科,目前推薦/觀察名單,11,all,全部,note,examples,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    import_csv.write_text(
        "\n".join([
            "代號,5 年平均 ROE,本益比,連續配息年數",
            "2408,18.5,22.1,7",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", priority_csv)

    result = svc.prepare_priority_fundamentals_import(import_csv, dry_run=False)

    text = priority_csv.read_text(encoding="utf-8")
    assert result["dry_run"] is False
    assert result["updated_code_count"] == 1
    assert result["updated_field_count"] == 3
    assert "2408,南亞科" in text
    assert "18.5" in text
    assert "22.1" in text
    assert ",7" in text


def test_build_priority_import_template_rows_uses_focus_targets(monkeypatch):
    monkeypatch.setattr(svc, "_load_leader_codes", lambda: ["2330", "2408"])
    monkeypatch.setattr(svc, "_load_recommendation_priority", lambda: ["2408"])
    monkeypatch.setattr(svc, "load_stock_names", lambda: {"2408": "南亞科"})
    monkeypatch.setattr(svc, "load_fundamentals", lambda: {
        "2330": {field: 1 for field in svc.REQUIRED_FIELDS},
        "2408": {field: None for field in svc.REQUIRED_FIELDS},
    })

    rows = svc.build_priority_import_template_rows(limit=1)

    assert rows == [{
        "code": "2408",
        "name": "南亞科",
        "source_note": "外部資料填入後，先 dry-run 匯入 priority CSV；百分比請填 28.5，不要填 0.285。",
        "roe_5y_avg": "",
        "operating_margin_5y_avg": "",
        "free_cash_flow_positive_years": "",
        "operating_cash_flow_to_net_income": "",
        "debt_to_equity": "",
        "interest_coverage": "",
        "revenue_growth_5y_cagr": "",
        "eps_growth_5y_cagr": "",
        "pe": "",
        "fcf_yield": "",
        "dividend_years": "",
    }]


def test_write_priority_import_template_csv_writes_readable_header(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "build_priority_import_template_rows", lambda limit=20: [{
        "code": "2408",
        "name": "南亞科",
        "source_note": "外部資料填入後，先 dry-run 匯入 priority CSV；百分比請填 28.5，不要填 0.285。",
        **{field: "" for field in svc.REQUIRED_FIELDS},
    }])

    path = svc.write_priority_import_template_csv(tmp_path, limit=1)

    text = path.read_text(encoding="utf-8")
    assert path == tmp_path / "fundamentals_priority_import_template.csv"
    assert "code,name,source_note,roe_5y_avg" in text
    assert "2408,南亞科" in text
    assert "百分比請填 28.5" in text


def test_build_priority_fill_rows_uses_priority_targets(monkeypatch):
    monkeypatch.setattr(svc, "_load_leader_codes", lambda: ["2330", "2408"])
    monkeypatch.setattr(svc, "_load_recommendation_priority", lambda: ["2408"])
    monkeypatch.setattr(svc, "load_stock_names", lambda: {"2408": "南亞科"})
    monkeypatch.setattr(svc, "load_fundamentals", lambda: {
        "2330": {field: 1 for field in svc.REQUIRED_FIELDS},
        "2408": {
            **{field: None for field in svc.REQUIRED_FIELDS},
            "pe": 18.5,
        },
    })

    rows = svc.build_priority_fill_rows(limit=1)

    assert rows[0]["code"] == "2408"
    assert rows[0]["name"] == "南亞科"
    assert rows[0]["priority_reason"] == "目前推薦/觀察名單"
    assert rows[0]["pe"] == 18.5
    assert "5 年平均 ROE" in rows[0]["missing_field_labels"]


def test_write_priority_fill_csv_writes_expected_header(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "build_priority_fill_rows", lambda limit=20: [{
        "code": "2408",
        "name": "南亞科",
        "priority_reason": "目前推薦/觀察名單",
        "missing_count": 1,
        "missing_fields": "roe_5y_avg",
        "missing_field_labels": "5 年平均 ROE",
        "fill_format_note": "百分比請填 28.5，不要填 0.285",
        "example_values": "roe_5y_avg=28.5",
        **{field: "" for field in svc.REQUIRED_FIELDS},
    }])

    path = svc.write_priority_fill_csv(tmp_path, limit=1)

    text = path.read_text(encoding="utf-8")
    assert "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values" in text
    assert "2408,南亞科" in text
    assert "百分比請填 28.5" in text


def test_write_priority_fill_csv_preserves_existing_filled_values(tmp_path, monkeypatch):
    existing_path = tmp_path / "fundamentals_priority_fill.csv"
    header = "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values," + ",".join(svc.REQUIRED_FIELDS)
    existing_path.write_text(
        header + "\n2408,南亞科,目前推薦/觀察名單,11,all,全部,note,examples,12.5,,,,,,,,18.2,,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "build_priority_fill_rows", lambda limit=20: [{
        "code": "2408",
        "name": "南亞科",
        "priority_reason": "目前推薦/觀察名單",
        "missing_count": 11,
        "missing_fields": "all",
        "missing_field_labels": "全部",
        "fill_format_note": "百分比請填 28.5，不要填 0.285",
        "example_values": "roe_5y_avg=28.5",
        **{field: "" for field in svc.REQUIRED_FIELDS},
    }])

    path = svc.write_priority_fill_csv(tmp_path, limit=1)
    text = path.read_text(encoding="utf-8")

    assert "2408,南亞科" in text
    assert "12.5" in text
    assert "18.2" in text


def test_write_priority_fill_csv_preserves_invalid_existing_values(tmp_path, monkeypatch):
    existing_path = tmp_path / "fundamentals_priority_fill.csv"
    header = "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,fill_format_note,example_values," + ",".join(svc.REQUIRED_FIELDS)
    existing_path.write_text(
        header + "\n2408,南亞科,目前推薦/觀察名單,11,all,全部,note,examples,abc,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "build_priority_fill_rows", lambda limit=20: [{
        "code": "2408",
        "name": "南亞科",
        "priority_reason": "目前推薦/觀察名單",
        "missing_count": 11,
        "missing_fields": "all",
        "missing_field_labels": "全部",
        "fill_format_note": "百分比請填 28.5，不要填 0.285",
        "example_values": "roe_5y_avg=28.5",
        **{field: "" for field in svc.REQUIRED_FIELDS},
    }])

    path = svc.write_priority_fill_csv(tmp_path, limit=1)
    text = path.read_text(encoding="utf-8")

    assert "abc" in text


def test_get_priority_fill_csv_path_writes_to_out(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "_OUT", tmp_path)
    monkeypatch.setattr(svc, "build_priority_fill_rows", lambda limit=20: [{
        "code": "2408",
        "name": "南亞科",
        "priority_reason": "目前推薦/觀察名單",
        "missing_count": 1,
        "missing_fields": "roe_5y_avg",
        "missing_field_labels": "5 年平均 ROE",
        "fill_format_note": "百分比請填 28.5，不要填 0.285",
        "example_values": "roe_5y_avg=28.5",
        **{field: "" for field in svc.REQUIRED_FIELDS},
    }])

    path = svc.get_priority_fill_csv_path(limit=1)

    assert path == tmp_path / "fundamentals_priority_fill.csv"
    assert path.exists()
    assert "2408,南亞科" in path.read_text(encoding="utf-8")


def test_build_priority_fill_rows_includes_fill_guidance(monkeypatch):
    monkeypatch.setattr(svc, "_load_leader_codes", lambda: ["2408"])
    monkeypatch.setattr(svc, "_load_recommendation_priority", lambda: ["2408"])
    monkeypatch.setattr(svc, "load_stock_names", lambda: {"2408": "南亞科"})
    monkeypatch.setattr(svc, "load_fundamentals", lambda: {
        "2408": {field: None for field in svc.REQUIRED_FIELDS},
    })

    rows = svc.build_priority_fill_rows(limit=1)

    assert rows[0]["fill_format_note"] == "百分比欄位請填 28.5，不要填 0.285；倍數與年數填一般數字。"
    assert "roe_5y_avg=28.5" in rows[0]["example_values"]


def test_merge_priority_fill_csv_dry_run_does_not_write_json(tmp_path, monkeypatch):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    fundamentals_csv = tmp_path / "fundamentals.csv"
    fundamentals_json = tmp_path / "fundamentals.json"
    header = "code,name,priority_reason,missing_count,missing_fields,missing_field_labels," + ",".join(svc.REQUIRED_FIELDS)
    priority_csv.write_text(
        header + "\n2408,南亞科,目前推薦/觀察名單,1,roe_5y_avg,5 年平均 ROE,12.5,,,,,,,,,,\n",
        encoding="utf-8",
    )
    fundamentals_csv.write_text("code," + ",".join(svc.REQUIRED_FIELDS) + "\n2408,,,,,,,,,,,\n", encoding="utf-8")
    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", priority_csv)
    monkeypatch.setattr(svc, "_FUNDAMENTALS_CSV_PATH", fundamentals_csv)
    monkeypatch.setattr(svc, "_FUNDAMENTALS_JSON_PATH", fundamentals_json)

    result = svc.merge_priority_fill_csv(dry_run=True)

    assert result["dry_run"] is True
    assert result["updated_field_count"] == 1
    assert result["merge_allowed"] is False
    assert result["complete_codes"] == []
    assert result["partial_codes"] == ["2408"]
    assert result["row_statuses"][0]["code"] == "2408"
    assert result["row_statuses"][0]["status"] == "partial"
    assert result["row_statuses"][0]["missing_field_count"] == 10
    assert "補齊 11 欄" in result["blocked_reason"]
    assert result["signals_refresh_required"] is False
    assert result["next_action_label"] == "lite guard 可參考；正式合併仍需補齊 11 欄"
    assert fundamentals_json.exists() is False


def test_merge_priority_fill_csv_requires_confirm_for_write(tmp_path, monkeypatch):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text("code,name,priority_reason,missing_count,missing_fields,missing_field_labels\n", encoding="utf-8")
    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", priority_csv)

    try:
        svc.merge_priority_fill_csv(dry_run=False, confirm=None)
    except ValueError as exc:
        assert "MERGE_PRIORITY_FUNDAMENTALS" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_merge_priority_fill_csv_rejects_write_without_complete_priority_row(tmp_path, monkeypatch):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    fundamentals_csv = tmp_path / "fundamentals.csv"
    fundamentals_json = tmp_path / "fundamentals.json"
    header = "code,name,priority_reason,missing_count,missing_fields,missing_field_labels," + ",".join(svc.REQUIRED_FIELDS)
    priority_csv.write_text(
        header + "\n2408,南亞科,目前推薦/觀察名單,1,roe_5y_avg,5 年平均 ROE,12.5,,,,,,,,,,\n",
        encoding="utf-8",
    )
    fundamentals_csv.write_text("code," + ",".join(svc.REQUIRED_FIELDS) + "\n2408,,,,,,,,,,,\n", encoding="utf-8")
    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", priority_csv)
    monkeypatch.setattr(svc, "_FUNDAMENTALS_CSV_PATH", fundamentals_csv)
    monkeypatch.setattr(svc, "_FUNDAMENTALS_JSON_PATH", fundamentals_json)

    try:
        svc.merge_priority_fill_csv(dry_run=False, confirm="MERGE_PRIORITY_FUNDAMENTALS")
    except ValueError as exc:
        assert "補齊 11 欄" in str(exc)
    else:
        raise AssertionError("expected ValueError")

    assert fundamentals_json.exists() is False


def test_merge_priority_fill_csv_writes_csv_and_json(tmp_path, monkeypatch):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    fundamentals_csv = tmp_path / "fundamentals.csv"
    fundamentals_json = tmp_path / "fundamentals.json"
    header = "code,name,priority_reason,missing_count,missing_fields,missing_field_labels," + ",".join(svc.REQUIRED_FIELDS)
    complete_values = ",".join(["12.5", "28.1", "5", "1.2", "35", "18", "8", "10", "18", "4", "10"])
    priority_csv.write_text(
        header + f"\n2408,南亞科,目前推薦/觀察名單,11,all,全部,{complete_values}\n",
        encoding="utf-8",
    )
    fundamentals_csv.write_text("code," + ",".join(svc.REQUIRED_FIELDS) + "\n2408,,,,,,,,,,,\n", encoding="utf-8")
    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", priority_csv)
    monkeypatch.setattr(svc, "_FUNDAMENTALS_CSV_PATH", fundamentals_csv)
    monkeypatch.setattr(svc, "_FUNDAMENTALS_JSON_PATH", fundamentals_json)

    result = svc.merge_priority_fill_csv(dry_run=False, confirm="MERGE_PRIORITY_FUNDAMENTALS")

    assert result["dry_run"] is False
    assert result["merge_allowed"] is True
    assert result["complete_codes"] == ["2408"]
    assert result["signals_refresh_required"] is True
    assert result["next_action_label"] == "重新產生訊號"
    assert result["imported_count"] == 1
    assert fundamentals_json.exists()
    assert '"roe_5y_avg": 12.5' in fundamentals_json.read_text(encoding="utf-8")


def test_merge_priority_fill_csv_returns_fundamental_preview_for_complete_rows(tmp_path, monkeypatch):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    fundamentals_csv = tmp_path / "fundamentals.csv"
    fundamentals_json = tmp_path / "fundamentals.json"
    header = "code,name,priority_reason,missing_count,missing_fields,missing_field_labels," + ",".join(svc.REQUIRED_FIELDS)
    complete_values = ",".join(["22", "28", "5", "1.2", "35", "18", "8", "10", "18", "5.5", "10"])
    priority_csv.write_text(
        header + f"\n2330,台積電,目前推薦/觀察名單,11,all,全部,{complete_values}\n",
        encoding="utf-8",
    )
    fundamentals_csv.write_text("code," + ",".join(svc.REQUIRED_FIELDS) + "\n2330,,,,,,,,,,,\n", encoding="utf-8")
    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", priority_csv)
    monkeypatch.setattr(svc, "_FUNDAMENTALS_CSV_PATH", fundamentals_csv)
    monkeypatch.setattr(svc, "_FUNDAMENTALS_JSON_PATH", fundamentals_json)
    monkeypatch.setattr(svc, "load_stock_names", lambda: {"2330": "台積電"})

    result = svc.merge_priority_fill_csv(dry_run=True)

    assert result["merge_allowed"] is True
    assert result["signals_refresh_required"] is False
    assert result["next_action_label"] == "可合併，合併後重新產生訊號"
    assert result["fundamental_preview"][0]["code"] == "2330"
    assert result["fundamental_preview"][0]["name"] == "台積電"
    assert result["fundamental_preview"][0]["fundamental_data_ok"] is True
    assert result["fundamental_preview"][0]["fundamental_score"] is not None


def test_build_fundamentals_status_includes_priority_csv_validation(tmp_path, monkeypatch):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "\n".join([
            "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2408,南亞科,目前推薦/觀察名單,1,roe_5y_avg,5 年平均 ROE,12.5,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", priority_csv)
    monkeypatch.setattr(svc, "_load_leader_codes", lambda: ["2408"])
    monkeypatch.setattr(svc, "_load_recommendation_priority", lambda: ["2408"])
    monkeypatch.setattr(svc, "load_stock_names", lambda: {"2408": "南亞科"})
    monkeypatch.setattr(svc, "load_fundamentals", lambda: {
        "2408": {field: None for field in svc.REQUIRED_FIELDS},
    })

    status = svc.build_fundamentals_status()

    assert status["priority_csv_validation"]["valid"] is True
    assert status["priority_csv_validation"]["row_count"] == 1
    assert status["priority_csv_validation"]["filled_code_count"] == 1
    assert status["priority_csv_validation"]["filled_field_count"] == 1


def test_build_fundamentals_status_includes_priority_fill_readiness(tmp_path, monkeypatch):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "\n".join([
            "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2408,南亞科,目前推薦/觀察名單,1,roe_5y_avg,5 年平均 ROE,12.5,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", priority_csv)
    monkeypatch.setattr(svc, "_load_leader_codes", lambda: ["2408"])
    monkeypatch.setattr(svc, "_load_recommendation_priority", lambda: ["2408"])
    monkeypatch.setattr(svc, "load_stock_names", lambda: {"2408": "南亞科"})
    monkeypatch.setattr(svc, "load_fundamentals", lambda: {
        "2408": {field: None for field in svc.REQUIRED_FIELDS},
    })

    status = svc.build_fundamentals_status()

    readiness = status["priority_fill_readiness"]
    assert readiness["status"] == "ready_to_preview"
    assert readiness["can_preview"] is True
    assert readiness["can_merge"] is False
    assert readiness["filled_code_count"] == 1
    assert readiness["filled_field_count"] == 1
    assert readiness["complete_code_count"] == 0
    assert readiness["partial_code_count"] == 1
    assert readiness["suggested_action"] == "已部分填寫，可作為 Quality Momentum Lite 避雷參考；正式合併仍需補齊 11 欄。"
    workflow = status["workflow_summary"]
    assert workflow["stage"] == "fill_priority_csv"
    assert workflow["headline"] == "補齊 Quality Momentum Lite 避雷欄位"
    assert workflow["primary_action"]["label"] == "繼續填 CSV"
    assert workflow["checklist"][0]["status"] == "done"
    assert workflow["checklist"][1]["status"] == "todo"
    assert workflow["checklist"][2]["status"] == "blocked"


def test_build_fundamentals_status_allows_merge_when_one_priority_row_complete(tmp_path, monkeypatch):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    complete_values = ",".join(["20", "30", "5", "1.2", "35", "18", "8", "10", "18", "4", "10"])
    priority_csv.write_text(
        "\n".join([
            "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            f"2330,台積電,目前推薦/觀察名單,11,all,全部,{complete_values}",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", priority_csv)
    monkeypatch.setattr(svc, "_load_leader_codes", lambda: ["2330"])
    monkeypatch.setattr(svc, "_load_recommendation_priority", lambda: ["2330"])
    monkeypatch.setattr(svc, "load_stock_names", lambda: {"2330": "台積電"})
    monkeypatch.setattr(svc, "load_fundamentals", lambda: {
        "2330": {field: None for field in svc.REQUIRED_FIELDS},
    })

    status = svc.build_fundamentals_status()

    readiness = status["priority_fill_readiness"]
    assert readiness["status"] == "ready_to_merge"
    assert readiness["can_preview"] is True
    assert readiness["can_merge"] is True
    assert readiness["complete_code_count"] == 1
    assert readiness["suggested_action"] == "先按預覽合併，確認更新檔數與欄位數後再合併匯入。"
    workflow = status["workflow_summary"]
    assert workflow["stage"] == "ready_to_merge"
    assert workflow["headline"] == "先預覽，再合併基本面避雷資料"
    assert workflow["primary_action"]["label"] == "預覽合併"
    assert workflow["primary_action"]["command"] == "POST /api/system/fundamentals-priority-fill/merge"
    assert workflow["checklist"][1]["status"] == "done"
    assert workflow["checklist"][2]["status"] == "todo"


def test_build_fundamentals_status_includes_priority_fill_guide(tmp_path, monkeypatch):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    complete_values = ",".join(["20", "30", "5", "1.2", "35", "18", "8", "10", "18", "4", "10"])
    priority_csv.write_text(
        "\n".join([
            "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            f"2330,台積電,目前推薦/觀察名單,11,all,全部,{complete_values}",
            "2408,南亞科,目前推薦/觀察名單,11,all,全部,12.5,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", priority_csv)
    monkeypatch.setattr(svc, "_load_leader_codes", lambda: ["2330", "2408"])
    monkeypatch.setattr(svc, "_load_recommendation_priority", lambda: ["2330", "2408"])
    monkeypatch.setattr(svc, "load_stock_names", lambda: {"2330": "台積電", "2408": "南亞科"})
    monkeypatch.setattr(svc, "load_fundamentals", lambda: {
        "2330": {field: None for field in svc.REQUIRED_FIELDS},
        "2408": {field: None for field in svc.REQUIRED_FIELDS},
    })

    status = svc.build_fundamentals_status()

    guide = status["priority_fill_guide"]
    assert guide["next_action_label"] == "可先預覽合併 1 檔"
    assert guide["complete_ready_count"] == 1
    assert guide["partial_count"] == 1
    assert guide["empty_count"] == 0
    assert "百分比欄位請填 28.5" in guide["format_note"]


def test_build_fundamentals_status_blocks_invalid_priority_fill_csv(tmp_path, monkeypatch):
    priority_csv = tmp_path / "fundamentals_priority_fill.csv"
    priority_csv.write_text(
        "\n".join([
            "code,name,priority_reason,missing_count,missing_fields,missing_field_labels,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2408,南亞科,目前推薦/觀察名單,1,roe_5y_avg,5 年平均 ROE,abc,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", priority_csv)
    monkeypatch.setattr(svc, "_load_leader_codes", lambda: ["2408"])
    monkeypatch.setattr(svc, "_load_recommendation_priority", lambda: ["2408"])
    monkeypatch.setattr(svc, "load_stock_names", lambda: {"2408": "南亞科"})
    monkeypatch.setattr(svc, "load_fundamentals", lambda: {
        "2408": {field: None for field in svc.REQUIRED_FIELDS},
    })

    status = svc.build_fundamentals_status()

    readiness = status["priority_fill_readiness"]
    assert readiness["status"] == "invalid"
    assert readiness["can_preview"] is False
    assert readiness["can_merge"] is False
    assert "row 2 code 2408" in readiness["message"]


def test_build_fundamentals_status_includes_fundamentals_csv_validation(tmp_path, monkeypatch):
    fundamentals_csv = tmp_path / "fundamentals.csv"
    fundamentals_csv.write_text(
        "\n".join([
            "code,roe_5y_avg,operating_margin_5y_avg,free_cash_flow_positive_years,operating_cash_flow_to_net_income,debt_to_equity,interest_coverage,revenue_growth_5y_cagr,eps_growth_5y_cagr,pe,fcf_yield,dividend_years",
            "2330,abc,,,,,,,,,,",
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(svc, "_FUNDAMENTALS_CSV_PATH", fundamentals_csv)
    monkeypatch.setattr(svc, "_PRIORITY_CSV_PATH", svc._OUT / "missing_priority.csv")
    monkeypatch.setattr(svc, "_load_leader_codes", lambda: ["2330"])
    monkeypatch.setattr(svc, "_load_recommendation_priority", lambda: [])
    monkeypatch.setattr(svc, "load_stock_names", lambda: {"2330": "台積電"})
    monkeypatch.setattr(svc, "load_fundamentals", lambda: {
        "2330": {field: None for field in svc.REQUIRED_FIELDS},
    })

    status = svc.build_fundamentals_status()

    assert status["fundamentals_csv_validation"]["valid"] is False
    assert status["fundamentals_csv_validation"]["errors"][0]["row_number"] == 2
    assert status["fundamentals_csv_validation"]["errors"][0]["field"] == "roe_5y_avg"
