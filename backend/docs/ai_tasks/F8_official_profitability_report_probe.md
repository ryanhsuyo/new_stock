# F8 Official Profitability Report Probe

Status: completed

## Goal

Build a minimal report-only probe for official profitability summary sources.

Use only confirmed official OpenAPI endpoints:

* TWSE listed profitability summary: `/opendata/t187ap17_L`
* TPEx OTC profitability summary: `/mopsfin_187ap17_O`

Hard rules:

* Report-only output only.
* Do not write `fundamentals.csv`, `fundamentals.json`, or priority CSV.
* Do not fill `operating_margin_5y_avg` yet.
* Do not fabricate missing years or missing OTC/listed data.
* Keep fundamentals as `steady_momentum` support data, not a third strategy.

## Tasks

1. Service/parser test
   - Status: completed
   - Add fixed fixture tests for TWSE/TPEx profitability summary row normalization.

2. Service implementation
   - Status: completed
   - Normalize code, name, year, quarter, operating margin, pre-tax margin, after-tax margin, source, and skip reason.

3. CLI/report-only path
   - Status: completed
   - Add a report-only command/output CSV for official profitability summaries.

4. Docs/rules update
   - Status: completed
   - Document that this is a neutral report and not an apply path.

5. Verification
   - Status: completed
   - Run focused backend tests.

## Implementation Notes

* Added `official_fundamentals_profitability.csv` as a neutral report-only output.
* Added CLI flags:
  - `--write-profitability-report`
  - `--twse-profitability-fixture`
  - `--tpex-profitability-fixture`
* Added the profitability report to `POST /api/system/fundamentals-official/reports` defaults.
* This does not write `fundamentals.csv`, `fundamentals.json`, priority CSV, or `operating_margin_5y_avg`.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py::test_build_official_profitability_report_rows_normalizes_twse_and_tpex_rows -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_cli.py::test_update_fundamentals_official_writes_profitability_report_from_fixtures -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_api.py::test_run_official_fundamentals_reports_endpoint_defaults_to_report_only backend/tests/test_official_fundamentals_api.py::test_run_official_fundamentals_reports_writes_profitability_csv -q`

## Acceptance

* A generated neutral CSV can show listed + OTC profitability summary rows.
* Missing or malformed values produce skip reasons.
* No strategy score or required fundamentals field is modified.
