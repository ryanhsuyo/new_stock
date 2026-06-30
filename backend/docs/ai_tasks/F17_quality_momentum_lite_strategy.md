# F17 Quality Momentum Lite Strategy

Status: complete

## Goal

Constrain the second recommendation strategy so it can find good stocks without requiring paid data, heavy financial-statement ingestion, or all 11 advanced fundamentals fields.

## Decision

`steady_momentum` remains the API bucket and strategy id, but its product meaning is now Quality Momentum Lite:

* Price trend, relative strength, entry location, risk/reward, and heat control remain the core.
* Fundamentals are a lightweight guardrail, not a value-investing database.
* Missing advanced fundamentals should not block the second strategy.

## Lite Guard Fields

The formal 11-field CSV format stays for backward compatibility and advanced future work.

The strategy guard only requires low-cost fields:

* `pe`
* `operating_margin_5y_avg`
* `debt_to_equity`
* `revenue_growth_5y_cagr`
* `eps_growth_5y_cagr`

ROE, FCF, interest coverage, FCF yield, cash conversion, and dividend years remain optional advanced references.

## Completed

* Updated `fundamental_guard_service` to `fundamental_guard_v2`.
* Reduced the guard scoring gate from 3 legacy groups to any available lite guard field.
* Changed completeness and missing-field reporting to use lite guard fields.
* Kept the public `steady_momentum_v1` id stable, but updated the display name / docs to Quality Momentum Lite.
* Updated fundamentals workflow wording so partial official PE data is described as usable for lite guard while formal 11-field merge remains protected.
* Added regression tests for PE-only scoring and two-group lite scoring.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamental_guard.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamental_service.py backend/tests/test_fundamentals_cli.py backend/tests/test_fundamental_guard.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_api.py backend/tests/test_daily_check.py backend/tests/test_pm_worklist.py backend/tests/test_workflow_status.py backend/tests/test_rules_metadata_service.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 backend/scripts/check_fundamentals.py`

## Remaining Risk

This phase changes strategy interpretation but does not yet auto-derive the remaining lite guard fields from official report-only CSVs. PE is already auto-fillable; operating margin, debt-to-equity, revenue growth, and EPS growth still need separate apply phases before the workflow becomes mostly hands-off.
