# How to use test-story

A practical guide to the global `test-story` skill for Claude Code. Install it first (see
[README.md](README.md)).

## Before the first run

1. Install the project's dependencies, e.g. `npm ci` (and `cd ios && pod install` for iOS).
2. Have a simulator (Xcode) or an emulator (Android Studio) available.
3. Put the user story somewhere you can point to: a markdown file in the repo works best. You can
   also paste the text.
4. Close heavy apps if your Mac is short on memory; the simulator and Metro need room.

Maestro and Java are checked at the start; if missing, the skill asks once and installs them.

## Commands

### Test a story for the first time

```text
/test-story <story> <feature>
```

```text
/test-story docs/stories/CHECKOUT-001.md checkout
/test-story src/features/profile/stories/edit-profile.md src/features/profile
```

- **Story:** a file path, or the story text pasted in.
- **Feature:** a folder path, or a name. With a name, the skill shows the matching folders and
  asks you to confirm one.

### Retest only what failed

```text
/test-story retest checkout
```

Or just say: `retest checkout`, `re-test the checkout story`, `run the failed cases again`.

### Run the whole story again

Use the first-run command again. Approved cases are reused; only new or changed cases need your
approval.

### Continue a run that stopped

Run the same command again. The skill finds the unfinished run and offers to continue it from
where it stopped.

### Choose English up front (optional)

Add your English choice so the run does not pause after Arabic to ask:

```text
/test-story retest checkout — English: message checks only
```

Choices: `message checks only`, `all cases`, `skip English`.

## What you answer during a run

1. **Platform:** iOS simulator or Android emulator.
2. **Test data:** one question per value the cases need. Real identifiers (IDs, phone numbers,
   accounts) are never invented: type them in, skip the cases that need them, or leave them for
   later. For "invalid" values the skill offers obviously fake ones.
3. **Choices:** whether to add `testID` props to the feature's elements (recommended: it makes
   the tests stable in both languages; the question says exactly which files change), and whether
   to run cases that send real SMS / email or create records.
4. **Spec gaps:** for each unclear story sentence that changes an expected result, pick the
   intended behaviour or keep it as a gap.
5. **Approve:** "Approve and run", "I want to edit the file first", or "Stop here".
6. **Log in** on the device when the feature needs a session; the skill waits and checks.
7. **After the Arabic run:** English for message checks only (recommended), all cases, or skip.

## Arabic first, then English

Every automated case runs in Arabic first. Then the skill shows the Arabic results and asks about
English:

| Choice | Runs | When to use |
| --- | --- | --- |
| Message checks only (recommended) | cases whose expected result is a translated text (validation, success, error messages) | everyday runs: language bugs live in the messages |
| All cases | every case | before a release |
| Skip English | nothing | quick checks; English-only bugs are not caught |

Cases you skip show as "skipped by you" in the report and do not count against the verdict.

## Retest

After the developers fix the reported problems:

1. Say `retest <feature>` (or use `/test-story retest <feature>`).
2. The skill finds the latest run of that story and takes only the case × language pairs whose
   final attempt failed. It shows the list and starts — no approval needed unless you changed
   `test-cases.md`.
3. Only those pairs run (Arabic first). No Figma comparison.
4. The new report starts with a before → now table:

   ```text
   | Case  | Language | Before | Now                    |
   | TC-11 | en       | BUG-04 | fixed                  |
   | TC-18 | ar       | BUG-02 | still failing — BUG-02 |
   2 of 20 pairs fixed.
   ```

A retest of a retest works the same way. Retest reads the previous run from `test-runs/`, which
lives only on the machine that ran it.

## Reading the report

`test-report-<runId>.md` opens with a verdict (PASS, PASS WITH ISSUES, FAIL) and the top issues.
Then: run information, bugs, content issues, gaps, design deviations, test data and environment
issues, flaky tests, test errors, manual checks for you, findings outside the feature, a
coverage matrix (acceptance criterion → cases → result per language) and an appendix.

| Category | Means | Who fixes it |
| --- | --- | --- |
| Bug | the app contradicts a clear acceptance criterion | developers |
| Content issue | wrong, garbled or wrong-language text that comes from the CMS / server | content / backend |
| Spec gap | the story is unclear; the app does what its code intends | product |
| Design deviation | the screen differs from Figma | design or developers |
| Test data issue | the entered data does not exist on the server | you (new data) |
| Environment issue | server error, time-out, unreachable | backend / infra |
| Flaky | failed, then passed on retry | watch it |
| Test error | the test itself was wrong | the skill / you |

Each finding has steps to reproduce, expected vs actual, a screenshot link (red box on the
problem), the API call when relevant, the code location, and 2–3 fix options.

## What to commit

Commit `test-cases.md` and `test-report-<runId>.md`. The skill never commits or pushes.

`e2e/` (Maestro flows) and `test-runs/` (screenshots and run data) are git-ignored; the skill
adds these entries to `.gitignore` before writing:

```gitignore
test-runs/
**/test-stories/*/e2e/
```

## Tips

- **Approve the testIDs.** Text selectors break when wording or language changes; testIDs don't.
- **Give Figma links per screen** when asked, or skip the comparison.
- **Hand-edited flows are safe.** If you edit a flow in `e2e/`, the skill notices and asks before
  touching it.
- **Disk:** a finished run keeps a few MB; only the newest 5 runs per story are kept.

## Troubleshooting

| You see | Do |
| --- | --- |
| "Metro on 8081 not started by the skill" | allow the restart: the skill needs its own Metro log to read API calls |
| The language switch failed | the skill stops before the cases; it fixes the language subflow and continues |
| The login screen appears mid-run | the session expired: log in again; the skill re-runs that case |
| Another app keeps coming to the front | the skill closes other apps before each case; uninstall the app if it still happens |
| Maestro or Java missing | accept the install offer, or install them yourself and run again |
