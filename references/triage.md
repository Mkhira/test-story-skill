# Triage (Phase 6)

Every final failed / error result (case × language) gets exactly one classification, recorded in
`<runDir>/artifacts/triage.json`. `scripts/triage_check.py` must pass before Phase 8.

## Procedure, per failed case × language

1. **Is the flow wrong?** Open the failure hierarchy (`failureHierarchy` in results.json).
   - Selector not in the hierarchy but the intended element is on screen under another id/text,
     a missing wait, a parse error, text inside a grouped accessibility label → fix the flow
     **once**, re-stamp, re-run with `--attempt N+1`.
   - Passes → not a failure; add a `flowFixes` note (what changed) — no finding.
   - Still failing for a flow reason → `Test error`.
   - Never change an expected value or remove an assertion here (hard rule 2).
2. **Retry once** — `run_suite.py` already did it for `failKind` `flow` / `timeout` (passed →
   `Flaky` with both attempts' evidence). `failKind: check` (a step labelled `EXPECT …` failed) is
   not retried: the check waited its full timeout. Open the failure hierarchy: the expected screen,
   settled → deterministic, classify. Still loading or a different screen → retry once by hand
   (`run_flow.sh --attempt N+1`).
3. **Inspect** the final failing attempt:
   - screenshot (`failureScreenshot`) and hierarchy
   - `scripts/net_log_extract.py <metro.log> <start> <end> --lang <lang>` → calls + errors in the
     case window (already masked; still quote only the fields relevant to the finding). en and ar
     run in parallel into one Metro log: `--lang` keeps that language's requests and their
     responses. `ambiguous` responses or `errorsMayMix` behind a Bug → re-run the case alone and
     extract again before citing network evidence.
   - the code the AC traces to (Phase 2), to cite file:line
4. **Classify** with the table. Pick the first row that fits.
5. **Annotate:** `scripts/annotate.py <failureScreenshot> --hierarchy <failureHierarchy> (--id|--text) …
   --label "<ID>: <expected> vs <actual>"`; element absent → `--missing "<element>"`. Both files
   are already in the run folder (`<runDir>/<lang>/<TC>_fail[_aN].png`,
   `<runDir>/artifacts/hierarchy/`); the output is `<TC>_fail[_aN]_annotated.png`. Every finding
   gets one — the Phase 8 prune keeps only annotated images.
6. **Verify every Bug independently** (below). Downgraded → use the verifier's classification.
7. **Fix options:** 2–3 per finding, one marked recommended, and the exact cases to re-run.

| Evidence | Classification |
| --- | --- |
| Request not sent, wrong endpoint, or wrong payload | Bug |
| Correct response, but the UI shows it wrong or not at all | Bug |
| App crash, red screen, or unhandled exception in the log | Bug |
| Behaviour contradicts a clear AC | Bug |
| Text on screen is wrong, garbled, empty or in the wrong language, and the app shows exactly what the CMS / server returned (the network body or the message catalog proves it) | Content issue |
| 4xx because the test data doesn't exist or is invalid | Test data issue |
| 5xx, time-out, or unreachable server | Environment issue |
| Behaviour matches the code, but the AC is ambiguous or unreachable as written | Spec gap |
| Screen matches the AC but differs from Figma | Design deviation |
| The approved expected result itself contradicts the AC / story | Test error (expectation) |
| Flow still broken after one fix | Test error |
| Passed on retry | Flaky |

Two cases that look alike:
- Expected value wrong in `test-cases.md` (e.g. 240 for 200 at 15%): never "fix" it; classify
  `Test error (expectation)` and ask the user to correct the case for the next run.
- The UI makes an AC's input impossible (a keypad or sanitiser drops "-", so a negative can
  never be entered): `Spec gap` when the story does not say which is wanted; `Bug` only when
  the story clearly requires the input to be accepted and rejected with the message.

## Severity (Bugs; other categories get one too, for sorting)

- **Critical:** crash, data loss, or the story's main AC blocked
- **High:** an AC violated with no workaround
- **Medium:** an AC violated with a workaround, or wrong message text
- **Low:** cosmetic or wording

## Independent verifier

One subagent per Bug candidate (in parallel), `subagent_type: general-purpose`. It gets ONLY
the material below, never your reasoning or the classification you picked. Fill the template
exactly:

```
You are checking a candidate bug from an automated mobile-app test. Decide from the evidence
only. Do not trust any conclusion that is not in the evidence.

Acceptance criterion: <AC id and Given/When/Then, verbatim from test-cases.md>
Story sentence: <the story source quote>
Test case: <TC id, steps, data values as entered, expected result verbatim>
Language: <en|ar>
Observed: <the failing assertion message from Maestro>
Screenshot: <absolute path to the unannotated failure screenshot> (open it with Read)
Network in the case window: <net_log_extract calls, relevant ones only, masked>
Log errors in the window: <net_log_extract errors or "none">
Code the AC traces to: <file:line list> (you may read these files)

Classifications:
- Bug: the app contradicts a clear AC, mishandles a correct response, sends a wrong request, or crashes.
- Content issue: the wrong text comes from the CMS or server unchanged (the app displays exactly
  what it received); the fix is in the content, not the app code.
- Spec gap: the app does what its code intends, but the AC is ambiguous, or the AC's input or
  situation cannot happen in this UI as written (e.g. the keypad cannot type the value).
- Test error (expectation): the test's expected result itself contradicts the AC or story.
- Test error: the test's steps or selectors are wrong, not the app.
- Test data issue: the entered data does not exist or is invalid on the server (e.g. a 4xx for an unknown ID).
- Environment issue: 5xx, time-out, or unreachable server.

Answer with JSON only:
{"verdict": "CONFIRMED" | "DOWNGRADED",
 "classification": "Bug" | "Content issue" | "Spec gap" | "Test error (expectation)" | "Test error" | "Test data issue" | "Environment issue",
 "reason": "<two sentences citing the evidence>",
 "severity": "Critical" | "High" | "Medium" | "Low" | null}
```

Record `verified: true|false` and the verifier's reason in the finding.

## triage.json

```json
{
 "flowFixes": [{"case": "TC-05", "lang": "ar", "change": "selector id → text 'مسح الكل'", "result": "passed attempt 2"}],
 "findings": [{
  "id": "BUG-01", "case": "TC-04", "lang": "ar", "attempts": [1, 2],
  "classification": "Bug", "severity": "High",
  "title": "…", "ac": "AC-3", "expected": "…", "actual": "…",
  "evidence": {"screenshot": "…_fail.png", "annotated": "…_fail_annotated.png",
               "network": "GET /v1/… → 200 (relevant fields)", "logErrors": [], "hierarchy": "…"},
  "code": ["path/file.ts:77"],
  "fixOptions": [{"text": "…", "recommended": true}, {"text": "…"}],
  "retest": ["TC-04 en", "TC-04 ar"],
  "verified": true, "verifierReason": "…"
 }]
}
```

Optional fields: `"scope": "outside"` for a failure caused by code outside the story's feature
(reported only in "Outside feature scope", with the owning folder in `code`), and
`"beyondStory": "<rule>"` for findings from beyond-the-story cases (e.g. "double tap on submit").

IDs by classification: `BUG-nn`, `GAP-nn` (spec gap), `TD-nn` (test data), `ENV-nn`,
`FLAKY-nn`, `TE-nn` (test error), `DD-nn` (design deviation, Phase 7). One finding may cover the
same failure in both languages (`"lang": "en,ar"`) and several cases with one root cause
(`"case": "TC-04,TC-05"`); every case × language is still covered exactly once.
