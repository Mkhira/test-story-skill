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

Build status: all phases are live (M1–M5) and validated end to end on a real feature (M6,
2026-10-01: establishment-signup, iOS, en + ar). M7 (Arabic first + English choice, EXPECT-only
no-retry, retest mode, Content issue, Prettier) is verified offline only — not yet on a live
device. Not yet run on Android.

Scripts live in `scripts/` next to this file (`S=~/.claude/skills/test-story/scripts`). Run them
from the project root; each prints JSON.

## Hard rules

1. Never run a test, or change code, before the user approves `test-cases.md`. Never run a case marked `skip`.
2. Expected results come only from the approved `test-cases.md`. Never change an expected result or weaken an assertion to make a case pass.
3. The only production changes allowed are approved `testID` props and approved `testID` pass-through props on shared components. Every one is listed in the report.
4. Never invent real-looking data (TIN, national ID, phone, IBAN). Use only the values the user entered.
5. Never guess when you can ask: feature match, login, OTP, missing data, unclear language switch.
6. Every failure gets exactly one classification; nothing reaches the report unclassified.
7. Every bug cites its AC (or its beyond-the-story rule), a screenshot, the network evidence when available, and the file and line when found.
8. Mask tokens, `Authorization` headers and config secrets (`clientSecret`, encryption keys) from logs before writing them anywhere; mask PII fields in any network excerpt written to the report.
9. `test-runs/` and `e2e/` inside every story folder are git-ignored before the first file is written into them.
10. Never assert a duration the story does not state.
11. Never overwrite a hand-edited flow without asking.
12. Never commit or push.
13. Always write the report, even for an aborted run, with the reason.

## Outputs

```
<feature>/test-stories/<story-slug>/
├── test-cases.md                 # approval file (committed)
├── test-report-<runId>.md        # one per run (committed)
├── e2e/                          # Maestro flows (git-ignored), synced each run
└── test-runs/<runId>/            # git-ignored; <runDir> below
    ├── en/  ar/                  # during the run: step + failure shots; after prune: *_fail*_annotated.png
    ├── figma/                    # exported Figma frames
    ├── figma-dd/                 # DD-nn.png side-by-sides (app vs Figma)
    └── artifacts/                # results.json, triage.json, run-info.json, data.json, metro.log
```

## Retest mode

When the user says "retest" (after fixes), run ONLY what failed last time:
1. Find the story folder (a feature with several stories → ask which). Latest run = the newest
   `<story>/test-runs/<runId>/` with `artifacts/results.json`.
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
6. The report shows a before → now table (`fixed` / `still failing`) and counts only the scope.

## Run folder

`<runId>` is local time `YYYY-MM-DD_HHMM`. Maestro's raw output goes to
`$TMPDIR/test-story/<runId>/` and is deleted after each case, so the run folder stays small
(the simulator log alone is 20–70 MB per attempt). After the report data is complete,
`prune_run.py` cuts the run folder to the annotated failures, the Figma images and the JSON.

## Phase 0 – Preflight

1. **Expo project?** `expo` in `package.json` and an `app.json` / `app.config.*`. Read iOS
   `bundleIdentifier` and Android `package` (Maestro `appId`). Not Expo → stop and say so.
2. **Platform:** ask with a multiple-choice question: iOS simulator or Android emulator.
3. **Project run skill:** look for a repo skill that runs the app (e.g. `.claude/skills/run-zatca/`).
   When present, read it; device boot, build, Metro, deep links and Maestro facts follow it.
4. **Tools:** `$S/preflight.sh <platform>`. `installable` lists what the skill may install
   (`maestro`, `java17`): ask once, then re-run with `--install-maestro` / `--install-java`.
   `manual` lists what only the user can install (Xcode, SDK, AVD) → stop with those steps before
   Phase 4 (Phases 1–3 can still run).
5. **Leftovers:** `$S/prune_run.py --stale-tmp` deletes temp Maestro output that a crashed or
   killed run left in `$TMPDIR/test-story/` (untouched for 6 hours).
