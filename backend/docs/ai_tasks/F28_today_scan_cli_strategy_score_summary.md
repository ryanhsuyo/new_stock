# F28 Today Scan CLI Strategy Score Summary

## Goal

Make `backend/scripts/today_scan.py` text output show the backend-provided two-strategy score summary from F27.

## Scope

Allowed:

* Display `strategy_score_summary.summary_label` in the text CLI item line when present.
* Add focused CLI tests.
* Update docs and loop state.

Not allowed:

* Recalculate strategy scores.
* Add strategy buckets.
* Change JSON output shape.
* Modify trades, holdings, cash, or formal trading records.

## Checklist

* [x] Add failing CLI text-output test.
* [x] Implement minimal CLI display.
* [x] Run focused CLI tests.
* [x] Update `current_rules.md`, execution plan, and loop state.
* [ ] Commit the completed slice.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_today_scan_cli.py -q`
* `git diff --check`

## Result

Completed. Text CLI output now shows `strategy_score_summary.summary_label` when present, while JSON output remains unchanged.
