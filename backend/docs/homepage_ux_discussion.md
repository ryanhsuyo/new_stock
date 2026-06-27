# Homepage UX Discussion: Reduce Text Density

Status: discussion draft  
Date: 2026-06-17  
Scope: Homepage / Dashboard information architecture only. No implementation yet.

## 1. Context

The current Dashboard has already moved toward a PM decision console, but the screen still feels text-heavy. The main issue is not missing data; it is that too many explanations, workflow details, warnings, and stock notes compete in the same visual layer.

OpenSpec check:

- No project-level `openspec/` directory was found.
- Existing project planning lives in `backend/docs/homepage_pm_roadmap.md` and `backend/docs/ai_tasks/*.md`.
- This document should be used as a discussion draft before creating a new implementation task.

## 2. External Product Patterns Reviewed

References checked:

- TradingView features: charts, alerts, watchlist alerts, screeners, fundamental metrics.
  Source: https://www.tradingview.com/features/
- Koyfin features: alerts, market dashboards, watchlists, custom dashboards, company snapshots.
  Source: https://www.koyfin.com/features/
- Yahoo Finance portfolio tracking overview via Investopedia: portfolio dashboard, benchmarks, custom metrics, alerts.
  Source: https://www.investopedia.com/articles/investing/092214/tracking-your-portfolio-yahoo-finance.asp

Common patterns:

- Use a compact top-level dashboard for "what changed" and "what needs attention".
- Keep watchlists and screeners dense, but make rows scannable with columns, chips, and short labels.
- Put deeper explanations behind detail pages, drawers, expanded rows, or chart drilldowns.
- Alerts focus on thresholds and next actions, not long prose.
- Dashboards work best when customized around the user's decision flow, not when every data source is visible at once.

## 3. Product Diagnosis

The Dashboard currently mixes four different jobs:

1. Decision console: Can I use today's data, and what should I do first?
2. Risk console: Which holdings are risky or need exit / stop review?
3. Research console: Which candidates are worth checking?
4. Maintenance console: Which files, scripts, notes, or reports are stale?

When all four jobs appear together with full explanations, the user has to read too much before acting.

## 4. Recommended Direction

Make the first screen a "Today Operating Console", not a report page.

The first screen should answer only:

1. Is the data usable?
2. What is the single most important action?
3. Are there holding risks today?
4. Are there high-quality candidates worth checking?

Everything else should be one click lower.

## 5. Proposed First-Screen Structure

### A. Status Strip

Keep it one line if possible:

- Data date
- Price basis: latest close, not realtime
- Trade output usability
- Stale / blocked indicator

Do not show long refresh commands here. Show a compact "needs refresh" action that expands or copies the command.

### B. Primary Action

Show only one action:

- Label
- Why it matters, one short sentence
- One main button
- Optional secondary "details" link

If there are multiple problems, PM Worklist can still contain them, but the top should not show multiple equal-priority warning cards.

### C. Today Focus

Use three lanes, each with max 3 items:

1. Holding Risk
2. Entry Candidates
3. Review / Maintenance

Each item should show:

- Stock code and name
- One status chip
- One key price or range
- One next action

Long reason text should move to details.

### D. Market Posture

Show a compact posture summary:

- Risk level
- Trend state
- Position sizing tone
- Manual note freshness

Avoid showing full manual note paragraphs on the first screen.

## 6. Text Budget Rules

Suggested hard limits:

- First-screen card title: max 12 Chinese characters.
- First-screen card body: max 1-2 lines.
- Primary action reason: max 40 Chinese characters.
- Today Focus item reason: max 24 Chinese characters.
- Table row visible reason: max 32 Chinese characters.
- Full explanations belong in detail views, expanded rows, or stock detail pages.

If the backend reason is long, the backend should provide both:

- `short_reason` for cards and rows.
- `reason` or `detail_reason` for drilldown.

The frontend should not summarize strategy logic by itself.

## 7. Candidate Table Changes

The candidate table should become scan-first:

- Freeze identity columns: code, name, market.
- Keep status chips short: ready, wait, review, blocked.
- Replace long "reason / no buy reason" text with a short reason plus "details".
- Move command-like maintenance information out of candidate rows.
- Keep detailed range, invalidation, and R/R visible because they support decisions.

Recommended visible columns: Stock, Status, Action, Entry range, Stop / invalidation, Target / exit, Score / risk, Details.

## 8. Information Placement

Keep on first screen: Status Strip, Primary Action, Today Focus, Market Posture.

Move below first screen: PM Worklist full details, Daily Check details, Update Workflow details, file health, fundamentals maintenance, full manual note text.

Move to detail pages or expanded rows: long stock reasons, full signal explanation, full daily checklist, price-level derivation, historical notes.

## 9. Backend Contract Implications

To support a cleaner UI without moving strategy logic into the frontend, the backend should eventually expose display-safe fields:

- `short_label`
- `short_reason`
- `primary_metric`
- `primary_price`
- `action_label`
- `detail_reason`
- `detail_url` or route hint
- `severity`
- `display_group`

This should extend existing contracts rather than replace them.

## 10. Suggested Implementation Phases

| Phase | Goal |
|-------|------|
| UX-01 | Define card and row display fields in backend docs. No UI change yet. |
| UX-02 | Add short display fields to PM Worklist / Today Focus / candidate report services. |
| UX-03 | Adjust Dashboard to render compact cards from backend-provided display fields. |
| UX-04 | Reduce candidate table row text and move long explanations to details. |
| UX-05 | Verify desktop and mobile screenshots for readable first screen, no overflow, holding risk first, and maintenance details below primary decisions. |

## 11. Discussion Questions

1. Should the homepage become strictly "today's operating console", with reports moved lower?
2. Should commands and file health be hidden by default unless data is blocked?
3. Should stock details open as a drawer, modal, or existing detail page?
4. For candidate rows, do you prefer fewer columns with expandable detail, or a dense table with horizontal scan?
5. Should manual market notes show only posture on the first screen, with full text below?

## 12. Recommended Next Step

Before implementation, create a small AI task file for `UX-01`:

- Confirm final first-screen sections.
- Define `short_reason` / `detail_reason` contract.
- Decide whether stock details should use drawer, modal, or route.
- Then implement only one UI slice at a time.
