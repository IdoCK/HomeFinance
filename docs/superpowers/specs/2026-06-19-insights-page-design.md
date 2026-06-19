# Plan 10 — AI Insights Page Design

> Page-level addendum to `2026-06-18-finance-ui-rewrite-design.md` (§3 showpiece, §7 API, §5 teaser).
> Covers the **AI Insights** page + its backend router. Locked decisions below.

## Goal
The one place in the app that spends its boldness: a glassy gradient **showpiece** that turns
the household's anonymized aggregates into coaching text from Anthropic. Reuses
`modules/ai_insights.py` unchanged. Privacy is the headline feature, not a footnote.

## Signature (where the boldness is spent — spec §3.3)
The **glassy gradient hero** — the only surface in the whole app allowed the showpiece gradient
`#FDBA74 → #F472B6 → #A855F7 → #3B82F6`. Everything else on the page stays quiet (soft cards,
neutral chrome). The hero carries the page title + the privacy promise + the Generate action.

## Privacy model (carried verbatim from the engine)
Only anonymized **aggregates** ever leave the machine — category totals, monthly savings,
month-over-month %, goal progress %. Never raw transactions, merchants, names, or notes. The
two people are sent as "Person A" / "Person B" / "Household". The page must show **exactly**
what would be sent (`ai_insights.preview_payload`) before any call goes out, in a disclosure.

## Persona model
- **Joint** (`person_id` omitted): household — one summary per person ("Person A", "Person B")
  plus a "Household (shared goals)" summary over all transactions + shared goals. (Mirrors
  `app.py` household branch.)
- **You / Spouse** (`person_id` set): a single "Person A" summary for that person.

## Backend contract — `backend/api/insights.py` (prefix `/insights`)
- `GET /api/insights/preview?person_id=<int?>` → `{ payload: str, has_key: bool }` where
  `payload` is `ai_insights.preview_payload(summaries)` (the exact JSON to be sent) and
  `has_key` reflects `ANTHROPIC_API_KEY` presence (drives the button's enabled state).
- `POST /api/insights/generate` body `{ person_id?: int }` → `{ text: str }` from
  `ai_insights.get_insights(summaries)`. Without a key the engine returns a preview-mode
  message (graceful) — still a valid `text`, so the endpoint never errors on a missing key.

Summaries are built with `ai_insights.build_anonymized_summary(label, txns, goals, analytics)`.

## Frontend (`web/src/pages/Insights.tsx`)
- **Glassy hero**: gradient showpiece card — title "What the numbers say", the privacy line,
  and the **Generate insights** button (label stays "Generate insights" → result; disabled with
  an inline note when `has_key` is false: "Set ANTHROPIC_API_KEY to enable live insights").
- **"See exactly what's sent"** disclosure (`<details>`): the `payload` JSON, monospace.
- **Result**: the returned coaching text in a quiet frosted card. Rendered as pre-wrapped text
  (v1 — see deferrals). Loading + empty states.

## Out of scope / deferred (ponytail)
- Rich markdown rendering of the result (v1 = `white-space: pre-wrap`; no markdown dep).
- Persisting/caching insights (engine returns fresh text; no store — matches `app.py`).
- The Overview "latest insight teaser" (§5) — Overview already shipped; wire later if wanted.
