#!/usr/bin/env python3
"""Run one language's cases on one device, in order (Phase 5): Arabic first, then the English
cases the user chose. (Two suites can run in parallel on two devices — results.json is locked —
but only when the user asks.)

  run_suite.py --run <runDir> --e2e <story>/e2e --lang en --device <id> --platform ios --app <appId>
               --cases TC-01,TC-02 [--data <runDir>/artifacts/data.json] [--setup]
               [--login-marker REGEX] [--no-retry] [--timeout SEC]

--setup         run subflows/set-language-<lang>.yaml first (--no-record); failure stops the suite.
--login-marker  a regex that only the login screen shows; a failure whose hierarchy matches it
                stops the suite (session expired → the agent runs assisted login, re-runs that
                case with run_flow.sh --attempt N+1, then starts the suite again).
--no-retry      never retry (default: retry once when failKind is flow or timeout; a failed
                "EXPECT …" check is deterministic and is not retried).

Resume: a (case, lang) that already has a record in results.json is skipped.
Before every attempt, other third-party apps on the device are terminated (an app left in the
foreground stole focus and spoiled failure screenshots in the first real run).
Prints one JSON line per attempt, then a summary line. Exit 0 done, 4 setup failed, 5 login needed.
"""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def other_apps(platform, device, app):
    try:
        if platform == 'ios':
            raw = subprocess.run(['xcrun', 'simctl', 'listapps', device], capture_output=True).stdout
            data = json.loads(subprocess.run(['plutil', '-convert', 'json', '-o', '-', '--', '-'],
                                             input=raw, capture_output=True).stdout or b'{}')
            return [k for k, v in data.items() if v.get('ApplicationType') == 'User' and k != app]
        out = subprocess.run(['adb', '-s', device, 'shell', 'pm', 'list', 'packages', '-3'],
                             capture_output=True, text=True).stdout
        return [l.split(':', 1)[1].strip() for l in out.splitlines() if l.startswith('package:')
                and l.split(':', 1)[1].strip() != app]
    except Exception:
        return []


def terminate(platform, device, apps):
    for a in apps:
        cmd = (['xcrun', 'simctl', 'terminate', device, a] if platform == 'ios'
               else ['adb', '-s', device, 'shell', 'am', 'force-stop', a])
        subprocess.run(cmd, capture_output=True)


def last_json(text):
    # run_flow.sh prints exactly one (possibly indented) JSON object; Maestro output goes to console.log
    try:
        return json.loads(text[text.index('{'):]) if '{' in text else {}
    except Exception:
        return {}


def flow_for(e2e, case):
    hits = sorted(Path(e2e).glob(f'{case}_*.yaml'))
    return hits[0] if hits else None


def done_pairs(results):
    p = Path(results)
    if not p.exists() or not p.stat().st_size:
        return set()
    return {(r['case'], r['lang']) for r in json.loads(p.read_text(encoding='utf-8'))}


def run_flow(a, flow, case, attempt, record=True):
    cmd = [str(HERE / 'run_flow.sh'), str(flow), a.lang, a.run, a.device, case,
           '--attempt', str(attempt), '--timeout', str(a.timeout)]
    if a.data:
        cmd += ['--data', a.data]
    if not record:
        cmd.append('--no-record')
    t0 = time.time()
    out = subprocess.run(cmd, capture_output=True, text=True)
    rec = last_json(out.stdout)
    rec['_sec'] = round(time.time() - t0)
    return rec


def emit(**kw):
    print(json.dumps(kw, ensure_ascii=False), flush=True)


def main():
    ap = argparse.ArgumentParser()
    for f in ('run', 'e2e', 'lang', 'device', 'platform', 'app', 'cases'):
        ap.add_argument('--' + f, required=True)
    ap.add_argument('--data', default='')
    ap.add_argument('--setup', action='store_true')
    ap.add_argument('--login-marker', default='')
    ap.add_argument('--no-retry', action='store_true')
    ap.add_argument('--timeout', type=int, default=600)
    a = ap.parse_args()
    t_start = time.time()
    results = Path(a.run) / 'artifacts' / 'results.json'
    apps = other_apps(a.platform, a.device, a.app)
    summary = {'summary': True, 'lang': a.lang, 'device': a.device, 'passed': 0, 'failed': 0,
               'retried': 0, 'skipped': 0, 'terminatedApps': apps}

    if a.setup:
        terminate(a.platform, a.device, apps)
        rec = run_flow(a, Path(a.e2e) / 'subflows' / f'set-language-{a.lang}.yaml', f'SETUP-lang-{a.lang}', 1, False)
        emit(case=f'SETUP-lang-{a.lang}', status=rec.get('status'), error=rec.get('error', ''), sec=rec['_sec'])
        if rec.get('status') != 'passed':
            emit(**summary, stopped='setup-failed', maestroDir=rec.get('maestroDir'))
            raise SystemExit(4)

    done = done_pairs(results)
    for case in [c for c in a.cases.split(',') if c]:
        if (case, a.lang) in done:
            summary['skipped'] += 1
            continue
        flow = flow_for(a.e2e, case)
        if not flow:
            emit(case=case, lang=a.lang, status='error', error='no flow file')
            summary['failed'] += 1
            continue
        attempt = 1
        while True:
            terminate(a.platform, a.device, apps)
            rec = run_flow(a, flow, case, attempt)
            emit(case=case, lang=a.lang, attempt=attempt, status=rec.get('status'),
                 failKind=rec.get('failKind'), error=(rec.get('error') or '')[:160], sec=rec['_sec'])
            if rec.get('status') == 'passed':
                summary['passed'] += 1
                break
            hier = rec.get('failureHierarchy')
            if a.login_marker and hier and Path(hier).exists() and \
                    re.search(a.login_marker, Path(hier).read_text(encoding='utf-8', errors='replace')):
                emit(**summary, stopped='login-required', case=case, attempt=attempt)
                raise SystemExit(5)
            if attempt == 1 and not a.no_retry and rec.get('failKind') in ('flow', 'timeout'):
                attempt = 2
                summary['retried'] += 1
                continue
            summary['failed'] += 1
            break
    summary['minutes'] = round((time.time() - t_start) / 60, 1)
    emit(**summary)


if __name__ == '__main__':
    main()
