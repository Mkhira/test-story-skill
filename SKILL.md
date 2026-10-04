---
name: test-story
description: "Turn one user story and one React Native (Expo) feature into approved end-to-end test cases, run them with Maestro on an iOS simulator or Android emulator in English and Arabic, and write a bug-and-gap report into the feature folder. Use when the user runs /test-story, or asks to test a user story / feature end to end on a simulator or emulator, generate test cases from a story, or produce a QA report for a feature. Also use when the user says 'retest', 're-test', 'test again after the fix' or 'run the failed cases again' for a story or feature that was already tested: retest mode re-runs only the failed cases."
user-invocable: true
argument-hint: "<story path or pasted text> <feature path or name> | retest <story folder or feature>"
---

# test-story

`/test-story <story> <feature>` → `<feature>/test-stories/<story-slug>/test-cases.md` (approval file)
→ after approval: Maestro runs Arabic on one device, then asks whether to run English (all /
message checks only / skip) → `test-report-<runId>.md` in the same folder.

`/test-story retest <story folder | feature>` (or the user says "retest") → **Retest mode** below:
only the case × language pairs that failed in the latest run are run again.

Build status: all phases are live and validated on a real feature (a bilingual sign-up flow, iOS,
en + ar): full run (M6, 2026-10-01), then M7 live in two retests (2026-10-01, 2026-10-04):
Arabic first, EXPECT checks not retried, retest scope, run clean-up. M8 (2026-10-04: failKind
`app`, fail fast on a shared blocking step, "blocked" pairs in the report, flows committed)
is verified offline against the 2026-10-04 run's data (its report was built live with the
blocked rows). M9 (2026-10-05: flow lint, deep smoke, subflow-grouped order, INCOMPLETE verdict,
local test data, masked metro.log) is verified offline. M10 (2026-10-05: build check against
the native fingerprint, `verified` only for verifier-seen findings, documented `steps`) is
verified offline on the 2026-10-04 run's data and the live device record. M11 (2026-10-05:
"Code tested" and skill version in the report, skill-change guard exit 7, `run_app.sh --stop`)
is verified offline plus a live `--stop`. Not yet run on Android.

Scripts live in `scripts/` next to this file (`S=~/.claude/skills/test-story/scripts`). Run them
from the project root; each prints JSON.

## Hard rules

1. Never run a test, or change code, before the user approves `test-cases.md`. Never run a case marked `skip`.
2. Expected results come only from the approved `test-cases.md`. Never change an expected result or weaken an assertion to make a case pass.
3. The only production changes allowed are approved `testID` props and approved `testID` pass-through props on shared components. Every one is listed in the report.
4. Never invent real-looking data (TIN, national ID, phone, IBAN). Use only the values the user entered. Real values (they exist in the test environment) go to the git-ignored `<story>/test-data.local.json`, never into a committed file; the Test data table says `local`.
5. Never guess when you can ask: feature match, login, OTP, missing data, unclear language switch.
6. Every failure gets exactly one classification; nothing reaches the report unclassified.
7. Every bug cites its AC (or its beyond-the-story rule), a screenshot, the network evidence when available, and the file and line when found.
8. Mask tokens, `Authorization` headers and config secrets (`clientSecret`, encryption keys) from logs before writing them anywhere; mask PII fields in any network excerpt written to the report. The kept `metro.log` is rewritten masked by the Phase 8 prune.
9. `test-runs/` inside every story folder is git-ignored before the first file is written into it. `e2e/` flows are committed (teammates re-run them; the hashes catch hand edits).
10. Never assert a duration the story does not state.
11. Never overwrite a hand-edited flow without asking.
12. Never commit or push.
13. Always write the report, even for an aborted run, with the reason.

## Outputs

```
<feature>/test-stories/<story-slug>/
├── test-cases.md                 # approval file (committed)
├── test-data.local.json          # real test values (git-ignored), when there are any
├── test-report-<runId>.md        # one per run (committed)
├── e2e/                          # Maestro flows (committed, Prettier-formatted), synced each run
└── test-runs/<runId>/            # git-ignored; <runDir> below
    ├── en/  ar/                  # during the run: step + failure shots; after prune: *_fail*_annotated.png
    ├── figma/                    # exported Figma frames
    ├── figma-dd/                 # DD-nn.png side-by-sides (app vs Figma)
    └── artifacts/                # results.json, triage.json, run-info.json, data.json, metro.log
```

