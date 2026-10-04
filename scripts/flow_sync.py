#!/usr/bin/env python3
"""Keep Maestro flows in <story>/e2e/ in step with the approved cases in test-cases.md.

  flow_sync.py plan  <test-cases.md> <e2eDir>   → JSON: create / regenerate / delete / keep / skip / manual / handEdited
  flow_sync.py stamp <test-cases.md> <flow.yaml> → write the header (case id, case hash, flow hash) after the agent wrote the flow
  flow_sync.py data  <test-cases.md>            → JSON: {values: {KEY: value}, unfilled: [KEY], usedBy: {KEY: [TC]},
                                                  local: [KEY]}
  flow_sync.py messages <test-cases.md>         → JSON: {cases: [TC], others: [TC]} — approved Auto cases that
                                                  check a translated text (the "English only for message checks" set)
  flow_sync.py lint  <test-cases.md> <e2eDir>   → JSON: {ok, problems: [...]} — run before every suite (Phase 5)
  flow_sync.py smoke <test-cases.md> <e2eDir> [--min 3] → JSON: {subflows: [...]} — the shared subflows to run
                                                  once before the suite (Phase 4 deep smoke)

Test data: the Value column of the Test data table holds synthetic values. A real value (an ID,
mobile, email or account that exists) is kept out of git: the column says `local` and the value
lives in <story>/test-data.local.json ({"KEY": "value"}, git-ignored). Keys ending in _AR / _EN are
per-language variants: run_flow.sh passes them as KEY in that language's run.

A flow starts with three header comments:
  # test-story case: TC-04
  # test-story case-hash: <12 hex>   (case text without its Status line)
  # test-story flow-hash: <12 hex>   (everything below the header)
A flow whose body no longer matches its flow-hash was edited by hand → reported, never touched.
The flow-hash ignores whitespace and quote style (Prettier reformatting is not an edit); a flow
stamped before that rule (exact-text hash) still matches.
Subflows (e2e/subflows/) are not tracked here.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

CASE_RE = re.compile(r'^###\s+(TC-\d+)\s*[–-]\s*(.*)$')
HEADER_RE = re.compile(r'^#\s*test-story (case|case-hash|flow-hash):\s*(\S+)\s*$')


def h12(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]


def flow_norm(body):
    # flows are committed, so `prettier --write .` may re-indent them or swap ' and " quotes
    return '\n'.join(re.sub(r'\s+', '', l).replace('"', "'") for l in body.splitlines() if l.strip())


def body_matches(stored, body):
    return stored in (h12(flow_norm(body)), h12(body))


def field(block, name):
    m = re.search(r'^-\s*' + name + r':\s*(.+)$', block, re.M)
    return m.group(1).strip() if m else ''


def parse_cases(md_path):
    lines = Path(md_path).read_text(encoding='utf-8').splitlines()
    cases, cur = [], None
    for line in lines:
        m = CASE_RE.match(line)
        if m:
            cur = {'id': m.group(1), 'title': m.group(2).strip(), 'lines': [line]}
            cases.append(cur)
        elif line.startswith('## ') or line.startswith('### '):
            cur = None
        elif cur is not None:
            cur['lines'].append(line)
    out = []
    for c in cases:
        block = '\n'.join(c['lines']).strip()
        kept = [l for l in c['lines'] if not re.match(r'^-\s*Status:', l)]
        legacy = '\n'.join(l.rstrip() for l in kept).strip()
        # Prettier (run on test-cases.md so CI format:check passes) collapses spaces and adds blank
        # lines; hashing the whitespace-normalised text keeps formatting from looking like an edit.
        normal = '\n'.join(re.sub(r'\s+', ' ', l).strip() for l in kept if l.strip())
        status = field(block, 'Status').split('|')[0].strip().lower() or 'approved'
        mode_line = field(block, 'Covers')
        mode = 'manual' if re.search(r'Mode:\s*Manual', block, re.I) else 'auto'
        tags = field(block, 'Tags')
        out.append({'id': c['id'], 'title': c['title'], 'status': status, 'mode': mode,
                    'cleanState': 'needs-clean-state' in tags and not tags.lower().startswith('none'),
                    'darkMode': 'needs-dark-mode' in tags,
                    'hash': h12(normal), 'hashes': {h12(normal), h12(legacy)}, 'covers': mode_line})
    return out


def slug(title):
    s = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')
    return '_'.join(s.split('_')[:6]) or 'case'


def read_flow(path):
    text = Path(path).read_text(encoding='utf-8')
    lines = text.splitlines(keepends=True)
    header, i = {}, 0
    while i < len(lines):
        m = HEADER_RE.match(lines[i].rstrip('\n'))
        if not m:
            break
        header[m.group(1)] = m.group(2)
        i += 1
    body = ''.join(lines[i:])
    return header, body


def plan(md, e2e):
    cases = parse_cases(md)
    e2e = Path(e2e)
    flows = {}
    for f in sorted(e2e.glob('TC-*.yaml')) if e2e.exists() else []:
        cid = f.name.split('_')[0]
        flows[cid] = f
    res = {k: [] for k in ('create', 'regenerate', 'delete', 'keep', 'skip', 'manual', 'handEdited')}
    res['cleanStateLast'], res['darkModeLast'] = [], []
    ids = set()
    for c in cases:
        ids.add(c['id'])
        f = flows.get(c['id'])
        target = str(f) if f else str(e2e / f"{c['id']}_{slug(c['title'])}.yaml")
        entry = {'case': c['id'], 'title': c['title'], 'file': target}
        if c['mode'] == 'manual':
            res['manual'].append(entry)
            continue
        if c['status'] not in ('approved', 'skip'):
            continue  # proposed / NEW / CHANGED items are not runnable until approved
        if f is None:
            res['skip' if c['status'] == 'skip' else 'create'].append(entry)
            continue
        header, body = read_flow(f)
        if header.get('flow-hash') and not body_matches(header['flow-hash'], body):
            entry['reason'] = 'body differs from stored flow-hash'
            entry['caseChanged'] = header.get('case-hash') not in c['hashes']
            res['handEdited'].append(entry)
        elif c['status'] == 'skip':
            res['skip'].append(entry)
        elif header.get('case-hash') not in c['hashes']:
            res['regenerate'].append(entry)
        else:
            res['keep'].append(entry)
        if c['cleanState'] and c['status'] == 'approved':
            res['cleanStateLast'].append(c['id'])
        if c['darkMode'] and c['status'] == 'approved':
            res['darkModeLast'].append(c['id'])
    for cid, f in flows.items():
        if cid not in ids:
            header, body = read_flow(f)
            edited = bool(header.get('flow-hash')) and not body_matches(header['flow-hash'], body)
            (res['handEdited'] if edited else res['delete']).append(
                {'case': cid, 'file': str(f), 'reason': 'case removed' + (' but flow edited by hand' if edited else '')})
    return res


def stamp(md, flow):
    cid = Path(flow).name.split('_')[0]
    case = next((c for c in parse_cases(md) if c['id'] == cid), None)
    if case is None:
        raise SystemExit(json.dumps({'error': f'{cid} not found in {md}'}))
    _, body = read_flow(flow)
    body = body.lstrip('\n')
    header = (f'# test-story case: {cid}\n# test-story case-hash: {case["hash"]}\n'
              f'# test-story flow-hash: {h12(flow_norm(body))}\n')
    Path(flow).write_text(header + body, encoding='utf-8')
    return {'case': cid, 'caseHash': case['hash'], 'flowHash': h12(flow_norm(body))}


RANGE_RE = re.compile(r'TC-(\d+)\s*(?:…|\.\.\.?|–|—|-|to)\s*TC-(\d+)')


def case_ids(cell):
    """'TC-03, TC-09 … TC-15' → every id, ranges expanded (skipping the cases that use a value
    must skip TC-10 … TC-14 too)."""
    ids = set(re.findall(r'TC-\d+', cell))
    for a, b in RANGE_RE.findall(cell):
        width = len(a)
        ids.update(f'TC-{n:0{width}d}' for n in range(int(a), int(b) + 1))
    return sorted(ids)


def local_values(md):
    f = Path(md).parent / 'test-data.local.json'
    try:
        return json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
    except Exception:
        return {}


def data(md):
    text = Path(md).read_text(encoding='utf-8')
    m = re.search(r'^##\s+\d*\.?\s*Test data.*?$(.*?)(?=^##\s)', text, re.M | re.S)
    values, unfilled, used, local = {}, [], {}, []
    loc = local_values(md)
    if m:
        for line in m.group(1).splitlines():
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) < 3 or cells[0] in ('Key', '') or set(cells[0]) <= set('-: '):
                continue
            key, value = cells[0].strip('`'), cells[2].strip('`')
            used[key] = case_ids(cells[3]) if len(cells) > 3 else []
            if value.lower() == 'local':
                local.append(key)
                value = str(loc.get(key, ''))
            if not value or '{{' in value:
                unfilled.append(key)
            else:
                values[key] = value
    return {'values': values, 'unfilled': unfilled, 'usedBy': used, 'local': local}


# ---------- lint and deep smoke ----------

RUNFLOW_RE = re.compile(r'runFlow:\s*(?:\n\s+file:\s*)?["\']?([\w./-]+\.ya?ml)')
ENV_RE = re.compile(r'\$\{([A-Z][A-Z0-9_]*)\}')
BUILTIN_ENV = {'LANG_CODE'}


def subflows_of(flow, seen=None):
    """Every subflow a flow reaches (runFlow paths are relative to the file that names them)."""
    seen = set() if seen is None else seen
    try:
        text = Path(flow).read_text(encoding='utf-8')
    except OSError:
        return seen
    for ref in RUNFLOW_RE.findall(text):
        sub = (Path(flow).parent / ref).resolve()
        if sub not in seen:
            seen.add(sub)
            subflows_of(sub, seen)
    return seen


def yaml_problem(path):
    try:
        import yaml
    except ImportError:
        import subprocess
        r = subprocess.run(['maestro', 'check-syntax', str(path)], capture_output=True, text=True)
        return None if r.returncode == 0 else (r.stdout + r.stderr).strip()[-200:]
    try:
        list(yaml.safe_load_all(Path(path).read_text(encoding='utf-8')))
        return None
    except Exception as e:
        return str(e).splitlines()[0][:200]


def lint(md, e2e):
    """What would waste an attempt or mislabel a result, found before anything runs."""
    e2e = Path(e2e)
    d = data(md)
    known = set(d['values']) | BUILTIN_ENV
    known |= {k[:-3] for k in d['values'] if k.endswith(('_AR', '_EN'))}
    problems, checked = [], set()
    for c in parse_cases(md):
        if c['mode'] != 'auto' or c['status'] != 'approved':
            continue
        hits = sorted(e2e.glob(f"{c['id']}_*.yaml"))
        if not hits:
            problems.append(f"{c['id']}: no flow file")
            continue
        flow = hits[0]
        files = [flow] + sorted(subflows_of(flow))
        text = flow.read_text(encoding='utf-8')
        # the label decides failKind: without it a failed check is retried and reported "blocked"
        if not re.search(r'label:\s*["\']?EXPECT', text):
            problems.append(f"{c['id']}: no step labelled EXPECT (its expected-result checks must carry "
                            f"label: \"EXPECT …\")")
        if not read_flow(flow)[0].get('flow-hash'):
            problems.append(f"{c['id']}: not stamped (run flow_sync.py stamp)")
        for f in files:
            if not f.exists():
                problems.append(f"{c['id']}: runFlow target missing: {f}")
                continue
            if f not in checked:
                checked.add(f)
                err = yaml_problem(f)
                if err:
                    problems.append(f'{f.name}: YAML does not parse: {err}')
            for key in sorted(set(ENV_RE.findall(f.read_text(encoding='utf-8'))) - known):
                problems.append(f"{c['id']}: ${{{key}}} in {f.name} is not in the Test data table "
                                '(or still unfilled)')
    return {'ok': not problems, 'problems': sorted(set(problems), key=problems.index), 'filesChecked': len(checked)}


def smoke(md, e2e, minimum=3):
    """Subflows that at least `minimum` approved Auto cases go through, minus those another listed
    subflow already runs: running each once before the suite finds a broken shared step (a
    server call, a changed screen) in minutes instead of after several cases."""
    e2e = Path(e2e)
    use = {}
    for c in parse_cases(md):
        if c['mode'] != 'auto' or c['status'] != 'approved':
            continue
        hits = sorted(e2e.glob(f"{c['id']}_*.yaml"))
        for sub in subflows_of(hits[0]) if hits else []:
            use.setdefault(sub, []).append(c['id'])
    shared = {s: ids for s, ids in use.items() if len(ids) >= minimum and 'set-language' not in s.name}
    covered = set().union(*[subflows_of(s) for s in shared]) if shared else set()
    top = [s for s in shared if s not in covered]
    return {'subflows': [{'file': str(s), 'cases': shared[s]} for s in sorted(top, key=lambda s: -len(shared[s]))]}


ARABIC_QUOTED = re.compile(r'["“][^"”]*[\u0600-\u06FF][^"”]*["”]')


def messages(md):
    """Cases whose expected result is a translated text: language bugs (e.g. Arabic messages in the
    English app) only show there. Rule: the Expected line quotes an Arabic text (the case gives the
    en / ar pair), or the Message sources table lists the case under Used by."""
    text = Path(md).read_text(encoding='utf-8')
    listed = set()
    m = re.search(r'^##\s+\d*\.?\s*Message sources.*?$(.*?)(?=^##\s)', text, re.M | re.S)
    if m:
        for line in m.group(1).splitlines():
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) >= 5:
                listed.update(re.findall(r'TC-\d+', cells[-1]))
    hits, others = [], []
    for c in parse_cases(md):
        if c['mode'] != 'auto' or c['status'] != 'approved':
            continue
        block = re.search(r'^###\s+' + c['id'] + r'\b.*?(?=^##|\Z)', text, re.M | re.S).group(0)
        exp = re.search(r'^-\s*Expected:\s*(.*)$', block, re.M)
        (hits if c['id'] in listed or (exp and ARABIC_QUOTED.search(exp.group(1))) else others).append(c['id'])
    return {'cases': hits, 'others': others}


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    if cmd == 'plan' and len(sys.argv) == 4:
        out = plan(sys.argv[2], sys.argv[3])
    elif cmd == 'stamp' and len(sys.argv) == 4:
        out = stamp(sys.argv[2], sys.argv[3])
    elif cmd == 'data':
        out = data(sys.argv[2])
    elif cmd == 'messages':
        out = messages(sys.argv[2])
    elif cmd == 'lint' and len(sys.argv) == 4:
        out = lint(sys.argv[2], sys.argv[3])
    elif cmd == 'smoke' and len(sys.argv) >= 4:
        out = smoke(sys.argv[2], sys.argv[3], int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[4] == '--min' else 3)
    else:
        raise SystemExit(__doc__)
    print(json.dumps(out, ensure_ascii=False, indent=1))
