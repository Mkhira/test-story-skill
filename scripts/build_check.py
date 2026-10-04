#!/usr/bin/env python3
"""Is the installed dev build the one this checkout needs? Run before run_app.sh (Phase 4 step 3).

  build_check.py <ios|android> <appId> <deviceId> [--record]

Run from the project root. Prints JSON:
  {"ok", "install": [{name, want, have}], "installCommand", "rebuild": true|false|null,
   "prebuild", "basis", "reasons": [...], "fingerprint", "recordedAt"}

Why: JS reaches the app through Metro, native code does not. After a branch switch or a pull that
adds a native package, the old build either crashes at launch or silently tests old native code.

1. node_modules against the lockfile (or package.json): a dependency missing or at another
   version → `install` lists it and `rebuild` is null (nothing native can be judged until the
   install is done; run this again after it).
2. Expo's native fingerprint (`@expo/fingerprint`: native packages, config plugins, app config,
   patches) against the record `--record` saved after the last build the skill made on this
   device. Different → `rebuild: true` with the changed sources. The installed app changed since
   the record (someone built outside the skill) → the record is ignored.
3. No usable record → iOS: native packages whose pods are missing from ios/Podfile.lock, or a
   Podfile.lock newer than the installed app → `rebuild: true`; nothing found → `rebuild: null`
   (unknown, basis "podfile"). Android: `rebuild: null` (basis "unknown").

`prebuild` is true when a rebuild is needed and the native folder is git-ignored (Expo CNG): run
`npx expo prebuild --platform <p> --no-install` before the build so new config plugins land
(`run_app.sh --build --prebuild` does both).

`--record` (run_app.sh calls it after a successful build) saves the current fingerprint and the
installed app's timestamp under ~/.cache/test-story/builds/.
"""
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CACHE = Path.home() / '.cache' / 'test-story' / 'builds'
SDK = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or str(Path.home() / 'Library/Android/sdk')


def run(cmd, timeout=180):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ''


def read_json(path):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return None


def install_command():
    for lock, cmd in (('package-lock.json', 'npm ci'), ('yarn.lock', 'yarn install --frozen-lockfile'),
                      ('pnpm-lock.yaml', 'pnpm install --frozen-lockfile'), ('bun.lockb', 'bun install'),
                      ('bun.lock', 'bun install')):
        if Path(lock).exists():
            return cmd
    return 'npm install'


def stale_modules(pkg):
    """Dependencies missing from node_modules, or at another version than package-lock.json pins."""
    lock = (read_json('package-lock.json') or {}).get('packages', {})
    out = []
    for name in sorted({**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}):
        have = (read_json(f'node_modules/{name}/package.json') or {}).get('version')
        want = lock.get(f'node_modules/{name}', {}).get('version')
        if have is None or (want and have != want):
            out.append({'name': name, 'want': want or pkg.get('dependencies', {}).get(name)
                        or pkg['devDependencies'][name], 'have': have})
    return out


def fingerprint(platform):
    code, out = run(['node_modules/.bin/fingerprint', 'fingerprint:generate', '--platform', platform])
    data = None
    if code == 0:
        try:
            data = json.loads(out)
        except ValueError:
            pass
    if not data:
        return None, {}
    return data['hash'], {(s.get('filePath') or s.get('id')): s['hash'] for s in data.get('sources', [])}


def installed_stamp(platform, app, dev):
    """When the installed app was last (re)installed — changes on every build, wherever it came from."""
    if platform == 'ios':
        code, out = run(['xcrun', 'simctl', 'get_app_container', dev, app])
        if code != 0:
            return None
        info = read_json_plist(Path(out.strip()) / 'Info.plist')
        exe = Path(out.strip()) / (info or {}).get('CFBundleExecutable', '')
        target = exe if exe.is_file() else Path(out.strip())
        return int(target.stat().st_mtime)
    adb = 'adb' if run(['which', 'adb'])[0] == 0 else f'{SDK}/platform-tools/adb'
    code, out = run([adb, '-s', dev, 'shell', 'dumpsys', 'package', app])
    for line in out.splitlines():
        if 'lastUpdateTime=' in line:
            return line.split('lastUpdateTime=')[1].strip()
    return None


def read_json_plist(path):
    code, out = run(['plutil', '-convert', 'json', '-o', '-', str(path)])
    try:
        return json.loads(out) if code == 0 else None
    except ValueError:
        return None


def record_path(app, dev):
    project = hashlib.sha1(str(Path.cwd().resolve()).encode()).hexdigest()[:12]
    return CACHE / f'{project}_{app}_{dev}.json'


