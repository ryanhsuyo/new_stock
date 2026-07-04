# F54 Fundamentals Warning Truthfulness

Status: completed

Purpose:

Make Quality Momentum Lite fundamentals messaging honest when fundamentals are missing. Missing fundamentals may still use a conservative internal fallback for score continuity, but user-facing reasons must not look like a real completed fundamentals score.

## Scope

Allowed:

* Update steady momentum reason text when `fundamental_data_ok=false`.
* Add focused tests proving missing fundamentals do not show as a completed `/10` fundamentals score.
* Update current rules to document the distinction between internal fallback and user-facing score wording.

Not allowed:

* Do not fabricate fundamentals.
* Do not change Quality Momentum Lite score weights or strategy thresholds in this slice.
* Do not apply report-only fields or fill ROE, FCF, interest coverage, dividend years, 5-year averages, or CAGR.

## Tasks

1. Status: done — Add/update failing test for missing fundamentals user-facing reason.
2. Status: done — Update steady momentum reason text for missing fundamentals.
3. Status: done — Run focused steady momentum / signal tests.
4. Status: done — Complete phase docs, update loop state, and commit.

## Acceptance

* Missing fundamentals reason includes `基本面資料不足` and `未完成，無法評分`.
* Missing fundamentals reason does not include `基本面避雷6/10` or `中性保留6/10`.
* Existing complete fundamentals score wording remains unchanged.

## Verification

* RED check: focused missing-fundamentals test failed while the reason still said `中性保留6/10`.
* Focused tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_steady_momentum_service.py -q`.
* Signal integration tests passed: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_signals_api.py::TestSignalsOutput::test_signal_snapshot_outputs_are_written backend/tests/test_daily_brief.py -q`.
* `scripts/run_signals.py` refreshed `summary.json` / `universe_report.csv`; sample `2330` reason now says `基本面資料不足，未完成，無法評分`.
