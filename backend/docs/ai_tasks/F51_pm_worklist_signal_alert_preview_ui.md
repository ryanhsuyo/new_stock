# F51 PM Worklist Signal Alert Preview UI

Status: completed

Purpose:

Use the F50 backend `signal_alerts.preview_alerts` contract in the PM Worklist so the primary blocker card shows the concrete stocks and review actions without parsing text or recomputing alert logic in the frontend.

## Scope

Allowed:

* Add frontend types for backend-provided `preview_alerts`.
* Render `preview_alerts` in the PM Worklist primary and secondary action cards when present.
* Keep `preview_items` and `focus_codes` fallback behavior.
* Add frontend structure tests.

Not allowed:

* Do not sort, filter, or recompute alert severity in frontend.
* Do not change strategy scoring, recommendation buckets, or Daily Check blocker logic.
* Do not modify trades, holdings, cash, or formal trading records.

## Tasks

1. Status: done — Add a failing frontend structure test for PM Worklist `preview_alerts`.
2. Status: done — Update frontend type contract and PM Worklist rendering.
3. Status: done — Run frontend structure tests.
4. Status: done — Complete phase docs, update loop state, and commit if verified.

## Verification

* RED: `node --test frontend/tests/pm-worklist-signal-alert-preview.test.mjs` failed because `preview_alerts` was not typed / rendered.
* GREEN: `node --test frontend/tests/pm-worklist-signal-alert-preview.test.mjs` passed.
* Frontend structure: `node --test frontend/tests/*.test.mjs` passed (`21 passed`).
* Build: `npm run build` passed from `frontend/`; Vite reported the existing chunk-size warning only.

## Acceptance

* `PmWorklistItem.action_payload.preview_alerts` is typed.
* PM Worklist renders backend-provided `preview_alerts` before falling back to `preview_items` / `focus_codes`.
* Frontend does not sort or recompute signal-alert severity.
* Focused frontend tests pass.
