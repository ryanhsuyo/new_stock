# AI Loop State

Purpose:

Track automatic phase continuation without making `ai_execution_plan.md` too long.

Rules:

* Keep this file under 200 lines.
* Update this file whenever a phase completes or a new phase becomes active.
* Do not store long reports here; keep only execution state.

## Current State

Active phase: none

Loop mode: waiting_for_next_safe_phase

Last completed phase:

* `F48_signal_alert_block_first_preview.md` — Daily Check signal alert previews now sort block alerts first and include backend-owned action labels.

Current phase status:

* F44 completed: if Daily Check reports partial stale tracked stocks, Update Workflow returns `action_required` with a safe daily update action instead of `ready`.
* F45 completed: `signal_alerts.json.alerts[*]` now includes `action_label`, `next_action`, and `review_focus`.
* F46 completed: backfill now retries first-pass skipped OHLCV codes during the same daily update run; `daily_update.py --months 1` verified 2408 / 2412 / 2882 / 2330 at `2026-07-03` with skip count 0.
* F47 completed: full backend tests no longer pollute `backend/out/signal_alerts.json`; after `775 passed`, summary / snapshot review / alerts all remained `2026-07-03`.
* F48 completed: Daily Check `signal_alerts` top action now exposes severity counts and block-first preview items with action labels.
* Use `backend/docs/ai_tasks/F21_heartbeat_development_operating_contract.md` to select the next low-risk productization slice.

## Completed Phase History Summary

Large historical phase detail is intentionally summarized here. Use phase files and git history for exact implementation details.

* Homepage / Dashboard / PM-facing UI phases H2.5 through H8.3 are complete.
* Reliability, storage, backup, schedule, signal, snapshot, and rules metadata phases S / M / L / R are complete.
* Fundamentals priority import phases R9.0 through R9.2 are complete.
* Daily Check / Today Scan observability phase D1.0 is complete.
* Official fundamentals and Quality Momentum Lite phases F1 through F20 are complete.
* Heartbeat/product-health phases F21 through F45 are complete.

Recent completed phases:

* F21 — Added heartbeat operating contract, safe backlog order, slice limits, and notify policy.
* F22 — Promoted partial stale universe rows into a Daily Check data freshness action.
* F23 — Mapped Daily Check data freshness into PM Worklist.
* F24 — Grouped PM Worklist data freshness with Dashboard data repair / blocker work.
* F25 — Surfaced PM Worklist data freshness primary action in Today Focus.
* F26 — Archived long loop-state verification history and compacted this state file.
* F27 — Added Today Scan strategy score summaries for first/second strategy scanability.
* F28 — Displayed Today Scan strategy score summaries in text CLI output.
* F29 — Added read-only Today Scan system API endpoint.
* F30 — Added frontend Today Scan API client/types contract.
* F31 — Displayed backend-owned Today Scan summary in Dashboard Decision Console.
* F32 — Displayed backend-owned Today Scan freshness warning in Dashboard Decision Console.
* F33 — Added stable `action_type` values to Daily Check top actions.
* F34 — Fixed PM Worklist data freshness metric to use Daily Check details counts instead of preview length.
* F35 — Preserved Daily Check-provided action types in PM Worklist generic items.
* F36 — Promoted generic Daily Check block actions above warning maintenance actions in PM Worklist.
* F37 — Made Daily Check trade output usability consistent with report and extra-action blockers.
* F38 — Converted Update Workflow Daily Check file blockers into safe executable copy commands.
* F39 — Preserved Update Workflow action payload context in PM Worklist primary actions.
* F40 — Rendered backend-owned Primary Action payload context on the Dashboard first screen.
* F41 — Added safe copy command and expected outputs to Daily Check signal alert file actions.
* F42 — Added Daily Check awareness for stale manual market notes.
* F43 — Staged umbrella: harden decision trust around missing fundamentals, stale chips, snapshot wording, block recovery, schedule visibility, and stale docs.
* F43.1 — Completed: missing fundamentals are explicit neutral fallback in Quality Momentum Lite reason text.
* F43.2 — Completed: Old Wang chip reasons include chip date / stale wording when chip numbers are quoted.
* F43.3 — Completed: signal alert wording matches `previous_as_of` -> `as_of` comparison windows.
* F43.4 — Completed: Update Workflow exposes schedule health and block alert inspection remains actionable.
* F43.5 — Completed: cleaned stale collaboration docs without weakening strategy guardrails.
* F44 — Completed: Update Workflow surfaces Daily Check partial data freshness warnings as action-required health status.
* F45 — Completed: Signal alerts include outcome-specific action hints for PM review.
* F46 — Completed: OHLCV backfill retries first-pass skipped codes in the same run and verified no recoverable partial stale data remained.
* F47 — Completed: Prevented signal timeout tests from writing fixed-date signal snapshot / alert outputs to product `backend/out`.
* F48 — Completed: Daily Check signal alert previews prioritize block items and show action labels.

