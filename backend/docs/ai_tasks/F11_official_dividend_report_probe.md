# F11 Official Dividend Report Probe

Status: completed

## Goal

Build the next small report-only probe for official dividend distribution sources.

Use only confirmed official OpenAPI endpoints:

* TWSE listed dividend distribution: `/opendata/t187ap45_L`
* TPEx OTC dividend distribution: `/mopsfin_t187ap39_O`

Hard rules:

* Report-only output only.
* Do not write `fundamentals.csv`, `fundamentals.json`, or priority CSV.
* Do not fill `dividend_years` or any derived field yet.
* Do not fabricate missing years, cash dividends, stock dividends, or OTC/listed data.
* Keep fundamentals as `steady_momentum` support data, not a third strategy.

## Tasks

1. Source shape decision
   - Status: done
   - Confirmed stable official JSON fields:
     - TWSE `/opendata/t187ap45_L`
     - TPEx `/mopsfin_t187ap39_O`
   - The official rows split cash / stock distribution into earnings and capital reserve components. The report normalizes these into per-share `cash_dividend` and `stock_dividend` by summing official per-share component fields.

2. Service/parser test
   - Status: done
   - Add fixed fixture tests for selected TWSE/TPEx dividend row normalization.

3. Service implementation
   - Status: done
   - Normalize code, name, dividend year, period, cash dividend, stock dividend, source, and skip reason when official fields are present.

4. CLI/API report-only path
   - Status: done
   - Add a neutral CSV output only if field names are stable enough.

5. Verification
   - Status: done
   - Run focused backend tests.

## Output

`backend/out/official_fundamentals_dividend.csv`

Fields:

* `code`
* `name`
* `dividend_year`
* `period`
* `cash_dividend`
* `stock_dividend`
* `source`
* `skip_reason`

CLI:

```bash
cd backend
python3 scripts/update_fundamentals_official.py --write-dividend-report
```

HTTP:

* `POST /api/system/fundamentals-official/reports`
* Includes `dividend` in the default report-only set.

## Verification

Passed:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_service.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_api.py -q
```

## Acceptance

* A generated neutral CSV can show listed + OTC dividend reference rows.
* Missing or malformed values produce skip reasons.
* No strategy score or required fundamentals field is modified.
