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
    TPEX_BALANCE_SHEET_CI_URL,
    TPEX_DAILY_PE_URL,
    TPEX_DIVIDEND_URL,
    TPEX_INCOME_STATEMENT_CI_URL,
    TPEX_PROFITABILITY_URL,
    TWSE_BALANCE_SHEET_CI_URL,
    TWSE_BWIBBU_URL,
    TWSE_DIVIDEND_URL,
    TWSE_INCOME_STATEMENT_CI_URL,
    TWSE_MONTHLY_REVENUE_URL,
    TWSE_PROFITABILITY_URL,
    build_official_balance_sheet_report_rows,
    build_official_dividend_report_rows,
    build_official_income_statement_report_rows,
    build_official_profitability_report_rows,
    build_tpex_daily_pe_report_rows,
    build_twse_bwibbu_report_rows,
    build_twse_monthly_revenue_report_rows,
)
from app.storage.fundamental_store import REQUIRED_FIELDS

_OUT = Path(__file__).resolve().parent.parent.parent / "out"
DEFAULT_PRIORITY_CSV_PATH = _OUT / "fundamentals_priority_fill.csv"

DEFAULT_REPORT_KEYS = [
    "twse_bwibbu",
    "twse_monthly_revenue",
    "tpex_daily_pe",
    "profitability",
    "balance_sheet",
    "income_statement",
    "dividend",
]

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
    "profitability": {
        "label": "Official TWSE/TPEx profitability summary reference",
        "path": _OUT / "official_fundamentals_profitability.csv",
        "source": "twse_tpex_openapi_profitability",
    },
    "balance_sheet": {
        "label": "Official TWSE/TPEx balance sheet reference",
        "path": _OUT / "official_fundamentals_balance_sheet.csv",
        "source": "twse_tpex_openapi_balance_sheet_ci",
    },
    "income_statement": {
        "label": "Official TWSE/TPEx income statement reference",
        "path": _OUT / "official_fundamentals_income_statement.csv",
        "source": "twse_tpex_openapi_income_statement_ci",
    },
    "dividend": {
        "label": "Official TWSE/TPEx dividend distribution reference",
        "path": _OUT / "official_fundamentals_dividend.csv",
        "source": "twse_tpex_openapi_dividend",
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
    "profitability": [
        "code",
        "name",
        "year",
        "quarter",
        "operating_margin",
        "pre_tax_margin",
        "after_tax_margin",
        "source",
        "skip_reason",
    ],
    "balance_sheet": [
        "code",
        "name",
        "year",
        "quarter",
        "total_assets",
        "liabilities",
        "equity",
        "source",
        "skip_reason",
    ],
    "income_statement": [
        "code",
        "name",
        "year",
        "quarter",
        "revenue",
        "operating_profit",
        "net_income",
        "eps",
        "source",
        "skip_reason",
    ],
    "dividend": [
        "code",
        "name",
        "dividend_year",
        "period",
        "cash_dividend",
        "stock_dividend",
        "source",
        "skip_reason",
    ],
}

_AUDIT_REPORT_KEY_FIELDS: dict[str, list[str]] = {
    "twse_bwibbu": ["pe"],
    "twse_monthly_revenue": ["monthly_revenue_yoy_pct", "cumulative_revenue_yoy_pct"],
    "tpex_daily_pe": ["pe", "dividend_yield", "pb_ratio"],
    "profitability": ["operating_margin", "pre_tax_margin", "after_tax_margin"],
    "balance_sheet": ["total_assets", "liabilities", "equity"],
    "income_statement": ["revenue", "operating_profit", "net_income", "eps"],
    "dividend": ["cash_dividend", "stock_dividend"],
}

FORMALLY_FILLABLE_OFFICIAL_FIELDS = ["pe"]
BLOCKED_FORMAL_FIELDS = [field for field in REQUIRED_FIELDS if field not in FORMALLY_FILLABLE_OFFICIAL_FIELDS]


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


def _clean_cell(value: Any) -> str:
    return str(value or "").strip()


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _read_priority_targets(path: Path) -> list[dict[str, str]]:
    rows = _read_csv_rows(path)
    targets: list[dict[str, str]] = []
    for row in rows:
        code = _clean_cell(row.get("code"))
        if not code:
            continue
        targets.append(
            {
                "code": code,
                "name": _clean_cell(row.get("name")),
                "priority_reason": _clean_cell(row.get("priority_reason")),
            }
        )
    return targets


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


