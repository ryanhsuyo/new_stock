"""Official fundamentals ingestion helpers.

First slice:
- Use TWSE OpenAPI BWIBBU data.
- Safely fill only fields that map directly to the current fundamentals schema.
- Keep unmapped official fields in the report instead of inventing derived data.
"""

from __future__ import annotations

import csv
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.storage.fundamental_store import REQUIRED_FIELDS, validate_priority_csv

TWSE_BWIBBU_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
TWSE_MONTHLY_REVENUE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
TWSE_PROFITABILITY_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap17_L"
TWSE_BALANCE_SHEET_CI_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci"
TWSE_INCOME_STATEMENT_CI_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci"
TPEX_DAILY_PE_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/peQryDate"
TPEX_PROFITABILITY_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_187ap17_O"
TPEX_BALANCE_SHEET_CI_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap07_O_ci"
TPEX_INCOME_STATEMENT_CI_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_ci"
TWSE_DIVIDEND_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap45_L"
TPEX_DIVIDEND_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap39_O"
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


def _first_clean(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _clean(row.get(key))
        if value:
            return value
    return ""


def _sum_decimal_strings(row: dict[str, Any], *keys: str) -> str:
    total = Decimal("0")
    found = False
    scale = 0
    for key in keys:
        raw = _clean(row.get(key))
        if not raw:
            continue
        try:
            value = Decimal(raw.replace(",", ""))
        except InvalidOperation:
            continue
        found = True
        total += value
        exponent = value.as_tuple().exponent
        if exponent < 0:
            scale = max(scale, -exponent)
    if not found:
        return ""
    return f"{total:.{scale}f}" if scale else str(total)


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


def build_official_profitability_report_rows(
    *,
    twse_rows: list[dict[str, Any]] | None = None,
    tpex_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Build a neutral listed + OTC profitability summary report.

    These rows are report-only references. They intentionally do not fill
    `operating_margin_5y_avg` or other required fundamentals fields.
    """

    def normalize(row: dict[str, Any], source: str) -> dict[str, str] | None:
        code = _row_code(row)
        if not code:
            return None
        operating_margin = _first_clean(row, "營業利益率(%)", "operating_margin")
        pre_tax_margin = _first_clean(row, "稅前純益率(%)", "pre_tax_margin")
        after_tax_margin = _first_clean(row, "稅後純益率(%)", "after_tax_margin")
        skip_reasons = []
        if not operating_margin:
            skip_reasons.append("operating_margin_missing")
        if not pre_tax_margin:
            skip_reasons.append("pre_tax_margin_missing")
        if not after_tax_margin:
            skip_reasons.append("after_tax_margin_missing")
        return {
            "code": code,
            "name": _row_name(row),
            "year": _first_clean(row, "年度", "year"),
            "quarter": _first_clean(row, "季別", "quarter"),
            "operating_margin": operating_margin,
            "pre_tax_margin": pre_tax_margin,
            "after_tax_margin": after_tax_margin,
            "source": source,
            "skip_reason": ";".join(skip_reasons),
        }

    report_rows: list[dict[str, str]] = []
    for row in twse_rows or []:
        normalized = normalize(row, "twse_openapi_profitability_t187ap17_l")
        if normalized is not None:
            report_rows.append(normalized)
    for row in tpex_rows or []:
        normalized = normalize(row, "tpex_openapi_profitability_187ap17_o")
        if normalized is not None:
            report_rows.append(normalized)
    return report_rows


def build_official_balance_sheet_report_rows(
    *,
    twse_rows: list[dict[str, Any]] | None = None,
    tpex_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Build a neutral general-industry balance sheet reference report."""

    def normalize(row: dict[str, Any], source: str) -> dict[str, str] | None:
        code = _first_clean(row, "公司代號", "SecuritiesCompanyCode", "Code", "code")
        if not code:
            return None
        total_assets = _first_clean(row, "資產總額", "資產總計", "total_assets")
        liabilities = _first_clean(row, "負債總額", "負債總計", "liabilities")
        equity = _first_clean(row, "權益總額", "權益總計", "equity")
        skip_reasons = []
        if not total_assets:
            skip_reasons.append("total_assets_missing")
        if not liabilities:
            skip_reasons.append("liabilities_missing")
        if not equity:
            skip_reasons.append("equity_missing")
        return {
            "code": code,
            "name": _first_clean(row, "公司名稱", "CompanyName", "Name", "name"),
            "year": _first_clean(row, "年度", "year"),
            "quarter": _first_clean(row, "季別", "quarter"),
            "total_assets": total_assets,
            "liabilities": liabilities,
            "equity": equity,
            "source": source,
            "skip_reason": ";".join(skip_reasons),
        }

    report_rows: list[dict[str, str]] = []
    for row in twse_rows or []:
        normalized = normalize(row, "twse_openapi_balance_sheet_t187ap07_l_ci")
        if normalized is not None:
            report_rows.append(normalized)
    for row in tpex_rows or []:
        normalized = normalize(row, "tpex_openapi_balance_sheet_t187ap07_o_ci")
        if normalized is not None:
            report_rows.append(normalized)
    return report_rows


def build_official_income_statement_report_rows(
    *,
    twse_rows: list[dict[str, Any]] | None = None,
    tpex_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Build a neutral general-industry income statement reference report."""

    def normalize(row: dict[str, Any], source: str) -> dict[str, str] | None:
        code = _first_clean(row, "公司代號", "SecuritiesCompanyCode", "Code", "code")
        if not code:
            return None
        revenue = _first_clean(row, "營業收入", "revenue")
        operating_profit = _first_clean(row, "營業利益（損失）", "營業利益", "operating_profit")
        net_income = _first_clean(row, "本期淨利（淨損）", "本期淨利", "net_income")
        eps = _first_clean(row, "基本每股盈餘（元）", "eps")
        skip_reasons = []
        if not revenue:
            skip_reasons.append("revenue_missing")
        if not operating_profit:
            skip_reasons.append("operating_profit_missing")
        if not net_income:
            skip_reasons.append("net_income_missing")
        if not eps:
            skip_reasons.append("eps_missing")
        return {
            "code": code,
            "name": _first_clean(row, "公司名稱", "CompanyName", "Name", "name"),
            "year": _first_clean(row, "年度", "Year", "year"),
            "quarter": _first_clean(row, "季別", "Season", "quarter"),
            "revenue": revenue,
            "operating_profit": operating_profit,
            "net_income": net_income,
            "eps": eps,
            "source": source,
            "skip_reason": ";".join(skip_reasons),
        }

    report_rows: list[dict[str, str]] = []
    for row in twse_rows or []:
        normalized = normalize(row, "twse_openapi_income_statement_t187ap06_l_ci")
        if normalized is not None:
            report_rows.append(normalized)
    for row in tpex_rows or []:
        normalized = normalize(row, "tpex_openapi_income_statement_t187ap06_o_ci")
        if normalized is not None:
            report_rows.append(normalized)
    return report_rows


def build_official_dividend_report_rows(
    *,
    twse_rows: list[dict[str, Any]] | None = None,
    tpex_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Build a neutral listed + OTC dividend distribution reference report.

    Cash and stock dividend values are per-share sums of official component
    fields. The output remains report-only and must not fill `dividend_years`.
    """

    def normalize(row: dict[str, Any], source: str) -> dict[str, str] | None:
        code = _first_clean(row, "公司代號", "SecuritiesCompanyCode", "Code", "code")
        if not code:
            return None
        if source.startswith("twse"):
            cash_dividend = _sum_decimal_strings(
                row,
                "股東配發-盈餘分配之現金股利(元/股)",
                "股東配發-法定盈餘公積發放之現金(元/股)",
                "股東配發-資本公積發放之現金(元/股)",
            )
            stock_dividend = _sum_decimal_strings(
                row,
                "股東配發-盈餘轉增資配股(元/股)",
                "股東配發-法定盈餘公積轉增資配股(元/股)",
                "股東配發-資本公積轉增資配股(元/股)",
            )
            period = _first_clean(row, "股利所屬年(季)度", "期別", "period")
        else:
            cash_dividend = _sum_decimal_strings(
                row,
                "股東配發內容-盈餘分配之現金股利(元/股)",
                "股東配發內容-法定盈餘公積、資本公積發放之現金(元/股)",
            )
            stock_dividend = _sum_decimal_strings(
                row,
                "股東配發內容-盈餘轉增資配股(元/股)",
                "股東配發內容-法定盈餘公積、資本公積轉增資配股(元/股)",
            )
            period = _first_clean(row, "股利所屬年(季)度", "期別", "period")
        skip_reasons = []
        if not cash_dividend:
            skip_reasons.append("cash_dividend_missing")
        if not stock_dividend:
            skip_reasons.append("stock_dividend_missing")
        return {
            "code": code,
            "name": _first_clean(row, "公司名稱", "CompanyName", "Name", "name"),
            "dividend_year": _first_clean(row, "股利年度", "dividend_year"),
            "period": period,
            "cash_dividend": cash_dividend,
            "stock_dividend": stock_dividend,
            "source": source,
            "skip_reason": ";".join(skip_reasons),
        }

    report_rows: list[dict[str, str]] = []
    for row in twse_rows or []:
        normalized = normalize(row, "twse_openapi_dividend_t187ap45_l")
        if normalized is not None:
            report_rows.append(normalized)
    for row in tpex_rows or []:
        normalized = normalize(row, "tpex_openapi_dividend_t187ap39_o")
        if normalized is not None:
            report_rows.append(normalized)
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
    return apply_official_pe_values_to_priority_csv(
        priority_csv_path,
        twse_bwibbu_rows=bwibbu_rows,
        tpex_daily_pe_rows=[],
        dry_run=dry_run,
        legacy_twse_skip_reasons=True,
    )


def apply_official_pe_values_to_priority_csv(
    priority_csv_path: Path,
    *,
    twse_bwibbu_rows: list[dict[str, Any]] | None = None,
    tpex_daily_pe_rows: list[dict[str, Any]] | None = None,
    dry_run: bool = True,
    legacy_twse_skip_reasons: bool = False,
) -> dict[str, Any]:
    """Fill direct official PE values into fundamentals priority CSV.

    Safe direct mapping only:
    - TWSE BWIBBU `PEratio` / report `pe` -> fundamentals `pe`
    - TPEx daily PE report `pe` -> fundamentals `pe`

    Other official fields remain report-only references.
    """
    priority_csv_path = Path(priority_csv_path)
    fieldnames, rows = _load_priority_rows(priority_csv_path)
    twse_by_code = {
        _row_code(row): row
        for row in twse_bwibbu_rows or []
        if _row_code(row)
    }
    tpex_by_code = {
        _row_code(row): row
        for row in tpex_daily_pe_rows or []
        if _row_code(row)
    }

    updated_codes: list[str] = []
    updated_sources: dict[str, str] = {}
    skipped: list[dict[str, str]] = []
    updated_field_count = 0

    for row in rows:
        code = _clean(row.get("code"))
        if not code:
            continue
        twse_official = twse_by_code.get(code)
        official = twse_official
        source = "twse_openapi_bwibbu_all"
        if official is None or not _row_pe(official):
            official = tpex_by_code.get(code)
            source = "tpex_after_trading_pe_qry_date"
        if official is None:
            if legacy_twse_skip_reasons and twse_official is None:
                skipped.append({"code": code, "reason": "twse_b_wibbu_missing"})
                continue
            if legacy_twse_skip_reasons and twse_official is not None:
                skipped.append({"code": code, "reason": "twse_pe_missing_or_empty"})
                continue
            skipped.append({"code": code, "reason": "official_pe_missing"})
            continue
        pe = _row_pe(official)
        if not pe:
            skipped.append({"code": code, "reason": "official_pe_missing_or_empty"})
            continue
        if _clean(row.get("pe")) != pe:
            row["pe"] = pe
            updated_field_count += 1
            updated_codes.append(code)
            updated_sources[code] = source

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
        "source": "twse_tpex_official_pe",
        "source_url": f"{TWSE_BWIBBU_URL}; {TPEX_DAILY_PE_URL}",
        "source_row_count": len(twse_bwibbu_rows or []) + len(tpex_daily_pe_rows or []),
        "updated_code_count": len(updated_codes),
        "updated_codes": updated_codes,
        "updated_sources": updated_sources,
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
