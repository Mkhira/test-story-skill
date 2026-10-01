# Test design (Phase 3)

Every case is end-to-end on a device and runs in both en and ar unless marked otherwise.
Expected results are observable on screen (or in the network log) and come from an AC, a
beyond-the-story rule, or the story's own wording. Never invent a number, a timing or a text.

## Story-driven techniques

| Technique | Produces |
| --- | --- |
| Happy path | one Positive case per AC |
| Equivalence classes | one case per valid class and per invalid class of each input |
| Boundary values | min-1, min, max, max+1 for every stated length or range |
| Negative inputs | empty, spaces only, wrong format, special characters, pasted text |
| State transitions | each allowed transition, and one forbidden one per state |
| Screen states | empty, loading, error, and populated states the feature has |
| Server errors | each error code the code handles, and one it does not |

Use the rule from the story or code for boundaries. If neither gives a value, write a
SPEC-GAP instead of guessing.

## Expected texts

Quote the exact en and ar text from the Phase 2 message map (app translation key, CMS /
service-message key, or server). Write both in Expected (`en: "…" · ar: "…"`) with the source,
e.g. `(CMS e-signup/NID_PREFIX)`. A server text known only after a call → expect the app's
behaviour (a message appears under the field) and record the text the run sees. Never paraphrase:
a wrong expected text becomes a Test error (expectation) after an hour of running.

## Bilingual checks (always)

- Arabic letters in text inputs; Eastern Arabic digits (٠-٩) in numeric inputs (expect them
  normalised to Western digits when the app does that, e.g. ZATCA `useBaseInput`).
- Mixed Arabic letters + digits in free-text inputs.
- RTL mirroring: back arrows, chevrons, row order, alignment, icons that carry direction.
- Long Arabic text: labels and values that wrap or truncate.
- Server messages asserted in the run's language (`Accept-Language`); a server text that stays in
  the other language is a finding, not a flow error.
- Missing translation keys: a raw key (`feature.section.label`) visible on screen.

## Beyond the story (always proposed; the user may skip)

- Accessibility labels on interactive elements; touch targets ≥ 44 pt (iOS) / 48 dp (Android).
- No network (airplane mode) on the main action.
- Double tap on submit / primary action → one request only.
- Back navigation mid-flow and after success.
- Keyboard covering the focused input or the primary button.
- App sent to background and brought back during loading and mid-form.
- Dark mode rendering of the feature's screens.

## Mode, type, priority, tags

- **Mode:** `Auto` (Maestro) or `Manual` (camera scan, push, biometrics, Nafath approval,
  anything the simulator cannot do). Manual cases give steps and the reason.
- **Type:** Positive, Negative, Boundary, State, Bilingual, Accessibility, Resilience, Design.
- **Priority:** P1 = the story's main AC path; P2 = other ACs and their negatives; P3 = beyond
  the story.
- **Tags:** `needs-clean-state` when the case needs a logged-out or first-launch app
  (`clearState` + `clearKeychain`, then the user logs in again). Use it sparingly.

## Timing

One global element wait covers loading. No case asserts a duration unless the story states
one, and then the case quotes the story sentence.

## Test data

Every identifier is a placeholder `{{KEY}}` in the Test data table with its meaning and the
cases that use it. Values are real test-environment data the user fills in. Generic free text
(e.g. "abc", "مرحبا") may be written directly into steps.

## Case IDs

`TC-01`, `TC-02`… in AC order, then beyond-the-story cases. IDs never change once approved; new
cases in re-run mode continue the sequence.