## Retest mode

When the user says "retest" (after fixes), run ONLY what failed last time:
1. Find the story folder (a feature with several stories → ask which). Latest run = the newest
   `<story>/test-runs/<runId>/` with `artifacts/results.json`. It has no `test-report-<runId>.md`
   → finish it first (Phase 0 step 6): a retest needs its triage for the before → now table.
   Platform and device: reuse the latest run's (run-info), no question.
2. `$S/parse_results.py failed --results <latest>/artifacts/results.json` → `pairs` (case ×
   language whose final attempt failed, plus scope pairs that never ran). Empty → tell the user
   nothing failed; stop.
3. Show the pairs (case, language, last error) in a short table and go on; no question. A
   `test-cases.md` changed since that run → re-run mode rules (Phase 3) apply to the changed cases
   first; a failed case the user set to `skip` is dropped.
4. New run id; run-info gets `retestOf: <latest runId>` and `scope: [{case, lang}, …]`.
5. Phases 0, 4–6 and 8 as usual (Phase 7 Figma is skipped: run-info `figma` = `"not run: retest"`), limited to the scope: `run_suite.py --cases` per language gets only that
   language's failed cases, Arabic first; no English question (the scope already decides).
   Pairs skipped by the user last time are not failures, so they are not retested. Triage only
   what still fails; carry over the previous finding (same id, new evidence) when the failure is
   the same.
6. The report shows a before → now table and counts only the scope: `fixed`, `still failing` (the
   check ran and failed again), `blocked — check not reached` (the case stopped earlier, so the
   fix is unverified) or `not run`. Blocked and not-run pairs come back in the next retest.

## Run folder

`<runId>` is local time `YYYY-MM-DD_HHMM`. Maestro's raw output goes to
`$TMPDIR/test-story/<runId>/` and is deleted after each case, so the run folder stays small
(the simulator log alone is 20–70 MB per attempt). After the report data is complete,
`prune_run.py` cuts the run folder to the annotated failures, the Figma images and the JSON.

## Phase 0 – Preflight

1. **Expo project?** `expo` in `package.json` and an `app.json` / `app.config.*`. Read iOS
   `bundleIdentifier` and Android `package` (Maestro `appId`). Not Expo → stop and say so.
