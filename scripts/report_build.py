#!/usr/bin/env python3
"""Build test-report-<runId>.md from the run's data (Phase 8). The format lives here, nowhere else.

  report_build.py --cases <story>/test-cases.md --results <runDir>/artifacts/results.json
                  --triage <runDir>/artifacts/triage.json --run-info <runDir>/artifacts/run-info.json
                  --out <story>/test-report-<runId>.md [--repo-root .] [--aborted "reason"]

run-info.json (written by the agent in Phases 0–5):
  {"runId", "story", "storyTitle", "feature", "featurePath", "platform", "device", "os", "env", "apiBase",
   "maestro", "started", "finished",                       # ISO times, local or UTC
   "testIdsAdded": [{"file", "line", "id"}], "passThroughs": [{"file", "line", "component"}],
   "networkLogVisible": true, "figma": "not run: <reason>" | "compared",
   "notes": ["…"]}
Everything else comes from test-cases.md, results.json and triage.json, so numbers never drift
from the evidence. Nothing here re-reads metro.log: network text comes from triage.json, which
net_log_extract.py already masked.
"""
import argparse
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

SEV = ['Critical', 'High', 'Medium', 'Low']
CLASS_ORDER = ['Bug', 'Content issue', 'Spec gap', 'Design deviation', 'Test data issue', 'Environment issue', 'Flaky',
               'Test error (expectation)', 'Test error']
LANGS = ['en', 'ar']


# ---------- test-cases.md ----------

def sections(md):
    out, cur = {}, None
    for line in md.splitlines():
        m = re.match(r'^##\s+(?:\d+\.\s*)?(.+?)\s*$', line)
        if m and not line.startswith('###'):
            cur = m.group(1).lower()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def find_section(secs, *keys):
    for name, lines in secs.items():
        if any(k in name for k in keys):
            return lines
    return []


