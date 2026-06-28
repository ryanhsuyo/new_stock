"""Official fundamentals ingestion helpers.

First slice:
- Use TWSE OpenAPI BWIBBU data.
- Safely fill only fields that map directly to the current fundamentals schema.
- Keep unmapped official fields in the report instead of inventing derived data.
"""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from typing import Any

from app.storage.fundamental_store import REQUIRED_FIELDS, validate_priority_csv

TWSE_BWIBBU_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
TWSE_MONTHLY_REVENUE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
TPEX_DAILY_PE_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/peQryDate"
UNMAPPED_OFFICIAL_FIELDS = ["DividendYield", "PBratio"]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _row_code(row: dict[str, Any]) -> str:
    return _clean(row.get("Code") or row.get("code") or row.get("公司代號"))


def _row_pe(row: dict[str, Any]) -> str:
    return _clean(row.get("PEratio") or row.get("pe") or row.get("本益比"))


def _row_name(row: dict[str, Any]) -> str:
    return _clean(row.get("Name") or row.get("name") or row.get("公司名稱"))


def _row_dividend_yield(row: dict[str, Any]) -> str:
    return _clean(row.get("DividendYield") or row.get("dividend_yield") or row.get("殖利率"))


def _row_pb_ratio(row: dict[str, Any]) -> str:
    return _clean(row.get("PBratio") or row.get("pb_ratio") or row.get("股價淨值比"))


