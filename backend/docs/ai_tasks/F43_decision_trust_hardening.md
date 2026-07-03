# F43 Decision Trust Hardening

## Goal

Turn the 2026-07-02 Fable codebase / product audit into small, verifiable fixes that improve daily decision trust before adding more features.

The priority is not to redesign strategies. The priority is to make existing outputs honest about missing data, stale data, and comparison windows.

## Source Audit

Fable audit summary received on 2026-07-02:

* Backend tests reportedly passed: 768 tests.
* Two-strategy constraint looked healthy: `old_wang` and `steady_momentum` / Quality Momentum Lite only.
* Main trust risks:
  * Missing fundamentals can still appear as `基本面避雷6/10`.
  * Old Wang chip reasons may quote stale chip numbers without a visible `data_as_of`.
  * Signal alert wording may imply a one-day change even when snapshots span multiple trading days.
  * Block alerts need a clearer inspection / recovery path.
  * Local scheduling / data freshness may be invisible when no real schedule is installed.
  * `AGENTS.md` / `CLAUDE.md` may still contain stale output or frontend guidance.

Before implementing each item, verify against the current code and generated files. Do not blindly apply audit findings if current state differs.

## Scope

Allowed:

* Backend service / script changes that make existing outputs more truthful.
* Focused tests for changed behavior.
* Docs updates in `backend/docs/**`, `AGENTS.md`, or `CLAUDE.md` if they remove stale guidance.
* Minimal frontend display changes only if needed to consume backend-owned fields.

Not allowed:

* Add a third strategy.
* Change formal strategy rules without updating `current_rules.md` and tests.
* Fabricate fundamentals, chip data, or schedule state.
* Modify trades, holdings, cash, or formal personal records.
* Auto-install launchd / scheduled tasks without explicit user approval.

## Heartbeat-Friendly Stages

Run these as separate small phases. Each phase must verify the audit finding before changing code.

1. `F43_1_fundamental_neutral_fallback.md`
   * Make missing fundamentals explicit when Quality Momentum Lite uses a neutral fallback.
   * Avoid presenting `基本面避雷6/10` as a real evaluated score when `fundamental_data_ok=false`.
2. `F43_2_old_wang_chip_freshness.md`
   * Add chip `data_as_of` / stale wording to backend-owned Old Wang reasons or risk notes where needed.
3. `F43_3_signal_alert_snapshot_window.md`
   * Make signal alert wording match `previous_as_of` -> `as_of` comparison windows.
4. `F43_4_block_and_schedule_actionability.md`
   * Improve safe inspection / recovery actions for block alerts and schedule / update freshness visibility.
   * Do not auto-install local schedulers.
5. `F43_5_collaboration_docs_cleanup.md`
   * Remove stale collaboration guidance such as obsolete output files or outdated frontend restrictions.

## Umbrella Checklist

* [x] F43.1 completed and verified.
* [x] F43.2 completed and verified.
* [x] F43.3 completed and verified.
* [x] F43.4 completed and verified.
* [x] F43.5 completed and verified.
* [x] Final docs consistency check completed.
* [x] `ai_execution_plan.md` and `loop_state.md` returned to no active phase or next safe phase.

Stop after any stage if the safe fix is unclear or would require product decisions.

## Verification

Use focused commands first, then broader checks when behavior touches shared output:

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_signals_service.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_update_workflow.py -q`
* `git diff --check`

## Result

Status: completed. F43.1 through F43.5 are complete.
