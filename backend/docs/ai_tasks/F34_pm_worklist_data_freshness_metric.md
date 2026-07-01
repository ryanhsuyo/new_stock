# F34 PM Worklist Data Freshness Metric

## Goal

Make PM Worklist data freshness metrics use the backend-owned Daily Check counts instead of the truncated preview list length.

## Scope

Allowed:

* Read `daily_check.json.top_actions[*].details.stale_count` and `missing_date_count`.
* Keep preview items for focus codes and user-readable examples.
* Add focused PM Worklist tests.
* Update docs and loop state.

Not allowed:

* Recompute freshness in PM Worklist.
* Change Daily Check, Today Scan, strategy scoring, or recommendation buckets.
* Modify trades, holdings, cash, or formal trading records.

## Checklist

* [x] Add failing PM Worklist test for stale count larger than preview count.
* [x] Use Daily Check details count for the PM Worklist metric.
* [x] Run focused PM Worklist tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [x] Commit the completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`
* `git diff --check`

## Result

Completed. PM Worklist data freshness now uses Daily Check details counts instead of truncated preview length.
