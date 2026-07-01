# F40 Primary Action Payload Preview

## Goal

Make the Dashboard first-screen Primary Action card show backend-owned payload context such as file paths, preview items, and expected outputs.

## Scope

Allowed:

* Render `primaryAction.action_payload.file_path`.
* Render the first few `preview_items` and `expected_outputs`.
* Add lightweight frontend structure tests.
* Update docs and loop state.

Not allowed:

* Recompute PM priority or action grouping in the frontend.
* Change backend strategy, scoring, recommendation buckets, trades, holdings, cash, or formal records.

## Checklist

* [x] Add failing frontend structure test for Primary Action payload preview.
* [x] Render backend-owned file / preview / expected output context in `PrimaryActionCard`.
* [x] Run focused/all frontend structure tests and build.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [ ] Commit the completed slice.

## Verification

* `node --test frontend/tests/primary-action-card-payload.test.mjs`
* `node --test frontend/tests/*.test.mjs`
* `npm run build`
* `git diff --check`

## Result

Completed. Dashboard first-screen Primary Action now renders backend-owned `file_path`, `preview_items`, and `expected_outputs` context without recomputing PM priority or action grouping in the frontend.
