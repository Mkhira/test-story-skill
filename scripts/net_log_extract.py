#!/usr/bin/env python3
"""API calls and errors from metro.log inside one case's time window, masked for the report.

  net_log_extract.py <metro.log> <startISO> <endISO> [--pad SEC] [--max-body N] [--tag HttpClient]
                     [--lang en|ar]

Prints JSON {window, calls:[{time, dir, method, url, status, meta, body}], errors:[…], count}.
- A line belongs to the window by its own ISO timestamp; lines without one (LogBox errors, stack
  traces) are kept when they sit between two in-window lines.
- Requests look like "→ [DEV] GET https://…" and responses "← [DEV] 200 /v1/…" (ZATCA
  LoggerService); other shapes are kept as raw lines under calls with dir "?".
- Masking (hard rule 8) happens here, before anything reaches the agent's context:
  secrets/tokens are removed, PII values keep only their last 2 characters.
- --lang (en and ar ran in parallel, so their windows overlap in the one Metro log): keeps the
  requests whose meta says that language ("language":"EN"/"AR" in ZATCA) and the responses paired
  with them (the oldest open request to the same path). A response whose open requests come from
  both languages is kept with "ambiguous": true; log errors cannot be attributed and are flagged
  "errorsMayMix": true. Ambiguous evidence for a Bug → re-run that case alone for a clean window.
"""
import argparse
import json
import re
from datetime import datetime, timedelta, timezone

TS_RE = re.compile(r'\[?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\]?')
LEVEL_RE = re.compile(r'^\s*(LOG|DEBUG|INFO|WARN|ERROR)\s+(.*)$')
REQ_RE = re.compile(r'→\s*(?:\[\w+\]\s*)?(GET|POST|PUT|PATCH|DELETE|HEAD)\s+(\S+)')
RES_RE = re.compile(r'←\s*(?:\[\w+\]\s*)?(\d{3}|ERR\w*|NETWORK\w*)\s+(\S+)')

SECRET_KEYS = re.compile(r'(authorization|access_?token|refresh_?token|id_?token|token|secret|password|'
                         r'api_?key|encryption_?key|encryption_?iv|cookie|set-cookie|session)', re.I)
PII_KEYS = re.compile(r'(name|tin|vat_?number|national_?id|nid|iqama|id_?number|identity|mobile|phone|'
                      r'email|iban|account_?number|address|birth|dob|passport|cr_?number|commercial)', re.I)
SAFE_KEYS = re.compile(r'^(serviceName|serviceKey|servicePageName|fileName|typeName|statusName|'
                       r'description|code|message|requestID)$', re.I)
