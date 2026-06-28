"""HTTP-facing helpers for official fundamentals reports.

Routers should call this module instead of reading generated CSV files directly.
"""

from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from app.services.official_fundamentals_service import (
    TPEX_DAILY_PE_URL,
    TWSE_BWIBBU_URL,
    TWSE_MONTHLY_REVENUE_URL,
    build_tpex_daily_pe_report_rows,
    build_twse_bwibbu_report_rows,
    build_twse_monthly_revenue_report_rows,
)

_OUT = Path(__file__).resolve().parent.parent.parent / "out"

DEFAULT_REPORT_KEYS = ["twse_bwibbu", "twse_monthly_revenue", "tpex_daily_pe"]

OFFICIAL_REPORTS: dict[str, dict[str, Any]] = {
    "twse_bwibbu": {
        "label": "TWSE BWIBBU PE/PB/dividend reference",
        "path": _OUT / "official_fundamentals_twse_bwibbu.csv",
        "source": "twse_openapi_bwibbu_all",
    },
    "twse_monthly_revenue": {
        "label": "TWSE listed monthly revenue reference",
        "path": _OUT / "official_fundamentals_twse_monthly_revenue.csv",
        "source": "twse_openapi_monthly_revenue_t187ap05_l",
    },
    "tpex_daily_pe": {
        "label": "TPEx PE/PB/dividend reference",
        "path": _OUT / "official_fundamentals_tpex_daily_pe.csv",
        "source": "tpex_after_trading_pe_qry_date",
    },
}

_REPORT_FIELDNAMES: dict[str, list[str]] = {
    "twse_bwibbu": ["code", "name", "pe", "dividend_yield", "pb_ratio", "source", "skip_reason"],
    "twse_monthly_revenue": [
        "code",
        "name",
        "revenue_year_month",
        "monthly_revenue",
        "monthly_revenue_yoy_pct",
        "cumulative_revenue",
        "cumulative_revenue_yoy_pct",
        "source",
        "note",
        "skip_reason",
    ],
    "tpex_daily_pe": [
        "code",
        "name",
        "pe",
        "dividend_per_share",
        "dividend_year",
        "dividend_yield",
        "pb_ratio",
        "financial_period",
        "source",
        "source_date",
        "skip_reason",
    ],
}


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def _modified_at(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _write_report(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _fetch_twse_rows(url: str, *, timeout: int = 20) -> list[dict[str, Any]]:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        raise ValueError("TWSE 官方 API 回應不是 JSON array")
    return [item for item in raw if isinstance(item, dict)]


def _fetch_tpex_daily_pe(date: str | None, *, timeout: int = 20) -> dict[str, Any]:
    response = requests.post(
        TPEX_DAILY_PE_URL,
        data={"date": date or "", "cate": "", "response": "json"},
        timeout=timeout,
    )
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, dict):
        raise ValueError("TPEx 官方 API 回應不是 JSON object")
    if raw.get("stat") != "ok":
        raise ValueError("TPEx 官方 API 回應失敗: " + str(raw.get("stat")))
    return raw


def get_official_fundamentals_status() -> dict[str, Any]:
    """Return generated official fundamentals report status."""
    reports: dict[str, dict[str, Any]] = {}
    existing_count = 0
    for key, meta in OFFICIAL_REPORTS.items():
        path = Path(meta["path"])
        exists = path.exists()
        if exists:
            existing_count += 1
        reports[key] = {
            "key": key,
            "label": meta["label"],
            "source": meta["source"],
            "path": str(path),
            "exists": exists,
            "row_count": _count_csv_rows(path),
            "modified_at": _modified_at(path),
        }

    if existing_count == 0:
        overall_status = "missing"
    elif existing_count == len(OFFICIAL_REPORTS):
        overall_status = "ready"
    else:
        overall_status = "partial"

    return {
        "overall_status": overall_status,
        "reports": reports,
        "next_action_label": "可用 POST /api/system/fundamentals-official/reports 產生官方 report-only CSV",
    }


def run_official_fundamentals_reports(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate official fundamentals report-only CSV files.

    This HTTP wrapper intentionally does not apply values to the priority CSV.
    Priority CSV updates remain a separate dry-run/apply CLI workflow so the
    API cannot accidentally mutate fundamentals scoring inputs.
    """
    requested_reports = payload.get("reports") or list(DEFAULT_REPORT_KEYS)
    apply = bool(payload.get("apply", False))
    sleep_seconds = float(payload.get("sleep", 1.0) or 0)
    tpex_daily_pe_date = payload.get("tpex_daily_pe_date")

    unknown_reports = [key for key in requested_reports if key not in OFFICIAL_REPORTS]
    if unknown_reports:
        raise ValueError("未知官方報告: " + ", ".join(unknown_reports))
    if apply:
        raise ValueError("HTTP API 只支援 report-only/dry-run；priority CSV apply 請使用 CLI 並人工確認")

    results: dict[str, dict[str, Any]] = {}

    for key in requested_reports:
        path = Path(OFFICIAL_REPORTS[key]["path"])
        _sleep(sleep_seconds)
        if key == "twse_bwibbu":
            source_rows = _fetch_twse_rows(TWSE_BWIBBU_URL)
            rows = build_twse_bwibbu_report_rows(source_rows)
        elif key == "twse_monthly_revenue":
            source_rows = _fetch_twse_rows(TWSE_MONTHLY_REVENUE_URL)
            rows = build_twse_monthly_revenue_report_rows(source_rows)
        elif key == "tpex_daily_pe":
            source_payload = _fetch_tpex_daily_pe(tpex_daily_pe_date)
            rows = build_tpex_daily_pe_report_rows(source_payload)
        else:  # pragma: no cover - guarded by unknown_reports above
            continue

        _write_report(path, _REPORT_FIELDNAMES[key], rows)
        results[key] = {
            "path": str(path),
            "row_count": len(rows),
            "source": OFFICIAL_REPORTS[key]["source"],
        }

    return {
        "dry_run": True,
        "apply": False,
        "requested_reports": list(requested_reports),
        "reports": results,
        "warnings": [],
    }
