#!/usr/bin/env python3
"""Keep Maestro flows in <story>/e2e/ in step with the approved cases in test-cases.md.

  flow_sync.py plan  <test-cases.md> <e2eDir>   → JSON: create / regenerate / delete / keep / skip / manual / handEdited
  flow_sync.py stamp <test-cases.md> <flow.yaml> → write the header (case id, case hash, flow hash) after the agent wrote the flow
  flow_sync.py data  <test-cases.md>            → JSON: {values: {KEY: value}, unfilled: [KEY], usedBy: {KEY: [TC]}}
  flow_sync.py messages <test-cases.md>         → JSON: {cases: [TC], others: [TC]} — approved Auto cases that
                                                  check a translated text (the "English only for message checks" set)

A flow starts with three header comments:
  # test-story case: TC-04
  # test-story case-hash: <12 hex>   (case text without its Status line)
  # test-story flow-hash: <12 hex>   (everything below the header)
A flow whose body no longer matches its flow-hash was edited by hand → reported, never touched.
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
    res['cleanStateLast'] = []
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
        if header.get('flow-hash') and header['flow-hash'] != h12(body):
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
    for cid, f in flows.items():
        if cid not in ids:
            header, body = read_flow(f)
            edited = bool(header.get('flow-hash')) and header['flow-hash'] != h12(body)
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
              f'# test-story flow-hash: {h12(body)}\n')
    Path(flow).write_text(header + body, encoding='utf-8')
    return {'case': cid, 'caseHash': case['hash'], 'flowHash': h12(body)}


def data(md):
    text = Path(md).read_text(encoding='utf-8')
    m = re.search(r'^##\s+\d*\.?\s*Test data.*?$(.*?)(?=^##\s)', text, re.M | re.S)
    values, unfilled, used = {}, [], {}
    if m:
        for line in m.group(1).splitlines():
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) < 3 or cells[0] in ('Key', '') or set(cells[0]) <= set('-: '):
                continue
            key, value = cells[0].strip('`'), cells[2]
            used[key] = re.findall(r'TC-\d+', cells[3]) if len(cells) > 3 else []
            if not value or '{{' in value:
                unfilled.append(key)
            else:
                values[key] = value.strip('`')
    return {'values': values, 'unfilled': unfilled, 'usedBy': used}


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
    else:
        raise SystemExit(__doc__)
    print(json.dumps(out, ensure_ascii=False, indent=1))
