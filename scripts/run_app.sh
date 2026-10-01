#!/usr/bin/env bash
# run_app.sh <ios|android> <runDir> <appId> <deviceId> [--build] [--restart-metro] [--clear] [--timeout SEC]
# --clear: start Metro with -c (after source edits such as added testIDs — the file watcher can miss
# edits made just before a launch, and the device then runs the old bundle).
# Run from the project root. Starts Metro under the skill (output → <runDir>/artifacts/metro.log),
# then builds (--build or app missing) or relaunches the app AFTER Metro is ready (stale-bundle rule),
# and waits for a "Bundled" line. Prints JSON. A Metro on 8081 not started by this script →
# {"metroOwned":false}; ask the user, then call again with --restart-metro.
set -u
PLATFORM="$1"; RUN="$2"; APP="$3"; DEV="$4"; shift 4
BUILD=0; RESTART=0; CLEAR=""; TMO=900
while [ $# -gt 0 ]; do case "$1" in --build) BUILD=1;; --restart-metro) RESTART=1;; --clear) CLEAR="-c";; --timeout) TMO="$2"; shift;; esac; shift; done
ART="$RUN/artifacts"; mkdir -p "$ART"; LOG="$ART/metro.log"
PIDFILE="${TMPDIR:-/tmp}/test-story-metro-$(pwd | shasum | cut -c1-12).pid"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"; ADB=$(command -v adb || echo "$SDK/platform-tools/adb")
wait_s() { perl -e "select(undef,undef,undef,$1)"; }
json_fail() { python3 -c 'import json,sys; print(json.dumps({"ok":False,"reason":sys.argv[1],"lastLines":open(sys.argv[2],errors="replace").read().splitlines()[-25:] if sys.argv[2] else []}))' "$1" "${2:-}"; exit 1; }

cur=$(lsof -ti tcp:8081 -sTCP:LISTEN 2>/dev/null | head -1)
ours=$(cat "$PIDFILE" 2>/dev/null || echo "")
if [ -n "$cur" ]; then
  # Metro's listener may be a child of the pid we started; compare the process group.
  cur_pg=$(ps -o pgid= -p "$cur" | tr -d ' '); ours_pg=$( [ -n "$ours" ] && ps -o pgid= -p "$ours" 2>/dev/null | tr -d ' ')
  if [ -z "$ours_pg" ] || [ "$cur_pg" != "$ours_pg" ]; then
    [ $RESTART -eq 0 ] && { echo "{\"ok\":false,\"metroOwned\":false,\"pid\":$cur,\"cmd\":\"$(ps -o command= -p "$cur" | cut -c1-120)\"}"; exit 3; }
  fi
  # Always restart: our log must be this run's metro.log.
  kill "$cur" 2>/dev/null; [ -n "$ours" ] && kill "$ours" 2>/dev/null
  for i in $(seq 1 20); do lsof -ti tcp:8081 -sTCP:LISTEN >/dev/null 2>&1 || break; wait_s 0.5; done
fi

: > "$LOG"
CI=1 nohup npx expo start --port 8081 $CLEAR >> "$LOG" 2>&1 &
echo $! > "$PIDFILE"; disown 2>/dev/null || true
for i in $(seq 1 120); do grep -q "Waiting on" "$LOG" && break; wait_s 1; done
grep -q "Waiting on" "$LOG" || json_fail "metro did not start" "$LOG"
[ "$PLATFORM" = "android" ] && "$ADB" -s "$DEV" reverse tcp:8081 tcp:8081 >/dev/null 2>&1

installed=true
if [ "$PLATFORM" = "ios" ]; then xcrun simctl get_app_container "$DEV" "$APP" >/dev/null 2>&1 || installed=false
else "$ADB" -s "$DEV" shell pm path "$APP" 2>/dev/null | grep -q package: || installed=false; fi

before=$(grep -c "Bundled" "$LOG")
start=$(date +%s)
if [ $BUILD -eq 1 ] || [ "$installed" = false ]; then
  BLOG="$ART/build.log"
  if [ "$PLATFORM" = "ios" ]; then npx expo run:ios --no-bundler --device "$DEV" > "$BLOG" 2>&1 &
  else npx expo run:android --no-bundler --device "$DEV" > "$BLOG" 2>&1 & fi
  BPID=$!
  while kill -0 $BPID 2>/dev/null; do
    [ $(( $(date +%s) - start )) -gt "$TMO" ] && { kill $BPID; json_fail "build timed out after ${TMO}s" "$BLOG"; }
    wait_s 3
  done
  wait $BPID || json_fail "build failed" "$BLOG"
  action=build
else
  if [ "$PLATFORM" = "ios" ]; then
    xcrun simctl terminate "$DEV" "$APP" >/dev/null 2>&1; xcrun simctl launch "$DEV" "$APP" >/dev/null || json_fail "launch failed" ""
  else
    "$ADB" -s "$DEV" shell am force-stop "$APP"; "$ADB" -s "$DEV" shell monkey -p "$APP" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
  fi
  action=relaunch
fi

while [ "$(grep -c "Bundled" "$LOG")" -le "$before" ]; do
  [ $(( $(date +%s) - start )) -gt "$TMO" ] && json_fail "no Bundled line after ${TMO}s" "$LOG"
  grep -q "Bundling failed\|SyntaxError" "$LOG" && json_fail "bundling failed" "$LOG"
  wait_s 2
done
python3 -c 'import json,sys; print(json.dumps({"ok":True,"metroOwned":True,"action":sys.argv[1],"seconds":int(sys.argv[2]),"metroLog":sys.argv[3]}))' "$action" "$(( $(date +%s) - start ))" "$LOG"
