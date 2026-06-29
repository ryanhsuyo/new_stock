# F6 Official Fundamentals Report Action

Status: completed

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
   - Status: done
   - Add client method for `POST /api/system/fundamentals-official/reports`.

2. Dashboard action
   - Status: done
   - Add a clear button in the official fundamentals status card to generate report-only CSVs.

3. Result feedback
   - Status: done
   - Refresh official report status after success and show a short result message.

4. Guardrails
   - Status: done
   - Copy must say this does not apply to priority CSV or fill 11 required fields.

5. Verification
   - Status: done
   - Run frontend structure tests and build.

## Verification

* `node --test frontend/tests/*.test.mjs` — 9 passed.
* `npm run build` from `frontend/` — passed with existing Vite chunk-size warning.

## Acceptance

* User can trigger official report-only generation from Dashboard.
* UI remains explicit that this is not a strategy-data apply.
* Existing two-strategy product contract remains unchanged.
