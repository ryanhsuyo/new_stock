# F16 Official PE Priority Apply

Status: complete

## Goal

Allow official PE data to safely reduce the fundamentals priority CSV workload for both listed and OTC stocks.

## Scope

Allowed:

* Use TWSE BWIBBU PE and TPEx daily PE as direct official `pe` sources.
* Support dry-run and apply for `backend/out/fundamentals_priority_fill.csv`.
* Preserve all other required fundamentals fields as manual / derived / blocked until formulas and official sources are confirmed.

Not allowed:

* Do not write `fundamentals.csv` or `fundamentals.json`.
* Do not fill ROE, EPS CAGR, FCF, dividend streak, debt ratio, interest coverage, growth, or margin fields from report-only rows.
* Do not treat fundamentals as a third recommendation strategy.

## Completed

* Added `apply_official_pe_values_to_priority_csv()` service helper.
* Kept the legacy TWSE-only helper compatible for existing callers and tests.
* Updated `update_fundamentals_official.py` so live dry-run/apply uses TWSE + TPEx PE when no fixtures are provided.
* Kept fixture-mode tests network-free: TPEx fixture is used only when explicitly provided, or when a TPEx report is explicitly requested.
* Added service and CLI regression tests proving TPEx PE can fill an OTC priority row while unrelated fields stay blank.

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_cli.py::test_update_fundamentals_official_apply_uses_tpex_pe_fixture -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_api.py -q`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 backend/scripts/update_fundamentals_official.py --sleep 1 --apply`
* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 backend/scripts/check_fundamentals.py`

## Remaining Risk

Only `pe` is formally auto-fillable. The other 10 required fundamentals fields still need confirmed official formulas / source coverage before any automatic apply path is allowed.
