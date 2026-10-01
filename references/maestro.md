# Maestro flows (Phase 5)

Proven on Maestro 2.11.0, iOS 26.2 simulator, ZATCA Expo dev build (30 Sep 2026).

## Layout

```
<story>/e2e/
├── subflows/
│   ├── go-to-feature.yaml      # cold start → deep link (or tap path) → wait for a feature element
│   ├── set-language-en.yaml    # switch in app, cold relaunch, wait for home
│   └── set-language-ar.yaml
└── TC-04_valid_tin_shows_details.yaml   # one per approved Auto case: TC-xx_<title slug>.yaml
```

Start every case flow from `templates/flow.template.yaml`. After writing or regenerating a case
flow, run `flow_sync.py stamp <test-cases.md> <flow>`; never hand-write the header lines.

## Conventions

- `appId` from Phase 0. Never `clearState` except in `needs-clean-state` cases.
- Every case starts with `- runFlow: subflows/go-to-feature.yaml`.
- **Cold start per case.** `go-to-feature` begins with `launchApp: {stopApp: true}`: a deep link
  alone reopens the existing screen with its old form state, so the previous case leaks in. The
  session survives a cold start (M0).
- After arriving, wait for a feature element with `extendedWaitUntil` (≤ 30 s).
  `waitForAnimationToEnd` returns mid-transition.
- Selectors: `id:` (testID) first, `text:` only as a fallback.
- Test data: `${KEY}` from the Test data table, passed by `run_flow.sh --data`. Never write a
  value into a flow.
- Language-dependent text: `LANG_CODE` is passed by `run_flow.sh` (`en` / `ar`). Always double-quote
  the whole expression, or the `: ` in the ternary breaks YAML parsing:
  `- assertVisible: "${LANG_CODE == 'ar' ? 'هذا الحقل مطلوب' : 'This field is required'}"`
- Screenshots: `takeScreenshot: TC-04_step3` (a bare name). Maestro 2.11 rejects absolute paths and
  paths outside `--test-output-dir`; `run_flow.sh` copies them to `<runDir>/<lang>/` (kept until
  the Phase 8 prune, for triage and Figma capture), then deletes Maestro's temp output.
- One screenshot per step that has an expected result, taken after its assertion.

## Expected-result checks and waits

- Every step that checks the case's expected result carries `label: "EXPECT stepN: <short
  expected>"` (map form: `- assertVisible: {text: …, label: …}` or inside `extendedWaitUntil`).
  `parse_results.py` reads the failed step's label: `EXPECT` → `failKind: check`, which
  `run_suite.py` never retries (it already waited on a settled screen). Navigation and setup waits
  have no label → `failKind: flow`, retried once. In the first real run every one of 25 retries of
  a failed check failed again and the retries took about an hour.
- Timeouts by what is awaited:
  - local UI / validation message / enabled state: `timeout: 5000`
  - right after a server call (verify, submit, search): `timeout: 15000`
  - arrival on a screen after navigation or launch: `timeout: 30000` (cold launch: 60000)
- "Must not appear": `waitForAnimationToEnd`, then `assertNotVisible` (labelled `EXPECT`); never a
  long `extendedWaitUntil: notVisible`.

## Language order

One device: `run_suite.py --lang ar --setup` first, then (after the user's English choice)
`--lang en --setup` with the chosen cases. `--setup` switches the language once per suite, not per
case. A parallel English run on a second device (`clone_device.sh`) is possible only on request:
both apps share one Metro and append to the same `results.json` under a lock.

## Text matching

- Text selectors are full-string regexes. Cards, buttons and pressables that group their
  children expose ONE accessibility text joined with ", " (e.g.
  `"Total Price value, 115.00, Total amount including Value Added Tax"`), so match with
  `".*Total Price value.*"`, or use a testID.
- Escape regex characters in expected values: `".*115\\.00.*"` (YAML double quotes need `\\`).
- Alternatives for either language: `"Menu|القائمة"`.

## Gotchas

| Symptom | Cause | Do |
| --- | --- | --- |
| `Couldn't hide the keyboard` | `hideKeyboard` fails in some RN apps on iOS | tap a neutral element (a title) instead |
| Tab tap does nothing | dev LogBox bar ("Open debugger to view warnings.") covers the tab bar; it is not in the hierarchy | `retryTapIfNoChange: true`; if still blocked, tap the bar's × (leading side) |
| `Parsing Failed at …:7:50` | unquoted `${…}` containing `: ` | quote the whole value |
| Assertion false but text is on screen | grouped accessibility text | `.*text.*` or testID |
| Previous case's input still there | deep link reused the screen | cold start in `go-to-feature` |
| Eastern digits typed as Western | app normalises digits (e.g. `useBaseInput`) | expect the normalised value |
| App switches to another app (or SpringBoard) during a long failing wait; failure capture shows the wrong app | iOS "◀ <other app>" back-link: the app was opened while another app was frontmost | terminate other running apps before each case (`xcrun simctl terminate booted <id>`); note it in run-info |
| Tap on a button that becomes enabled after a pick does nothing | the CTA enables a moment later; the first tap is swallowed | `extendedWaitUntil: {visible: {text: …, enabled: true}}` then `tapOn: {text: …, retryTapIfNoChange: true}` |
| Text tap lands on the label, not the input | form builder fields repeat the label as the input's accessibility text | `index: 2` when the placeholder equals the label (label, input, inner); otherwise tap the placeholder text; ambiguous radio/label/input trios → `point:` tap |
| Date wheel: tapping a year/month far from the selection closes the sheet | off-screen wheel rows are in the hierarchy but not tappable | keep the default (today) and tap Select, or swipe the wheel |
| Searchable dropdown: tapping the result hits the search box | the box holds the typed text too | close the keyboard (tap the sheet title), `waitForAnimationToEnd`, then `tapOn: {text: …, index: 1}` |
| Two consecutive `maestro` commands lose the screen | Maestro backgrounds the app between invocations | do every check inside one flow; probe with a deliberately failing `assertVisible` to capture the hierarchy |
| Mixed Arabic letters + Eastern digits doubled | fast typing vs. per-keystroke rewrite | report as a finding; type the parts in two `inputText` steps to isolate |

## Subflow shapes

```yaml
# subflows/go-to-feature.yaml
appId: ${APP_ID}
---
- launchApp:
    stopApp: true
- extendedWaitUntil:
    visible: "<home marker en|ar>"
    timeout: 60000
- openLink: "<deep link>"
- extendedWaitUntil:
    visible: "<feature element en|ar>"
    timeout: 30000
```

```yaml
# subflows/set-language-ar.yaml (in-app switch + cold relaunch for native RTL)
appId: ${APP_ID}
---
- launchApp:
    stopApp: true
- extendedWaitUntil:
    visible: "<menu tab en|ar>"
    timeout: 60000
- tapOn:
    text: "<menu tab en|ar>"
    retryTapIfNoChange: true
- tapOn: "<Arabic option>"
- launchApp:
    stopApp: true
- extendedWaitUntil:
    visible: "<home marker ar>"
    timeout: 60000
```

`${APP_ID}` is shown for the template only: write the literal app id into the flow.

## Clean-state cases

```yaml
- clearState
- clearKeychain      # iOS: the login token lives in the keychain and survives clearState
- launchApp
```

Then the agent asks the user to log in (Phase 4 assisted login) before the rest of the case runs.
Split such a case into `…_a_reset.yaml` (reset only, run with `--no-record`) and the case flow
itself, so the login pause sits between them.
