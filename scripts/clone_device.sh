#!/usr/bin/env bash
# clone_device.sh <ios|android> <appId> <sourceDeviceId>
# A second device with the same app build, so en and ar run in parallel (Phase 5).
# iOS: reuses or creates a simulator "<source name> (test-story)" of the same type and runtime,
#      boots it and installs the .app copied from the source simulator's container. A debug build
#      loads its JS from Metro on localhost:8081, so both simulators share the one Metro.
# Android (untested): starts a second -read-only instance of the source's AVD on port 5556 and
#      installs the source's APK.
# Prints JSON {deviceId, name, created, appInstalled}. The user logs in on it too when the
# feature needs a session (assisted login per device).
set -u
PLATFORM="$1"; APP="$2"; SRC="$3"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
ADB=$(command -v adb || echo "$SDK/platform-tools/adb"); EMU=$(command -v emulator || echo "$SDK/emulator/emulator")
wait_s() { perl -e "select(undef,undef,undef,$1)"; }

if [ "$PLATFORM" = "ios" ]; then
  APPDIR=$(xcrun simctl get_app_container "$SRC" "$APP" app 2>/dev/null)
  [ -z "$APPDIR" ] && { echo "{\"error\":\"$APP is not installed on $SRC\"}"; exit 1; }
  read -r TYPE RUNTIME NAME < <(xcrun simctl list devices -j | python3 -c '
import json,sys
src=sys.argv[1]
for rt,devs in json.load(sys.stdin)["devices"].items():
    for d in devs:
        if d["udid"]==src: print(d["deviceTypeIdentifier"], rt, d["name"])' "$SRC")
  [ -z "${TYPE:-}" ] && { echo "{\"error\":\"source simulator $SRC not found\"}"; exit 1; }
  CLONE_NAME="$NAME (test-story)"
  NEW=$(xcrun simctl list devices -j | python3 -c '
import json,sys
want=sys.argv[1]
for devs in json.load(sys.stdin)["devices"].values():
    for d in devs:
        if d["name"]==want and d.get("isAvailable",True): print(d["udid"]); raise SystemExit' "$CLONE_NAME")
  CREATED=false
  if [ -z "$NEW" ]; then NEW=$(xcrun simctl create "$CLONE_NAME" "$TYPE" "$RUNTIME") || exit 1; CREATED=true; fi
  xcrun simctl boot "$NEW" >/dev/null 2>&1; open -a Simulator; xcrun simctl bootstatus "$NEW" -b >/dev/null 2>&1
  xcrun simctl install "$NEW" "$APPDIR" || { echo '{"error":"install failed"}'; exit 1; }
  printf '{"deviceId":"%s","name":"%s","created":%s,"appInstalled":true}\n' "$NEW" "$CLONE_NAME" "$CREATED"
elif [ "$PLATFORM" = "android" ]; then
  AVD=$("$ADB" -s "$SRC" emu avd name 2>/dev/null | head -1 | tr -d '\r')
  APK=$("$ADB" -s "$SRC" shell pm path "$APP" 2>/dev/null | head -1 | tr -d '\r' | sed 's/^package://')
  [ -z "$APK" ] && { echo "{\"error\":\"$APP is not installed on $SRC\"}"; exit 1; }
  TMP="${TMPDIR:-/tmp}/test-story-clone.apk"; "$ADB" -s "$SRC" pull "$APK" "$TMP" >/dev/null || exit 1
  NEW=emulator-5556
  if ! "$ADB" devices | grep -q "^$NEW"; then
    nohup "$EMU" -avd "$AVD" -read-only -port 5556 -no-snapshot-save >/dev/null 2>&1 &
    "$ADB" -s "$NEW" wait-for-device
    for i in $(seq 1 180); do [ "$("$ADB" -s "$NEW" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] && break; wait_s 1; done
  fi
  "$ADB" -s "$NEW" install -r "$TMP" >/dev/null || { echo '{"error":"install failed"}'; exit 1; }
  "$ADB" -s "$NEW" reverse tcp:8081 tcp:8081 >/dev/null 2>&1
  printf '{"deviceId":"%s","name":"%s (read-only)","created":false,"appInstalled":true}\n' "$NEW" "$AVD"
else
  echo '{"error":"usage: clone_device.sh <ios|android> <appId> <sourceDeviceId>"}'; exit 2
fi
