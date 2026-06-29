# F9 Official Balance Sheet Report Probe

Status: completed

## Goal

Build the next small report-only probe for official balance sheet sources.

Use only confirmed official OpenAPI endpoints:

* TWSE listed balance sheet: `/opendata/t187ap07_L_*`
* TPEx OTC balance sheet: `/mopsfin_t187ap07_O_*`

Hard rules:

* Report-only output only.
* Do not write `fundamentals.csv`, `fundamentals.json`, or priority CSV.
* Do not fill `debt_to_equity`, `roe_5y_avg`, or any derived field yet.
* Do not fabricate missing industry variants, years, or OTC/listed data.
* Keep fundamentals as `steady_momentum` support data, not a third strategy.

## Tasks

1. Source shape decision
   - Status: completed
   - Pick the smallest official balance sheet variant to support first and document why.

2. Service/parser test
   - Status: completed
   - Add fixed fixture tests for selected TWSE/TPEx balance sheet row normalization.

3. Service implementation
   - Status: completed
   - Normalize code, name, year, quarter, total assets, liabilities, equity, source, and skip reason when official fields are present.

4. CLI/API report-only path
   - Status: completed
   - Add a neutral CSV output only if field names are stable enough.

5. Verification
   - Status: completed
   - Run focused backend tests.

## Source Shape Decision

Use the general-industry variants first:

* TWSE `/opendata/t187ap07_L_ci`
* TPEx `/mopsfin_t187ap07_O_ci`

Reason:

* They cover the common non-financial statement shape.
* Both live official endpoints return stable JSON arrays.
* The required neutral fields are present with clear names:
  - TWSE: `公司代號`, `公司名稱`, `資產總額`, `負債總額`, `權益總額`
  - TPEx: `SecuritiesCompanyCode`, `CompanyName`, `資產總計`, `負債總計`, `權益總計`

Do not include financial, insurance, securities/futures, holding-company, or mixed-industry variants until each variant has fixture tests.

## Implementation Notes

* Added `official_fundamentals_balance_sheet.csv` as a neutral report-only output.
* Added CLI flags:
  - `--write-balance-sheet-report`
  - `--twse-balance-sheet-fixture`
  - `--tpex-balance-sheet-fixture`
* Added the balance sheet report to `POST /api/system/fundamentals-official/reports` defaults.
* This does not write `fundamentals.csv`, `fundamentals.json`, priority CSV, `debt_to_equity`, or `roe_5y_avg`.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py::test_build_official_balance_sheet_report_rows_normalizes_general_industry_rows -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_cli.py::test_update_fundamentals_official_writes_balance_sheet_report_from_fixtures -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_api.py::test_run_official_fundamentals_reports_endpoint_defaults_to_report_only backend/tests/test_official_fundamentals_api.py::test_run_official_fundamentals_reports_writes_balance_sheet_csv -q`

## Acceptance

* A generated neutral CSV can show listed + OTC balance sheet reference rows.
* Missing or malformed values produce skip reasons.
* No strategy score or required fundamentals field is modified.
