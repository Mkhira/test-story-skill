#!/usr/bin/env python3
"""Gate before the report: every failure is classified exactly once, every finding is complete.

  triage_check.py <runDir>/artifacts/results.json <runDir>/artifacts/triage.json

Prints JSON {ok, problems:[…], unclassified:[…]}; exit 1 when not ok.
- Final attempt failed/error for a case × language → exactly one finding covers it (hard rule 6).
- A failed attempt later passing → a Flaky finding, unless a flowFixes entry explains it.
- Every finding: classification, severity, title, expected, actual, evidence.screenshot,
  2–3 fixOptions with exactly one recommended, retest.
- Bugs: an AC (or "beyond-story:<rule>"), verified is true/false with a verifierReason, and
  evidence.network or an explicit "none" (hard rule 7). Content issues: verified the same way.
- Any other class: verified absent or null (no verifier ran); false is reserved for a candidate a
  verifier downgraded, and then the verifierReason says so.
- A blocked pair (final failKind flow / app / timeout: the check was never reached) must be
  covered by the finding for its blocking step, not by a check finding carried over from an
  earlier run: Content issue / Spec gap / Design deviation there is a problem; a Bug there is a
  warning (an app bug can block a step — make sure the finding describes that step).
"""
import json
import sys
from collections import defaultdict

CLASSES = {'Bug', 'Content issue', 'Spec gap', 'Test data issue', 'Environment issue', 'Design deviation',
           'Test error', 'Test error (expectation)', 'Flaky'}


def main(results_path, triage_path):
    results = json.load(open(results_path))
    triage = json.load(open(triage_path))
    findings = triage.get('findings', [])
    fixes = {(f['case'], f['lang']) for f in triage.get('flowFixes', [])}
    problems, unclassified, warnings = [], [], []

    attempts = defaultdict(list)
    for r in results:
        attempts[(r['case'], r['lang'])].append(r)
    covers = defaultdict(list)
    for f in findings:
        # one finding may cover several cases with the same root cause: "case": "TC-04,TC-05"
        for case in str(f.get('case', '')).split(','):
            for lang in str(f.get('lang', '')).split(','):
                covers[(case.strip(), lang.strip())].append(f.get('id'))

    for key, runs in attempts.items():
        runs.sort(key=lambda r: r['attempt'])
        final = runs[-1]['status']
        failed_before = any(r['status'] != 'passed' for r in runs[:-1])
        ids = covers.get(key, [])
        if final != 'passed':
            fk = runs[-1].get('failKind')
            if fk and fk != 'check':
                for f in findings:
                    if f.get('id') not in ids:
                        continue
                    if f.get('classification') in ('Content issue', 'Spec gap', 'Design deviation'):
                        problems.append(f"{key[0]} {key[1]}: blocked before its check ({fk}) but covered by "
                                        f"{f['id']} ({f['classification']}); cover it with the blocking step's finding")
                    elif f.get('classification') == 'Bug':
                        warnings.append(f"{key[0]} {key[1]}: blocked before its check ({fk}); {f['id']} must describe "
                                        'the blocking step, not the unchecked expected result')
            if not ids:
                unclassified.append(f'{key[0]} {key[1]}: final {final}, no finding')
            elif len(ids) > 1:
                problems.append(f'{key[0]} {key[1]}: classified {len(ids)} times {ids}')
        elif failed_before and key not in fixes:
            kinds = [f['classification'] for f in findings if f.get('id') in ids]
            if 'Flaky' not in kinds:
                unclassified.append(f'{key[0]} {key[1]}: failed then passed — needs Flaky or a flowFixes note')

    seen = set()
    for f in findings:
        fid = f.get('id', '?')
        if fid in seen:
            problems.append(f'{fid}: duplicate id')
        seen.add(fid)
        if f.get('classification') not in CLASSES:
            problems.append(f'{fid}: unknown classification {f.get("classification")!r}')
        for k in ('severity', 'title', 'expected', 'actual', 'retest'):
            if not f.get(k):
                problems.append(f'{fid}: missing {k}')
        if not (f.get('evidence') or {}).get('screenshot'):
            problems.append(f'{fid}: missing evidence.screenshot')
        opts = f.get('fixOptions') or []
        if not 2 <= len(opts) <= 3:
            problems.append(f'{fid}: needs 2–3 fixOptions, has {len(opts)}')
        if sum(1 for o in opts if o.get('recommended')) != 1:
            problems.append(f'{fid}: exactly one fix option must be recommended')
        if f.get('classification') == 'Content issue' and (f.get('verified') is None or not f.get('verifierReason')):
            problems.append(f'{fid}: Content issue not independently verified')
        if (f.get('classification') not in ('Bug', 'Content issue') and f.get('verified') is not None
                and not f.get('verifierReason')):
            problems.append(f'{fid}: verified is set but no verifierReason (omit verified when no verifier ran)')
        if f.get('classification') == 'Bug':
            if not f.get('ac'):
                problems.append(f'{fid}: Bug without an AC')
            if f.get('verified') is None or not f.get('verifierReason'):
                problems.append(f'{fid}: Bug not independently verified')
            if 'network' not in (f.get('evidence') or {}):
                problems.append(f'{fid}: Bug without evidence.network (use "none" when no call applies)')

    ok = not problems and not unclassified
    print(json.dumps({'ok': ok, 'problems': problems, 'unclassified': unclassified, 'warnings': warnings},
                     ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
