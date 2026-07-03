# F48 Signal Alert Block-First Preview

Status: completed

Purpose:

Make Daily Check signal alert blockers easier to act on by showing block
alerts first in `action_payload.preview_items` and including each alert's
backend-owned action label.

## Problem

`signal_alerts.json` can contain many items. Daily Check currently previews the
first five raw alerts, which can mix info / warn items before all block items
are visible. When signal alerts block trade outputs, the first screen should
show the highest-severity items first.

## Scope

Allowed:

* Sort signal alert preview items by severity: block, warn, info.
* Include `action_label` in preview text.
* Add details counts by severity.
* Add focused Daily Check tests.

Not allowed:

* Do not change strategy rules.
* Do not change signal alert generation semantics.
* Do not modify trades, holdings, or cash.

## Tasks

1. Add failing test for block-first signal alert previews.
   Status: done

2. Implement block-first preview and action label display.
   Status: done

3. Run focused Daily Check tests.
   Status: done

4. Run full backend tests and update loop state.
   Status: done

## Acceptance

* Daily Check signal alert preview items show block alerts before warn/info.
* Preview items include the backend action label, such as `先復盤風險`.
* Full backend tests pass.
