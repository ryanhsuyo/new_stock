# AI Loop State

Purpose:

Track automatic phase continuation without making `ai_execution_plan.md` too long.

Rules:

* Keep this file under 200 lines.
* Update this file whenever a phase completes or a new phase becomes active.
* Do not store long reports here; keep only execution state.

## Current State

Active phase: none

Loop mode: stopped after approved phase completion

Last completed phase:

* `R9.2_fundamentals_import_template.md` — Fundamentals external import template

Current phase status:

* No active phase.

## Completed Phase History

* H2.5 — Git baseline, Today Focus contract, fixture tests, frontend consumption, docs reconciliation.
* H2.6 — Homepage readability, market posture summary, candidate text density, mobile first-screen CSS.
* H2.7 — Visual acceptance checklist; browser screenshot pass soft-blocked by local browser policy.
* H2.8 — Extracted file status row component from Dashboard and verified frontend build.
* H3.0 — Improved candidate table scanability by keeping stock identity visible during horizontal scroll.
* H4.0 — Clarified market posture note status, applies-to date, and Chinese fallback wording.
* H4.1 — Rendered Daily Check action preview items consistently with PM Worklist.
* H6.0 — Reconciled status and phase docs with completed homepage PM work.
* H6.1 — Full backend/frontend verification passed and commit summary prepared.
* H7.0 — Confirmed stale status uses trading-day logic, added weekend regression test, and reconciled docs.
* H7.1 — Extracted `ParseErrorAlert` from Dashboard and verified frontend build.
* H7.2 — Selected the next safe product slice: Today Focus component boundary.
* H7.3 — Extracted `TodayFocusCards` from Decision Console and verified frontend build.
* H7.4 — Extracted `DecisionStatusStrip` from Decision Console and verified frontend build.
* H7.5 — Extracted `PrimaryActionCard` from Decision Console and verified frontend build.
* H7.6 — Extracted `MarketPostureCard` from Decision Console and verified frontend build.
* H7.7 — Extracted market summary boxes from Dashboard and verified frontend build.
* H7.8 — Extracted `ChangeReport` from Dashboard and verified frontend build.
* H7.9 — Extracted Daily Brief list/panel helpers and verified frontend build.
* H7.10 — Extracted `DailyBriefBox` from Dashboard and verified frontend build.
* H7.11 — Extracted `DataRepairQueueBox` from Dashboard and verified frontend build.
* H7.12 — Extracted `UpdateWorkflowBox` from Dashboard and verified frontend build.
* H7.13 — Extracted `DailyCheckBox` from Dashboard and verified frontend build.
* H8.0 — Added compact Today Focus fields, reduced first-screen detail density, and compressed the candidate table.
* H8.1 — Verified desktop/mobile layout, fixed mobile nav overflow, and reconciled roadmap status.
* H8.2 — Grouped all secondary Dashboard content into four collapsed intent-based sections and preserved focus navigation.
* H8.3 — Kept desktop Market Posture unchanged and moved the phone version into a collapsed disclosure after Today Focus.
* H5.0 — Closed formal screenshot acceptance with an explicit environment waiver; no screenshot was claimed.
* S1.1 — Added per-stock spawn-process timeout protection, explainable fallback rows, timeout observability, and regression tests.
* M6.1 — Made successful trade-derived positions authoritative, including empty portfolios, with exception-only legacy fallback.
* L3.1 — Added safe environment-configured CORS origins and real preflight regression tests.
* L10.1 — Added derived schedule health states with weekday-aware overdue detection.
* S2.1 — Added head-and-shoulders top detection, conservative risk weights, and explainable signal text.
* L2.1 — Added three-touch trendline validation, 2% tolerance, violation rejection, candidate ranking, and two-point fallback tests.
* R1.1 — Added single-stock core backtesting with historical-prefix isolation, next-open fills, costs, metrics, and generated CLI outputs.
* R2.1 — Added local trading calendar, data coverage report, batch lineage, and coverage blockers in Doctor / Daily Check / Update Workflow.
* S3.0 — Reconciled the two-strategy product contract, fixed Universe Report core-signal promotion, and verified backend/frontend outputs.
* R3.1 — Added personal-data backup, dry-run restore preview, confirmed restore, pre-restore backup, API/CLI access, and regression tests.
* R4.1 — Added daily signal snapshots, next-run action review, files_written integration, CLI summary text, and regression tests.
* R5.1 — Added auditable price source fields across signals, universe_report, daily_brief, signal snapshots, and regression tests.
* R6.1 — Added local signal alerts summary, run_signals output integration, Daily Check top action, and regression tests.
* R7.1 — Added rules version metadata across summary, daily brief, signal snapshots, signal alerts, and regression tests.
* R8.1 — Added derived today scan service / CLI, bucket tests, docs, run_signals auto-refresh, historical snapshots, and Daily Check summary.
* R9.0 — Added safe fundamentals priority CSV import preparation, dry-run/apply CLI, alias mapping, skipped-code reporting, validation reuse, and focused tests.
* R9.1 — Surfaced fundamentals priority import commands in PM Worklist and Daily Check action payloads, with shared expected outputs and regression tests.
* R9.2 — Added fundamentals external import template generation, CLI support, workflow payload hints, and focused tests.

