import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def test_today_scan_json_cli_outputs_report(monkeypatch, capsys, tmp_path):
    import today_scan

    monkeypatch.setattr(today_scan, "build_today_scan_report", lambda out_dir, limit=1000: {
        "as_of": "2026-06-25",
        "formal_entries": [{"code": "2337", "name": "旺宏"}],
        "old_wang_candidates": [],
        "steady_momentum_candidates": [],
        "risk_items": [],
    })

    code = today_scan.run(today_scan.parse_args(["--backend", str(tmp_path), "--json"]))

    assert code == 0
    body = json.loads(capsys.readouterr().out)
    assert body["as_of"] == "2026-06-25"
    assert body["formal_entries"][0]["code"] == "2337"


def test_today_scan_write_report_calls_service(monkeypatch, tmp_path):
    import today_scan

    calls = []

    def fake_write(out_dir, limit=10):
        calls.append((out_dir, limit))
        path = out_dir / "today_scan.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        return path

    monkeypatch.setattr(today_scan, "write_today_scan_report", fake_write)

    code = today_scan.run(today_scan.parse_args(["--backend", str(tmp_path), "--write-report", "--limit", "3"]))

    assert code == 0
    assert calls == [(tmp_path / "out", 3)]


def test_today_scan_text_cli_prints_key_sections(monkeypatch, capsys, tmp_path):
    import today_scan

    monkeypatch.setattr(today_scan, "build_today_scan_report", lambda out_dir, limit=1000: {
        "as_of": "2026-06-25",
        "market_context": {"market_filter": "allow", "old_wang_market_filter": "block"},
        "formal_entries": [{"code": "2337", "name": "旺宏", "reason": "可分批"}],
        "old_wang_candidates": [{"code": "2303", "name": "聯電", "reason": "短均線轉強"}],
        "steady_momentum_candidates": [],
        "risk_items": [{"code": "2603", "name": "長榮", "reason": "跌破支撐"}],
        "notes": ["老王大盤濾網目前封鎖追價。"],
    })

    code = today_scan.run(today_scan.parse_args(["--backend", str(tmp_path)]))

    out = capsys.readouterr().out
    assert code == 0
    assert "資料日：2026-06-25" in out
    assert "正式可小試" in out
    assert "2337 旺宏" in out
    assert "老王觀察" in out
    assert "風險處理" in out
