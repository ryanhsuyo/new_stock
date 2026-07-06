# F64 User Input Required Actions

Status: completed

## Goal

Make non-automatable Daily Check / PM Worklist tasks explicit so heartbeat does not keep trying to auto-complete work that requires true user-provided data.

## Scope

* Manual market note updates require the user's real post-close observations.
* Fundamentals priority CSV work requires true external fundamentals data.
* Frontend and heartbeat may display / route these actions, but must not fabricate content or mark them done automatically.

## Tasks

1. Status: done — Add backend payload metadata for manual market note actions: `requires_user_input`, `user_input_kind`, and a short note.
2. Status: done — Add backend payload metadata for fundamentals copy-text actions with the same contract.
3. Status: done — Cover the metadata with focused Daily Check / PM Worklist tests.
4. Status: done — Update rules / loop state and verify.

## Acceptance

* Manual market note and fundamentals warning actions clearly say they need user-provided data.
* No strategy, score, recommendation bucket, generated fundamentals field, trade, holding, or cash behavior changes.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_daily_check.py::test_daily_check_builds_summary_from_doctor_report backend/tests/test_daily_check.py::test_daily_check_surfaces_stale_manual_market_note backend/tests/test_pm_worklist.py::test_pm_worklist_prioritizes_data_repair_before_followup_work -q`
