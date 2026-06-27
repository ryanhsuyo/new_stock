"""基本面資料狀態服務。"""

from collections import Counter
import csv
import json
from pathlib import Path
import tempfile

from app.services.fundamental_guard_service import evaluate_fundamental_guard
from app.storage.fundamental_store import (
    FUNDAMENTALS_PATH,
    FUNDAMENTALS_CSV_PATH,
    REQUIRED_FIELDS,
    check_fundamentals,
    format_csv_validation_error,
    load_fundamentals_from_csv,
    load_fundamentals,
    merge_priority_csv_into_fundamentals,
    save_fundamentals,
    validate_fundamentals_csv,
    validate_priority_csv,
)
from app.storage.name_store import load_stock_names

_BACKEND = Path(__file__).resolve().parent.parent.parent
_LEADERS_PATH = _BACKEND / "data" / "leaders.json"
_OUT = _BACKEND / "out"
_SUMMARY_PATH = _OUT / "summary.json"
_REPORT_PATH = _OUT / "fundamentals_report.json"
_FUNDAMENTALS_CSV_PATH = FUNDAMENTALS_CSV_PATH
_FUNDAMENTALS_JSON_PATH = FUNDAMENTALS_PATH
_PRIORITY_CSV_PATH = _OUT / "fundamentals_priority_fill.csv"
_MERGE_CONFIRM = "MERGE_PRIORITY_FUNDAMENTALS"

FIELD_LABELS = {
    "roe_5y_avg": "5 年平均 ROE",
    "operating_margin_5y_avg": "5 年平均營業利益率",
    "free_cash_flow_positive_years": "近 5 年自由現金流為正年數",
    "operating_cash_flow_to_net_income": "營業現金流 / 淨利",
    "debt_to_equity": "負債權益比",
    "interest_coverage": "利息保障倍數",
    "revenue_growth_5y_cagr": "營收 5 年 CAGR",
    "eps_growth_5y_cagr": "EPS 5 年 CAGR",
    "pe": "本益比",
    "fcf_yield": "自由現金流殖利率",
    "dividend_years": "連續配息年數",
}

FIELD_EXAMPLE_VALUES = {
    "roe_5y_avg": "28.5",
    "operating_margin_5y_avg": "42.1",
    "free_cash_flow_positive_years": "5",
    "operating_cash_flow_to_net_income": "1.18",
    "debt_to_equity": "35",
    "interest_coverage": "80",
    "revenue_growth_5y_cagr": "14.2",
    "eps_growth_5y_cagr": "12.8",
    "pe": "22.5",
    "fcf_yield": "3.6",
    "dividend_years": "10",
}

FILL_FORMAT_NOTE = "百分比欄位請填 28.5，不要填 0.285；倍數與年數填一般數字。"

IMPORT_FIELD_ALIASES = {
    "code": "code",
    "stockid": "code",
    "stock_id": "code",
    "ticker": "code",
    "代號": "code",
    "股票代號": "code",
    "roe5y": "roe_5y_avg",
    "roe5yavg": "roe_5y_avg",
    "5年平均roe": "roe_5y_avg",
    "營業利益率": "operating_margin_5y_avg",
    "5年平均營業利益率": "operating_margin_5y_avg",
    "fcfpositiveyears": "free_cash_flow_positive_years",
    "近5年自由現金流為正年數": "free_cash_flow_positive_years",
    "ocftoni": "operating_cash_flow_to_net_income",
    "營業現金流淨利": "operating_cash_flow_to_net_income",
    "營業現金流/淨利": "operating_cash_flow_to_net_income",
    "debttoequity": "debt_to_equity",
    "負債權益比": "debt_to_equity",
    "interestcoverage": "interest_coverage",
    "利息保障倍數": "interest_coverage",
    "revenuegrowth5ycagr": "revenue_growth_5y_cagr",
    "營收5年cagr": "revenue_growth_5y_cagr",
    "epsgrowth5ycagr": "eps_growth_5y_cagr",
    "eps5年cagr": "eps_growth_5y_cagr",
    "pe": "pe",
    "本益比": "pe",
    "fcfyield": "fcf_yield",
    "自由現金流殖利率": "fcf_yield",
    "dividendyears": "dividend_years",
    "連續配息年數": "dividend_years",
}


