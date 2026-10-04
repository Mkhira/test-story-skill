#!/usr/bin/env python3
"""Maestro JUnit → results.json (the run's resume checkpoint).

  parse_results.py append --junit J --console C --outdir D --results R --case TC-04 --lang en
                          --attempt 1 --start ISO --end ISO --exit N --flow F --shots <runDir>/<lang>
                          [--app-error REGEX]
      Appends one record, copies named screenshots to --shots, the failure screenshot to
      --shots/<case>_fail[_aN].png and its hierarchy to <runDir>/artifacts/hierarchy/, prints the record.
  parse_results.py status --results R --cases TC-01,TC-02 [--langs ar,en] [--pairs TC-04:en,TC-11:ar]
      Final state per case and language, and the (case, lang) pairs still to run → resume point.
      --pairs replaces cases × langs. Without it, a run-info.json `scope` (retest run) next to
      results.json limits the pairs to that scope.
  parse_results.py failed --results R
      Retest scope: the (case, lang) pairs whose final attempt did not pass, plus the run's
      scope pairs that never ran (an interrupted retest).

Each record carries `failedCommand` (Maestro's failing step: type, label, message) and `failKind`:
  check   – a step labelled "EXPECT …" failed: the expected result was not met on a settled screen.
            Deterministic; run_suite.py does not retry it.
  timeout – the per-case time limit killed Maestro.
  app     – another step failed while the failure screen shows an app error (a text matching
            --app-error, default: generic "Something went wrong" dialogs). The app refused the step
            (e.g. a server call it could not handle) → deterministic, not retried. `appError` holds
            the matched text.
  flow    – any other step (tap, input, navigation wait, subflow): can be timing → retried once.
Only `check` means the case reached its expected result; every other kind stopped before it
("blocked" in the report: the expected result was never checked).
"""
import argparse
import fcntl
import json
import re
import shutil
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from pathlib import Path


def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() and p.stat().st_size else []


def save(path, records):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(path)  # atomic, so an interrupted run never leaves half a checkpoint


@contextmanager
def locked(path):
    # en and ar run in parallel on two devices and append to the same results.json
    with open(str(path) + '.lock', 'w') as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def find_label(obj):
    # where Maestro stores `label:` differs by command type, so search the whole command object
    if isinstance(obj, dict):
        if isinstance(obj.get('label'), str):
            return obj['label']
        for v in obj.values():
            hit = find_label(v)
            if hit:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = find_label(v)
            if hit:
                return hit
    return ''


def failed_command(outdir):
    """The step Maestro marked FAILED (deepest one wins: a failing subflow step, not its runFlow)."""
    best = None
    for cj in Path(outdir).rglob('commands.json'):
        try:
            cmds = json.loads(cj.read_text(encoding='utf-8'))
        except Exception:
            continue
        for c in cmds:
            md = c.get('metadata') or {}
            if md.get('status') != 'FAILED':
                continue
            body = c.get('command') or {}
            ctype = next(iter(body), '?')
            inner = body.get(ctype) or {}
            cand = {'type': ctype, 'label': find_label(body),
                    'message': ((md.get('error') or {}).get('message') or '')[:300],
                    'depth': md.get('depth', 0)}
            if best is None or cand['depth'] >= best['depth']:
                best = cand
    return best


# Generic error-dialog titles (en/ar). Projects pass their own with --app-error (Phase 2 finds them).
# Console "[ERROR]" lines are left out on purpose: dev builds show unrelated console errors on
# every screen, and matching them would stop the retry that rescues real timing flakes.
DEFAULT_APP_ERROR = r'Something went wrong|An error occurred|Unexpected error|حدث خطأ'


def screen_texts(hier_path):
    texts = []

    def walk(n):
        if isinstance(n, dict):
            at = n.get('attributes') or {}
            for k in ('text', 'accessibilityText', 'hintText'):
                if at.get(k):
                    texts.append(str(at[k]))
            for c in n.get('children') or []:
                walk(c)
    try:
        walk(json.loads(Path(hier_path).read_text(encoding='utf-8', errors='replace')))
    except Exception:
        pass
    return texts


def app_error(hier_path, regex):
    if not hier_path or not regex:
        return ''
    for t in screen_texts(hier_path):
        m = re.search(regex, t)
        if m:
            return t[:160]
    return ''


def fail_kind(status, exit_code, cmd, app_err=''):
    if status == 'passed':
        return None
    if exit_code in ('142', '14'):
        return 'timeout'
    if cmd and cmd['label'].upper().startswith('EXPECT'):
        return 'check'
    if app_err:
        return 'app'
    return 'flow'