6. **Resume check:** a `<story>/test-runs/<runId>/artifacts/results.json` with no
   `test-report-<runId>.md` → run `$S/parse_results.py status --results <it> --cases <approved Auto
   ids>` (an interrupted retest is limited to its own `scope` automatically); `todo` non-empty →
   offer to continue that run id with only the `todo` pairs (`run_suite.py --cases` per language).
7. **Run id**, `run-info.json` (start it now: runId, story, feature, featurePath, platform, and
   later fields as they become known — see `references/report-rules.md`) and `.gitignore`:
   `git check-ignore -q <story>/test-runs/x <story>/e2e/x`; not ignored → add `test-runs/` and
   `**/test-stories/*/e2e/`, before writing any file under them.

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
4. **Language switch:** find how the app changes language and whether it reloads. Use the run
   skill's facts when present (ZATCA: Menu tab → `العربية` / `English`, live text switch, native
   RTL only after a cold relaunch, session kept). Backend messages follow `Accept-Language`, so
   server texts are asserted per language. Unknown → ask once.
5. **Path to the feature:** a deep link first (ZATCA: `zatca://service-flow/<serviceId>`, ids in
   the services data / deep-link map), else the tap path from home. Note the feature element to
   wait on after arrival.
6. **testID audit:** every element a case touches that has no `testID` → a row with a kebab-case id
   `<feature>-<screen>-<element>` in the repo's existing style. If the element is rendered by a
   shared component that does not forward `testID`, add a separate pass-through row for that
   component. Nothing is edited now.
7. **Message map:** for every text a case will assert (validation, success, error), find its
   exact en and ar wording and source: app translation key (feature `translations/en.ts` /
   `ar.ts`, global `en.json` / `ar.json`), CMS / service-message catalog key (ZATCA:
   `core/localization/service-messages-localization/{en,ar}.json`, served by the BFF), or server
   response (unknown until the run). Expected results quote these texts; never paraphrase. A
   story text that differs from the app's text is a static finding, asked as a spec gap.
8. **Environment:** read which env the running build uses (env file, API base URL; ZATCA: the
   `ConfigService` "Loaded configuration" log line or `.env` + `.env.development`). Shown at
   approval and in the report; no gate.

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
     use it" and "Leave it for later" — the user types the value through "Other";
   - for values that only need to break a rule (wrong prefix, too short, bad format): offer
     1–2 obviously synthetic values that cannot be a real identifier (e.g. `123456789` for a
     9-digit ID, `2000000000` for a wrong National ID prefix), each labelled with why it fails,
     plus "Skip the cases that use it".
   Write each answer into the table's Value column; "Skip…" sets those cases to `skip`;
   "Leave it for later" keeps `{{fill}}`.
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
3. **Metro + app:** `$S/run_app.sh <platform> <runDir> <appId> <deviceId>` (add `--build` after
   testID edits only if native code changed — JS edits reach the app through Metro). Exit 3 → ask
   to restart Metro, then `--restart-metro`; declined → record the gap and go on without network
   triage.
