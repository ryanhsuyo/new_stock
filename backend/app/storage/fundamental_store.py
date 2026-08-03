"""基本面資料讀寫層，供基本面避雷品質價值指標使用。"""

import csv
import json
from pathlib import Path

from app.storage.atomic_write import atomic_write_csv

_DATA = Path(__file__).resolve().parent.parent.parent / "data"
FUNDAMENTALS_PATH = _DATA / "fundamentals.json"
FUNDAMENTALS_CSV_PATH = _DATA / "fundamentals.csv"

REQUIRED_FIELDS = (
    "roe_5y_avg",
    "operating_margin_5y_avg",
    "free_cash_flow_positive_years",
    "operating_cash_flow_to_net_income",
    "debt_to_equity",
    "interest_coverage",
    "revenue_growth_5y_cagr",
    "eps_growth_5y_cagr",
    "pe",
    "fcf_yield",
    "dividend_years",
)
INTEGER_FIELDS = {"free_cash_flow_positive_years", "dividend_years"}
PERCENT_FIELDS = {
    "roe_5y_avg",
    "operating_margin_5y_avg",
    "revenue_growth_5y_cagr",
    "eps_growth_5y_cagr",
    "fcf_yield",
}


def _parse_number(value: str | None, field: str) -> float | int | None:
    if value is None:
        return None
    raw = value.strip()
    if raw == "":
        return None
    number = float(raw.replace(",", ""))
    if field in INTEGER_FIELDS:
        return int(number)
    return number