2. **Platform:** ask with a multiple-choice question: iOS simulator or Android emulator (retest:
   reuse the previous run's platform, no question).
3. **Project run skill:** look for a repo skill that runs the app (e.g. `.claude/skills/run-myapp/`).
   When present, read it; device boot, build, Metro, deep links and Maestro facts follow it, and
   so do the app facts Phase 2 needs (language switch, path to a feature, message sources, error
   dialog, network log format, environment, logged-in marker). Project facts live there, never in
   this skill. Phase 2 found one that the run skill lacks → offer to add it there.
4. **Tools:** `$S/preflight.sh <platform>`. `installable` lists what the skill may install
   (`maestro`, `java17`): ask once, then re-run with `--install-maestro` / `--install-java`.
   `manual` lists what only the user can install (Xcode, SDK, AVD) → stop with those steps before
   Phase 4 (Phases 1–3 can still run).
5. **Leftovers:** `$S/prune_run.py --stale-tmp` deletes temp Maestro output that a crashed or
   killed run left in `$TMPDIR/test-story/` (untouched for 6 hours).
6. **Resume check:** a `<story>/test-runs/<runId>/artifacts/results.json` with no
   `test-report-<runId>.md` → run `$S/parse_results.py status --results <it> --cases <approved Auto
   ids>` (an interrupted retest is limited to its own `scope` automatically). `todo` non-empty →
   ask: "Continue that run (Recommended)" (only the `todo` pairs, `run_suite.py --cases` per
   language) or "Report what ran" (Phases 6 and 8 with `--aborted "stopped: <n> pairs not run"`).
   `todo` empty → the run finished but was never reported (a crash or closed terminal after the
   last case): ask "Triage and write its report now (Recommended)" before anything else.
7. **Run id**, `run-info.json` (start it now: runId, story, feature, featurePath, platform, and
   later fields as they become known — see `references/report-rules.md`) and `.gitignore`:
   `git check-ignore -q <story>/test-runs/x`, then `git check-ignore -q
   <story>/test-data.local.json`; not ignored → add `test-runs/` / `test-data.local.json` before
   writing either. Do not ignore `e2e/`: the flows are committed with the cases. Then
   `$S/run_meta.py skill --run <runDir>`: the skill's commit and scripts hash, which
   `run_suite.py` checks before every case (exit 7 below).

## Phase 1 – Intake

Read `references/story-parsing.md` first.

1. **Story:** an existing path → read it; otherwise the argument is pasted text; nothing → ask.
2. **Feature:** an existing folder → use it. A name → search `src/features/` and legacy
   `src/presentation/` (other projects also `features/`, `app/`, `src/modules/`), show the
   matches, ask the user to confirm one. A story spanning several features → ask which folder
   owns it; the others are traced in Phase 2 and their bugs go to "Outside feature scope".
3. **Story folder:** slug from the story title (kebab-case, ≤ 5 words). An existing folder with a
   `test-cases.md` whose status is `APPROVED` → re-run mode (Phase 3).
4. Extract role, screens, inputs, validation rules, business rules, messages, navigation.
5. Write ACs `AC-1…` in Given / When / Then, each with the exact story sentence it came from.
6. Vague ACs become `SPEC-GAP-n` with the question they raise.

## Phase 2 – Analyze

Read-only. No device.

1. **Map the feature:** routes/screens, controller/hooks, use cases, repositories, services and
   endpoints, field configs and validation, i18n keys (feature `translations/en.ts` / `ar.ts` and
   the global `en.json` / `ar.json`).
2. **Trace each AC** to file:line → `Implemented` / `Partial` / `Missing`.
3. **Static gaps:** ACs with no code; behaviour the story never mentions; API errors with no UI
   handling; keys in en but not ar (and the reverse); hard-coded visible strings.
4. **Language switch:** find how the app changes language: where the control is, whether text
   switches live or needs a reload, whether native RTL needs a cold relaunch, whether the session
   survives. Find how the backend picks its language (usually `Accept-Language`); server texts are
   then asserted per language. Run skill first; unknown → ask once.
5. **Path to the feature:** a deep link first (the app's scheme and the route or id that opens the
   feature, from the run skill or the linking config / deep-link map), else the tap path from
   home. Note the feature element to wait on after arrival.
6. **testID audit:** every element a case touches that has no `testID` → a row with a kebab-case id
   `<feature>-<screen>-<element>` in the repo's existing style. If the element is rendered by a
   shared component that does not forward `testID`, add a separate pass-through row for that
   component. Nothing is edited now.
7. **Message map:** for every text a case will assert (validation, success, error), find its
   exact en and ar wording and source: app translation key (feature `translations/en.ts` /
   `ar.ts`, global `en.json` / `ar.json`), CMS / server-message catalog key (its local default and
   the endpoint that overrides it at runtime), or server response (unknown until the run). Expected results quote these texts; never paraphrase. A
   story text that differs from the app's text is a static finding, asked as a spec gap.
   Also note the app's generic error-dialog titles in en and ar (the translation key behind the
   app's error popup) → run-info `appError` (a regex, e.g. `Something went wrong|<ar title>`),
   passed to `run_suite.py --app-error`.
8. **Network log format:** find how the app logs API calls to the console. `net_log_extract.py`
   reads by default `[HttpClient]` lines with `→ <METHOD> <url>` / `← <status> <path>` and a
   `"language"` field. Another format → run-info `network: {tag, reqRe, resRe,
   langField}` (regexes with groups method, url / status, url), passed to `net_log_extract.py`. No
   API logging at all → the gap "network calls not visible" (adding a logger is a code change: it
   is not the skill's to make).
9. **Environment:** read which env the running build uses (the env files Expo loads, the API base
   URL, a config log line at startup — mask secrets in it). Shown at approval and in the report;
   no gate.

## Phase 3 – Test cases and approval

Read `references/test-design.md` and fill `templates/test-cases.template.md`.

**New story:** write the full suite: every AC, beyond-the-story checks, manual cases for
device-only steps. Status `AWAITING APPROVAL`.

**Re-run mode** (approved file exists):
1. Keep every approved case, its ID and its data unchanged.
2. Re-analyse; append only new or changed proposals marked `NEW` / `CHANGED` with a one-line reason.
3. No proposals → no approval needed (go to Phase 4 once built). Otherwise ask for approval of the
   marked items only.

**Approval loop — ask, don't make the user edit the file**

The user answers questions; the skill writes the answers into `test-cases.md`. Editing the
file by hand stays possible but is never required.

1. Tell the user in 3–5 lines: the file path, case counts by type and mode, the active
   environment, and that you will now ask for what is missing.
2. **Test data:** one AskUserQuestion per `{{fill}}` key, up to 4 per call, in the order of the
   Test data table. Question: the key's meaning and the cases that use it. Options (2–4):
   - for values that must be real (IDs, mobiles, emails, CRs, accounts): "Skip the cases that
     use it" and "Leave it for later" — the user types the value through "Other". A typed real
     value goes into `<story>/test-data.local.json` (`{"KEY": "value"}`) and the table's Value
     says `local`; never write it into `test-cases.md` (committed);
   - for values that only need to break a rule (wrong prefix, too short, bad format): offer
     1–2 obviously synthetic values that cannot be a real identifier (e.g. `123456789` for a
     9-digit ID, `2000000000` for a wrong National ID prefix), each labelled with why it fails,
     plus "Skip the cases that use it".
   Write each answer into the table's Value column; "Skip…" sets those cases to `skip` (every
   case in Used by — `flow_sync.py data` expands ranges such as "TC-09 … TC-15"); "Leave it for
   later" keeps `{{fill}}`. A value that differs per language: two keys `KEY_AR` / `KEY_EN`; the
   flow uses `${KEY}` and gets the run's language variant.
3. **Choices that change the run** (one call, ≤ 4 questions): the testIDs, cases that send real
   SMS/email or create records, any case the user may want to skip. Apply the answers to the file.
   testIDs: say in plain words that this edits feature files (a `testID` prop on the listed
   elements, nothing else) and recommend it whenever flows would otherwise tap by text — text
   selectors change per language and with CMS wording and caused every test error in the first
   real run. Options: "Add the testIDs (Recommended)", "No code changes — use text selectors".
4. **Spec gaps:** one call per up to 4 gaps, only for gaps whose answer changes an expected
   result; options are the plausible readings (the code's current behaviour first, marked as
   such) plus "Don't know — keep as a gap". Write the answer under the gap as
   `→ Answer (<date>): …` and update the affected expected results.
5. **Approve:** one question — "Approve and run", "I want to edit the file first" (then wait for
   "approved"), "Stop here".
6. On approval re-read the file (it is the source of truth), give new cases IDs, check every
   approved Auto case has its placeholders filled (any gap → ask again), set status `APPROVED`
   with the date.
7. After every write to `test-cases.md`: `$S/format_md.sh <story>/test-cases.md` (the project's
   Prettier, so CI `format:check` passes when the user commits it; case hashes ignore spacing).

## Phase 4 – Prepare

Read `references/expo-device.md` (and the project run skill, if any).

1. **Add the approved testIDs** exactly as listed (props and approved pass-throughs only). Record
   each file:line for the report. Run the project's typecheck if it has one; a failure caused by
   these edits → fix the prop, nothing else.
2. **Device:** `$S/device.sh <platform> "" <appId>` → `deviceId`. One device runs both
   languages, Arabic first. (`clone_device.sh` can make a second device for a parallel English
   run, but only when the user asks for it: on a 16 GB Mac a second idle simulator alone pushed
   1.4 GB into swap.)
3. **Build check:** `$S/build_check.py <platform> <appId> <deviceId>` — does the installed build
   match this checkout's native code? `install` non-empty → ask before installing (it changes the
   user's node_modules), then check again; `rebuild: true` → build (`--build`, plus `--prebuild`
   when `prebuild`); `rebuild: null` → no record yet, note it and go on. Details and the questions:
   `references/expo-device.md` "Which build". Every retest runs this too: a branch switch between
   runs is the usual cause.
