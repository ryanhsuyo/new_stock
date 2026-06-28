# F2 Official Fundamentals Ingestion

Phase: Official fundamentals data ingestion

Goal:

Use official low-frequency APIs to reduce manual fundamentals entry without fabricating values.

Scope:

* First source: TWSE OpenAPI `BWIBBU_ALL`.
* First direct mapping: `PEratio` -> `pe`.
* `DividendYield` and `PBratio` can be written to an official reference report because the current fundamentals schema has no exact destination for them.
* TPEx / OTC official source is not implemented in this slice; OTC symbols are skipped when TWSE has no row.

Do not:

* Scrape HTML.
* Fill ROE, EPS, FCF, interest coverage, or other derived fields without a verified official source and formula.
* Treat official fundamentals as a third strategy.

## Task F2-01 — Official Mapping Contract

Status: done

Checklist:

* [x] Add tests for TWSE official rows updating only direct mapped fields.
* [x] Dry-run must not mutate `fundamentals_priority_fill.csv`.
* [x] Missing TWSE rows must produce skip reasons.
* [x] Blank PE must not be written.

Verification:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py -q
```

## Task F2-02 — Official Update CLI

Status: done

Checklist:

* [x] Add `backend/scripts/update_fundamentals_official.py`.
* [x] Default to dry-run.
* [x] Support `--apply`.
* [x] Support `--fixture` for tests without network.
* [x] Support `--write-report` to write official BWIBBU reference rows.
* [x] Use official JSON API, not HTML scraping.
* [x] Include skip reason and unmapped official fields in output.

Verification:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_cli.py -q
```

## Task F2-02b — Official Reference Report

Status: done

Checklist:

* [x] Preserve official `PEratio`, `DividendYield`, and `PBratio` in a neutral report schema.
* [x] Keep the report separate from scoring fields so it cannot become a third strategy.
* [x] Mark blank PE rows with `twse_pe_missing_or_empty`.

Verification:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py -q
```

## Task F2-03 — Reconcile Docs

Status: done

Checklist:

* [x] Document the first official mapping in current rules.
* [x] Mark F2 complete in loop state.

Verification:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_fundamental_service.py backend/tests/test_fundamentals_cli.py -q
curl -s https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL -o /private/tmp/twse_bwibbu_all.json
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -c "import json, pathlib; data=json.loads(pathlib.Path('/private/tmp/twse_bwibbu_all.json').read_text(encoding='utf-8')); print(type(data).__name__, len(data)); print(sorted(data[0].keys())[:8] if data else [])"
```

Latest result:

* Focused fundamentals flow tests passed, 43 tests after F2-02b.
* Official TWSE endpoint returned JSON `list` with 1077 rows and fields including `Code`, `Date`, `DividendYield`, `Name`, `PBratio`, `PEratio`.
