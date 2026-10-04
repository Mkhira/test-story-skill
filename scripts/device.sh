#!/usr/bin/env bash
# device.sh <ios|android> <device name|udid|avd|""> <appId>
# Boots the device when needed. Prints JSON {platform, deviceId, name, booted, appInstalled, appRunning}.
# Empty device name → an already booted device, else the most recently booted iPhone / the first AVD.
set -u
PLATFORM="$1"; WANT="${2:-}"; APP="$3"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
ADB=$(command -v adb || echo "$SDK/platform-tools/adb"); EMU=$(command -v emulator || echo "$SDK/emulator/emulator")
out() { printf '{"platform":"%s","deviceId":"%s","name":"%s","booted":%s,"appInstalled":%s,"appRunning":%s%s}\n' "$PLATFORM" "$1" "$2" "$3" "$4" "$5" "${6:-}"; }
wait_s() { perl -e "select(undef,undef,undef,$1)"; }

if [ "$PLATFORM" = "ios" ]; then
  pick=$(xcrun simctl list devices available -j | python3 -c '
import json,sys
want=sys.argv[1]; d=json.load(sys.stdin)["devices"]
devs=[x for v in d.values() for x in v if "iPhone" in x["name"]]
# nothing booted: the most recently used iPhone (it is the one that has the dev build), else the last listed
recent=sorted([x for x in devs if x.get("lastBootedAt")], key=lambda x: x["lastBootedAt"])
m=[x for x in devs if want and want in (x["udid"],x["name"])] or [x for x in devs if not want and x["state"]=="Booted"] or ([] if want else (recent or devs)[-1:])
print(m[0]["udid"]+"\t"+m[0]["name"]+"\t"+m[0]["state"] if m else "")' "$WANT")
  [ -z "$pick" ] && { echo "{\"error\":\"no simulator matches '$WANT'\"}"; exit 1; }
  UDID=$(echo "$pick" | cut -f1); NAME=$(echo "$pick" | cut -f2); STATE=$(echo "$pick" | cut -f3)
  if [ "$STATE" != "Booted" ]; then
    xcrun simctl boot "$UDID" >/dev/null 2>&1; open -a Simulator; xcrun simctl bootstatus "$UDID" -b >/dev/null 2>&1
  fi
  inst=false; xcrun simctl get_app_container "$UDID" "$APP" >/dev/null 2>&1 && inst=true
  run=false; xcrun simctl spawn "$UDID" launchctl list 2>/dev/null | grep -q "UIKitApplication:$APP\[" && run=true
  out "$UDID" "$NAME" true $inst $run
elif [ "$PLATFORM" = "android" ]; then
  SERIAL=$("$ADB" devices | awk 'NR>1 && $2=="device" && $1 ~ /^emulator-/ {print $1; exit}')
  if [ -z "$SERIAL" ]; then
    AVD="$WANT"; [ -z "$AVD" ] && AVD=$("$EMU" -list-avds 2>/dev/null | head -1)
    [ -z "$AVD" ] && { echo '{"error":"no AVD; create one in Android Studio > Device Manager"}'; exit 1; }
    nohup "$EMU" -avd "$AVD" -no-snapshot-save >/dev/null 2>&1 &
    "$ADB" wait-for-device
    for i in $(seq 1 180); do [ "$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] && break; wait_s 1; done
    SERIAL=$("$ADB" devices | awk 'NR>1 && $2=="device" && $1 ~ /^emulator-/ {print $1; exit}')
  fi
  NAME=$("$ADB" -s "$SERIAL" emu avd name 2>/dev/null | head -1 | tr -d '\r')
  "$ADB" -s "$SERIAL" reverse tcp:8081 tcp:8081 >/dev/null 2>&1
  inst=false; "$ADB" -s "$SERIAL" shell pm path "$APP" 2>/dev/null | grep -q package: && inst=true
  run=false; [ -n "$("$ADB" -s "$SERIAL" shell pidof "$APP" 2>/dev/null | tr -d '\r')" ] && run=true
  out "$SERIAL" "$NAME" true $inst $run
else
  echo '{"error":"usage: device.sh <ios|android> <device> <appId>"}'; exit 2
fi
