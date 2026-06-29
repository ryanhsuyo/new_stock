# F13 Official Fundamentals Coverage API

Status: completed

## Goal

Expose the F12 read-only official fundamentals coverage audit through a thin API endpoint.

Hard rules:

* Router only handles HTTP and response models.
* Service owns CSV reading and audit logic.
* Do not write `fundamentals.csv`, `fundamentals.json`, priority CSV, trades, holdings, or cash.
* Do not fill `dividend_years`, growth CAGR, ROE, FCF, or any derived formal field.
* Do not turn fundamentals into a third strategy.

## Tasks

1. API/service contract test
   - Status: done
   - Add endpoint test using monkeypatched service output.

2. Models
   - Status: done
   - Add loose but stable Pydantic response model for the audit result.

3. Router
   - Status: done
   - Add `GET /api/system/fundamentals-official/coverage-audit`.

4. Verification
   - Status: done
   - Run focused official fundamentals API tests.

## Output

Endpoint:

```text
GET /api/system/fundamentals-official/coverage-audit
```

Behavior:

* Reads the existing priority CSV and official report-only CSV files.
* Does not generate official reports.
* Does not write `fundamentals.csv`, `fundamentals.json`, priority CSV, trades, holdings, or cash.
* Returns `404` with a clear message if `backend/out/fundamentals_priority_fill.csv` is missing.

## Verification

Passed:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_api.py backend/tests/test_official_fundamentals_cli.py backend/tests/test_official_fundamentals_service.py -q
```

## Acceptance

* API returns the F12 audit without generating reports or mutating inputs.
* Missing priority CSV returns a clear HTTP error.
* Frontend can consume the endpoint later without recreating audit rules.