def _flatten_codes(obj) -> list[str]:
    codes: list[str] = []
    if isinstance(obj, dict):
        for value in obj.values():
            codes.extend(_flatten_codes(value))
    elif isinstance(obj, list):
        for item in obj:
            codes.extend(_flatten_codes(item))
    elif isinstance(obj, str):
        codes.append(obj.strip())
    return codes


def _load_leader_codes(path: Path = _LEADERS_PATH) -> list[str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    seen: set[str] = set()
    codes: list[str] = []
    for code in _flatten_codes(raw):
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def _load_recommendation_priority(path: Path = _SUMMARY_PATH) -> list[str]:
    if not path.exists():
        return []
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    priority: list[str] = []
    seen: set[str] = set()
    buckets = summary.get("recommendation_buckets") or {}
    for key in ("old_wang", "steady_momentum"):
        for item in buckets.get(key) or []:
            code = str(item.get("code") or "").strip()
            if code and code not in seen:
                seen.add(code)
                priority.append(code)
    return priority


def _field_missing_counts(incomplete: dict[str, list[str]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for fields in incomplete.values():
        counter.update(fields)
    return dict(counter.most_common())


def _priority_csv_validation(path: Path | None = None) -> dict | None:
    path = path or _PRIORITY_CSV_PATH
    if not path.exists():
        return None
    return validate_priority_csv(path)


def _fundamentals_csv_validation(path: Path | None = None) -> dict | None:
    path = path or _FUNDAMENTALS_CSV_PATH
    if not path.exists():
        return None
    return validate_fundamentals_csv(path)


def _priority_fill_readiness(validation: dict | None) -> dict:
    if validation is None:
        return {
            "status": "not_generated",
            "can_preview": False,
            "can_merge": False,
            "message": "尚未產生 fundamentals_priority_fill.csv。",
            "suggested_action": "先下載補資料 CSV，填完必要欄位後再預覽合併。",
            "filled_code_count": 0,
            "filled_field_count": 0,
            "row_count": 0,
        }

    filled_code_count = int(validation.get("filled_code_count") or 0)
    filled_field_count = int(validation.get("filled_field_count") or 0)
    complete_code_count = int(validation.get("complete_code_count") or 0)
    partial_code_count = len(validation.get("partial_codes") or [])
    row_count = int(validation.get("row_count") or 0)

    if not validation.get("valid"):
        return {
            "status": "invalid",
            "can_preview": False,
            "can_merge": False,
            "message": format_csv_validation_error(validation, label="priority CSV"),
            "suggested_action": "先修正 CSV 內的錯誤值、空白代號或重複代號，再重新預覽。",
            "filled_code_count": filled_code_count,
            "filled_field_count": filled_field_count,
            "complete_code_count": complete_code_count,
            "partial_code_count": partial_code_count,
            "row_count": row_count,
        }

    if filled_field_count == 0:
        return {
            "status": "empty",
            "can_preview": True,
            "can_merge": False,
            "message": f"補資料 CSV 有 {row_count} 檔，但尚未填任何基本面欄位。",
            "suggested_action": "先填 ROE、現金流、負債、成長與估值欄位，再按預覽合併。",
            "filled_code_count": filled_code_count,
            "filled_field_count": filled_field_count,
            "complete_code_count": complete_code_count,
            "partial_code_count": partial_code_count,
            "row_count": row_count,
        }

    if complete_code_count == 0:
        return {
            "status": "ready_to_preview",
            "can_preview": True,
            "can_merge": False,
            "message": f"補資料 CSV 已部分填寫 {filled_code_count} 檔、{filled_field_count} 個欄位，但尚無完整 11 欄股票。",
            "suggested_action": "已部分填寫，仍需補齊 11 欄才會產生基本面避雷結果。",
            "filled_code_count": filled_code_count,
            "filled_field_count": filled_field_count,
            "complete_code_count": complete_code_count,
            "partial_code_count": partial_code_count,
            "row_count": row_count,
        }

    return {
        "status": "ready_to_merge",
        "can_preview": True,
        "can_merge": True,
        "message": f"補資料 CSV 已有 {complete_code_count} 檔完整可評分，合併後可產生基本面避雷結果。",
        "suggested_action": "先按預覽合併，確認更新檔數與欄位數後再合併匯入。",
        "filled_code_count": filled_code_count,
        "filled_field_count": filled_field_count,
        "complete_code_count": complete_code_count,
        "partial_code_count": partial_code_count,
        "row_count": row_count,
    }


def _priority_fill_guide(validation: dict | None) -> dict:
    if validation is None:
        return {
            "next_action_label": "先下載補資料 CSV",
            "complete_ready_count": 0,
            "partial_count": 0,
            "empty_count": 0,
            "warning_count": 0,
            "format_note": FILL_FORMAT_NOTE,
            "example_values": FIELD_EXAMPLE_VALUES,
        }

    complete_count = int(validation.get("complete_code_count") or 0)
    partial_count = len(validation.get("partial_codes") or [])
    empty_count = len(validation.get("empty_codes") or [])
    warning_count = len(validation.get("warnings") or [])
    if not validation.get("valid"):
        next_action = "先修正 CSV 錯誤"
    elif complete_count > 0:
        next_action = f"可先預覽合併 {complete_count} 檔"
    elif partial_count > 0:
        next_action = f"已部分填寫 {partial_count} 檔，補齊 11 欄後再合併"
    else:
        next_action = "先填優先 20 檔"
    return {
        "next_action_label": next_action,
        "complete_ready_count": complete_count,
        "partial_count": partial_count,
        "empty_count": empty_count,
        "warning_count": warning_count,
        "format_note": FILL_FORMAT_NOTE,
        "example_values": FIELD_EXAMPLE_VALUES,
    }


def _workflow_step(key: str, label: str, detail: str, status: str) -> dict:
    return {
        "key": key,
        "label": label,
        "detail": detail,
        "status": status,
    }


def _fill_targets_copy_text(
    next_fill_targets: list[dict],
    complete: int,
    total: int,
    limit: int = 10,
) -> str:
    lines = [
        "基本面避雷優先補資料清單",
        f"覆蓋率 {complete}/{total}，優先補 {min(limit, len(next_fill_targets))} 檔",
        FILL_FORMAT_NOTE,
        "",
    ]
    for index, target in enumerate(next_fill_targets[:limit], start=1):
        lines.append(
            f"{index}. {target.get('name') or target.get('code')} {target.get('code')} - "
            f"{target.get('priority_reason') or 'leaders 清單'}，缺 {target.get('missing_count')} 欄"
        )
        for field, label in zip(target.get("missing_fields") or [], target.get("missing_field_labels") or []):
            example = FIELD_EXAMPLE_VALUES.get(field)
            example_part = f"，範例 {example}" if example else ""
            lines.append(f"   - {label} ({field}{example_part})")
        lines.append("")
    return "\n".join(lines).strip()


def _fundamentals_workflow_summary(
    status: dict,
    readiness: dict,
    fill_guide: dict,
    next_fill_targets: list[dict],
) -> dict:
    readiness_status = str(readiness.get("status") or "")
    complete = int(status.get("complete_count") or 0)
    total = int(status.get("total_codes") or 0)
    coverage_pct = float(status.get("coverage_pct") or 0)
    complete_ready_count = int(readiness.get("complete_code_count") or 0)
    partial_count = int(readiness.get("partial_code_count") or 0)
    filled_field_count = int(readiness.get("filled_field_count") or 0)

    if readiness_status == "invalid":
        stage = "fix_priority_csv"
        headline = "先修正基本面避雷補資料 CSV"
        detail = readiness.get("message") or "priority CSV 有錯誤，修正後才能預覽或合併。"
        primary_action = {
            "label": "修正 CSV",
            "command": str(_PRIORITY_CSV_PATH),
            "kind": "file",
        }
        checklist_status = ("done", "blocked", "blocked", "blocked")
    elif readiness_status == "ready_to_merge":
        stage = "ready_to_merge"
        headline = "先預覽，再合併基本面避雷資料"
        detail = (
            f"目前有 {complete_ready_count} 檔已補齊 11 欄，可先預覽分數與更新欄位，確認後合併匯入。"
        )
        primary_action = {
            "label": "預覽合併",
            "command": "POST /api/system/fundamentals-priority-fill/merge",
            "kind": "api",
        }
        checklist_status = ("done", "done", "todo", "blocked")
    elif readiness_status == "ready_to_preview":
        stage = "fill_priority_csv"
        headline = "補齊基本面避雷必要欄位"
        detail = (
            f"補資料 CSV 已部分填寫 {partial_count} 檔、{filled_field_count} 個欄位；"
            "每檔需補齊 11 欄才會進入基本面避雷評分。"
        )
        primary_action = {
            "label": "繼續填 CSV",
            "command": str(_PRIORITY_CSV_PATH),
            "kind": "file",
        }
        checklist_status = ("done", "todo", "blocked", "blocked")
    elif readiness_status == "empty":
        stage = "fill_priority_csv"
        headline = "開始填基本面避雷優先補資料 CSV"
        detail = "補資料 CSV 已產生，但尚未填入基本面欄位；先補優先清單前幾檔即可。"
        primary_action = {
            "label": "填寫 CSV",
            "command": str(_PRIORITY_CSV_PATH),
            "kind": "file",
        }
        checklist_status = ("done", "todo", "blocked", "blocked")
    else:
        stage = "generate_priority_csv"
        headline = "先產生基本面避雷優先補資料 CSV"
        detail = (
            f"目前基本面避雷覆蓋率 {complete}/{total}（{coverage_pct:.1f}%）；"
            "先下載優先補資料 CSV，不必一次補完全部追蹤股。"
        )
        primary_action = {
            "label": "下載補資料 CSV",
            "command": "GET /api/system/fundamentals-priority-fill",
            "kind": "download",
        }
        checklist_status = ("todo", "blocked", "blocked", "blocked")

    checklist = [
        _workflow_step(
            "download_priority_csv",
            "產生優先 CSV",
            "下載或產生 backend/out/fundamentals_priority_fill.csv。",
            checklist_status[0],
        ),
        _workflow_step(
            "fill_required_fields",
            "補齊 11 欄",
            fill_guide.get("format_note") or FILL_FORMAT_NOTE,
            checklist_status[1],
        ),
        _workflow_step(
            "preview_and_merge",
            "預覽並合併",
            "先預覽基本面避雷試算與更新欄位，再正式合併匯入 fundamentals.json。",
            checklist_status[2],
        ),
        _workflow_step(
            "rerun_signals",
            "重新產生訊號",
            "合併後執行 python3 scripts/run_signals.py，讓基本面避雷分數進入 summary / universe_report。",
            checklist_status[3],
        ),
    ]

    return {
        "stage": stage,
        "headline": headline,
        "detail": detail,
        "coverage_label": f"{complete}/{total} 完整",
        "primary_action": primary_action,
        "checklist": checklist,
        "focus_targets": next_fill_targets[:5],
        "fill_targets_copy_text": _fill_targets_copy_text(next_fill_targets, complete, total),
        "field_missing_counts": status.get("field_missing_counts") or {},
    }


def _fundamental_preview_from_priority_csv(validation: dict | None) -> list[dict]:
    if not validation or not validation.get("valid"):
        return []
    complete_codes = [str(code) for code in validation.get("complete_codes") or []]
    if not complete_codes or not _PRIORITY_CSV_PATH.exists():
        return []

    names = load_stock_names()
    priority_data = load_fundamentals_from_csv(_PRIORITY_CSV_PATH)
    preview: list[dict] = []
    for code in complete_codes:
        result = evaluate_fundamental_guard(code, priority_data.get(code))
        preview.append({
            "code": code,
            "name": names.get(code, code),
            "fundamental_flag": result.get("fundamental_flag"),
            "fundamental_score": result.get("fundamental_score"),
            "fundamental_signal": result.get("fundamental_signal"),
            "fundamental_data_ok": result.get("fundamental_data_ok"),
            "fundamental_reason": result.get("fundamental_reason"),
            "fundamental_data_missing_reason": result.get("fundamental_data_missing_reason"),
            "fundamental_quality_score": result.get("fundamental_quality_score"),
            "fundamental_value_score": result.get("fundamental_value_score"),
            "fundamental_safety_score": result.get("fundamental_safety_score"),
            "fundamental_growth_score": result.get("fundamental_growth_score"),
        })
    return preview


def _next_fill_targets(report: dict, codes: list[str], limit: int = 20) -> list[dict]:
    names = load_stock_names()
    priority = _load_recommendation_priority()
    ordered_codes = [code for code in priority if code in codes]
    ordered_codes.extend(code for code in codes if code not in set(ordered_codes))

    targets: list[dict] = []
    for code in ordered_codes:
        fields = report["incomplete"].get(code)
        if fields is None and code in report["missing_codes"]:
            fields = list(REQUIRED_FIELDS)
        if not fields:
            continue
        targets.append({
            "code": code,
            "name": names.get(code, code),
            "missing_count": len(fields),
            "missing_fields": fields,
            "missing_field_labels": [FIELD_LABELS.get(field, field) for field in fields],
            "priority_reason": "目前推薦/觀察名單" if code in priority else "leaders 清單",
        })
        if len(targets) >= limit:
            break
    return targets


def build_fundamentals_status(codes: list[str] | None = None) -> dict:
    if codes is None:
        codes = _load_leader_codes()
    report = check_fundamentals(load_fundamentals(), codes)
    total = report["total_codes"]
    complete = report["complete_count"]
    coverage_pct = round(complete / total * 100, 1) if total else 0.0
    priority_validation = _priority_csv_validation()
    field_missing_counts = _field_missing_counts(report["incomplete"])
    next_fill_targets = _next_fill_targets(report, codes)
    readiness = _priority_fill_readiness(priority_validation)
    fill_guide = _priority_fill_guide(priority_validation)
    status = {
        **report,
        "coverage_pct": coverage_pct,
        "field_missing_counts": field_missing_counts,
    }
    return {
        **report,
        "coverage_pct": coverage_pct,
        "required_fields": list(REQUIRED_FIELDS),
        "field_labels": FIELD_LABELS,
        "field_missing_counts": field_missing_counts,
        "next_fill_targets": next_fill_targets,
        "csv_path": str(_FUNDAMENTALS_CSV_PATH),
        "json_path": str(_BACKEND / "data" / "fundamentals.json"),
        "priority_csv_path": str(_PRIORITY_CSV_PATH),
        "fundamentals_csv_validation": _fundamentals_csv_validation(),
        "priority_csv_validation": priority_validation,
        "priority_fill_readiness": readiness,
        "priority_fill_guide": fill_guide,
        "workflow_summary": _fundamentals_workflow_summary(status, readiness, fill_guide, next_fill_targets),
    }


def get_fundamentals_status() -> dict:
    return build_fundamentals_status()


def write_fundamentals_report(out_dir: Path | None = None) -> Path:
    target_dir = out_dir or _OUT
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "fundamentals_report.json"
    path.write_text(
        json.dumps(build_fundamentals_status(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def build_priority_fill_rows(limit: int = 20) -> list[dict]:
    status = build_fundamentals_status()
    fundamentals = load_fundamentals()
    rows: list[dict] = []

    for target in status["next_fill_targets"][:limit]:
        code = str(target["code"])
        existing = fundamentals.get(code, {})
        row = {
            "code": code,
            "name": target["name"],
            "priority_reason": target["priority_reason"],
            "missing_count": target["missing_count"],
            "missing_fields": ",".join(target["missing_fields"]),
            "missing_field_labels": "、".join(target["missing_field_labels"]),
            "fill_format_note": FILL_FORMAT_NOTE,
            "example_values": "; ".join(
                f"{field}={FIELD_EXAMPLE_VALUES[field]}"
                for field in REQUIRED_FIELDS
            ),
        }
        for field in REQUIRED_FIELDS:
            value = existing.get(field)
            row[field] = "" if value is None else value
        rows.append(row)

    return rows


def build_priority_import_template_rows(limit: int = 20) -> list[dict]:
    """產生外部基本面資料整理模板，不填任何實際數字。"""
    status = build_fundamentals_status()
    rows: list[dict] = []
    note = "外部資料填入後，先 dry-run 匯入 priority CSV；百分比請填 28.5，不要填 0.285。"

    for target in status["next_fill_targets"][:limit]:
        row = {
            "code": str(target["code"]),
            "name": target["name"],
            "source_note": note,
        }
        for field in REQUIRED_FIELDS:
            row[field] = ""
        rows.append(row)

    return rows


def _load_existing_priority_fill_raw_values(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    values: dict[str, dict[str, str]] = {}
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = str(row.get("code") or "").strip()
                if not code:
                    continue
                values[code] = {
                    field: str(row.get(field) or "").strip()
                    for field in REQUIRED_FIELDS
                    if str(row.get(field) or "").strip() != ""
                }
    except OSError:
        return {}
    return values


def _normalize_import_header(value: str) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("％", "%")
    )


def _map_import_headers(fieldnames: list[str] | None) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for header in fieldnames or []:
        raw = str(header or "").strip()
        if not raw:
            continue
        normalized = _normalize_import_header(raw)
        target = IMPORT_FIELD_ALIASES.get(normalized)
        if target is None and raw in REQUIRED_FIELDS:
            target = raw
        if target is None:
            for field, label in FIELD_LABELS.items():
                if normalized == _normalize_import_header(label):
                    target = field
                    break
        if target:
            mapped[raw] = target
    return mapped


def _write_priority_rows(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_priority_import_template_csv(
    out_dir: Path | None = None,
    limit: int = 20,
) -> Path:
    """寫出給外部資料整理用的空白 CSV 模板。"""
    target_dir = out_dir or _OUT
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "fundamentals_priority_import_template.csv"
    fieldnames = ["code", "name", "source_note", *REQUIRED_FIELDS]
    rows = build_priority_import_template_rows(limit=limit)
    _write_priority_rows(path, fieldnames, rows)
    return path


def prepare_priority_fundamentals_import(
    source_csv_path: Path,
    dry_run: bool = True,
) -> dict:
    """把外部整理好的基本面 CSV 正規化填入 priority CSV。

    此步驟只更新 `fundamentals_priority_fill.csv` 的 11 個基本面欄位。
    不會合併到正式 `fundamentals.csv`，也不會更新 `fundamentals.json`。
    """
    source_csv_path = Path(source_csv_path)
    if not source_csv_path.exists():
        raise ValueError(f"找不到匯入 CSV: {source_csv_path}")
    if not _PRIORITY_CSV_PATH.exists():
        write_priority_fill_csv(_OUT)

    with _PRIORITY_CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        priority_reader = csv.DictReader(f)
        fieldnames = list(priority_reader.fieldnames or [])
        rows = [dict(row) for row in priority_reader]

    missing_required_columns = [field for field in REQUIRED_FIELDS if field not in fieldnames]
    if "code" not in fieldnames or missing_required_columns:
        raise ValueError(
            "priority CSV 缺少必要欄位: "
            + ", ".join(["code", *missing_required_columns])
        )

    row_by_code = {
        str(row.get("code") or "").strip(): row
        for row in rows
        if str(row.get("code") or "").strip()
    }
    updated_codes: list[str] = []
    skipped_codes: list[str] = []
    updated_field_count = 0
    source_row_count = 0

    with source_csv_path.open(encoding="utf-8-sig", newline="") as f:
        source_reader = csv.DictReader(f)
        header_map = _map_import_headers(source_reader.fieldnames)
        code_headers = [header for header, target in header_map.items() if target == "code"]
        if not code_headers:
            raise ValueError("匯入 CSV 缺少 code / stock_id / 代號 欄位")
        code_header = code_headers[0]

        for raw_row in source_reader:
            source_row_count += 1
            code = str(raw_row.get(code_header) or "").strip()
            if not code:
                continue
            target_row = row_by_code.get(code)
            if target_row is None:
                if code not in skipped_codes:
                    skipped_codes.append(code)
                continue

            row_updated = False
            for header, target_field in header_map.items():
                if target_field == "code" or target_field not in REQUIRED_FIELDS:
                    continue
                raw_value = str(raw_row.get(header) or "").strip()
                if raw_value == "":
                    continue
                if str(target_row.get(target_field) or "").strip() != raw_value:
                    target_row[target_field] = raw_value
                    updated_field_count += 1
                    row_updated = True

            if row_updated and code not in updated_codes:
                updated_codes.append(code)

    if dry_run:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            _write_priority_rows(tmp_path, fieldnames, rows)
            validation = validate_priority_csv(tmp_path)
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass
    else:
        _write_priority_rows(_PRIORITY_CSV_PATH, fieldnames, rows)
        validation = validate_priority_csv(_PRIORITY_CSV_PATH)

    return {
        "dry_run": dry_run,
        "source_csv_path": str(source_csv_path),
        "priority_csv_path": str(_PRIORITY_CSV_PATH),
        "source_row_count": source_row_count,
        "updated_code_count": len(updated_codes),
        "updated_codes": updated_codes,
        "updated_field_count": updated_field_count,
        "skipped_code_count": len(skipped_codes),
        "skipped_codes": skipped_codes,
        "validation": validation,
        "next_action_label": (
            "檢查 priority CSV 驗證結果，若有完整 11 欄即可預覽合併"
            if not dry_run
            else "確認 dry-run 更新清單後，用 --apply 寫入 priority CSV"
        ),
    }


def write_priority_fill_csv(
    out_dir: Path | None = None,
    limit: int = 20,
) -> Path:
    target_dir = out_dir or _OUT
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "fundamentals_priority_fill.csv"
    fieldnames = [
        "code",
        "name",
        "priority_reason",
        "missing_count",
        "missing_fields",
        "missing_field_labels",
        "fill_format_note",
        "example_values",
        *REQUIRED_FIELDS,
    ]
    rows = build_priority_fill_rows(limit=limit)
    existing_values = _load_existing_priority_fill_raw_values(path)
    for row in rows:
        code = str(row.get("code") or "")
        existing = existing_values.get(code) or {}
        for field in REQUIRED_FIELDS:
            if row.get(field) in ("", None) and existing.get(field):
                row[field] = existing[field]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def get_priority_fill_csv_path(limit: int = 20) -> Path:
    """產生並回傳基本面優先補資料 CSV 路徑。"""
    return write_priority_fill_csv(_OUT, limit=limit)


def merge_priority_fill_csv(
    dry_run: bool = True,
    confirm: str | None = None,
) -> dict:
    """將優先補資料 CSV 合併回 fundamentals.csv，正式合併後同步匯入 JSON。"""
    if not _PRIORITY_CSV_PATH.exists():
        write_priority_fill_csv(_OUT)

    if not dry_run and confirm != _MERGE_CONFIRM:
        raise ValueError(f"正式合併必須提供 confirm={_MERGE_CONFIRM}")

    result = merge_priority_csv_into_fundamentals(
        _PRIORITY_CSV_PATH,
        fundamentals_path=_FUNDAMENTALS_CSV_PATH,
        dry_run=dry_run,
    )
    validation = result["validation"]
    readiness = _priority_fill_readiness(validation)
    merge_allowed = bool(readiness.get("can_merge"))
    blocked_reason = None if merge_allowed else readiness.get("suggested_action") or readiness.get("message")
    next_action_label = (
        "可合併，合併後重新產生訊號"
        if merge_allowed
        else "補齊 11 欄後再預覽"
    )

    response = {
        "dry_run": bool(result["dry_run"]),
        "updated_code_count": int(result["updated_code_count"]),
        "updated_codes": result["updated_codes"],
        "updated_field_count": int(result["updated_field_count"]),
        "added_count": int(result["added_count"]),
        "added_codes": result["added_codes"],
        "csv_path": result["path"],
        "source": result["source"],
        "json_path": None,
        "imported_count": None,
        "validation": result["validation"],
        "merge_allowed": merge_allowed,
        "blocked_reason": blocked_reason,
        "complete_codes": validation.get("complete_codes") or [],
        "partial_codes": validation.get("partial_codes") or [],
        "empty_codes": validation.get("empty_codes") or [],
        "row_statuses": validation.get("row_statuses") or [],
        "warning_count": len(validation.get("warnings") or []),
        "warnings": validation.get("warnings") or [],
        "fundamental_preview": _fundamental_preview_from_priority_csv(validation),
        "signals_refresh_required": False,
        "next_action_label": next_action_label,
    }

    if dry_run:
        return response

    if not merge_allowed:
        raise ValueError(str(blocked_reason or "補資料 CSV 尚未達到合併條件。"))

    fundamentals_validation = validate_fundamentals_csv(_FUNDAMENTALS_CSV_PATH)
    if not fundamentals_validation["valid"]:
        raise ValueError(format_csv_validation_error(fundamentals_validation, label="fundamentals.csv"))

    data = load_fundamentals_from_csv(_FUNDAMENTALS_CSV_PATH)
    save_fundamentals(data, path=_FUNDAMENTALS_JSON_PATH)
    response["json_path"] = str(_FUNDAMENTALS_JSON_PATH)
    response["imported_count"] = len(data)
    response["signals_refresh_required"] = True
    response["next_action_label"] = "重新產生訊號"
    return response
