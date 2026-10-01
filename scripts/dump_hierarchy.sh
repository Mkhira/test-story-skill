#!/usr/bin/env bash
# dump_hierarchy.sh <runDir> <label> <deviceId> [--find REGEX]
# Saves the current screen hierarchy to <runDir>/artifacts/hierarchy/<label>.json and prints JSON:
# {path, rootWidth, rootHeight, elements:[{id,text,bounds}] (only labelled ones), found}
# --find REGEX → found=true when any element's id, text or accessibility text matches (e.g. a
# post-login marker). Used for assisted login polling and for annotation bounds.
set -u
RUN="$1"; LABEL="$2"; DEV="$3"; shift 3; FIND=""
[ "${1:-}" = "--find" ] && FIND="$2"
export PATH="$HOME/.maestro/bin:$PATH" MAESTRO_CLI_NO_ANALYTICS=1 MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true
D="$RUN/artifacts/hierarchy"; mkdir -p "$D"; OUT="$D/$LABEL.json"
maestro --device "$DEV" hierarchy > "$OUT" 2>"$D/$LABEL.err" || { echo "{\"error\":\"hierarchy failed\",\"stderr\":\"$(tail -1 "$D/$LABEL.err" | tr -d '"')\"}"; exit 1; }
python3 - "$OUT" "$FIND" <<'PY'
import json,re,sys
path,find=sys.argv[1],sys.argv[2]
h=json.load(open(path)); els=[]; found=False
rx=re.compile(find) if find else None
def nums(b): return [int(x) for x in re.findall(r'-?\d+',b or '')]
root=None
def walk(n):
    global root,found
    a=n.get('attributes',{})
    b=nums(a.get('bounds'))
    if root is None and len(b)==4 and b[2]>0: root=b
    rid=a.get('resource-id',''); txt=a.get('text','') or a.get('accessibilityText','')
    if rid or txt:
        els.append({"id":rid,"text":txt[:80],"bounds":b})
        if rx and (rx.search(rid) or rx.search(a.get('text','')) or rx.search(a.get('accessibilityText',''))): found=True
    for c in n.get('children',[]): walk(c)
walk(h)
print(json.dumps({"path":path,"rootWidth":root[2] if root else None,"rootHeight":root[3] if root else None,
 "found":found if find else None,"count":len(els),"elements":els},ensure_ascii=False))
PY