## Next Phase Candidates

Use `F21_heartbeat_development_operating_contract.md` when no active phase exists. Current preferred backlog order:

* Product health and freshness.
* Daily use path noise reduction.
* Today Scan / Universe Report scanability and strategy score clarity.
* Two-strategy reliability checks.
* Official fundamentals observability and PE-only apply guardrails.
* Documentation consistency.

## Last Verification

Historical verification archive:

* `backend/docs/ai_tasks/archive/loop_state_verification_archive_2026-07-01.md`

Recent verification:

* F22 Daily Check tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* F23 PM Worklist tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`
* F23 Daily Check / PM Worklist integration tests passed.
* F24 frontend focused and structure tests passed.
* F25 PM Worklist and Daily Check integration tests passed.
* F26 docs sanity checks passed and confirmed `loop_state.md` is back under the 200-line limit.
* F27 Today Scan service tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_service.py -q`
* F28 Today Scan CLI tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_cli.py -q`
* F29 Today Scan API tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_api.py -q`
* F30 frontend Today Scan contract test passed: `node --test frontend/tests/today-scan-api-contract.test.mjs`
* F31 frontend structure tests passed: `node --test frontend/tests/*.test.mjs`
* F32 frontend focused/all structure tests and build passed: `node --test frontend/tests/today-scan-dashboard.test.mjs`, `node --test frontend/tests/*.test.mjs`, `npm run build`
* F33 Daily Check tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* F34 PM Worklist and Daily Check tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`, `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* F35 PM Worklist and Daily Check tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`, `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* F36 PM Worklist and Daily Check tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`, `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* F37 Daily Check, PM Worklist, and Update Workflow tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`, `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`, `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_workflow.py -q`
* F38 Update Workflow, PM Worklist, and Daily Check tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_workflow.py -q`, `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`, `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* F39 PM Worklist and Update Workflow tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`, `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_workflow.py -q`
* F40 frontend focused/all structure tests and build passed: `node --test frontend/tests/primary-action-card-payload.test.mjs`, `node --test frontend/tests/*.test.mjs`, `npm run build`
* F41 Daily Check, PM Worklist, and Update Workflow tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`, `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`, `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_workflow.py -q`
* F42 Daily Check, PM Worklist, and Update Workflow tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`, `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`, `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_workflow.py -q`
* F46 focused tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_backfill_tpex.py backend/tests/test_backfill_market_indices.py backend/tests/test_daily_check.py backend/tests/test_update_workflow.py -q`
* F46 full backend tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests -q` (`775 passed`)
* F47 focused tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_signal_timeout.py backend/tests/test_signals_api.py::TestSignalsOutput::test_signal_snapshot_outputs_are_written -q`
* F47 full backend tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests -q` (`775 passed`)
* F48 Daily Check tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* F48 full backend tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests -q` (`776 passed`)

## Last Stop Reason

F48 completed. Continue proactively by selecting the next safe small productization phase from the F21 operating contract when no active phase exists.
