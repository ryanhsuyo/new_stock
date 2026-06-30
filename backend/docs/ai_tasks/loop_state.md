# AI Loop State

Purpose:

Track automatic phase continuation without making `ai_execution_plan.md` too long.

Rules:

* Keep this file under 200 lines.
* Update this file whenever a phase completes or a new phase becomes active.
* Do not store long reports here; keep only execution state.

## Current State

Active phase: none

Loop mode: waiting_for_next_phase

Last completed phase:

* `F19_partial_data_freshness_visibility.md` — Daily Check now surfaces partial stale Today Scan rows

Current phase status:

* No active phase. F19 is done; start a new phase only when there is a concrete next product or data task.

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
* D1.0 — Added Daily Check `status_reason` / `trade_outputs_note` / `blocked_by` and Today Scan `bucket_notes`.
* F1 — Added Daily Check frontend rendering for fundamentals workflow stage, primary action, and checklist.
* F2 — Added official TWSE fundamentals priority CSV dry-run/apply update for direct PE mapping and neutral BWIBBU reference report output.
* F2.1 — Added TWSE listed-company monthly revenue report output for official YoY reference fields.
* F2.2 — Added TPEx official PE/PB/dividend report output for OTC reference fields.
* F3 — Mapped all 11 required fundamentals fields to direct / derived / blocked source decisions and formulas.
* F4 — Added official fundamentals report status and report-only HTTP API wrapper.
* F5 — Added Dashboard official fundamentals report status display and frontend API contract.
* F6 — Added Dashboard action for official fundamentals report-only generation.
* F7 — Mapped TWSE/TPEx official financial statement OpenAPI source decisions and blocked cash-flow-dependent fields.
* F8 — Added TWSE/TPEx official profitability report-only probe across service, CLI, and HTTP API.
* F9 — Added TWSE/TPEx general-industry balance sheet report-only probe across service, CLI, and HTTP API.
* F10 — Added TWSE/TPEx general-industry income statement report-only probe across service, CLI, and HTTP API.
* F11 — Added TWSE/TPEx dividend distribution report-only probe across service, CLI, and HTTP API.
* F12 — Added read-only official fundamentals report coverage audit service and CLI JSON output.
* F13 — Added read-only official fundamentals coverage audit API wrapper.
* F14 — Added Dashboard / PM-facing official coverage audit status display without frontend recomputation.
* F15 — Added Daily Check / PM Worklist official coverage awareness without triggering report generation or formal fundamentals writes.
* F16 — Added official TWSE/TPEx PE priority CSV dry-run/apply path while keeping other fundamentals fields blocked.
* F17 — Constrained `steady_momentum` to Quality Momentum Lite so the second strategy uses low-cost fundamentals guardrails instead of requiring all 11 advanced fields.
* F18 — Closed end-to-end two-strategy execution verification, read-only Quality Momentum Lite guard coverage, API visibility, and PE-only apply-path decision.
* F19 — Added Today Scan data freshness summary and Daily Check preview for partial stale universe rows.

## Next Phase Candidates

* Prepare a commit-ready change summary for F1-F15 official fundamentals workflow.
* Add a small official fundamentals smoke-verification phase only after deciding whether generated `backend/out/*` refreshes should be part of the heartbeat.

## Last Verification

