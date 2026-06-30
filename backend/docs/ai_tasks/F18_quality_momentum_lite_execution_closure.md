# F18 Quality Momentum Lite Execution Closure

Status: done

## Goal

Make both recommendation strategies operational end-to-end while keeping the second strategy low-cost:

* `old_wang` runs from OHLCV / market / chip-compatible context.
* `steady_momentum_v1` remains the API bucket but is interpreted as Quality Momentum Lite.
* Quality Momentum Lite can execute without all 11 advanced fundamentals fields.
* Heartbeat work should focus on small, testable pieces that improve lite guard data coverage.

## Guardrails

* Keep recommendation buckets limited to `old_wang` and `steady_momentum`.
* Do not add a third strategy.
* Do not require paid APIs.
* Do not fake ROE, FCF, interest coverage, dividend streak, or 5-year CAGR values.
* Do not write formal `fundamentals.csv` / `fundamentals.json` from partial report-only data.
* Router stays thin; calculations belong in services.

## Current Evidence

* `run_signals.py` completed on 2026-06-30T14:09:12.
* Output buckets were `old_wang=5`, `steady_momentum=17`.
* `strategy_catalog` contains only `old_wang_market_chip_rotation` and `steady_momentum_v1`.
* Quality Momentum Lite currently uses neutral fundamentals guard when formal lite fields are missing.
* Focused strategy/output tests passed: 75 tests.
* Read-only Quality Momentum Lite guard coverage summary exists in service code; it counts PE as the only direct apply field and keeps operating margin, debt inputs, revenue growth reference, and EPS reference as report-only / derived-input references.
* `GET /api/system/fundamentals-official/quality-momentum-lite-guard` exposes the read-only guard coverage summary without generating reports or writing formal fundamentals.
* Task 6 decision: PE remains the only safe direct apply path. No additional formal lite guard field should be applied from report-only CSVs yet, because operating margin, debt inputs, revenue growth reference, and EPS reference would otherwise imply 5-year averages, CAGR, or derived ratios that are not validated from a full historical series.

## Apply Path Decision

Decision: keep the first safe apply path as PE-only.

Rationale:

* TWSE BWIBBU and TPEx daily PE provide a direct official PE value that maps cleanly to the existing `pe` field.
* Profitability reports provide current-period margins, not a validated `operating_margin_5y_avg`.
* Balance sheet reports provide raw liabilities / equity inputs, not a validated formal `debt_to_equity` series.
* Monthly revenue reports provide YoY / cumulative YoY references, not a 5-year `revenue_growth_5y_cagr`.
* Income statement reports provide current-period EPS, not a 5-year `eps_growth_5y_cagr`.

Allowed next improvement:

* Add new explicitly named report-derived reference fields only if the codebase first defines separate fields such as `official_latest_operating_margin_reference` or `official_monthly_revenue_yoy_reference`.
* Do not map report-only values into existing `*_5y_avg`, `*_5y_cagr`, or derived ratio fields.

## Tasks

1. Status: done — Verify `run_signals.py` produces `summary.json`, `universe_report.csv`, `today_scan.json`, and `daily_check.json`.
2. Status: done — Verify recommendation buckets contain only `old_wang` and `steady_momentum`.
3. Status: done — Update public strategy wording to Quality Momentum Lite while preserving `steady_momentum_v1`.
4. Status: done — Build a read-only service that summarizes lite guard coverage from official report-only CSVs for priority / recommended stocks.
5. Status: done — Add CLI/API visibility for lite guard coverage without writing formal fundamentals.
6. Status: done — Decide the first safe apply path for a lite guard field that is not misleading, likely PE only or a new report-derived guard field, not `*_5y_avg` unless a true 5-year series exists.
7. Status: done — Run focused tests and `run_signals.py` after each completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 backend/scripts/run_signals.py`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_signals_api.py::TestSignalsOutput backend/tests/test_today_scan_service.py backend/tests/test_today_scan_cli.py backend/tests/test_rules_metadata_service.py backend/tests/test_fundamental_guard.py backend/tests/test_fundamental_service.py backend/tests/test_fundamentals_cli.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_api.py backend/tests/test_official_fundamentals_service.py -q`

## Stop Conditions

Stop and report instead of implementing if:

* A task would require paid data.
* A task would require deriving 5-year values from a single report row.
* A task would require changing trades, holdings, cash, or formal personal records.
* Official source fields are ambiguous across industry variants.

## Suggested Next Heartbeat

F18 is closed. Start a new phase only if there is a concrete next product or data task.
