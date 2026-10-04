# Report rules (Phase 8)

`scripts/report_build.py` owns the report format; never hand-write or hand-edit the report.
To change wording, change the source (`triage.json`, `run-info.json`, `test-cases.md`) and rebuild.

## Inputs and who writes them

| File | Written in | Holds |
| --- | --- | --- |
| `<story>/test-cases.md` | Phase 3 (user approves) | ACs, spec gaps, static findings, test data, cases |
| `<runDir>/artifacts/results.json` | Phase 5 (`run_flow.sh`) | every attempt of every case × language |
| `<runDir>/artifacts/triage.json` | Phase 6 (+ Phase 7 design deviations) | findings and flow-fix notes |
| `<runDir>/artifacts/run-info.json` | Phases 0, 4, 5 (agent) | run facts the other files lack |

`run-info.json` fields (see the script docstring): `runId`, `story`, `storyTitle`, `feature`,
`featurePath` (repo-relative), `platform`, `device`, `os`, `env`, `apiBase`, `maestro`,
`started` (Phase 4 start), `finished` (end of Phase 6), `retestOf` + `scope` (retest runs only:
the previous run id and the `[{case, lang}]` pairs re-run), `langChoice` (one line: what ran in
which language and why) and `skippedByUser` (`[{case, lang}]` the user chose not to run — shown as
"skipped by you", not as "not run", and not held against the verdict), `testIdsAdded` and `passThroughs` (file,
line, id / component, from Phase 4), `networkLogVisible`, `figma` (`"compared"` or
`"not run: <reason>"`), `network` (`{tag, reqRe, resRe, langField}` when the app's API log format
is not the default, Phase 2), `skill` (`run_meta.py skill`: commit, local changes, scripts hash —
the report's "test-story" row), `code` (`run_meta.py code`: branch, commit, uncommitted changes —
the "Code tested" row), `appError` (the app's error-dialog regex, Phase 2), `stoppedEarly`
(`[{lang, step, remaining}]` when the user stopped a suite that exited 6 — shown under "Not
checked"), `notes` (short facts a reader needs, e.g. "session expired once; re-ran
TC-07 en").

## Build

```
$S/report_build.py --cases <story>/test-cases.md --results <runDir>/artifacts/results.json \
  --triage <runDir>/artifacts/triage.json --run-info <runDir>/artifacts/run-info.json \
  --out <story>/test-report-<runId>.md --repo-root <repo root>
```

- Run `triage_check.py` first; do not build on a failing check (except an aborted run).
- Verdict: FAIL (a Critical/High Bug), INCOMPLETE (any in-scope pair blocked or not run: its
  expected result was never checked; the verdict names the findings that blocked them),
  PASS WITH ISSUES, PASS. Top issues are the three most severe findings of any class except
  Flaky and Test error.
- The script refuses a report that contains a value from `test-data.local.json`; real test data
  is referred to by key (the Test data table shows "not in git").
- **Aborted run** (any stop after Phase 3: device lost, user stops, build fails): build with
  `--aborted "<reason>"` from whatever exists — missing files are treated as empty. Hard rule 13.
- The script refuses to write a report containing a bearer token, JWT or config secret. Fix the
  finding text in `triage.json` and rebuild; never weaken the check.

## Writing the finding text (in triage.json)

The report is committed; screenshots are not (`<story>/test-runs/` is git-ignored and pruned to
annotated failures and Figma images). Evidence lines are links relative to the report and list
only files that still exist. A reader without the screenshots must understand every finding.

- `title`: what is wrong, in user terms, ≤ 90 characters. "Company name empty for a valid TIN",
  not "Assertion failed on details-card".
- `expected`: the approved expected result, verbatim.
- `actual`: what the screen showed, in words, including exact texts and numbers.
- `steps` (optional): the report's "Steps to reproduce". Omitted → the first case in `case`
  supplies them, so put the most telling case first or write `steps` (with data keys, not values).
- `verified`: only for findings a verifier saw (true = confirmed, false = downgraded); leave it
  out otherwise, never `false` for "not checked".
- `evidence.network`: `METHOD /path → status` plus only the fields that prove the point, already
  masked (`net_log_extract.py` output). `"none"` when no call applies.
- `code`: repo-relative `path:line`, the line that causes the behaviour when found.
- `fixOptions`: concrete changes, one `recommended`; for Test error (expectation) the fix is to
  the case, never to the app; for a Content issue the fix names the CMS / server key and the
  correct text in every run language.
- Retest runs: a failure that matches a previous finding keeps that finding's id with fresh
  evidence; the report adds a before → now table to the summary.
- `retest`: exact case × language pairs.
- PII: never paste names, TINs, national IDs, phones, IBANs or emails into any field; refer to test
  data by key (`VALID_TIN`).
- Findings are written in English whatever the run language; quote UI text in its own language
  exactly when it is the evidence.

## After building

1. Read the whole report once. Wrong or unclear text → fix the source, rebuild.
2. Tell the user: the report path, the verdict, the counts, and the top 3 issues in one line each.
3. Remind them the report and `test-cases.md` are committed by them, never by the skill (hard
   rule 12), and that `test-runs/<runId>/` next to the report holds the kept screenshots.
