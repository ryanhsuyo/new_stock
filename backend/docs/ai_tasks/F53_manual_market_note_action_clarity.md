# F53 Manual Market Note Action Clarity

Status: completed

Purpose:

Make the stale manual market note warning actionable by providing a backend-owned checklist and example request shape for `POST /api/stocks/market-notes`.

## Scope

Allowed:

* Add required field guidance, writing checklist, and example payload skeleton to the existing Daily Check `manual_market_note` action payload.
* Keep the action as guidance only.
* Add focused backend tests and refresh `backend/out/daily_check.json` via the script.

Not allowed:

* Do not invent market opinion or content.
* Do not save a market note.
* Do not modify trades, holdings, cash, or formal personal records.
* Do not change signal, strategy, or blocker rules.

## Tasks

1. Status: done — Add a failing Daily Check test for manual market note action guidance.
2. Status: done — Implement the minimal backend guidance payload.
3. Status: done — Run focused Daily Check / PM Worklist tests and refresh output.
4. Status: done — Complete phase docs, update loop state, and commit.

## Verification

* RED: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py::test_daily_check_surfaces_stale_manual_market_note -q` failed with `KeyError: 'required_fields'`.
* GREEN: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py::test_daily_check_surfaces_stale_manual_market_note -q` passed.
* Focused integration: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py backend/tests/test_pm_worklist.py -q` passed (`40 passed`).
* Output refresh: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 scripts/daily_check.py --write-report` wrote `backend/out/daily_check.json`; exit code `1` reflects expected WARN/BLOCK daily status.

## Acceptance

* `manual_market_note.action_payload.required_fields` is present.
* `example_payload` contains an empty/safe request shape without invented market judgment.
* `writing_checklist` tells the user what to fill.
* Existing API payload fields remain backward compatible.
