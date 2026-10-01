# Story parsing (Phase 1)

Goal: every testable statement in the story becomes an AC; everything else becomes a
SPEC-GAP question. Never fill a gap with a guess.

## Extract first

| Part | Look for | Example |
| --- | --- | --- |
| Role | "As a…", who is logged in, account type | individual taxpayer, establishment |
| Screens | named screens, steps, tabs | "search screen", "details page" |
| Inputs | fields, their type and format | TIN (10 digits), date, attachment |
| Validation | required, length, format, ranges, cross-field rules | "TIN must start with 3" |
| Business rules | eligibility, states, limits, calculations | "only active taxpayers" |
| Messages | exact texts, toasts, empty states | "No results found" |
| Navigation | where each action leads, back behaviour | "after submit, show success" |

## Writing ACs

- One observable outcome per AC. Split "shows details and enables submit" into two.
- Given (state + role) / When (one user action) / Then (what the user sees or what is sent).
- Quote the story sentence exactly in the "Story source" column, even if it is clumsy.
- Keep the story's own terms; do not rename fields to code names.
- Implicit ACs (an error path the story implies but never words) are still SPEC-GAPs, not ACs.

## SPEC-GAP triggers

Mark `SPEC-GAP-n (AC-x)` with a concrete question when the story uses:

- Unmeasurable words: proper, appropriate, fast, user-friendly, valid, correct, etc.
- An error with no text: "shows an error" → which text, and does it differ by error type?
- A format with no rule: "valid ID" → length, prefix, checksum?
- A missing branch: success is described, failure is not.
- A time or number with no value: "after a while", "limited attempts".
- Conflicts between two sentences, or between the story and Figma.

Each gap question should be answerable in one line by a product owner.

## Slug

Kebab-case from the story title, at most five words, no stop words:
"As a taxpayer I want to search by TIN" → `search-by-tin`.