def build_official_fundamentals_coverage_audit(
    priority_csv_path: str | Path,
    *,
    reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Read official report-only CSVs and summarize coverage for priority stocks.

    This audit intentionally does not derive or write any formal fundamentals
    fields. It only explains whether reference rows exist in generated reports.
    """
    report_meta = reports or OFFICIAL_REPORTS
    targets = _read_priority_targets(Path(priority_csv_path))
    code_rows = [
        {
            "code": target["code"],
            "name": target["name"],
            "priority_reason": target["priority_reason"],
            "available_report_count": 0,
            "reports": {},
        }
        for target in targets
    ]
    by_code = {row["code"]: row for row in code_rows}
    report_summaries: dict[str, dict[str, Any]] = {}
    available_cell_count = 0
    missing_report_files: list[str] = []

    for key, meta in report_meta.items():
        path = Path(meta["path"])
        key_fields = _AUDIT_REPORT_KEY_FIELDS.get(key, [])
        report_summary = {
            "key": key,
            "label": meta.get("label") or key,
            "source": meta.get("source") or "",
            "path": str(path),
            "status": "ready",
            "exists": path.exists(),
            "row_count": 0,
            "available_count": 0,
            "missing_row_count": 0,
            "key_fields": key_fields,
        }
        rows_by_code: dict[str, dict[str, str]] = {}
        if not path.exists():
            report_summary["status"] = "missing_file"
            missing_report_files.append(key)
        else:
            rows = _read_csv_rows(path)
            report_summary["row_count"] = len(rows)
            rows_by_code = {_clean_cell(row.get("code")): row for row in rows if _clean_cell(row.get("code"))}

        for code, code_summary in by_code.items():
            if report_summary["status"] == "missing_file":
                status = "missing_file"
                present_fields: list[str] = []
                skip_reason = "report_file_missing"
            else:
                row = rows_by_code.get(code)
                if row is None:
                    status = "missing_row"
                    present_fields = []
                    skip_reason = "report_row_missing"
                    report_summary["missing_row_count"] += 1
                else:
                    present_fields = [field for field in key_fields if _clean_cell(row.get(field))]
                    skip_reason = _clean_cell(row.get("skip_reason"))
                    if present_fields:
                        status = "available"
                        code_summary["available_report_count"] += 1
                        report_summary["available_count"] += 1
                        available_cell_count += 1
                    else:
                        status = "empty_values"
                        if not skip_reason:
                            skip_reason = "key_fields_empty"
            code_summary["reports"][key] = {
                "status": status,
                "present_fields": present_fields,
                "skip_reason": skip_reason,
            }
        report_summaries[key] = report_summary

    denominator = len(targets) * len(report_meta)
    coverage_pct = round(available_cell_count / denominator * 100, 1) if denominator else 0.0
    return {
        "priority_csv_path": str(priority_csv_path),
        "target_count": len(targets),
        "report_count": len(report_meta),
        "available_cell_count": available_cell_count,
        "coverage_pct": coverage_pct,
        "missing_report_files": missing_report_files,
        "formally_fillable_official_fields": list(FORMALLY_FILLABLE_OFFICIAL_FIELDS),
        "blocked_formal_fields": list(BLOCKED_FORMAL_FIELDS),
        "reports": report_summaries,
        "codes": code_rows,
        "next_action_label": "先補齊缺失的 official report-only CSV；正式基本面欄位仍需人工確認公式與資料完整性",
    }


def get_official_fundamentals_coverage_audit() -> dict[str, Any]:
    """Return the read-only official coverage audit using generated out files."""
    if not DEFAULT_PRIORITY_CSV_PATH.exists():
        raise FileNotFoundError(f"尚無 {DEFAULT_PRIORITY_CSV_PATH.name}，請先產生或下載優先補資料 CSV")
    return build_official_fundamentals_coverage_audit(DEFAULT_PRIORITY_CSV_PATH)


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
        elif key == "profitability":
            twse_rows = _fetch_twse_rows(TWSE_PROFITABILITY_URL)
            tpex_rows = _fetch_twse_rows(TPEX_PROFITABILITY_URL)
            rows = build_official_profitability_report_rows(twse_rows=twse_rows, tpex_rows=tpex_rows)
        elif key == "balance_sheet":
            twse_rows = _fetch_twse_rows(TWSE_BALANCE_SHEET_CI_URL)
            tpex_rows = _fetch_twse_rows(TPEX_BALANCE_SHEET_CI_URL)
            rows = build_official_balance_sheet_report_rows(twse_rows=twse_rows, tpex_rows=tpex_rows)
        elif key == "income_statement":
            twse_rows = _fetch_twse_rows(TWSE_INCOME_STATEMENT_CI_URL)
            tpex_rows = _fetch_twse_rows(TPEX_INCOME_STATEMENT_CI_URL)
            rows = build_official_income_statement_report_rows(twse_rows=twse_rows, tpex_rows=tpex_rows)
        elif key == "dividend":
            twse_rows = _fetch_twse_rows(TWSE_DIVIDEND_URL)
            tpex_rows = _fetch_twse_rows(TPEX_DIVIDEND_URL)
            rows = build_official_dividend_report_rows(twse_rows=twse_rows, tpex_rows=tpex_rows)
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
