# F43.1 Fundamental Neutral Fallback

## Goal

Make Quality Momentum Lite honest when fundamentals are missing. A neutral fallback may remain for score stability, but the output must clearly say it is a fallback, not a real `基本面避雷` evaluation.

## Verify First

Before editing behavior:

* Inspect `backend/app/services/signals_service.py` around Quality Momentum Lite score assembly.
* Inspect `backend/app/services/fundamental_guard_service.py` for `fundamental_data_ok=false` payloads.
* Find the focused tests that cover `steady_momentum` / `fundamental_reason` / universe report output.

## Scope

Allowed:

* Add focused backend tests around missing fundamentals reason text and score components.
* Change backend-owned reason / risk note wording for missing fundamental data.
* Update `current_rules.md` if output semantics change.

Not allowed:

* Fabricate or infer missing PE, ROE, FCF, dividend years, CAGR, or other fundamentals.
* Change the two strategy buckets.
* Change formal trades, holdings, cash, or personal records.
* Move scoring logic to frontend.

## Checklist

* [x] Add or update a failing test showing `fundamental_data_ok=false` does not look like a real `基本面避雷6/10` pass.
* [x] Implement explicit neutral fallback wording in backend-owned output.
* [x] Ensure reasons / risk notes still include enough context for `summary.json` / `universe_report.csv`.
* [x] Run focused tests.
* [x] Update `current_rules.md` if wording or semantics changed.
* [x] Update F43 umbrella, `ai_execution_plan.md`, and `loop_state.md` to move to F43.2 or stop with a clear reason.

## Verification

Use the smallest relevant commands first:

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_signals_service.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_service.py -q`
* `git diff --check`

## Result

Status: completed.

Superseded by F54: missing fundamentals now render as `基本面避雷：基本面資料不足，未完成，無法評分 (...)`. The internal fallback may still preserve score continuity, but user-facing wording must not expose `中性保留6/10` as if the fundamentals guard had been evaluated.
