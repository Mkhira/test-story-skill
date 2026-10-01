#!/usr/bin/env bash
# preflight.sh <ios|android> [--install-maestro] [--install-java]
# Prints JSON: tool versions, what is missing, what the agent must ask the user to install.
# Installs only when the matching flag is given (the agent asks the user first).
set -u
PLATFORM="${1:-}"; shift || true
INSTALL_MAESTRO=0; INSTALL_JAVA=0
for a in "$@"; do
  case "$a" in --install-maestro) INSTALL_MAESTRO=1;; --install-java) INSTALL_JAVA=1;; esac
done
export PATH="$HOME/.maestro/bin:$PATH"

ver() { "$@" 2>&1 | head -1 | tr -d '"\\' ; }
missing=(); manual=()

node_v=$(command -v node >/dev/null && node --version || echo "")
[ -z "$node_v" ] && manual+=("node: install Node.js LTS")
npx_ok=$(command -v npx >/dev/null && echo true || echo false)

java_line=$(java -version 2>&1 | head -1)
java_major=$(echo "$java_line" | sed -E 's/.*version "([0-9]+).*/\1/' | grep -E '^[0-9]+$' || echo 0)
if [ "$java_major" -lt 17 ]; then
  if [ $INSTALL_JAVA -eq 1 ] && command -v brew >/dev/null; then
    brew install --cask zulu@17 >/dev/null 2>&1
    java_line=$(java -version 2>&1 | head -1)
    java_major=$(echo "$java_line" | sed -E 's/.*version "([0-9]+).*/\1/' | grep -E '^[0-9]+$' || echo 0)
  fi
  [ "$java_major" -lt 17 ] && missing+=("java17")
fi

maestro_v=$(command -v maestro >/dev/null && MAESTRO_CLI_NO_ANALYTICS=1 maestro --version 2>/dev/null | tail -1 || echo "")
if [ -z "$maestro_v" ] && [ $INSTALL_MAESTRO -eq 1 ]; then
  curl -fsSL "https://get.maestro.mobile.dev" | bash >/dev/null 2>&1
  maestro_v=$(MAESTRO_CLI_NO_ANALYTICS=1 maestro --version 2>/dev/null | tail -1 || echo "")
fi
[ -z "$maestro_v" ] && missing+=("maestro")

platform_ok=true; devices="[]"
if [ "$PLATFORM" = "ios" ]; then
  if ! xcrun simctl help >/dev/null 2>&1; then platform_ok=false; manual+=("xcode: install Xcode and run xcode-select --install"); fi
  devices=$(xcrun simctl list devices available -j 2>/dev/null | python3 -c '
import json,sys
d=json.load(sys.stdin)["devices"]
print(json.dumps([{"name":x["name"],"udid":x["udid"],"state":x["state"],"runtime":k.split(".")[-1]} for k,v in d.items() for x in v if "iPhone" in x["name"]]))' 2>/dev/null || echo "[]")
elif [ "$PLATFORM" = "android" ]; then
  SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
  ADB=$(command -v adb || echo "$SDK/platform-tools/adb"); EMU=$(command -v emulator || echo "$SDK/emulator/emulator")
  [ -x "$ADB" ] || { platform_ok=false; manual+=("adb: install Android SDK platform-tools"); }
  if [ -x "$EMU" ]; then
    devices=$("$EMU" -list-avds 2>/dev/null | python3 -c 'import sys,json; print(json.dumps([{"name":l.strip()} for l in sys.stdin if l.strip()]))')
    [ "$devices" = "[]" ] && { platform_ok=false; manual+=("avd: create an emulator in Android Studio > Device Manager"); }
  else
    platform_ok=false; manual+=("emulator: install 'Android Emulator' and a system image via Android Studio > SDK Manager")
  fi
else
  echo '{"error":"usage: preflight.sh <ios|android> [--install-maestro] [--install-java]"}'; exit 2
fi

python3 - "$node_v" "$npx_ok" "$java_line" "$maestro_v" "$platform_ok" "$devices" "${missing[*]:-}" "$(printf '%s\n' "${manual[@]:-}")" <<'PY'
import json,sys
a=sys.argv[1:]
print(json.dumps({
 "node":a[0],"npx":a[1]=="true","java":a[2],"maestro":a[3],
 "platformToolsOk":a[4]=="true","devices":json.loads(a[5] or "[]"),
 "installable":[m for m in a[6].split() if m],
 "manual":[m for m in a[7].split("\n") if m],
 "ok": not a[6].split() and not [m for m in a[7].split("\n") if m],
},ensure_ascii=False,indent=1))
PY
