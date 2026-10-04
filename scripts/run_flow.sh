#!/usr/bin/env bash
# run_flow.sh <flow.yaml> <lang code> <runDir> <deviceId> <caseId> [--data data.json] [--attempt N] [--timeout SEC]
#             [--app-error REGEX] [--no-record]
# --no-record: setup flows (language switch, smoke) → print pass/fail JSON only, no results.json entry.
# Runs one Maestro flow, records UTC start/end (to cut metro.log later), copies the flow's named
# screenshots and the failure screenshot to <runDir>/<lang>/, appends one record to
# <runDir>/artifacts/results.json, and prints that record as JSON. data.json = the "values" object
# from `flow_sync.py data`. --app-error: the app's error-dialog texts (see parse_results.py failKind app).
# Maestro's own output (incl. a 20–70 MB simulator log per attempt) goes to a temp dir outside the
# repo and is deleted once the record is written; --no-record runs keep it (minus the big logs) for
# debugging and print its path as "maestroDir".
set -u
FLOW="$1"; LANGV="$2"; RUN="$3"; DEV="$4"; CASE="$5"; shift 5
DATA=""; ATTEMPT=1; TMO=600; RECORD=1; APPERR=""
while [ $# -gt 0 ]; do case "$1" in --data) DATA="$2"; shift;; --attempt) ATTEMPT="$2"; shift;; --timeout) TMO="$2"; shift;; --app-error) APPERR="$2"; shift;; --no-record) RECORD=0;; esac; shift; done
export PATH="$HOME/.maestro/bin:$PATH" MAESTRO_CLI_NO_ANALYTICS=1 MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${TMPDIR:-/tmp}/test-story/$(basename "$RUN")/$LANGV/${CASE}_a${ATTEMPT}"; rm -rf "$OUT"; mkdir -p "$OUT" "$RUN/artifacts"
ENV_ARGS=(-e "LANG_CODE=$LANGV")
if [ -n "$DATA" ]; then
  # KEY_<LANG> keys are per-language variants: in the ar run KEY_AR is also passed as KEY
  while IFS= read -r kv; do ENV_ARGS+=(-e "$kv"); done < <(python3 -c '
import json,sys
d=json.load(open(sys.argv[1])); suf="_"+sys.argv[2].upper()
d.update({k[:-len(suf)]: v for k, v in list(d.items()) if k.endswith(suf)})
[print(f"{k}={v}") for k,v in d.items()]' "$DATA" "$LANGV")
fi
START=$(python3 -c 'from datetime import datetime,timezone; print(datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z"))')
# perl alarm = portable per-case timeout (macOS has no `timeout`)
perl -e 'alarm shift; exec @ARGV' "$TMO" maestro --device "$DEV" test "$FLOW" "${ENV_ARGS[@]}" \
  --test-output-dir "$OUT" --debug-output "$OUT/debug" \
  --format junit --output "$OUT/junit.xml" > "$OUT/console.log" 2>&1
CODE=$?
# device logs are the bulk of the size and are never used by triage (metro.log is)
find "$OUT" -type f \( -name 'device-*.log' -o -name 'xctest_runner*.log' \) -delete 2>/dev/null
END=$(python3 -c 'from datetime import datetime,timezone; print(datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z"))')
if [ $RECORD -eq 0 ]; then
  python3 -c 'import json,sys,re; c=open(sys.argv[2],errors="replace").read(); f=re.findall(r"\[Failed\].*",c); print(json.dumps({"case":sys.argv[1],"status":"passed" if sys.argv[3]=="0" else "failed","error":f[-1] if f else "","maestroDir":sys.argv[4]},ensure_ascii=False))' "$CASE" "$OUT/console.log" "$CODE" "$OUT"
  exit $CODE
fi
python3 "$HERE/parse_results.py" append --junit "$OUT/junit.xml" --console "$OUT/console.log" --outdir "$OUT" \
  --results "$RUN/artifacts/results.json" --case "$CASE" --lang "$LANGV" --attempt "$ATTEMPT" \
  --start "$START" --end "$END" --exit "$CODE" --flow "$FLOW" --shots "$RUN/$LANGV" --app-error "$APPERR"
RC=$?
[ $RC -eq 0 ] && rm -rf "$OUT"
exit $RC
