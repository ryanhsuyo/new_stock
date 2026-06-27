# Homepage Visual Acceptance

Purpose:

Use this checklist after Dashboard or homepage CSS changes. It verifies that the first screen is readable and that decision priority is not hidden by secondary details.

## Preconditions

* Backend API is reachable on port 9000.
* Frontend dev server or production build is reachable.
* Data may be ready, stale, or blocked; the checklist accepts all states if the UI explains the state clearly.

## Desktop First Screen

Pass if the first screen shows:

* Status Strip with data date, trade output status, price basis, and last update.
* Price basis says latest close / non-realtime price.
* One Primary Action is visually dominant.
* Market Posture is a short summary, not long manual-note prose.
* Today Focus puts holding risk before candidates.
* PM Worklist begins below the Decision Console.

Fail if:

* Multiple red warnings compete as equal primary actions.
* Candidate stocks appear as buy-now actions while trade outputs are blocked.
* Manual-note long text pushes Primary Action or Today Focus out of view.
* Text overlaps or spills outside cards.

## Mobile First Screen

Pass if narrow screens prioritize:

1. Status Strip
2. Primary Action
3. Today Focus
4. Market Posture
5. PM Worklist details

Fail if:

* Cards remain side-by-side.
* Primary Action appears below PM Worklist details.
* Long reason text makes the first screen hard to scan.

## Candidate Report

Pass if:

* Daily action and detail navigation are easy to find.
* Long no-buy/risk text is visually constrained by default.
* Full text remains available through title tooltip or expansion controls.
* Price plan columns clearly show entry, stop, and target when available.

## Evidence To Record

* URL checked.
* Data date / status shown.
* Browser or viewport used.
* Any limitation, such as unavailable mobile viewport control.