def autolinking_excludes(pkg, platform):
    al = (pkg.get('expo') or {}).get('autolinking') or {}
    names = set(al.get('exclude') or [])
    for key in (['ios', 'apple'] if platform == 'ios' else ['android']):
        names |= set((al.get(key) or {}).get('exclude') or [])
    return names


def missing_pods(pkg):
    """Native packages (a podspec at the root, ios/ or apple/) whose pod is not in ios/Podfile.lock."""
    lock = Path('ios/Podfile.lock')
    if not lock.exists():
        return None
    text = lock.read_text(errors='replace')
    skip = autolinking_excludes(pkg, 'ios')
    out = []
    for name in sorted(pkg.get('dependencies', {})):
        if name in skip:
            continue
        specs = [Path(p).stem for d in ('', 'ios/', 'apple/')
                 for p in glob.glob(f'node_modules/{name}/{d}*.podspec')]
        if specs and not any(f'- {s} (' in text or f'- {s}/' in text for s in specs):
            out.append(f'{name} (pod {specs[0]})')
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) != 3 or args[0] not in ('ios', 'android'):
        raise SystemExit(__doc__)
    platform, app, dev = args
    pkg = read_json('package.json') or {}
    native_dir = 'ios' if platform == 'ios' else 'android'
    cng = subprocess.run(['git', 'check-ignore', '-q', native_dir]).returncode == 0
    rec_file = record_path(app, dev)
    res = {'ok': True, 'install': [], 'installCommand': None, 'rebuild': None, 'prebuild': False,
           'basis': 'unknown', 'reasons': [], 'fingerprint': None, 'recordedAt': None}

    if '--record' in sys.argv:
        fp, sources = fingerprint(platform)
        if not fp:
            print(json.dumps({'ok': False, 'reason': 'fingerprint unavailable (no @expo/fingerprint)'}))
            return 1
        rec_file.parent.mkdir(parents=True, exist_ok=True)
        json.dump({'fingerprint': fp, 'sources': sources, 'installed': installed_stamp(platform, app, dev),
                   'recordedAt': time.strftime('%Y-%m-%d %H:%M')}, open(rec_file, 'w'))
        print(json.dumps({'ok': True, 'recorded': str(rec_file), 'fingerprint': fp}))
        return 0

    stale = stale_modules(pkg)
    if stale:
        res.update(ok=False, install=stale, installCommand=install_command(), basis='node_modules')
        res['reasons'].append(f'{len(stale)} package{"s" if len(stale) > 1 else ""} missing or at another '
                              'version in node_modules — install first, then run build_check again')
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0

    installed = installed_stamp(platform, app, dev)
    if installed is None:
        res.update(ok=False, rebuild=True, prebuild=cng, basis='not installed',
                   reasons=[f'{app} is not installed on {dev}'])
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0

    fp, sources = fingerprint(platform)
    res['fingerprint'] = fp
    rec = read_json(rec_file)
    if fp and rec and rec.get('installed') == installed:
        res.update(basis='fingerprint', recordedAt=rec.get('recordedAt'))
        if rec.get('fingerprint') == fp:
            res['rebuild'] = False
        else:
            old = rec.get('sources', {})
            changed = sorted(k for k in set(old) | set(sources) if old.get(k) != sources.get(k))
            res.update(ok=False, rebuild=True, prebuild=cng)
            res['reasons'].append(f'native fingerprint changed since the build of {rec.get("recordedAt")}: '
                                  + ', '.join(changed[:8]) + (f' (+{len(changed) - 8} more)' if len(changed) > 8 else ''))
    elif platform == 'ios':
        res['basis'] = 'podfile'
        pods = missing_pods(pkg)
        lock = Path('ios/Podfile.lock')
        if pods:
            res['reasons'].append('native packages not in ios/Podfile.lock: ' + ', '.join(pods))
        if lock.exists() and isinstance(installed, int) and lock.stat().st_mtime > installed:
            res['reasons'].append('ios/Podfile.lock changed after the installed build')
        if pods is None:
            res['reasons'].append('no ios/Podfile.lock (native folder not generated)')
        if res['reasons']:
            res.update(ok=False, rebuild=True, prebuild=cng)
        else:
            res['reasons'].append('no build record for this device yet: the build cannot be compared '
                                  'exactly; a --build now records it')
    else:
        res['reasons'].append('no build record for this device yet: the build cannot be compared; '
                              'a --build now records it')
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
