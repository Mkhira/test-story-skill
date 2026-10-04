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
  normalised to Western digits when the app does that, e.g. in a shared base input).
- Mixed Arabic letters + digits in free-text inputs.
- RTL mirroring: back arrows, chevrons, row order, alignment, icons that carry direction.
- Long Arabic text: labels and values that wrap or truncate.
- Server messages asserted in the run's language (`Accept-Language`); a server text that stays in
  the other language is a finding, not a flow error.
- Missing translation keys: a raw key (`feature.section.label`) visible on screen.

## Beyond the story (always proposed; the user may skip)

- Accessibility labels on interactive elements; touch targets ≥ 44 pt (iOS) / 48 dp (Android).
- No network (airplane mode) on the main action — Manual on iOS (Maestro's `setAirplaneMode` is
  Android only; the iOS simulator has no airplane switch), Auto on Android.
- Double tap on submit / primary action → one request only.
- Back navigation mid-flow and after success.
- Keyboard covering the focused input or the primary button.
- App sent to background and brought back during loading and mid-form.
- Dark mode rendering of the feature's screens — the agent switches the device before the case
  (`xcrun simctl ui <udid> appearance dark` / `adb shell cmd uimode night yes`) and back after;
  a flow cannot. Mark it `needs-dark-mode` in Tags and run it after the suite like
  `cleanStateLast`, or Manual.

## OTP and other codes sent to a person

Automate a step that needs a code (SMS / email OTP) only when the test environment has a fixed
code the user gives as test data (e.g. a static staging OTP). Otherwise the case is Manual, or
the user types the code during an assisted pause; never read a real person's messages.

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
cases that use it (list every case, or a range "TC-09 … TC-15"). Synthetic values that only
break a rule go in the Value column. Real test-environment values go in the git-ignored
`<story>/test-data.local.json` and the Value column says `local`. A value that differs per
language: `KEY_AR` and `KEY_EN` rows, used in flows as `${KEY}`. Generic free text (e.g. "abc",
"مرحبا") may be written directly into steps.

## Checks in flows

Every assertion of an expected result carries `label: "EXPECT …"` — including "is visible",
"is disabled" and "is not visible" checks, and the wait that is itself the check (the code sheet
opens). Navigation and setup waits never do. `flow_sync.py lint` refuses a case flow without one.

## Case IDs

`TC-01`, `TC-02`… in AC order, then beyond-the-story cases. IDs never change once approved; new
cases in re-run mode continue the sequence.
