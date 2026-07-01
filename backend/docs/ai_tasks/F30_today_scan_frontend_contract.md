# F30 Today Scan Frontend Contract

## Goal

Make the frontend able to consume the read-only Today Scan API from F29 without recreating strategy logic.

## Scope

Allowed:

* Add frontend `TodayScanReport` / item / strategy summary types.
* Add `api.getTodayScanOrNull()` pointing to `/system/today-scan`.
* Add focused frontend structure tests.
* Update docs and loop state.

Not allowed:

* Add or redesign UI in this slice.
* Recalculate strategy scores in frontend.
* Add strategy buckets.
* Modify trades, holdings, cash, or formal trading records.

## Checklist

* [x] Add failing frontend contract test.
* [x] Add minimal types and API client method.
* [x] Run focused frontend tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [ ] Commit the completed slice.

## Verification

* `node --test frontend/tests/today-scan-api-contract.test.mjs`
* `git diff --check`

## Result

Completed. The frontend now has a typed read-only API client contract for Today Scan, without adding UI or duplicating backend strategy logic.