BEARER_RE = re.compile(r'(Bearer\s+)[A-Za-z0-9\-._~+/]+=*', re.I)
JWT_RE = re.compile(r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+')


def parse_ts(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def mask_value(v):
    s = str(v)
    return '***' + s[-2:] if len(s) > 4 else '***'


def mask(obj, key=''):
    if isinstance(obj, dict):
        return {k: mask(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [mask(v, key) for v in obj]
    if key and SECRET_KEYS.search(key) and not isinstance(obj, bool):
        return '[removed]'
    if key and PII_KEYS.search(key) and not SAFE_KEYS.match(key) and isinstance(obj, (str, int)) and not isinstance(obj, bool):
        return mask_value(obj)
    if isinstance(obj, str):
        return JWT_RE.sub('[jwt removed]', BEARER_RE.sub(r'\1[removed]', obj))
    return obj


def mask_text(s):
    """Mask a free-text line: JSON inside it when parseable, else regex scrubbing."""
    try:
        return json.dumps(mask(json.loads(s)), ensure_ascii=False)
    except Exception:
        s = JWT_RE.sub('[jwt removed]', BEARER_RE.sub(r'\1[removed]', s))
        s = re.sub(r'("(?:[^"]*(?:secret|token|password|key|iv)[^"]*)"\s*:\s*)"[^"]*"', r'\1"[removed]"', s, flags=re.I)
        return s


def parts_of(line):
    """Return (level, [message parts]) for a Metro console line."""
    m = LEVEL_RE.match(line)
    if not m:
        return None, [line.strip()]
    level, rest = m.group(1), m.group(2).strip()
    if rest.startswith('['):
        try:
            arr = json.loads(rest)
            return level, [a if isinstance(a, str) else json.dumps(a, ensure_ascii=False) for a in arr]
        except Exception:
            pass
    return level, [rest]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log'); ap.add_argument('start'); ap.add_argument('end')
    ap.add_argument('--pad', type=float, default=2.0)
    ap.add_argument('--max-body', type=int, default=1500)
    ap.add_argument('--tag', default='HttpClient')
    ap.add_argument('--lang', default='', choices=['', 'en', 'ar'])
    a = ap.parse_args()
    lo = parse_ts(a.start) - timedelta(seconds=a.pad)
    hi = parse_ts(a.end) + timedelta(seconds=a.pad)

    lines = open(a.log, encoding='utf-8', errors='replace').read().splitlines()
    stamped = []
    for i, line in enumerate(lines):
        m = TS_RE.search(line)
        if m:
            stamped.append((i, parse_ts(m.group(1))))
    inside = [i for i, t in stamped if lo <= t <= hi]
    if not inside:
        print(json.dumps({'window': [a.start, a.end], 'calls': [], 'errors': [], 'count': 0,
                          'note': 'no timestamped lines in window'}))
        return
    first, last = inside[0], inside[-1]
    # extend to the next stamped line so trailing untimed error lines are included
    nxt = next((i for i, t in stamped if i > last), len(lines))
    calls, errors = [], []
    for i in range(first, nxt):
        line = lines[i]
        level, parts = parts_of(line)
        ts = TS_RE.search(line)
        t = ts.group(1) if ts else None
        if ts and not (lo <= parse_ts(t) <= hi):
            continue
        joined = ' '.join(parts)
        if errors and not ts and re.match(r'^\s+(at |\.\.\.|\w+@)', line):
            # stack-trace continuation → belongs to the previous error (gives file:line)
            errors[-1]['text'] = (errors[-1]['text'] + '\n' + line.strip())[:a.max_body]
            continue
        if a.tag in joined:
            msg = next((p for p in parts if REQ_RE.search(p) or RES_RE.search(p)), '')
            rest = [p for p in parts[1:] if p is not msg]
            body = mask_text(rest[-1]) if rest else ''
            if len(body) > a.max_body:
                body = body[:a.max_body] + f'… [{len(body)} chars]'
            rq, rs = REQ_RE.search(msg), RES_RE.search(msg)
            if rq:
                calls.append({'time': t, 'dir': 'request', 'method': rq.group(1),
                              'url': rq.group(2), 'meta': body})
            elif rs:
                calls.append({'time': t, 'dir': 'response', 'status': rs.group(1),
                              'url': rs.group(2), 'body': body})
            else:
                calls.append({'time': t, 'dir': '?', 'raw': mask_text(joined)[:a.max_body]})
        elif level in ('ERROR', 'WARN') or re.search(r'(Error|Exception|Unhandled|Require cycle)', joined):
            errors.append({'time': t, 'level': level, 'text': mask_text(joined)[:a.max_body]})
    out = {'window': [a.start, a.end], 'calls': calls, 'errors': errors, 'count': len(calls)}
    if a.lang:
        out.update(by_lang(calls, a.lang))
        out['errorsMayMix'] = bool(errors)
    print(json.dumps(out, ensure_ascii=False, indent=1))


def req_lang(meta):
    m = re.search(r'"language"\s*:\s*"(\w+)"', meta or '')
    return m.group(1).lower() if m else None


def by_lang(calls, lang):
    """Keep one language's calls; responses inherit the language of their request (same path, FIFO)."""
    open_reqs, kept, ambiguous = {}, [], 0
    for c in calls:
        if c['dir'] == 'request':
            path = '/' + c['url'].split('://', 1)[-1].split('/', 1)[-1].split('?')[0] if '://' in c['url'] else c['url']
            c['lang'] = req_lang(c.get('meta'))
            open_reqs.setdefault(path, []).append(c['lang'])
            if c['lang'] in (lang, None):
                kept.append(c)
        elif c['dir'] == 'response':
            path = c['url'].split('?')[0]
            key = next((k for k in open_reqs if k.endswith(path) and open_reqs[k]), None)
            langs = open_reqs.get(key, [])
            if not langs:
                kept.append(c)
                continue
            if len(set(langs)) > 1:
                c['ambiguous'] = True
                ambiguous += 1
            c['lang'] = langs.pop(0)
            if c['lang'] in (lang, None) or c.get('ambiguous'):
                kept.append(c)
        else:
            kept.append(c)
    return {'calls': kept, 'count': len(kept), 'langFilter': lang, 'ambiguous': ambiguous}


if __name__ == '__main__':
    main()