def build_twse_bwibbu_report_rows(bwibbu_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build a neutral official-source report from TWSE BWIBBU rows.

    This report preserves official fields that are useful for human review but
    are not exact destinations in the current fundamentals scoring schema.
    """
    report_rows: list[dict[str, str]] = []
    for row in bwibbu_rows:
        code = _row_code(row)
        if not code:
            continue
        pe = _row_pe(row)
        report_rows.append(
            {
                "code": code,
                "name": _row_name(row),
                "pe": pe,
                "dividend_yield": _row_dividend_yield(row),
                "pb_ratio": _row_pb_ratio(row),
                "source": "twse_openapi_bwibbu_all",
                "skip_reason": "" if pe else "twse_pe_missing_or_empty",
            }
        )
    return report_rows


def build_twse_monthly_revenue_report_rows(monthly_revenue_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build a neutral report from TWSE listed-company monthly revenue rows."""
    report_rows: list[dict[str, str]] = []
    for row in monthly_revenue_rows:
        code = _row_code(row)
        if not code:
            continue
        monthly_yoy = _clean(row.get("營業收入-去年同月增減(%)") or row.get("monthly_revenue_yoy_pct"))
        cumulative_yoy = _clean(row.get("累計營業收入-前期比較增減(%)") or row.get("cumulative_revenue_yoy_pct"))
        skip_reasons = []
        if not monthly_yoy:
            skip_reasons.append("twse_monthly_revenue_yoy_missing")
        if not cumulative_yoy:
            skip_reasons.append("twse_cumulative_revenue_yoy_missing")
        report_rows.append(
            {
                "code": code,
                "name": _row_name(row),
                "revenue_year_month": _clean(row.get("資料年月") or row.get("revenue_year_month")),
                "monthly_revenue": _clean(row.get("營業收入-當月營收") or row.get("monthly_revenue")),
                "monthly_revenue_yoy_pct": monthly_yoy,
                "cumulative_revenue": _clean(row.get("累計營業收入-當月累計營收") or row.get("cumulative_revenue")),
                "cumulative_revenue_yoy_pct": cumulative_yoy,
                "source": "twse_openapi_monthly_revenue_t187ap05_l",
                "note": _clean(row.get("備註") or row.get("note")),
                "skip_reason": ";".join(skip_reasons),
            }
        )
    return report_rows


def build_tpex_daily_pe_report_rows(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Build a neutral report from TPEx daily PE/PB/dividend JSON."""
    table = (payload.get("tables") or [{}])[0]
    fields = table.get("fields") or []
    data_rows = table.get("data") or []
    source_date = _clean(payload.get("date"))

    def cell(row: list[Any], field_name: str) -> str:
        try:
            index = fields.index(field_name)
        except ValueError:
            return ""
        if index >= len(row):
            return ""
        return _clean(row[index])

    report_rows: list[dict[str, str]] = []
    for row in data_rows:
        if not isinstance(row, list):
            continue
        code = cell(row, "股票代號")
        if not code:
            continue
        pe = cell(row, "本益比")
        if pe.upper() == "N/A":
            pe = ""
        report_rows.append(
            {
                "code": code,
                "name": cell(row, "公司名稱"),
                "pe": pe,
                "dividend_per_share": cell(row, "每股股利"),
                "dividend_year": cell(row, "股利年度"),
                "dividend_yield": cell(row, "殖利率(%)"),
                "pb_ratio": cell(row, "股價淨值比"),
                "financial_period": cell(row, "財報年/季"),
                "source": "tpex_after_trading_pe_qry_date",
                "source_date": source_date,
                "skip_reason": "" if pe else "tpex_pe_missing_or_na",
            }
        )
    return report_rows


def _load_priority_rows(priority_csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with priority_csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    missing = [field for field in ("code", *REQUIRED_FIELDS) if field not in fieldnames]
    if missing:
        raise ValueError("priority CSV 缺少必要欄位: " + ", ".join(missing))
    return fieldnames, rows


def _write_priority_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def apply_twse_official_values_to_priority_csv(
    priority_csv_path: Path,
    bwibbu_rows: list[dict[str, Any]],
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Fill direct official TWSE fields into fundamentals priority CSV.

    Current direct mapping:
    - BWIBBU_ALL.PEratio -> fundamentals `pe`

    Dividend yield and P/B are returned as unmapped official fields because the
    current scoring schema has no exact destination for them.
    """
    priority_csv_path = Path(priority_csv_path)
    fieldnames, rows = _load_priority_rows(priority_csv_path)
    by_code = {
        _row_code(row): row
        for row in bwibbu_rows
        if _row_code(row)
    }

    updated_codes: list[str] = []
    skipped: list[dict[str, str]] = []
    updated_field_count = 0

    for row in rows:
        code = _clean(row.get("code"))
        if not code:
            continue
        official = by_code.get(code)
        if official is None:
            skipped.append({"code": code, "reason": "twse_b_wibbu_missing"})
            continue
        pe = _row_pe(official)
        if not pe:
            skipped.append({"code": code, "reason": "twse_pe_missing_or_empty"})
            continue
        if _clean(row.get("pe")) != pe:
            row["pe"] = pe
            updated_field_count += 1
            updated_codes.append(code)

    if dry_run:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as tmp:
            preview_path = Path(tmp.name)
        try:
            _write_priority_rows(preview_path, fieldnames, rows)
            validation = validate_priority_csv(preview_path)
        finally:
            preview_path.unlink(missing_ok=True)
    else:
        _write_priority_rows(priority_csv_path, fieldnames, rows)
        validation = validate_priority_csv(priority_csv_path)

    return {
        "dry_run": dry_run,
        "priority_csv_path": str(priority_csv_path),
        "source": "twse_openapi_bwibbu_all",
        "source_url": TWSE_BWIBBU_URL,
        "source_row_count": len(bwibbu_rows),
        "updated_code_count": len(updated_codes),
        "updated_codes": updated_codes,
        "updated_field_count": updated_field_count,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "unmapped_official_fields": list(UNMAPPED_OFFICIAL_FIELDS),
        "validation": validation,
        "next_action_label": (
            "確認 dry-run 更新清單後，用 --apply 寫入 priority CSV"
            if dry_run
            else "檢查 priority CSV；仍需補齊其餘真實基本面欄位後才能合併"
        ),
    }