4. **Metro + app:** first `$S/run_meta.py code --run <runDir> --story <story>` (branch, commit and
   the uncommitted changes the app is about to run with — the report's "Code tested" row, so a
   retest of uncommitted fixes says so). Then `$S/run_app.sh <platform> <runDir> <appId> <deviceId>
   [--build] [--prebuild]` (testID edits alone never need `--build` — JS edits reach the app through
   Metro). Exit 3 → ask to restart Metro, then `--restart-metro`; declined → record the gap and go
   on without network triage.
5. **Assisted login** (skip when the story's feature is pre-login): screenshot, ask the user to
   log in, poll `$S/dump_hierarchy.sh <runDir> login-check <deviceId> --find "<marker>"`.
6. **Network check:** after the smoke run, `grep -c "<api log tag>" metro.log` > 0, else record the
   gap "network calls not visible".
7. **run-info.json:** add device, os, env, apiBase, maestro version, `started`,
   testIdsAdded / passThroughs (file, line), networkLogVisible.
8. **Smoke:** `$S/run_flow.sh <e2e>/subflows/go-to-feature.yaml ar <runDir> <deviceId> SMOKE
   --no-record`. Failing → fix the subflow (hierarchy dump to see the screen) before any case.
9. **Deep smoke:** `$S/flow_sync.py smoke <test-cases.md> <e2e>` → the shared subflows that 3+
   cases go through (e.g. the contact verification step); run each once with `run_flow.sh … --data
   <runDir>/artifacts/data.json --no-record` (after Phase 5 steps 1–2 wrote the data). A failure
   here costs 2 minutes instead of several cases: the flow's fault → fix it; the app or server
   (an error dialog, an error response) → tell the user what failed and ask: "Run only the cases
   that don't use it (Recommended)", "I'll fix it — wait", "Stop and report". Cases left out
   this way → run-info `stoppedEarly` with that step.

## Phase 5 – Execute

Read `references/maestro.md`; start case flows from `templates/flow.template.yaml`.

1. **Sync:** `$S/flow_sync.py plan <test-cases.md> <e2e>`.
   - `create` / `regenerate` → write the flow from the case, `$S/format_md.sh <flow>` (flows are
     committed, so CI `format:check` sees them), then `$S/flow_sync.py stamp <test-cases.md>
     <flow>`. Same order after any flow or subflow fix: format, then stamp.
   - `delete` → delete the flow. `keep` → do not touch. `skip` → keep, never run.
   - `handEdited` → show the diff against what you would generate and ask: keep theirs (re-stamp),
     overwrite, or skip the case. Never decide alone.
   - Subflows are written once from Phase 2 findings; re-check them only if the smoke fails.
2. **Data:** `$S/flow_sync.py data <test-cases.md>` → `unfilled` must be empty for every case you
   will run; save `values` to `<runDir>/artifacts/data.json` (git-ignored; it holds the local
   values too).
2a. **Lint:** `$S/flow_sync.py lint <test-cases.md> <e2e>` must print `ok: true`: every case flow
   has a step labelled `EXPECT` (without it a failed check is retried and reported as blocked),
   is stamped, parses, reaches only existing subflows, and uses only `${KEY}`s from the Test data
   table. Fix what it lists (flows only, then format and stamp) before running anything.
3. **Arabic first** — `run_suite.py` in the background (Bash `run_in_background`):
   `$S/run_suite.py --run <runDir> --e2e <e2e> --lang ar --device <deviceId> --platform <p> --app
   <appId> --cases <approved Auto ids not in cleanStateLast / darkModeLast> --data <runDir>/artifacts/data.json
   --setup --app-error "<run-info appError>" [--login-marker "<login-screen regex>"]`. It switches
   the language, closes other apps before every attempt, runs the cases in order, retries once only
   `flow` / `timeout` failures (a failed `EXPECT` check and an app error are deterministic), and
   skips pairs already in `results.json` (resume = start it again). It runs cases that share
   subflows next to each other, so a broken shared step stops the suite early. Exit 4 → the language subflow
   failed (fix it); exit 5 → session expired: assisted login, re-run the case with `run_flow.sh
   --attempt N+1`, start the suite again. While it runs, download the Figma frames (Phase 7 step 2
   needs no device).
   Exit 6 → **blocked**: two cases in a row stopped at the same step before their checks (the
   summary line has `step`, `failKind`, `cases`, `remaining`), so every later case would stop there
   too. Read the last failure's screenshot, hierarchy and network window, then:
   - the flow's fault (`failKind` `flow`, the element is on screen under another selector) → fix
     the subflow, smoke it, start the suite again (resume runs only the remaining cases);
   - the app, server or test data (`failKind` `app`, an error response) → tell the user the step,
     what the app showed and the API response, and ask: "Stop and report (Recommended)", "I'll fix
     it — wait, then continue". Stop → run-info `stoppedEarly: [{lang, step, remaining}]`; the
     blocking cause becomes one finding covering every blocked pair (Phase 6). Do not start the
     English suite while the same step blocks Arabic: ask first.
   Exit 7 → **the skill changed**: the test-story scripts differ from the version recorded at the
   start (another session edited the skill). Re-read this file and the references the remaining
   phases use, tell the user in one line, then start the suite again with `--accept-skill-change`
   (it records the new version and a note; resume runs only the remaining cases).
4. **English: ask.** Show the Arabic results (case → passed / failed, one line per failure), then
   one AskUserQuestion. Get the message-check set first: `$S/flow_sync.py messages <test-cases.md>`
   → `cases` (Expected quotes a translated text) and `others`. Options:
   - "English only for message checks (Recommended)" — `<n>` of `<total>` cases; language bugs
     (e.g. Arabic messages in the English app, BUG-01 in the first real run) show up there;
   - "Run English for all cases";
   - "Skip English".
   The user already said which at approval or in this conversation → do that, don't ask again.
   Record it in run-info: `langChoice` (one line, e.g. "ar (all cases), then en for message
   checks only (14 of 24 cases) — chosen after the Arabic run") and `skippedByUser`
   (`[{case, lang: "en"}]` for every approved Auto case not run in English). Then run the chosen
   English cases with the same `run_suite.py` command and `--lang en`.
5. `cleanStateLast` cases: after the suites: reset flow (`--no-record`), assisted login, then the
   case with `run_flow.sh` (in each language that ran). `darkModeLast` cases: switch the device to
   dark mode (`xcrun simctl ui <udid> appearance dark` / `adb shell cmd uimode night yes`), run them
   with `run_flow.sh`, switch back to light.
6. A failed case gets **one** flow-fix attempt only when the failure is clearly the flow's
   (`failKind` `flow`: selector not found although the element is on screen, parse error): fix,
   re-stamp, re-run with `run_flow.sh --attempt N+1`. Never touch an expected result (hard rule 2).
7. **Summary:** `$S/parse_results.py status --results <runDir>/artifacts/results.json --cases <ids>`
   (retest: `--pairs TC-04:en,…`) → show a table: case × ar/en → passed / failed (`failKind`
   `check`) / blocked (any other `failKind`: the check was never reached) / skipped by you, plus
   Manual cases listed separately. Never call a blocked pair "still failing": its fix is untested.

## Phase 6 – Triage

Read `references/triage.md` and follow it for every case × language whose final attempt is not
`passed`, and for every case that failed and later passed.

1. Flow fixes follow Phase 5 step 6 (one fix per case); a fixed case that then passes → a
   `flowFixes` note, not a failure.
2. Retry: `run_suite.py` already retried `flow` / `timeout` failures once (passed → `Flaky`). A
   failed `EXPECT` check (`failKind: check`) is not retried when the failure hierarchy shows the
   expected screen settled; still loading or another screen → retry it once by hand. `failKind:
   app` (an error dialog was on screen, `appError` in the record) is not retried: triage the
   server call behind it. Pairs blocked by the same step share one finding (its `case` / `lang`
   list them all); the report marks them "blocked — check not reached", not as failed checks.
3. Evidence: failure screenshot (`<runDir>/<lang>/<TC>_fail[_aN].png`) + hierarchy from `results.json`;
   `$S/net_log_extract.py <runDir>/artifacts/metro.log <start> <end> --lang <lang>` (masked; `--lang`
   matters only if en and ar ever ran at the same time; add `--tag/--req-re/--res-re/--lang-field`
   from run-info `network` when Phase 2 recorded one). `ambiguous` responses behind a Bug →
   re-run that case alone for a clean window. Then the code the AC traces to.
4. Classify with the table; annotate with `$S/annotate.py` → `<TC>_fail[_aN]_annotated.png` beside
   it. Every finding needs one: after the prune it is the only screenshot left.
5. Every Bug and Content issue → one verifier subagent each, in parallel, with the template in `triage.md` and
   nothing else. Use its classification when it downgrades.
6. Write `<runDir>/artifacts/triage.json`; `$S/triage_check.py <results.json> <triage.json>` must
   print `ok: true` before moving on (hard rule 6); read its `warnings` too (a Bug covering a
   blocked pair must describe the blocking step).
7. Show a findings table: ID, class, severity, case × language, title, verified.

## Phase 7 – Evidence and Figma

Annotated screenshots are made in Phase 6 (`annotate.py`). For Figma, read
`references/figma-compare.md`.

1. Figma MCP not connected, or no Figma rows filled → set run-info `figma` to
   `"not run: <reason>"` and go to Phase 8.
2. Per mapped screen: resolve the frame (walk up from an element link), fetch it with the Figma
   MCP, download it into `<runDir>/figma/`.
3. Capture the app in the frame's language and state, top to bottom (existing case screenshots
   or a `--no-record` capture flow).
4. Compare on the rubric (elements, text, order/layout, colour role, RTL). Data values and state
   differences are notes, not deviations.
5. Each difference → a `DD-nn` finding in `triage.json` with confidence and a side-by-side from
   `$S/side_by_side.py --out <runDir>/figma-dd/DD-nn.png` (English labels). Re-run `triage_check.py`.
6. Set run-info `figma` to `"compared (<n> frames: <ids>, <langs>)"`.

## Phase 8 – Report

Read `references/report-rules.md`.

1. Set `finished` and any `notes` in run-info.json.
2. `$S/triage_check.py …` passes (skip for an aborted run).
3. **Prune:** `$S/prune_run.py <runDir>` keeps `<lang>/*_annotated.png`, `figma/`, `figma-dd/` and
   the artifacts JSON + `metro.log`; everything else (step shots, raw failure shots, hierarchy
   dumps, temp Maestro output) is deleted and `metro.log` is rewritten masked. It also deletes
   this story's run folders older than
   the newest 5 (never the run being retested), so a story's runs stay around 25 MB at most.
   Aborted run → prune too.
4. `$S/report_build.py --cases … --results … --triage … --run-info … --out
   <story>/test-report-<runId>.md --repo-root <repo root>` (`--aborted "<reason>"` when the run
   stopped early — any stop after Phase 3 still produces a report), then
   `$S/format_md.sh <story>/test-report-<runId>.md`.
5. Read the report; fix wording at its source and rebuild; never hand-edit the report.
5a. **Stop Metro:** `$S/run_app.sh <platform> <runDir> <appId> <deviceId> --stop` stops only the
   Metro the skill started (the app stays installed). Skip it when the user asked to keep Metro or a
   retest follows right away; one left running held port 8081 for three days.
6. Tell the user the path, verdict, counts, top 3 issues and the run folder's size. Never commit
   (hard rule 12). Verdicts: FAIL (a Critical/High bug), INCOMPLETE (pairs blocked or not run —
   their expected results were never checked; named with the blocking finding), PASS WITH
   ISSUES, PASS. The report refuses to build when it contains a `test-data.local.json` value.
