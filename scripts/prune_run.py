#!/usr/bin/env python3
"""Shrink a finished run folder to the evidence worth keeping (Phase 8, after triage_check).

  prune_run.py <runDir> [--dry-run] [--keep-runs N]
  prune_run.py --stale-tmp [--dry-run]

Kept:
  <lang>/*_annotated.png        failure screenshots with the red box (one per finding at least)
  figma-dd/**                   design-deviation side-by-sides (app next to Figma)
  figma/**                      the exported Figma frames they were compared against
  artifacts/{results,triage,run-info,data}.json, artifacts/metro.log
                                small; needed to rebuild the report or resume
Everything else is deleted: step screenshots, raw failure screenshots, hierarchy dumps, any
leftover Maestro output, and the run's temp dir under $TMPDIR/test-story/<runId>.
Prints JSON {kept, deleted, freedMB}. Run it before report_build.py so the report only lists
files that still exist.

--keep-runs N (default 5): afterwards, older run folders of the same story beyond the newest N
are deleted, except the run this one retests (its triage.json feeds the before → now table).
Their committed reports stay; only their machine-local screenshots go. Disk use per story is
bounded at about N × 5 MB.
--stale-tmp (Phase 0): deletes $TMPDIR/test-story/<runId> folders untouched for 6 hours — what a
crashed or killed run leaves behind (up to one case's simulator log, ~70 MB).
"""
import argparse
import json
import os
import shutil
import time
from pathlib import Path

KEEP_ARTIFACTS = {'results.json', 'triage.json', 'run-info.json', 'data.json', 'metro.log'}


def keep(rel: Path) -> bool:
    parts = rel.parts
    if parts[0] == 'artifacts':
        return len(parts) == 2 and parts[1] in KEEP_ARTIFACTS
    if 'figma-dd' in parts or parts[0] == 'figma':
        return True
    return rel.suffix == '.png' and rel.stem.endswith('_annotated') and len(parts) == 2


def size(p):
    return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())


def stale_tmp(dry):
    root = Path(os.environ.get('TMPDIR', '/tmp')) / 'test-story'
    gone, freed = [], 0
    for d in (root.iterdir() if root.exists() else []):
        newest = max([f.stat().st_mtime for f in d.rglob('*')] + [d.stat().st_mtime])
        if time.time() - newest > 6 * 3600:
            freed += size(d)
            gone.append(d.name)
            if not dry:
                shutil.rmtree(d)
    print(json.dumps({'dryRun': dry, 'staleTmpDeleted': gone, 'freedMB': round(freed / 1e6, 1)}))


def old_runs(run, keep, dry):
    info = run / 'artifacts' / 'run-info.json'
    protect = {run.name}
    if info.exists():
        protect.add(json.loads(info.read_text(encoding='utf-8')).get('retestOf') or '')
    runs = sorted((d for d in run.parent.iterdir() if d.is_dir()), key=lambda d: d.name, reverse=True)
    gone, freed = [], 0
    for d in runs[keep:]:
        if d.name in protect:
            continue
        freed += size(d)
        gone.append(d.name)
        if not dry:
            shutil.rmtree(d)
    return gone, freed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir', nargs='?')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--keep-runs', type=int, default=5)
    ap.add_argument('--stale-tmp', action='store_true')
    a = ap.parse_args()
    if a.stale_tmp:
        return stale_tmp(a.dry_run)
    run = Path(a.run_dir)
    if not (run / 'artifacts' / 'results.json').exists():
        raise SystemExit(json.dumps({'error': f'{run} has no artifacts/results.json; not a run folder'}))
    kept, deleted, freed = [], [], 0
    for f in sorted(p for p in run.rglob('*') if p.is_file()):
        rel = f.relative_to(run)
        if keep(rel):
            kept.append(str(rel))
            continue
        deleted.append(str(rel))
        freed += f.stat().st_size
        if not a.dry_run:
            f.unlink()
    if not a.dry_run:
        # drop directories left empty (maestro/, hierarchy/ …), deepest first
        for d in sorted((p for p in run.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
        tmp = Path(os.environ.get('TMPDIR', '/tmp')) / 'test-story' / run.name
        if tmp.exists():
            freed += sum(p.stat().st_size for p in tmp.rglob('*') if p.is_file())
            shutil.rmtree(tmp)
    gone, freed_old = old_runs(run, a.keep_runs, a.dry_run)
    print(json.dumps({'dryRun': a.dry_run, 'kept': kept, 'deletedCount': len(deleted),
                      'oldRunsDeleted': gone, 'freedMB': round((freed + freed_old) / 1e6, 1),
                      'runFolderMB': round(size(run) / 1e6, 1)}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