def append(a):
    status, error, duration = 'error', '', None
    jp = Path(a.junit)
    if jp.exists() and jp.stat().st_size:
        tc = ET.parse(jp).getroot().find('.//testcase')
        if tc is not None:
            duration = float(tc.get('time') or 0)
            fail = tc.find('failure') if tc.find('failure') is not None else tc.find('error')
            status = 'failed' if fail is not None else 'passed'
            if fail is not None:
                error = (fail.get('message') or fail.text or '').strip()[:500]
    if status == 'error':
        console = Path(a.console).read_text(errors='replace') if Path(a.console).exists() else ''
        m = re.findall(r'\[Failed\].*', console)
        error = (m[-1] if m else ('timed out' if a.exit in ('142', '14') else console.strip()[-400:]))
    shots_dir = Path(a.shots)
    shots_dir.mkdir(parents=True, exist_ok=True)
    shots = []
    suffix = '' if a.attempt == '1' else f'_a{a.attempt}'
    for png in sorted(Path(a.outdir).rglob('takeScreenshot/*.png')):
        dest = shots_dir / f'{png.stem}{suffix}.png'
        shutil.copyfile(png, dest)
        shots.append(str(dest))
    # The raw Maestro dir lives outside the repo and run_flow.sh deletes it after this call
    # (it holds ~40 MB of simulator log per attempt), so the failure evidence is copied out first.
    failshot = sorted(Path(a.outdir).rglob('screenshots/*.png'))
    hier = sorted(Path(a.outdir).rglob('screen-hierarchy/*.json'))
    fail_png = fail_hier = None
    if failshot:
        fail_png = shots_dir / f'{a.case}_fail{suffix}.png'
        shutil.copyfile(failshot[-1], fail_png)
    if hier:
        hdir = shots_dir.parent / 'artifacts' / 'hierarchy'
        hdir.mkdir(parents=True, exist_ok=True)
        fail_hier = hdir / f'{a.case}_{a.lang}_fail{suffix}.json'
        shutil.copyfile(hier[-1], fail_hier)
    rec = {'case': a.case, 'lang': a.lang, 'attempt': int(a.attempt), 'status': status,
           'durationSec': duration, 'start': a.start, 'end': a.end, 'error': error,
           'flow': a.flow, 'screenshots': shots,
           'failureScreenshot': str(fail_png) if fail_png else None,
           'failureHierarchy': str(fail_hier) if fail_hier else None}
    cmd = failed_command(a.outdir) if status != 'passed' else None
    rec['failedCommand'] = cmd
    app_err = app_error(fail_hier, a.app_error or DEFAULT_APP_ERROR) if status != 'passed' else ''
    if app_err:
        rec['appError'] = app_err
    rec['failKind'] = fail_kind(status, a.exit, cmd, app_err)
    with locked(a.results):
        records = load(a.results)
        records.append(rec)
        save(a.results, records)
    return rec


def final_map(records):
    final = {}
    for r in sorted(records, key=lambda r: r['attempt']):
        final[(r['case'], r['lang'])] = r
    return final


def status(a):
    records = load(a.results)
    if a.pairs:
        pairs = [tuple(p.split(':')) for p in a.pairs.split(',') if p]
    else:
        cases = [c for c in a.cases.split(',') if c]
        info = Path(a.results).parent / 'run-info.json'
        meta = json.loads(info.read_text(encoding='utf-8')) if info.exists() else {}
        # --langs, else the run's languages (run-info), else the en + ar pair of older runs
        langs = [l for l in a.langs.split(',') if l] or meta.get('languages') or ['en', 'ar']
        pairs = [(c, l) for l in langs for c in cases]
        # a retest run only covers its scope; without this, resuming it would run every case
        scope = meta.get('scope')
        if scope:
            keep = {(x['case'], x['lang']) for x in scope}
            pairs = [p for p in pairs if p in keep]
    final = final_map(records)
    todo = [{'case': c, 'lang': l} for c, l in pairs if (c, l) not in final]
    return {'done': sum(1 for p in pairs if p in final), 'todo': todo,
            'final': [{'case': c, 'lang': l, 'status': final[(c, l)]['status'], 'attempt': final[(c, l)]['attempt'],
                       'failKind': final[(c, l)].get('failKind')}
                      for c, l in pairs if (c, l) in final]}


def failed(a):
    results = Path(a.results)
    final = final_map(load(results))
    pairs = [{'case': c, 'lang': l, 'failKind': r.get('failKind'), 'error': r.get('error', '')[:160]}
             for (c, l), r in sorted(final.items()) if r['status'] != 'passed']
    info = results.parent / 'run-info.json'
    scope = json.loads(info.read_text(encoding='utf-8')).get('scope') if info.exists() else None
    never = [{'case': p['case'], 'lang': p['lang'], 'failKind': None, 'error': 'not run'}
             for p in (scope or []) if (p['case'], p['lang']) not in final]
    return {'runId': results.parent.parent.name, 'pairs': pairs + never,
            'cases': sorted({p['case'] for p in pairs + never})}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('cmd', choices=['append', 'status', 'failed'])
    for f in ('junit', 'console', 'outdir', 'results', 'case', 'lang', 'attempt', 'start', 'end', 'exit', 'flow',
              'shots', 'cases', 'pairs', 'app-error'):
        p.add_argument('--' + f, default='')
    p.add_argument('--langs', default='')
    a = p.parse_args()
    print(json.dumps({'append': append, 'status': status, 'failed': failed}[a.cmd](a), ensure_ascii=False, indent=1))