def _format_csv_value(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _semantic_warning(code: str, row_number: int, field: str, value: float | int) -> dict | None:
    if field in PERCENT_FIELDS and 0 < abs(float(value)) < 1:
        return {
            "row_number": row_number,
            "code": code,
            "field": field,
            "value": value,
            "message": "百分比疑似填成小數，請用 28.5 代表 28.5%",
        }
    if field in {"roe_5y_avg", "operating_margin_5y_avg"} and float(value) > 100:
        return {
            "row_number": row_number,
            "code": code,
            "field": field,
            "value": value,
            "message": "數值偏高，請確認百分比格式",
        }
    if field == "free_cash_flow_positive_years" and int(value) > 5:
        return {
            "row_number": row_number,
            "code": code,
            "field": field,
            "value": value,
            "message": "近 5 年自由現金流為正年數通常為 0 到 5",
        }
    if field == "pe" and float(value) <= 0:
        return {
            "row_number": row_number,
            "code": code,
            "field": field,
            "value": value,
            "message": "本益比小於等於 0，請確認是否因虧損或資料錯誤",
        }
    return None


def _validate_fundamental_like_csv(path: Path) -> dict:
    row_count = 0
    filled_field_count = 0
    filled_codes: set[str] = set()
    complete_codes: list[str] = []
    partial_codes: list[str] = []
    empty_codes: list[str] = []
    seen_codes: set[str] = set()
    duplicate_codes: list[str] = []
    missing_code_rows: list[int] = []
    errors: list[dict] = []
    warnings: list[dict] = []
    row_statuses: list[dict] = []

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row_number, raw_row in enumerate(reader, start=2):
            row_count += 1
            code = (raw_row.get("code") or "").strip()
            if not code:
                missing_code_rows.append(row_number)
                continue

            if code in seen_codes and code not in duplicate_codes:
                duplicate_codes.append(code)
            seen_codes.add(code)

            row_has_valid_value = False
            row_filled_fields: list[str] = []
            for field in REQUIRED_FIELDS:
                raw_value = raw_row.get(field)
                if raw_value is None or raw_value.strip() == "":
                    continue
                try:
                    _parse_number(raw_value, field)
                except ValueError:
                    errors.append({
                        "row_number": row_number,
                        "code": code,
                        "field": field,
                        "value": raw_value,
                        "message": "必須是數字",
                    })
                    continue
                warning = _semantic_warning(code, row_number, field, _parse_number(raw_value, field))
                if warning:
                    warnings.append(warning)
                filled_field_count += 1
                row_filled_fields.append(field)
                row_has_valid_value = True

            if row_has_valid_value:
                filled_codes.add(code)
            valid_field_count = len(row_filled_fields)
            missing_fields = [
                field
                for field in REQUIRED_FIELDS
                if field not in row_filled_fields
            ]
            if valid_field_count == len(REQUIRED_FIELDS):
                complete_codes.append(code)
                row_status = "complete"
            elif valid_field_count > 0:
                partial_codes.append(code)
                row_status = "partial"
            else:
                empty_codes.append(code)
                row_status = "empty"
            row_statuses.append({
                "row_number": row_number,
                "code": code,
                "status": row_status,
                "filled_field_count": valid_field_count,
                "missing_field_count": len(missing_fields),
                "filled_fields": row_filled_fields,
                "missing_fields": missing_fields,
            })

    return {
        "path": str(path),
        "valid": not errors and not missing_code_rows and not duplicate_codes,
        "row_count": row_count,
        "filled_code_count": len(filled_codes),
        "filled_field_count": filled_field_count,
        "complete_code_count": len(complete_codes),
        "complete_codes": complete_codes,
        "partial_codes": partial_codes,
        "empty_codes": empty_codes,
        "row_statuses": row_statuses,
        "duplicate_codes": duplicate_codes,
        "missing_code_rows": missing_code_rows,
        "errors": errors,
        "warnings": warnings,
    }


def validate_fundamentals_csv(path: Path = FUNDAMENTALS_CSV_PATH) -> dict:
    """驗證正式 fundamentals.csv 是否可安全匯入 fundamentals.json。"""
    return _validate_fundamental_like_csv(path)


def validate_priority_csv(priority_path: Path) -> dict:
    """
    驗證 fundamentals_priority_fill.csv 是否可安全合併。

    驗證重點：
    - code 不可空白。
    - REQUIRED_FIELDS 中非空白欄位必須能解析成數字。
    - 回報重複 code，避免使用者誤以為只填了一列。
    """
    return _validate_fundamental_like_csv(priority_path)


def format_csv_validation_error(report: dict, label: str = "CSV") -> str:
    """把 CSV validation report 轉成短而可讀的錯誤訊息。"""
    if report.get("errors"):
        first = report["errors"][0]
        return (
            f"{label} validation failed: "
            f"row {first['row_number']} code {first['code']} "
            f"field {first['field']} value {first['value']!r} {first['message']}"
        )
    if report.get("missing_code_rows"):
        return (
            f"{label} validation failed: "
            f"missing code at rows {report['missing_code_rows']}"
        )
    return (
        f"{label} validation failed: "
        f"duplicate codes {report.get('duplicate_codes', [])}"
    )


def load_fundamentals() -> dict[str, dict]:
    if not FUNDAMENTALS_PATH.exists():
        return {}
    try:
        raw = json.loads(FUNDAMENTALS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(code): value for code, value in raw.items() if isinstance(value, dict)}


def load_fundamentals_from_csv(path: Path = FUNDAMENTALS_CSV_PATH) -> dict[str, dict]:
    data: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get("code") or "").strip()
            if not code:
                continue
            data[code] = {
                field: _parse_number(row.get(field), field)
                for field in REQUIRED_FIELDS
            }
    return data


