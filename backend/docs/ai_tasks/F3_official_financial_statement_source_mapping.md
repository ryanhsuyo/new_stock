# F3 Official Financial Statement Source Mapping

Phase: Official financial statement source mapping for 11 required fundamentals fields

Goal:

Map each required fundamentals field to an official source decision and formula before building any more ingestion. This prevents fabricated or weakly sourced fundamentals from entering `fundamentals.csv`.

Current result:

* Direct official report feeds are available for PE / dividend / dividend yield / P/B reference data.
* TWSE listed monthly revenue YoY / cumulative YoY is available as a neutral report.
* A stable machine-readable financial statement source is not yet confirmed.
* Direct curl probes to MOPS financial statement pages returned a security block page, so MOPS financial statement ingestion is blocked until a safer official data path is confirmed.

## Field Mapping

| Field | Status | Official source decision | Formula / mapping | Current action |
| --- | --- | --- | --- | --- |
| `roe_5y_avg` | derived_blocked | Needs official annual income statement and balance sheet for net income and equity. MOPS page exists conceptually but direct probe was security-blocked. | Average of annual ROE for 5 years. Prefer `net_income / average_equity`; use one convention consistently and document it. | Blocked until official financial statement source is confirmed. |
| `operating_margin_5y_avg` | derived_blocked | Needs official annual income statement for operating income and revenue. | Average of `operating_income / revenue` for 5 years. | Blocked until official financial statement source is confirmed. |
| `free_cash_flow_positive_years` | derived_blocked | Needs official cash flow statement for operating cash flow and capital expenditure. | Count years where `operating_cash_flow - capital_expenditure > 0` over latest 5 years. | Blocked until official cash flow source is confirmed. |
| `operating_cash_flow_to_net_income` | derived_blocked | Needs official cash flow statement and income statement. | Prefer 5-year average of `operating_cash_flow / net_income`, with skip reason for negative or zero net income. | Blocked until official financial statement source is confirmed. |
| `debt_to_equity` | derived_blocked | Needs official balance sheet for total liabilities and total equity. | Latest annual `total_liabilities / total_equity`. | Blocked until official balance sheet source is confirmed. |
| `interest_coverage` | derived_blocked | Needs official income statement for operating income and interest expense. | Latest annual or 5-year conservative average `operating_income / interest_expense`; define zero-interest handling before applying. | Blocked until official income statement source is confirmed. |
| `revenue_growth_5y_cagr` | derived_partial | TWSE listed monthly revenue report can support listed-company revenue reference, but current slice only captures one month. Needs multi-year annual revenue or month aggregation. TPEx monthly revenue source is still missing. | `(latest_annual_revenue / revenue_5_years_ago) ** (1 / 5) - 1`. | Do not fill yet; first build multi-year official revenue source for TWSE and TPEx. |
| `eps_growth_5y_cagr` | derived_blocked | Needs official annual EPS series or enough income/share data to compute EPS. | `(latest_eps / eps_5_years_ago) ** (1 / 5) - 1`, with negative or zero base handling documented. | Blocked until official EPS source is confirmed. |
| `pe` | direct_partial | TWSE `BWIBBU_ALL.PEratio` can map to `pe` for listed symbols. TPEx `afterTrading/peQryDate` can produce PE reference for OTC symbols, but is currently report-only. | Direct value. Treat `N/A` / blank as missing. | TWSE listed can safely fill priority CSV; TPEx needs explicit merge rule before filling. |
| `fcf_yield` | derived_blocked | Needs free cash flow plus market cap. Market cap can come from official trading statistics or price/share data, but FCF source is not confirmed. | `free_cash_flow / market_cap`. | Blocked until cash flow and market cap source rule is confirmed. |
| `dividend_years` | derived_partial | TPEx report has current dividend year/reference values; TWSE BWIBBU has dividend yield only. Need multi-year official dividend history, likely MOPS dividend distribution source. | Count years with cash dividend or total dividend greater than zero over latest N years. | Do not fill yet; source map for multi-year dividends required. |

## Source Probes

Confirmed:

* TWSE listed PE / dividend yield / P/B reference: `https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL`
* TWSE listed monthly revenue: `https://openapi.twse.com.tw/v1/opendata/t187ap05_L`
* TPEx PE / dividend / dividend yield / P/B reference: `https://www.tpex.org.tw/www/zh-tw/afterTrading/peQryDate` via POST with `response=json`

Blocked or incomplete:

* MOPS financial statement pages probed with direct curl returned `FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED`.
* TPEx monthly revenue YoY source is not yet confirmed.
* Multi-year dividend history source is not yet confirmed.

## Decision

Do not attempt to fill all 11 required fields yet.

The safe next implementation phase should be one of:

1. Build an HTTP API wrapper around the existing official report outputs so the frontend can view status and trigger dry-run/report-only generation.
2. Investigate an official financial statement OpenData path that is machine-readable and does not require scraping security-blocked MOPS pages.
3. Add a TPEx monthly revenue source if a stable official JSON endpoint is confirmed.

## Verification

Docs-only phase. No production logic changed.

Sanity checks:

```bash
rg -n "F3|roe_5y_avg|official financial statement|derived_blocked" backend/docs/ai_tasks/F3_official_financial_statement_source_mapping.md backend/docs/current_rules.md backend/docs/ai_tasks/loop_state.md
```
