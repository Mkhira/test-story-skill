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
`"not run: <reason>"`), `notes` (short facts a reader needs, e.g. "session expired once; re-ran
TC-07 en").

## Build

```
$S/report_build.py --cases <story>/test-cases.md --results <runDir>/artifacts/results.json \
  --triage <runDir>/artifacts/triage.json --run-info <runDir>/artifacts/run-info.json \
  --out <story>/test-report-<runId>.md --repo-root <repo root>
```

- Run `triage_check.py` first; do not build on a failing check (except an aborted run).
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
- `evidence.network`: `METHOD /path → status` plus only the fields that prove the point, already
  masked (`net_log_extract.py` output). `"none"` when no call applies.
- `code`: repo-relative `path:line`, the line that causes the behaviour when found.
- `fixOptions`: concrete changes, one `recommended`; for Test error (expectation) the fix is to
  the case, never to the app; for a Content issue the fix names the CMS / server key and the
  correct en / ar text.
- Retest runs: a failure that matches a previous finding keeps that finding's id with fresh
  evidence; the report adds a before → now table to the summary.
- `retest`: exact case × language pairs.
- PII: never paste names, TINs, national IDs, phones, IBANs or emails into any field; refer to test
  data by key (`VALID_TIN`).
- English only, even for ar findings; quote Arabic UI text exactly when it is the evidence.

## After building

1. Read the whole report once. Wrong or unclear text → fix the source, rebuild.
2. Tell the user: the report path, the verdict, the counts, and the top 3 issues in one line each.
3. Remind them the report and `test-cases.md` are committed by them, never by the skill (hard
   rule 12), and that `test-runs/<runId>/` next to the report holds the kept screenshots.
