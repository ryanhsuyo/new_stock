# F27 Today Scan Strategy Score Summary

## Goal

Make Today Scan rows easier to read by exposing a backend-provided two-strategy score summary.

## Scope

Allowed:

* Add a compact derived summary to each Today Scan item using existing `old_wang_score` and `steady_momentum_score`.
* Keep `old_wang` as "第一 老王" and `steady_momentum` as "第二 穩健".
* Add focused backend tests and update state docs.

Not allowed:

* Recalculate strategies.
* Add a third recommendation strategy.
* Apply blocked fundamentals fields.
* Modify trades, holdings, cash, or formal trading records.

## Design

Each compact Today Scan item should include `strategy_score_summary`:

* `primary_strategy`: `old_wang`, `steady_momentum`, or `none`.
* `primary_label`: user-facing label such as `第一 老王` or `第二 穩健`.
* `primary_score`: the stronger product-strategy score.
* `old_wang_level` / `steady_momentum_level`: `high`, `mid`, or `low`.
* `score_gap`: absolute difference between the two strategy scores.
* `summary_label`: short PM-facing text that says which strategy is stronger.

## Checklist

* [x] Add failing Today Scan service test.
* [x] Implement the minimal derived summary in `today_scan_service`.
* [x] Run focused Today Scan tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [x] Commit the completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_service.py -q`
* `git diff --check`

## Result

Completed. Today Scan compact items now expose `strategy_score_summary`, allowing downstream UI / PM views to display which of the two product strategies is stronger without recalculating strategy logic.