def table(lines):
    rows = []
    for line in lines:
        if not line.strip().startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if all(set(c) <= set('-: ') for c in cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else []  # drop header


def parse_cases(lines):
    cases, cur = [], None
    for line in lines:
        m = re.match(r'^###\s+(TC-\d+)\s*[–-]\s*(.*)$', line)
        if m:
            cur = {'id': m.group(1), 'title': m.group(2).strip()}
            cases.append(cur)
            continue
        f = re.match(r'^-\s*([A-Za-z ]+):\s*(.*)$', line)
        if cur is not None and f:
            cur[f.group(1).strip().lower()] = f.group(2).strip()
    for c in cases:
        cov = c.get('covers', '')
        c['acs'] = re.findall(r'AC-\d+', cov.split('·')[0]) if cov else []
        c['mode'] = 'Manual' if re.search(r'Mode:\s*Manual', cov, re.I) else 'Auto'
        c['type'] = (re.search(r'Type:\s*([^·]+)', cov) or [None, ''])[1].strip()
        c['priority'] = (re.search(r'Priority:\s*(P\d)', cov) or [None, ''])[1]
        c['status'] = c.get('status', 'approved').split('|')[0].strip().lower()
    return cases


# ---------- helpers ----------

def rel(p, root):
    if not p:
        return p
    try:
        return os.path.relpath(p, root) if os.path.isabs(p) and Path(p).resolve().is_relative_to(Path(root).resolve()) else p
    except Exception:
        return p


OUT_DIR = '.'  # the report's folder; set in __main__


def link(p, root):
    """Markdown link to an evidence file, relative to the report so it opens from the IDE / GitHub.
    None when the file is gone (prune_run.py keeps only annotated and Figma images)."""
    if not p:
        return None
    f = Path(p) if os.path.isabs(p) else Path(root) / p
    if not f.exists():
        return None
    r = os.path.relpath(f, OUT_DIR)
    return f'[{f.name}]({r.replace(" ", "%20")})'


def final_results(results):
    by = defaultdict(list)
    for r in results:
        by[(r['case'], r['lang'])].append(r)
    return {k: sorted(v, key=lambda r: r['attempt']) for k, v in by.items()}


def sev_rank(f):
    return (SEV.index(f.get('severity')) if f.get('severity') in SEV else 9,
            CLASS_ORDER.index(f['classification']) if f['classification'] in CLASS_ORDER else 9)


def fmt_dur(started, finished):
    try:
        a = datetime.fromisoformat(started.replace('Z', '+00:00'))
        b = datetime.fromisoformat(finished.replace('Z', '+00:00'))
        s = int((b - a).total_seconds())
        return f'{s // 3600}h {s % 3600 // 60:02d}m' if s >= 3600 else f'{s // 60}m {s % 60:02d}s'
    except Exception:
        return 'unknown'


def finding_md(f, root):
    ev = f.get('evidence') or {}
    lines = [f"### {f['id']} – {f['title']} ({f.get('severity', '—')})"]
    head = []
    if f.get('ac'):
        head.append(f"AC: {f['ac']}")
    if f.get('beyondStory'):
        head.append(f"Beyond-the-story rule: {f['beyondStory']}")
    head.append(f"Case: {f.get('case', '—')}")
    head.append(f"Language: {f.get('lang', '—')}")
    head.append(f"Class: {f['classification']}")
    if f.get('confidence'):
        head.append(f"Confidence: {f['confidence']}")
    lines.append('- ' + ' · '.join(head))
    if f.get('steps'):
        lines.append(f"- Steps to reproduce: {f['steps']}")
    lines.append(f"- Expected: {f.get('expected', '—')}")
    lines.append(f"- Actual: {f.get('actual', '—')}")
    shots = [l for l in (link(ev.get(k), root) for k in ('annotated', 'screenshot')) if l]
    if shots:
        lines.append('- Evidence: ' + ' · '.join(shots))
    if ev.get('network'):
        lines.append(f"- Network: {ev['network']}")
    if ev.get('logErrors'):
        lines.append('- Log errors: ' + '; '.join(str(e).replace('\n', ' ⏎ ') for e in ev['logErrors']))
    if f.get('code'):
        lines.append('- Code: ' + ', '.join(f'`{c}`' for c in f['code']))
    opts = f.get('fixOptions') or []
    if opts:
        lines.append('- Fix options:')
        for i, o in enumerate(opts, 1):
            lines.append(f"  {i}. {'(Recommended) ' if o.get('recommended') else ''}{o['text']}")
    if f.get('retest'):
        lines.append('- Re-test: ' + ', '.join(f['retest']))
    # verified: true = a verifier confirmed it, false = a verifier downgraded it, absent / null =
    # no verifier ran (only Bug and Content issue candidates get one) — never call that "downgraded"
    why = re.sub(r'^(downgraded|confirmed|not run)\s*[:—-]\s*', '', f.get('verifierReason') or '', flags=re.I)
    if f.get('verified') is True or f.get('verified') is False:
        v = 'confirmed' if f['verified'] else 'downgraded'
        lines.append(f"- Independent check: {v}" + (f" — {why}" if why else ''))
    elif why:
        lines.append(f"- Independent check: not run (only Bug and Content issue candidates get one) — {why}")
    return '\n'.join(lines)


def code_line(c):
    """Branch and commit the run tested, and any uncommitted changes the app ran with (run_meta.py code)."""
    if not c:
        return 'not recorded'
    head = f"`{c.get('branch') or '?'}` @ `{c.get('commit') or '?'}`"
    n = c.get('uncommittedCount', 0)
    if not n:
        return head + ' · no uncommitted changes'
    listed = ', '.join(f'`{p}`' for p in c.get('uncommitted', []))
    more = n - len(c.get('uncommitted', []))
    return head + f" · **plus {n} uncommitted change{'s' if n > 1 else ''}**: {listed}" + (f' (+{more} more)' if more > 0 else '')


def skill_line(sk):
    if not sk:
        return 'not recorded'
    return f"`{sk.get('commit') or 'no git'}`" + (' + local changes' if sk.get('dirty') else '') + \
        f" · scripts `{sk.get('scriptsHash', '?')}`"


def blocked(r):
    """The attempt stopped before the case's EXPECT check (flow / app / timeout): its expected
    result was never checked, so it is neither a pass nor a confirmed failure. Records written
    before failKind existed count as plain failures."""
    return r['status'] != 'passed' and 'failKind' in r and r['failKind'] != 'check'


def step_of(r):
    fc = r.get('failedCommand') or {}
    return (fc.get('message') or r.get('error') or '?')[:140]


def blocked_lines(runs, fin, info):
    """Summary note: which pairs never reached their check, grouped by the step that stopped them."""
    by, errs = defaultdict(list), defaultdict(list)
    for k in runs:
        if k in fin and blocked(fin[k][-1]):
            r = fin[k][-1]
            g = (r['failKind'], step_of(r))
            by[g].append(f'{k[0]} {k[1]}')
            if r.get('appError') and r['appError'] not in errs[g]:
                errs[g].append(r['appError'])
    out = []
    for (kind, step), pairs in by.items():
        why = ' — the app showed ' + ' / '.join(f'"{e}"' for e in errs[(kind, step)]) if errs[(kind, step)] else ''
        out.append(f'- **Blocked ({kind}):** {", ".join(pairs)} stopped at `{step}`{why}. '
                   'Expected results not checked.')
    for st in info.get('stoppedEarly') or []:
        out.append(f"- **Stopped early ({st.get('lang', '?')}):** {', '.join(st.get('remaining') or [])} not run — "
                   f"the cases before them all stopped at `{st.get('step', '?')}`.")
    return (['**Not checked**', ''] + out + ['']) if out else []


def failed_any(runs, fin):
    return any(k in fin and fin[k][-1]['status'] != 'passed' for k in runs)


def covered(findings):
    m = defaultdict(list)
    for f in findings:
        for c in str(f.get('case', '')).split(','):
            for l in str(f.get('lang', '')).split(','):
                m[(c.strip(), l.strip())].append(f['id'])
    return m


def retest_table(a, info, runs, fin, findings):
    """Before/now per retested pair; 'before' comes from the previous run's triage.json."""
    prev_id = info.get('retestOf', '?')
    prev = Path(a.run_info).resolve().parents[2] / prev_id / 'artifacts' / 'triage.json'
    before = covered(json.load(open(prev)).get('findings', [])) if prev.exists() else {}
    now = covered(findings)
    out = [f'### Retest of run `{prev_id}`', '', '| Case | Language | Before | Now |', '| --- | --- | --- | --- |']
    tally = Counter()
    for k in runs:
        r = fin.get(k)
        if not r:
            state = 'not run'
        elif r[-1]['status'] == 'passed':
            state = '**fixed**'
        elif blocked(r[-1]):
            # the fix is unverified: the case never got to the check that failed before
            state = 'blocked — check not reached'
        else:
            state = 'still failing'
        tally[state] += 1
        b = ', '.join(before.get(k, [])) or 'failed'
        n = state if state != 'still failing' else state + (' — ' + ', '.join(now[k]) if now.get(k) else '')
        out.append(f'| {k[0]} | {k[1]} | {b} | {n} |')
    line = f"{tally['**fixed**']} of {len(runs)} pairs fixed · {tally['still failing']} still failing"
    if tally['blocked — check not reached'] or tally['not run']:
        line += (f" · {tally['blocked — check not reached'] + tally['not run']} not verified "
                 '(blocked or not run: retest them once the blocking step works)')
    out += ['', line + '.', '']
    return out


def block(title, items, root, empty):
    out = [f'## {title}', '']
    out += ([finding_md(f, root) + '\n' for f in items] if items else [empty, ''])
    return out


# ---------- build ----------

def build(a):
    root = a.repo_root
    md = Path(a.cases).read_text(encoding='utf-8')
    secs = sections(md)
    title_line = md.splitlines()[0] if md else ''
    acs = table(find_section(secs, 'acceptance'))
    # each gap keeps the answers written under it ("→ Answer (<date>): …")
    spec_gaps = []
    for l in find_section(secs, 'spec gap'):
        t = l.strip()
        if t.startswith('- SPEC-GAP'):
            spec_gaps.append(t[2:])
        elif t.startswith('→') and spec_gaps:
            spec_gaps[-1] += ' **' + t.lstrip('→ ').split(':', 1)[0] + ':**' + t.split(':', 1)[1]
    static = table(find_section(secs, 'static'))
    data_rows = table(find_section(secs, 'test data'))
    cases = parse_cases(find_section(secs, 'test cases'))
    results = json.load(open(a.results)) if Path(a.results).exists() else []
    triage = json.load(open(a.triage)) if Path(a.triage).exists() else {'findings': [], 'flowFixes': []}
    info = json.load(open(a.run_info)) if Path(a.run_info).exists() else {}
    findings = sorted(triage.get('findings', []), key=sev_rank)
    # Steps to reproduce default to the case's steps with the entered test data filled in.
    # `local` values live in git-ignored test-data.local.json and never reach the report
    values = {r[0].strip('`'): ('not in git' if r[2].strip('`').lower() == 'local' else r[2])
              for r in data_rows if len(r) > 2 and '{{' not in r[2]}
    for f in findings:
        first_case = str(f.get('case', '')).split(',')[0].strip()
        c = next((x for x in cases if x['id'] == first_case), None)
        if c and not f.get('steps') and c.get('steps'):
            f['steps'] = re.sub(r'\{\{(\w+)\}\}', lambda m: f"{m.group(1)} ({values.get(m.group(1), '?')})", c['steps'])
            if c.get('preconditions'):
                f['steps'] = f"Precondition: {c['preconditions']}. " + f['steps']
    fixes = triage.get('flowFixes', [])
    fin = final_results(results)

    outside = [f for f in findings if f.get('scope') == 'outside']
    inside = [f for f in findings if f.get('scope') != 'outside']
    by_class = defaultdict(list)
    for f in inside:
        by_class[f['classification']].append(f)

    # verdict
    bugs = by_class['Bug']
    worst = min((SEV.index(f['severity']) for f in bugs if f.get('severity') in SEV), default=9)
    auto_runs = [(c['id'], l) for c in cases if c['mode'] == 'Auto' and c['status'] == 'approved' for l in LANGS]
    # retest run: only the pairs that failed in the previous run are in scope
    scope = {(x['case'], x['lang']) for x in info.get('scope') or []}
    if scope:
        auto_runs = [k for k in auto_runs if k in scope]
    # pairs the user chose not to run (English skipped or limited after the Arabic run)
    user_skipped = {(x['case'], x['lang']) for x in info.get('skippedByUser') or []}
    skipped_pairs = [k for k in auto_runs if k in user_skipped]
    auto_runs = [k for k in auto_runs if k not in user_skipped]
    not_run = [k for k in auto_runs if k not in fin]
    # pairs whose expected result was never checked: a run cannot pass on them
    unchecked = [k for k in auto_runs if k not in fin or blocked(fin[k][-1])]
    blockers = sorted({fid for k in unchecked for fid in covered(findings).get(k, [])})
    gap = (f'{len(unchecked)} of {len(auto_runs)} pairs not checked'
           + (f" (blocked by {', '.join(blockers)})" if blockers else ''))
    if a.aborted:
        verdict = f'ABORTED — {a.aborted}'
    elif worst <= 1:
        verdict = 'FAIL — the story has Critical/High bugs' + (f'; {gap}' if unchecked else '')
    elif unchecked:
        verdict = f'INCOMPLETE — {gap}'
    elif findings or (scope and failed_any(auto_runs, fin)):
        verdict = 'PASS WITH ISSUES'
    else:
        verdict = 'PASS'
    passed = sum(1 for k in auto_runs if k in fin and fin[k][-1]['status'] == 'passed')
    n_blocked = sum(1 for k in auto_runs if k in fin and blocked(fin[k][-1]))
    failed = sum(1 for k in auto_runs if k in fin and fin[k][-1]['status'] != 'passed') - n_blocked

    out = [f"# Test report – {info.get('feature', '')} – {info.get('storyTitle') or title_line.split('–')[-1].strip()}", '']
    out.append(f"Run `{info.get('runId', '?')}` · {info.get('platform', '?')} · Env: {info.get('env', '?')}"
               f" · Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    out.append('')
    out.append(f"> Screenshots live in the git-ignored `test-runs/{info.get('runId', '<runId>')}/` folder next to this "
               'report, on the machine that ran the tests (only annotated failures and Figma comparisons are kept). '
               'Every finding is written out in full so this report stands alone.')
    if a.aborted:
        out += ['', f'> **Run aborted:** {a.aborted}. Results below cover what ran before the stop.']
    out.append('')

    # 1. Summary
    out += ['## 1. Summary', '', f'**Verdict:** {verdict}', '',
            f'Automated runs: {passed} passed · {failed} failed · '
            + (f'{n_blocked} blocked (check not reached) · ' if n_blocked else '')
            + f'{len(not_run)} not run '
            + (f'· {len(skipped_pairs)} skipped by you ' if skipped_pairs else '')
            + (f"(retest of run `{info.get('retestOf', '?')}`: the {len(auto_runs)} case × language pairs that failed there) · "
               if scope else f'(of {len(auto_runs) + len(skipped_pairs)} = {(len(auto_runs) + len(skipped_pairs)) // 2} cases × ar/en) · ') +
            f"Manual cases: {sum(1 for c in cases if c['mode'] == 'Manual' and c['status'] != 'skip')} · "
            f"Skipped: {sum(1 for c in cases if c['status'] == 'skip')}", '']
    counts = Counter((f['classification'], f.get('severity', '—')) for f in findings)
    classes = [c for c in CLASS_ORDER if any(k[0] == c for k in counts)]
    if classes:
        out += ['| Category | ' + ' | '.join(SEV) + ' | Total |', '| --- |' + ' --- |' * (len(SEV) + 1)]
        for c in classes:
            row = [counts.get((c, s), 0) for s in SEV]
            out.append(f'| {c} | ' + ' | '.join(str(x) for x in row) + f' | {sum(row)} |')
        out.append('')
    # by severity across classes: a High environment blocker outranks a Low spec gap
    top = [f for f in findings if f['classification'] not in ('Flaky', 'Test error', 'Test error (expectation)')][:3] \
        or findings[:3]
    if top:
        out.append('**Top issues**')
        out += [f"{i}. {f['id']} ({f.get('severity', '—')}, {f['classification']}): {f['title']}" for i, f in enumerate(top, 1)]
        out.append('')

    out += blocked_lines(auto_runs, fin, info)
    if scope:
        out += retest_table(a, info, auto_runs, fin, findings)

    # 2. Run information
    ids = info.get('testIdsAdded') or []
    pts = info.get('passThroughs') or []
    out += ['## 2. Run information', '',
            '| Item | Value |', '| --- | --- |',
            f"| Story | {info.get('story', '—')} |",
            f"| Feature | `{info.get('featurePath', '—')}` |",
            f"| Code tested | {code_line(info.get('code'))} |",
            f"| Platform / device / OS | {info.get('platform', '—')} · {info.get('device', '—')} · {info.get('os', '—')} |",
            f"| Environment | {info.get('env', '—')} ({info.get('apiBase', '—')}) |",
            f"| Maestro | {info.get('maestro', '—')} |",
            f"| test-story | {skill_line(info.get('skill'))} |",
            f"| Languages | {info.get('langChoice') or 'ar, en'} |",
            f"| Run duration | {fmt_dur(info.get('started', ''), info.get('finished', ''))} |",
            f"| Network log | {'captured' if info.get('networkLogVisible', True) else 'NOT visible (see Gaps)'} |",
            f"| Figma | {info.get('figma', 'not run')} |", '']
    if data_rows:
        out += ['**Test data used**', '', '| Key | Meaning | Value | Used by |', '| --- | --- | --- | --- |']
        out += [f'| {r[0]} | {r[1] if len(r) > 1 else ""} | {values.get(r[0].strip("`"), r[2] if len(r) > 2 else "")} | {r[3] if len(r) > 3 else ""} |' for r in data_rows]
        out.append('')
    out += ['**Production changes made by the run** (testID props and pass-throughs only)', '']
    if ids or pts:
        out += ['| File | Line | Change |', '| --- | --- | --- |']
        out += [f"| `{x['file']}` | {x.get('line', '')} | testID `{x['id']}` |" for x in ids]
        out += [f"| `{x['file']}` | {x.get('line', '')} | testID pass-through on {x.get('component', '')} |" for x in pts]
    else:
        out.append('None.')
    out.append('')
    for n in info.get('notes') or []:
        out.append(f'- {n}')
    if info.get('notes'):
        out.append('')

    # 3. Bugs (+ content issues: wrong CMS / server text, fixed outside the app code)
    out += block('3. Bugs', bugs, root, 'No bugs confirmed.')
    if by_class['Content issue']:
        out += ['### Content issues (CMS or server text — fix the content, not the app)', '']
        out += [finding_md(f, root) + '\n' for f in by_class['Content issue']]

    # 4. Gaps
    out += ['## 4. Gaps', '']
    missing = [r for r in acs if len(r) >= 5 and r[4].lower() in ('missing', 'partial')]
    sf = defaultdict(list)
    for r in static:
        if len(r) >= 4:
            sf[r[1].lower()].append(r)
    wrote = False
    if spec_gaps or by_class['Spec gap']:
        out += ['### Spec gaps', '']
        if spec_gaps:
            out += [f'- {g}' for g in spec_gaps] + ['']
        out += [finding_md(f, root) + '\n' for f in by_class['Spec gap']]
        wrote = True
    if missing or sf.get('missing implementation'):
        out += ['### Missing implementation', '']
        out += [f'- {r[0]} ({r[4]}): {r[1]} — code: {r[3]}' for r in missing]
        out += [f'- {r[0]}: {r[2]} — `{r[3]}`' for r in sf.get('missing implementation', [])]
        out.append('')
        wrote = True
    for kind, head in (('undocumented behaviour', 'Undocumented behaviour'), ('unhandled api error', 'Unhandled API errors'),
                       ('missing translation', 'Missing translations'), ('hard-coded string', 'Hard-coded strings')):
        rows = [r for k, v in sf.items() if k.startswith(kind[:12]) for r in v]
        if rows:
            out += [f'### {head}', ''] + [f'- {r[0]}: {r[2]} — `{r[3]}`' for r in rows] + ['']
            wrote = True
    if not info.get('networkLogVisible', True):
        out += ['### Network logging not visible', '',
                '- API calls did not reach the captured Metro log, so triage used screen evidence only.', '']
        wrote = True
    if not wrote:
        out += ['No gaps found.', '']

    # 5–9
    dd_empty = 'No design deviations.' if str(info.get('figma', '')).startswith('compared') else \
        f"Figma comparison {info.get('figma', 'not run')}."
    out += block('5. Design deviations', by_class['Design deviation'], root, dd_empty)
    out += block('6. Test data issues', by_class['Test data issue'], root, 'None.')
    out += block('7. Environment issues', by_class['Environment issue'], root, 'None.')
    out += block('8. Flaky tests', by_class['Flaky'], root, 'None.')
    te = by_class['Test error (expectation)'] + by_class['Test error']
    out += ['## 9. Test errors', '']
    out += [finding_md(f, root) + '\n' for f in te] if te else ['None.', '']
    if fixes:
        out += ['Flows fixed once during triage (then passed; not failures):', '']
        out += [f"- {x['case']} {x['lang']}: {x['change']} → {x['result']}" for x in fixes]
        out.append('')

    # 10. Manual
    manual = [c for c in cases if c['mode'] == 'Manual' and c['status'] != 'skip']
    out += ['## 10. Manual verification required', '']
    if manual:
        for c in manual:
            out += [f"### {c['id']} – {c['title']}",
                    f"- Covers: {', '.join(c['acs']) or '—'} · Why manual: {c.get('preconditions', '—')}",
                    f"- Steps: {c.get('steps', '—')}", f"- Expected: {c.get('expected', '—')}",
                    '- Result: ☐ pass ☐ fail — tested by ____ on ____', '']
    else:
        out += ['None.', '']

    # 11–12
    out += block('11. Outside feature scope', outside, root, 'None.')
    beyond = [f for f in findings if f.get('beyondStory')]
    out += ['## 12. Beyond-the-story findings', '']
    out += [f"- {f['id']} ({f['classification']}, {f.get('severity', '—')}) — {f['beyondStory']}: {f['title']}"
            for f in beyond] if beyond else ['None.']
    out.append('')

    # 13. Coverage
    def cell(cid, lang):
        c = next((x for x in cases if x['id'] == cid), None)
        if c and c['status'] == 'skip':
            return 'skip'
        if c and c['mode'] == 'Manual':
            return 'manual'
        r = fin.get((cid, lang))
        if (cid, lang) in user_skipped:
            return 'skipped by you'
        if scope and (cid, lang) not in scope:
            return '–'
        if not r:
            return 'not run'
        if r[-1]['status'] == 'passed':
            return 'pass'
        return 'BLOCKED' if blocked(r[-1]) else 'FAIL'
    out += ['## 13. Coverage matrix', '']
    if scope:
        out += ['`–` = not part of this retest (see the previous report).', '']
    out += ['| AC | Cases | en | ar |', '| --- | --- | --- | --- |']
    for r in sorted(acs, key=lambda r: int(re.sub(r'\D', '', r[0]) or 0)):
        ac = r[0]
        cids = [c['id'] for c in cases if ac in c['acs']]
        en = ', '.join(f'{cid} {cell(cid, "en")}' for cid in cids) or '—'
        ar = ', '.join(f'{cid} {cell(cid, "ar")}' for cid in cids) or '—'
        out.append(f"| {ac} | {', '.join(cids) or 'NO CASE'} | {en} | {ar} |")
    out.append('')

    # 14. Appendix
    out += ['## 14. Appendix', '', '### Case results', '',
            '| Case | Title | Mode | en | ar | Attempts | Duration (s) |', '| --- | --- | --- | --- | --- | --- | --- |']
    for c in cases:
        att = max([len(fin.get((c['id'], l), [])) for l in LANGS] or [0])
        dur = [fin[(c['id'], l)][-1].get('durationSec') for l in LANGS if (c['id'], l) in fin]
        dur_s = ' / '.join(f'{d:.0f}' for d in dur if d is not None) or '—'
        out.append(f"| {c['id']} | {c['title']} | {c['mode']} | {cell(c['id'], 'en')} | {cell(c['id'], 'ar')} | {att or '—'} | {dur_s} |")
    out.append('')
    fails = [(k, v) for k, v in fin.items() if any(r['status'] != 'passed' for r in v)]
    if fails:
        out += ['### Failure messages', '']
        for (cid, lang), runs in sorted(fails):
            for r in runs:
                if r['status'] != 'passed':
                    out.append(f"- {cid} {lang} attempt {r['attempt']}: {r['error'][:300]}")
        out.append('')
    ann = sorted({l for f in findings for k in ('annotated', 'screenshot')
                  if (l := link((f.get('evidence') or {}).get(k), root))})
    shots = sorted({l for r in results for s in r.get('screenshots', []) if (l := link(s, root))} - set(ann))
    out += ['### Screenshot index', '']
    out += [f'- {s}' for s in ann + shots] or ['None.']
    out.append('')
    return '\n'.join(out)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for f in ('cases', 'results', 'triage', 'run-info', 'out'):
        p.add_argument('--' + f, required=True)
    p.add_argument('--repo-root', default='.')
    p.add_argument('--aborted', default='')
    a = p.parse_args()
    OUT_DIR = str(Path(a.out).resolve().parent)
    text = build(a)
    # Last line of defence for hard rule 8: refuse to write a report that carries credentials.
    leak = re.search(r'(Bearer\s+[A-Za-z0-9\-._~+/]{12,}|eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.|'
                     r'"?(clientSecret|client_secret|paymentEncryptionKey|paymentEncryptionIv|password)"?\s*[:=]\s*"?[^"\s,*\[]{6,})',
                     text, re.I)
    if leak:
        raise SystemExit(json.dumps({'error': 'possible secret in report; mask it in triage.json and rebuild',
                                     'match': leak.group(0)[:24] + '…'}))
    # real test data (test-data.local.json) must not reach a committed report
    local_file = Path(a.cases).parent / 'test-data.local.json'
    local = json.loads(local_file.read_text(encoding='utf-8')) if local_file.exists() else {}
    hits = [k for k, v in local.items() if len(str(v)) >= 4 and str(v) in text]
    if hits:
        raise SystemExit(json.dumps({'error': 'real test data in report; refer to it by key in triage.json and rebuild',
                                     'keys': hits}))
    Path(a.out).write_text(text, encoding='utf-8')
    print(json.dumps({'out': a.out, 'lines': text.count('\n') + 1}))