* F1 frontend build: `cd frontend && npm run build` passed, with existing Vite chunk-size warning.
* F1 frontend structure tests: `cd frontend && node --test tests/*.test.mjs` passed, 6 tests.
* F2 official ingestion tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_service.py -q` passed, 7 tests.
* F2 focused fundamentals flow tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_fundamental_service.py backend/tests/test_fundamentals_cli.py -q` passed, 43 tests.
* F2.1 official ingestion tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_service.py -q` passed, 9 tests.
* F2.2 official ingestion tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_service.py -q` passed, 11 tests.
* F2.2 focused fundamentals flow tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_fundamental_service.py backend/tests/test_fundamentals_cli.py -q` passed, 47 tests.
* F3 docs/source sanity: `rg -n "F3|roe_5y_avg|official financial statement|derived_blocked" backend/docs/ai_tasks/F3_official_financial_statement_source_mapping.md backend/docs/current_rules.md backend/docs/ai_tasks/loop_state.md` passed.
* F4 official report API tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_api.py -q` passed, 5 tests.
* F5 frontend structure tests: `node --test frontend/tests/*.test.mjs` passed, 8 tests.
* F5 frontend build: `npm run build` from `frontend/` passed, with existing Vite chunk-size warning.
* F6 frontend structure tests: `node --test frontend/tests/*.test.mjs` passed, 9 tests.
* F6 frontend build: `npm run build` from `frontend/` passed, with existing Vite chunk-size warning.
* F7 docs/source sanity: `rg -n "F7|t187ap06|t187ap07|cash flow|report-only candidate|blocked" backend/docs/ai_tasks/F7_official_financial_statement_source_decision.md backend/docs/current_rules.md backend/docs/ai_tasks/loop_state.md` passed.
* F8 focused tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py::test_build_official_profitability_report_rows_normalizes_twse_and_tpex_rows backend/tests/test_official_fundamentals_cli.py::test_update_fundamentals_official_writes_profitability_report_from_fixtures backend/tests/test_official_fundamentals_api.py::test_run_official_fundamentals_reports_endpoint_defaults_to_report_only backend/tests/test_official_fundamentals_api.py::test_run_official_fundamentals_reports_writes_profitability_csv -q` passed.
* F9 focused tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py::test_build_official_balance_sheet_report_rows_normalizes_general_industry_rows backend/tests/test_official_fundamentals_cli.py::test_update_fundamentals_official_writes_balance_sheet_report_from_fixtures backend/tests/test_official_fundamentals_api.py::test_run_official_fundamentals_reports_endpoint_defaults_to_report_only backend/tests/test_official_fundamentals_api.py::test_run_official_fundamentals_reports_writes_balance_sheet_csv -q` passed.
* F10 official fundamentals tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_api.py -q` passed.
* F11 official fundamentals tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_api.py -q` passed.
* F12 official fundamentals tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_api.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_service.py -q` passed.
* F13 official fundamentals tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_api.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_service.py -q` passed.
* F14 frontend tests: `node --test frontend/tests/*.test.mjs` passed.
* F14 frontend build: `npm run build` from `frontend/` passed, with existing Vite chunk-size warning.
* F15 workflow tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py backend/tests/test_pm_worklist.py -q` passed, 31 tests.
* F16 official fundamentals tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_api.py -q` passed, 34 tests.
* F16 live official PE apply: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 backend/scripts/update_fundamentals_official.py --sleep 1 --apply` passed, updated 18 priority PE values, skipped 2 missing official PE values.
* F16 fundamentals check: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 backend/scripts/check_fundamentals.py` passed with priority CSV `ready_to_preview`, 18 partial priority rows, and no errors / warnings.
* F17 fundamental guard tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamental_guard.py -q` passed, 6 tests.
* F17 fundamentals workflow tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamental_service.py backend/tests/test_fundamentals_cli.py backend/tests/test_fundamental_guard.py -q` passed, 42 tests.
* F17 official / PM workflow regression: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_api.py backend/tests/test_daily_check.py backend/tests/test_pm_worklist.py backend/tests/test_workflow_status.py backend/tests/test_rules_metadata_service.py -q` passed, 81 tests.
* F17 fundamentals check: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 backend/scripts/check_fundamentals.py` passed with priority CSV `ready_to_preview` and next action describing lite guard usage.
* F18 final run signals: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 backend/scripts/run_signals.py` passed, generated 6 ready-to-enter stocks and refreshed summary / universe_report / today_scan / daily_check.
* F18 focused strategy tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_signals_api.py::TestSignalsOutput backend/tests/test_today_scan_service.py backend/tests/test_today_scan_cli.py backend/tests/test_rules_metadata_service.py backend/tests/test_fundamental_guard.py backend/tests/test_fundamental_service.py backend/tests/test_fundamentals_cli.py -q` passed, 75 tests.
* F18 lite guard coverage/API tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_api.py backend/tests/test_official_fundamentals_service.py -q` passed, 26 tests.
* F19 product observability tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_service.py backend/tests/test_daily_check.py -q` passed.
* Fundamentals wording regression tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamentals_cli.py -q` passed, 14 tests.
* R9 focused fundamentals service tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamental_service.py -q` passed, 20 tests.
* R9 focused fundamentals CLI tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamentals_cli.py::test_prepare_fundamentals_priority_import_help_exits_0 backend/tests/test_fundamentals_cli.py::test_prepare_fundamentals_priority_import_prints_preview -q` passed, 2 tests.
* R9.1 focused PM/Daily tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py::test_pm_worklist_prioritizes_data_repair_before_followup_work backend/tests/test_daily_check.py::test_daily_check_prints_action_payload_details -q` passed, 2 tests.
* R9.1 workflow tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_pm_worklist.py backend/tests/test_daily_check.py backend/tests/test_doctor.py backend/tests/test_workflow_status.py -q` passed, 59 tests.
* R9.2 focused template tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamental_service.py::test_build_priority_import_template_rows_uses_focus_targets backend/tests/test_fundamental_service.py::test_write_priority_import_template_csv_writes_readable_header backend/tests/test_fundamentals_cli.py::test_prepare_fundamentals_priority_import_help_exits_0 backend/tests/test_fundamentals_cli.py::test_prepare_fundamentals_priority_import_writes_template backend/tests/test_pm_worklist.py::test_pm_worklist_prioritizes_data_repair_before_followup_work backend/tests/test_daily_check.py::test_daily_check_prints_action_payload_details -q` passed, 6 tests.
* R9.2 workflow tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_fundamental_service.py backend/tests/test_fundamentals_cli.py backend/tests/test_pm_worklist.py backend/tests/test_daily_check.py backend/tests/test_doctor.py backend/tests/test_workflow_status.py -q` passed, 95 tests.
* D1.0 focused tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py backend/tests/test_today_scan_service.py -q` passed, 21 tests.
* Backend tests: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests -q` passed, 715 tests, during D1.0.
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

F19 completed. No safe autonomous next phase is currently selected; wait for the next concrete product/data signal before implementing more changes.
