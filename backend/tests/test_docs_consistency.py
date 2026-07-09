"""
test_docs_consistency.py — 防止已下線的輸出檔名重新出現在「現行」文件中

buy_list.json / sell_list.json / hold_list.json 早已不再產生，
但曾多次殘留在協作文件裡誤導 heartbeat 與新進代理。
本測試鎖住現行文件；歷史記錄（phases.md、ai_tasks/）不在檢查範圍。
"""

from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent

# 已下線、不應再被文件描述為現行輸出的檔名
RETIRED_OUTPUT_FILES = ["buy_list.json", "sell_list.json", "hold_list.json"]

# 現行文件（歷史記錄不列入：phases.md、ai_tasks/ 允許保留舊敘述）
LIVE_DOCS = [
    REPO / "README.md",
    REPO / "CLAUDE.md",
    REPO / "AGENTS.md",
    BACKEND / "docs" / "api.md",
    BACKEND / "docs" / "architecture.md",
    BACKEND / "docs" / "signal_rules.md",
    BACKEND / "docs" / "status_overview.md",
    BACKEND / "docs" / "operations.md",
    BACKEND / "docs" / "daily_runbook.md",
]


def test_live_docs_exist():
    missing = [str(p) for p in LIVE_DOCS if not p.exists()]
    assert not missing, f"現行文件清單過時，找不到：{missing}"


def test_no_retired_output_files_in_live_docs():
    offenders = []
    for doc in LIVE_DOCS:
        text = doc.read_text(encoding="utf-8")
        for name in RETIRED_OUTPUT_FILES:
            if name in text:
                offenders.append(f"{doc.relative_to(REPO)} 提到已下線輸出 {name}")
    assert not offenders, (
        "現行文件不應再描述已下線的輸出檔：\n  " + "\n  ".join(offenders)
    )
