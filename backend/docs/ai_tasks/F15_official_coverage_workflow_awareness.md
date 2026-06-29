# F15 Official Coverage Workflow Awareness

Status: complete

## Goal

Surface official fundamentals coverage audit status in Daily Check / PM Worklist so the daily workflow knows whether report-only official data is usable.

Hard rules:

* Do not generate official reports from Daily Check / PM Worklist.
* Do not write `fundamentals.csv`, `fundamentals.json`, priority CSV, trades, holdings, or cash.
* Do not fill `dividend_years`, growth CAGR, ROE, FCF, or any derived formal field.
* Do not turn fundamentals into a third strategy.
* Daily Check / PM Worklist should only summarize backend service output.

## Tasks

1. Backend workflow contract test
   - Status: done
   - Add focused tests that official coverage audit status appears as an informational action or detail when available.

2. Service integration
   - Status: done
   - Reuse official coverage audit service and gracefully handle missing priority CSV / missing reports.

3. Documentation
   - Status: done
   - Update current rules / phase state with the workflow behavior.

4. Verification
   - Status: done
   - Run focused Daily Check / PM Worklist tests.

## Acceptance

* Daily Check / PM Worklist can explain official report-only coverage status.
* Missing priority CSV or report-only CSVs produce clear guidance.
* No official data is generated and no formal fundamentals fields are modified.

## Result

* `daily_check.py --write-report` now adds an official coverage top action when report-only coverage is missing, low, or unreadable.
* PM Worklist keeps consuming Daily Check actions; if the Daily Check snapshot is missing/stale, it can read the coverage audit directly and show a safe status item.
* All actions use `GET /api/system/fundamentals-official/coverage-audit` only; no report generation, priority merge, or formal fundamentals write is triggered.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py backend/tests/test_pm_worklist.py -q` passed, 31 tests.
