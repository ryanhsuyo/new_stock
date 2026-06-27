import json
from datetime import date, timedelta

from app.services import data_coverage_service as svc
from app.services.workflow_outputs import DAILY_UPDATE_OUTPUTS


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _write_ohlcv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["date,code,open,high,low,close,volume"]
    for row in rows:
        lines.append(
            ",".join(
                [
                    row["date"],
                    row["code"],
                    "10",
                    "11",
                    "9",
                    "10.5",
                    "1000",
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _rows(code, start, count):
    current = start
    rows = []
    while len(rows) < count:
        if current.weekday() < 5:
            rows.append({"date": current.isoformat(), "code": code})
        current += timedelta(days=1)
    return rows


def test_build_data_coverage_report_classifies_tracked_symbols(tmp_path):
    leaders = tmp_path / "data" / "leaders.json"
    ohlcv = tmp_path / "data" / "ohlcv.csv"
    _write_json(
        leaders,
        {
            "large_cap": ["2330", "2317"],
            "watch": {"ai": ["2454"], "short": ["9999"]},
        },
    )
    _write_ohlcv(
        ohlcv,
        [
            *_rows("2330", date(2026, 3, 27), 62),
            *_rows("2454", date(2026, 3, 20), 62),
            *_rows("9999", date(2026, 6, 19), 2),
        ],
    )

    report = svc.build_data_coverage_report(
        leaders_path=leaders,
        ohlcv_path=ohlcv,
        batch_id="batch-test",
        today=date(2026, 6, 23),
        minimum_rows=60,
    )

    by_code = {item["code"]: item for item in report["symbols"]}
    assert report["batch_id"] == "batch-test"
    assert report["expected_trading_day"] == "2026-06-22"
    assert report["raw_ohlcv_as_of"] == "2026-06-22"
    assert report["tracked_count"] == 4
    assert report["ok_count"] == 1
    assert report["coverage_pct"] == 25.0
    assert by_code["2330"]["status"] == "ok"
    assert by_code["2317"]["status"] == "missing"
    assert by_code["2454"]["status"] == "lagging"
    assert by_code["9999"]["status"] == "insufficient"
    assert all(item["reason"] for item in report["symbols"])


def test_write_data_coverage_report_uses_generated_output_path(tmp_path):
    report = {
        "generated_at": "2026-06-23T20:00:00",
        "batch_id": "batch-test",
        "expected_trading_day": "2026-06-22",
        "raw_ohlcv_as_of": "2026-06-22",
        "tracked_count": 1,
        "ok_count": 1,
        "coverage_pct": 100.0,
        "symbols": [],
    }

    path = svc.write_data_coverage_report(report, tmp_path / "out")

    assert path == tmp_path / "out" / "data_coverage_report.json"
    assert json.loads(path.read_text(encoding="utf-8"))["batch_id"] == "batch-test"


def test_daily_update_expected_outputs_include_coverage_report():
    assert "backend/out/data_coverage_report.json" in DAILY_UPDATE_OUTPUTS
