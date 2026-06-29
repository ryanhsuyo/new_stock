# F7 Official Financial Statement Source Decision

Status: completed

## Goal

Decide whether the blocked fundamentals fields can use stable official OpenAPI sources.

Hard rules:

* Do not scrape MOPS security-blocked HTML pages.
* Do not fabricate ROE, EPS, FCF, interest coverage, or dividend history.
* Do not write official financial statement values into `fundamentals.csv` in this phase.
* Keep fundamentals as `steady_momentum` guardrail/support data, not a third strategy.

## Official Sources Checked

TWSE official Swagger:

* `https://openapi.twse.com.tw/`
* Spec URL: `https://openapi.twse.com.tw/v1/swagger.json`

TPEx official Swagger:

* `https://www.tpex.org.tw/openapi/`
* Spec URL: `https://www.tpex.org.tw/openapi/swagger.json`

Confirmed stable JSON/CSV endpoints:

* TWSE listed income statement: `/opendata/t187ap06_L_*`
* TWSE listed balance sheet: `/opendata/t187ap07_L_*`
* TWSE listed profitability summary: `/opendata/t187ap17_L`
* TWSE listed dividend distribution: `/opendata/t187ap45_L`
* TPEx OTC income statement: `/mopsfin_t187ap06_O_*`
* TPEx OTC balance sheet: `/mopsfin_t187ap07_O_*`
* TPEx OTC profitability summary: `/mopsfin_187ap17_O`
* TPEx OTC dividend distribution: `/mopsfin_t187ap39_O`

`*` means industry-specific variants such as general, financial, securities/futures, insurance, holding company, and mixed industry.

## Field Decisions

| Field | Decision | Reason |
| --- | --- | --- |
| `roe_5y_avg` | report-only candidate | Needs 5 years of net income and equity. Income statement and balance sheet sources exist for listed and OTC, but formula convention and annualization need a separate implementation phase. |
| `operating_margin_5y_avg` | report-only candidate | Profitability summary has operating margin fields for listed and OTC. Can be safer than deriving from raw statement rows. |
| `free_cash_flow_positive_years` | blocked | No stable official OpenAPI cash flow statement / capital expenditure source confirmed. |
| `operating_cash_flow_to_net_income` | blocked | No stable official operating cash flow source confirmed. |
| `debt_to_equity` | report-only candidate | Balance sheet sources include liabilities and equity totals for listed and OTC. Needs formula normalization across field naming variants. |
| `interest_coverage` | blocked | Income statement provides operating profit, but interest expense is not consistently exposed for general industry statements. |
| `revenue_growth_5y_cagr` | report-only candidate | Monthly revenue sources and income statement revenue fields exist. Needs multi-year series collection and TWSE/TPEx coverage alignment. |
| `eps_growth_5y_cagr` | report-only candidate | Income statement has basic EPS for listed and OTC. Needs negative/zero base handling before applying. |
| `pe` | already direct/partial | Covered by F2/F2.2 official report work. |
| `fcf_yield` | blocked | Depends on free cash flow; no official cash flow/capex source confirmed. |
| `dividend_years` | report-only candidate | Dividend distribution endpoints exist for listed and OTC. Needs multi-year history count rule. |

## Recommended Next Implementation

Do not fill `fundamentals.csv` yet.

Next safe phase should be `F8`: build a report-only official financial statement probe for one narrow source group:

1. Fetch listed + OTC general-industry profitability summaries.
2. Produce a neutral CSV report with operating margin / net margin fields.
3. Do not apply to the 11 required fields until formulas, years, and coverage are verified.

This gives useful coverage for `operating_margin_5y_avg` and revenue/profitability review without pretending the full fundamentals dataset is complete.

## Blockers

* Cash flow statement / capex source remains unconfirmed.
* Interest expense is not consistently available in the confirmed general-industry OpenAPI fields.
* Industry-specific statement variants require separate mapping before broad ingestion.
* Five-year derived fields need historical series collection and formula tests before apply.

## Verification

Commands used:

* `curl -s https://openapi.twse.com.tw/v1/swagger.json`
* `curl -s https://www.tpex.org.tw/openapi/swagger.json`
* Local Node parsing of official Swagger specs.

Docs sanity command:

```bash
rg -n "F7|t187ap06|t187ap07|cash flow|report-only candidate|blocked" backend/docs/ai_tasks/F7_official_financial_statement_source_decision.md backend/docs/current_rules.md backend/docs/ai_tasks/loop_state.md
```