4. **Assisted login** (skip when the story's feature is pre-login): screenshot, ask the user to
   log in, poll `$S/dump_hierarchy.sh <runDir> login-check <deviceId> --find "<marker>"`.
5. **Network check:** after the smoke run, `grep -c "<api log tag>" metro.log` > 0, else record the
   gap "network calls not visible".
6. **run-info.json:** add device, os, env, apiBase, maestro version, `started`,
   testIdsAdded / passThroughs (file, line), networkLogVisible.
7. **Smoke:** `$S/run_flow.sh <e2e>/subflows/go-to-feature.yaml ar <runDir> <deviceId> SMOKE
   --no-record`. Failing → fix the subflow (hierarchy dump to see the screen) before any case.

## Phase 5 – Execute

Read `references/maestro.md`; start case flows from `templates/flow.template.yaml`.

1. **Sync:** `$S/flow_sync.py plan <test-cases.md> <e2e>`.
   - `create` / `regenerate` → write the flow from the case, then `$S/flow_sync.py stamp
     <test-cases.md> <flow>`.
   - `delete` → delete the flow. `keep` → do not touch. `skip` → keep, never run.
   - `handEdited` → show the diff against what you would generate and ask: keep theirs (re-stamp),
     overwrite, or skip the case. Never decide alone.
   - Subflows are written once from Phase 2 findings; re-check them only if the smoke fails.
2. **Data:** `$S/flow_sync.py data <test-cases.md>` → `unfilled` must be empty for every case you
   will run; save `values` to `<runDir>/artifacts/data.json`.
3. **Arabic first** — `run_suite.py` in the background (Bash `run_in_background`):
   `$S/run_suite.py --run <runDir> --e2e <e2e> --lang ar --device <deviceId> --platform <p> --app
   <appId> --cases <approved Auto ids not in cleanStateLast> --data <runDir>/artifacts/data.json
   --setup [--login-marker "<login-screen regex>"]`. It switches the language, closes other apps
   before every attempt, runs the cases in order, retries once only `flow` / `timeout` failures (a
   failed `EXPECT` check is deterministic), and skips pairs already in `results.json` (resume = start
   it again). Exit 4 → the language subflow failed (fix it); exit 5 → session expired: assisted
   login, re-run the case with `run_flow.sh --attempt N+1`, start the suite again. While it runs,
   download the Figma frames (Phase 7 step 2 needs no device).
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
   case with `run_flow.sh` (in each language that ran).
6. A failed case gets **one** flow-fix attempt only when the failure is clearly the flow's
   (`failKind` `flow`: selector not found although the element is on screen, parse error): fix,
   re-stamp, re-run with `run_flow.sh --attempt N+1`. Never touch an expected result (hard rule 2).
7. **Summary:** `$S/parse_results.py status --results <runDir>/artifacts/results.json --cases <ids>`
   (retest: `--pairs TC-04:en,…`) → show a table: case × ar/en → passed / failed / error / skipped
   by you, plus Manual cases listed separately.

## Phase 6 – Triage

Read `references/triage.md` and follow it for every case × language whose final attempt is not
`passed`, and for every case that failed and later passed.

1. Flow fixes follow Phase 5 step 6 (one fix per case); a fixed case that then passes → a
   `flowFixes` note, not a failure.
2. Retry: `run_suite.py` already retried `flow` / `timeout` failures once (passed → `Flaky`). A
   failed `EXPECT` check (`failKind: check`) is not retried when the failure hierarchy shows the
   expected screen settled; still loading or another screen → retry it once by hand.
3. Evidence: failure screenshot (`<runDir>/<lang>/<TC>_fail[_aN].png`) + hierarchy from `results.json`;
   `$S/net_log_extract.py <runDir>/artifacts/metro.log <start> <end> --lang <lang>` (masked; `--lang`
   matters only if en and ar ever ran at the same time). `ambiguous` responses behind a Bug →
   re-run that case alone for a clean window. Then the code the AC traces to.
4. Classify with the table; annotate with `$S/annotate.py` → `<TC>_fail[_aN]_annotated.png` beside
   it. Every finding needs one: after the prune it is the only screenshot left.
5. Every Bug and Content issue → one verifier subagent each, in parallel, with the template in `triage.md` and
   nothing else. Use its classification when it downgrades.
6. Write `<runDir>/artifacts/triage.json`; `$S/triage_check.py <results.json> <triage.json>` must
   print `ok: true` before moving on (hard rule 6).
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
   dumps, temp Maestro output) is deleted. It also deletes this story's run folders older than
   the newest 5 (never the run being retested), so a story's runs stay around 25 MB at most.
   Aborted run → prune too.
4. `$S/report_build.py --cases … --results … --triage … --run-info … --out
   <story>/test-report-<runId>.md --repo-root <repo root>` (`--aborted "<reason>"` when the run
   stopped early — any stop after Phase 3 still produces a report), then
   `$S/format_md.sh <story>/test-report-<runId>.md`.
5. Read the report; fix wording at its source and rebuild; never hand-edit the report.
6. Tell the user the path, verdict, counts, top 3 issues and the run folder's size. Never commit
   (hard rule 12).
