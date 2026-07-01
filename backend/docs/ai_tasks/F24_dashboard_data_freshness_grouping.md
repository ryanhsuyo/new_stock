# F24 Dashboard Data Freshness Grouping

Status: completed

Purpose:

Make Dashboard group PM Worklist `data_freshness` items with data repair / blockers instead of generic maintenance.

## Context

F22 added Daily Check `data_freshness` actions. F23 maps those actions into PM Worklist with `action_type="data_freshness"`. The frontend grouping still only recognizes `data_repair`, so data freshness can fall into the generic maintenance group.

## Scope

* Treat `action_type="data_freshness"` like data repair in PM Worklist grouping.
* Keep command payload behavior unchanged: copy command remains the direct action.
* Add a structure test to protect the grouping contract.

## Guardrails

* Do not change backend strategy output.
* Do not trigger data updates from the frontend.
* Do not change trades, holdings, cash, or personal records.

## Acceptance

* Frontend structure test covers `data_freshness` grouping.
* Relevant frontend node tests pass.
* Phase docs and loop state are updated.

## Verification

* `node --test frontend/tests/pm-worklist-data-freshness.test.mjs` passed.
* `node --test frontend/tests/*.test.mjs` passed, 17 tests.
