# F6 Official Fundamentals Report Action

Status: in_progress

## Goal

Add a safe PM/Dashboard action to trigger official fundamentals report-only generation.

Hard rules:

* Use `POST /api/system/fundamentals-official/reports`.
* Default to report-only / dry-run behavior.
* Do not apply values to priority CSV or strategy inputs.
* Do not fabricate derived financial fields.
* Frontend must not recalculate strategies, scores, recommendation buckets, or fundamentals workflow rules.

## Tasks

1. Frontend action contract
   - Status: todo
   - Add client method for `POST /api/system/fundamentals-official/reports`.

2. Dashboard action
   - Status: todo
   - Add a clear button in the official fundamentals status card to generate report-only CSVs.

3. Result feedback
   - Status: todo
   - Refresh official report status after success and show a short result message.

4. Guardrails
   - Status: todo
   - Copy must say this does not apply to priority CSV or fill 11 required fields.

5. Verification
   - Status: todo
   - Run frontend structure tests and build.

## Acceptance

* User can trigger official report-only generation from Dashboard.
* UI remains explicit that this is not a strategy-data apply.
* Existing two-strategy product contract remains unchanged.
