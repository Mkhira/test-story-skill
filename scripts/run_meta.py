#!/usr/bin/env python3
"""What ran: the skill's own version and the code under test, saved in run-info.json.

  run_meta.py skill --run <runDir>                 Phase 0 step 7: run-info `skill`
  run_meta.py code  --run <runDir> [--story <dir>] Phase 4, right before the app launches: run-info `code`
  run_meta.py check --run <runDir>                 skill scripts unchanged since `skill`? exit 7 if not

Run from the project root. Prints JSON.

skill: {commit, dirty, scriptsHash, recordedAt}. The scripts hash covers scripts/*.py and *.sh.
  Why: on 2026-10-04 the scripts were rewritten by another session in the middle of a run and one
  call died on an unbound variable. run_suite.py calls `check` before every case.
code: {branch, commit, uncommitted: [paths], uncommittedCount}. Uncommitted = tracked files with
  changes anywhere in the repo plus untracked source files (story folders excluded). Why: a
  retest of uncommitted fixes produced a report that did not say which code it tested.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SOURCE_EXT = ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.json', '.swift', '.m', '.mm', '.kt', '.java')
MAX_LISTED = 15


def git(*args, cwd=None, strip=True):
    p = subprocess.run(['git', *args], capture_output=True, text=True, cwd=cwd)
    if p.returncode != 0:
        return ''
    # porcelain lines start with a status column that may be a space: never strip those
    return p.stdout.strip() if strip else p.stdout


def scripts_hash():
    h = hashlib.sha1()
    for f in sorted((SKILL / 'scripts').glob('*')):
        if f.suffix in ('.py', '.sh') and f.is_file():
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:12]


def skill_state():
    return {'commit': git('rev-parse', '--short', 'HEAD', cwd=SKILL) or None,
            'dirty': bool(git('status', '--porcelain', cwd=SKILL)),
            'scriptsHash': scripts_hash(), 'recordedAt': time.strftime('%Y-%m-%d %H:%M')}


def code_state(story):
    skip = ('test-stories/',) + ((str(Path(story)).rstrip('/') + '/',) if story else ())
    paths = []
    for line in git('status', '--porcelain', '--untracked-files=all', strip=False).splitlines():
        status, path = line[:2], line[3:].split(' -> ')[-1].strip('"')
        if any(s in path for s in skip) or path.startswith('node_modules/'):
            continue
        if status == '??' and not path.endswith(SOURCE_EXT):
            continue
        paths.append(path)
    return {'branch': git('rev-parse', '--abbrev-ref', 'HEAD') or None,
            'commit': git('rev-parse', '--short', 'HEAD') or None,
            'uncommitted': paths[:MAX_LISTED], 'uncommittedCount': len(paths)}


def update_info(run, key, value):
    p = Path(run) / 'artifacts' / 'run-info.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    info = json.load(open(p)) if p.exists() else {}
    info[key] = value
    json.dump(info, open(p, 'w'), ensure_ascii=False, indent=1)
    return info


def check(run):
    """{ok, recorded, now}; ok is True when nothing was recorded (older runs) or nothing changed."""
    p = Path(run) / 'artifacts' / 'run-info.json'
    rec = (json.load(open(p)) if p.exists() else {}).get('skill') or {}
    now = scripts_hash()
    return {'ok': not rec.get('scriptsHash') or rec['scriptsHash'] == now,
            'recorded': rec.get('scriptsHash'), 'now': now}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['skill', 'code', 'check'])
    ap.add_argument('--run', required=True)
    ap.add_argument('--story', default='')
    a = ap.parse_args()
    if a.cmd == 'skill':
        print(json.dumps(update_info(a.run, 'skill', skill_state())['skill']))
    elif a.cmd == 'code':
        print(json.dumps(update_info(a.run, 'code', code_state(a.story))['code'], ensure_ascii=False))
    else:
        res = check(a.run)
        print(json.dumps(res))
        return 0 if res['ok'] else 7
    return 0


if __name__ == '__main__':
    sys.exit(main())
