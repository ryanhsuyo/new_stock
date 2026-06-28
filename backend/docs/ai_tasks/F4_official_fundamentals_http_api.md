# F4 Official Fundamentals HTTP API

Status: completed

## Goal

Expose official fundamentals report status and safe report-only generation through thin FastAPI endpoints.

Rules:

* Keep routers HTTP-only.
* Do not apply official values into strategy inputs from HTTP.
* Do not fabricate EPS, ROE, FCF, interest coverage, or other derived fields.
* Keep `old_wang` and `steady_momentum` as the only recommendation strategies.

## Tasks

1. Status service
   - Status: done
   - Added report metadata and CSV row counting for TWSE BWIBBU, TWSE monthly revenue, and TPEx daily PE reports.

2. Status endpoint
   - Status: done
   - Added `GET /api/system/fundamentals-official/status`.

3. Report-only runner
   - Status: done
   - Added service-level report generation with request throttling.
   - Writes only official temporary report CSV files under `backend/out/`.
   - Rejects HTTP `apply=true`; priority CSV apply stays CLI/manual-confirmed.

4. Report endpoint
   - Status: done
   - Added `POST /api/system/fundamentals-official/reports`.

5. Tests
   - Status: done
   - Added service/API tests with monkeypatched official source calls.

## Endpoints

* `GET /api/system/fundamentals-official/status`
* `POST /api/system/fundamentals-official/reports`

Default `POST` body:

```json
{}
```

Equivalent explicit body:

```json
{
  "reports": ["twse_bwibbu", "twse_monthly_revenue", "tpex_daily_pe"],
  "apply": false,
  "sleep": 1.0,
  "tpex_daily_pe_date": null
}
```

## Verification

* `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest backend/tests/test_official_fundamentals_api.py -q`

Result:

* 5 passed

## Remaining Limits

* These endpoints do not fill the 11 required fundamentals fields.
* Direct official fields currently available through stable report outputs: PE, PB, dividend yield, monthly revenue YoY, cumulative revenue YoY.
* Derived / blocked fields still require a stable official financial statement source and formulas before ingestion.
