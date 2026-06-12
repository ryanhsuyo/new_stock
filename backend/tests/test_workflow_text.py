def test_preview_numbered_lines_supports_dash_and_plain_items():
    from app.services.workflow_text import preview_numbered_lines

    text = "\n".join([
        "巴菲特基本面優先補資料清單",
        "1. 台積電 2330 - 缺 11 欄",
        "2. 聯發科 2454",
        "   - ROE",
        "3. 台光電 2383 - 缺 8 欄",
    ])

    assert preview_numbered_lines(text) == ["台積電 2330", "聯發科 2454", "台光電 2383"]


def test_preview_numbered_lines_respects_limit():
    from app.services.workflow_text import preview_numbered_lines

    text = "\n".join([f"{idx}. 股票{idx} 00{idx}" for idx in range(1, 8)])

    assert preview_numbered_lines(text, limit=3) == ["股票1 001", "股票2 002", "股票3 003"]