## Next Phase Candidates

None selected. A new phase requires an explicit request or roadmap selection.

## Last Verification

* Fundamentals wording regression tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamentals_cli.py -q` passed, 14 tests.
* R9 focused fundamentals service tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamental_service.py -q` passed, 20 tests.
* R9 focused fundamentals CLI tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamentals_cli.py::test_prepare_fundamentals_priority_import_help_exits_0 backend/tests/test_fundamentals_cli.py::test_prepare_fundamentals_priority_import_prints_preview -q` passed, 2 tests.
* R9.1 focused PM/Daily tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py::test_pm_worklist_prioritizes_data_repair_before_followup_work backend/tests/test_daily_check.py::test_daily_check_prints_action_payload_details -q` passed, 2 tests.
* R9.1 workflow tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py backend/tests/test_daily_check.py backend/tests/test_doctor.py backend/tests/test_workflow_status.py -q` passed, 59 tests.
* R9.2 focused template tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamental_service.py::test_build_priority_import_template_rows_uses_focus_targets backend/tests/test_fundamental_service.py::test_write_priority_import_template_csv_writes_readable_header backend/tests/test_fundamentals_cli.py::test_prepare_fundamentals_priority_import_help_exits_0 backend/tests/test_fundamentals_cli.py::test_prepare_fundamentals_priority_import_writes_template backend/tests/test_pm_worklist.py::test_pm_worklist_prioritizes_data_repair_before_followup_work backend/tests/test_daily_check.py::test_daily_check_prints_action_payload_details -q` passed, 6 tests.
* R9.2 workflow tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamental_service.py backend/tests/test_fundamentals_cli.py backend/tests/test_pm_worklist.py backend/tests/test_daily_check.py backend/tests/test_doctor.py backend/tests/test_workflow_status.py -q` passed, 95 tests.
* Backend tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests -q` passed, 712 tests, during R9.2.
* Backend tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests -q` passed, 709 tests, during R9.1.
* Backend tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests -q` passed, 709 tests, during R9.0.
* Backend tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests -q` passed, 702 tests, during R8.1.
* Daily Check today scan tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py -q` passed, 17 tests.
* R8 auto-refresh focused tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_signals_api.py::TestSignalsOutput::test_signal_snapshot_outputs_are_written backend/tests/test_workflow_outputs.py -q` passed, 3 tests.
* R8 focused tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_service.py backend/tests/test_today_scan_cli.py -q` passed, 5 tests.
* R7 focused tests: `python3 -m pytest backend/tests/test_rules_metadata_service.py backend/tests/test_signals_api.py::TestSignalsOutput backend/tests/test_daily_brief.py backend/tests/test_signal_snapshot_service.py backend/tests/test_signal_alert_service.py -q` passed, 37 tests.
* Backend tests: `python3 -m pytest backend/tests -q` passed, 697 tests, during R7.1.
* R6 focused tests: `python3 -m pytest backend/tests/test_signal_alert_service.py backend/tests/test_signal_snapshot_service.py backend/tests/test_signals_api.py::TestSignalsOutput backend/tests/test_run_signals_cli.py backend/tests/test_daily_check.py -q` passed, 52 tests.
* R5 focused tests: `python3 -m pytest backend/tests/test_signals_api.py::TestSignalsOutput backend/tests/test_daily_brief.py backend/tests/test_signal_snapshot_service.py backend/tests/test_universe_report.py backend/tests/test_signals_pattern.py::TestUniverseReportPatternColumns -q` passed, 67 tests.
* R4 focused tests: `python3 -m pytest backend/tests/test_signal_snapshot_service.py backend/tests/test_signals_api.py::TestSignalsOutput backend/tests/test_run_signals_cli.py -q` passed, 32 tests.
* R3 focused tests: `python3 -m pytest backend/tests/test_personal_backup_service.py backend/tests/test_personal_backups_api.py backend/tests/test_personal_backup_cli.py -q` passed, 15 tests.
* Frontend build: `cd frontend && npm run build` passed during R7.1, with existing Vite chunk-size warning.
* Frontend structure tests: `node --test frontend/tests/*.test.mjs` passed 6 tests during S3.0 reconciliation.
* Browser sanity check: Decision Console passed at 1280x720 and 390x844; candidate row expansion passed; screenshot capture timed out.

## Last Stop Reason

R9.2 completed; the fundamentals priority import flow now includes a generated external-data template, dry-run preview, apply command, workflow payload hints, and regression coverage. The next meaningful blocker is still real fundamentals data; do not fabricate values.