def save_fundamentals(
    data: dict[str, dict],
    path: Path = FUNDAMENTALS_PATH,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def save_fundamentals_csv(
    data: dict[str, dict],
    codes: list[str],
    path: Path = FUNDAMENTALS_CSV_PATH,
) -> None:
    fieldnames = ["code", *REQUIRED_FIELDS]
    rows = [{
        "code": str(code),
        **{field: _format_csv_value(data.get(str(code), {}).get(field))
           for field in REQUIRED_FIELDS},
    } for code in codes]
    atomic_write_csv(path, fieldnames, rows)


def sync_fundamentals_csv(
    codes: list[str],
    path: Path = FUNDAMENTALS_CSV_PATH,
) -> dict:
    existing = load_fundamentals_from_csv(path) if path.exists() else {}
    seen: set[str] = set()
    ordered_codes: list[str] = []
    added_codes: list[str] = []

    for code in codes:
        code = str(code)
        if code in seen:
            continue
        seen.add(code)
        ordered_codes.append(code)
        if code not in existing:
            existing[code] = {field: None for field in REQUIRED_FIELDS}
            added_codes.append(code)

    for code in existing:
        if code not in seen:
            ordered_codes.append(code)

    save_fundamentals_csv(existing, ordered_codes, path=path)
    return {
        "path": str(path),
        "total_codes": len(ordered_codes),
        "added_count": len(added_codes),
        "added_codes": added_codes,
    }


def merge_priority_csv_into_fundamentals(
    priority_path: Path,
    fundamentals_path: Path = FUNDAMENTALS_CSV_PATH,
    dry_run: bool = False,
) -> dict:
    """
    將 fundamentals_priority_fill.csv 合併回正式 fundamentals.csv。

    合併規則：
    - priority CSV 空白欄位不覆蓋既有值。
    - 只有 REQUIRED_FIELDS 會被寫回，輔助欄位如 name / missing_fields 會忽略。
    - 若 priority CSV 有正式檔沒有的 code，會新增該 code row。
    """
    validation = validate_priority_csv(priority_path)
    if not validation["valid"]:
        raise ValueError(format_csv_validation_error(validation, label="priority CSV"))

    existing = load_fundamentals_from_csv(fundamentals_path) if fundamentals_path.exists() else {}
    order = list(existing.keys())
    touched_codes: list[str] = []
    updated_fields = 0
    added_codes: list[str] = []

    with priority_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            code = (raw_row.get("code") or "").strip()
            if not code:
                continue

            if code not in existing:
                existing[code] = {field: None for field in REQUIRED_FIELDS}
                order.append(code)
                added_codes.append(code)

            row_updated = False
            for field in REQUIRED_FIELDS:
                raw_value = raw_row.get(field)
                if raw_value is None or raw_value.strip() == "":
                    continue
                parsed = _parse_number(raw_value, field)
                if existing[code].get(field) != parsed:
                    existing[code][field] = parsed
                    updated_fields += 1
                    row_updated = True

            if row_updated:
                if code not in touched_codes:
                    touched_codes.append(code)

    if not dry_run:
        save_fundamentals_csv(existing, order, path=fundamentals_path)
    return {
        "path": str(fundamentals_path),
        "source": str(priority_path),
        "dry_run": dry_run,
        "updated_code_count": len(touched_codes),
        "updated_codes": touched_codes,
        "updated_field_count": updated_fields,
        "added_count": len(added_codes),
        "added_codes": added_codes,
        "validation": validation,
    }


def check_fundamentals(
    fundamentals: dict[str, dict],
    codes: list[str],
) -> dict:
    missing_codes: list[str] = []
    incomplete: dict[str, list[str]] = {}
    complete_codes: list[str] = []

    for code in codes:
        row = fundamentals.get(str(code))
        if not isinstance(row, dict):
            missing_codes.append(str(code))
            continue

        missing_fields = [
            field
            for field in REQUIRED_FIELDS
            if row.get(field) is None
        ]
        if missing_fields:
            incomplete[str(code)] = missing_fields
        else:
            complete_codes.append(str(code))

    return {
        "total_codes": len(codes),
        "complete_count": len(complete_codes),
        "incomplete_count": len(incomplete),
        "missing_count": len(missing_codes),
        "complete_codes": complete_codes,
        "incomplete": incomplete,
        "missing_codes": missing_codes,
    }
