# F5 Official Fundamentals Frontend Status

Status: completed

## Goal

Make official fundamentals report status readable from the PM/Dashboard view without adding strategy logic.

Hard rules:

* Frontend consumes backend API/out contracts only.
* Do not recompute strategies, scores, buckets, or fundamentals workflow rules in frontend.
* Do not fabricate ROE, EPS, FCF, interest coverage, or other derived fields.
* Keep `old_wang` and `steady_momentum` as the only recommendation strategies.

## Tasks

1. Phase activation
   - Status: done
   - Create this phase and point `ai_execution_plan.md` / `loop_state.md` to F5.

2. Frontend contract
   - Status: done
   - Add TypeScript types and API client method for `GET /api/system/fundamentals-official/status`.

3. PM visibility
   - Status: done
   - Render official report status in the fundamentals/Dashboard area: exists, row count, modified time, and next action.

4. Guardrails
   - Status: done
   - Make copy/action text clear that the HTTP report endpoint is report-only and does not apply to strategy inputs.

5. Verification
   - Status: done
   - Run frontend structure tests and build.

## Verification

* `node --test frontend/tests/*.test.mjs` — 8 passed.
* `npm run build` from `frontend/` — passed with existing Vite chunk-size warning.

## Acceptance

* Dashboard can show whether the three official report CSV files exist.
* User can see row count and last updated time for each report.
* UI clearly says derived financial fields remain blocked until real official financial statement data is confirmed.
* No new strategy bucket, score calculation, or recommendation logic is added.
