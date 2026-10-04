# Expo device handling (Phases 0, 2, 4)

A project run skill (e.g. `.claude/skills/run-zatca/`) overrides the generic steps here for
booting, building, deep links and language. Read it first when it exists.

## Scripts (run from the project root; all print JSON)

| Step | Command |
| --- | --- |
| Tools | `scripts/preflight.sh <ios\|android> [--install-maestro] [--install-java]` (flags only after the user agreed) |
| Device | `scripts/device.sh <ios\|android> "<name/udid/avd or empty>" <appId>` → `deviceId`, `appInstalled`, `appRunning` (empty name: the booted device, else the most recently booted iPhone; `appInstalled:false` → build with `run_app.sh --build`) |
| Build check | `scripts/build_check.py <platform> <appId> <deviceId>` → `install` (stale node_modules + `installCommand`), `rebuild` (true / false / null = unknown), `prebuild`, `reasons` |
| Metro + app | `scripts/run_app.sh <platform> <runDir> <appId> <deviceId> [--build] [--prebuild] [--restart-metro]`; `--stop` (Phase 8) stops only the Metro it started |
| Screen | `scripts/dump_hierarchy.sh <runDir> <label> <deviceId> [--find REGEX]` |
| Second device (only on request) | `scripts/clone_device.sh <ios\|android> <appId> <deviceId>` → `deviceId` of a clone with the same build (iOS: "<name> (test-story)", reused; Android: untested). A second idle simulator pushed 1.4 GB into swap on a 16 GB Mac |
| One language's cases | `scripts/run_suite.py --run … --e2e … --lang … --device … --platform … --app … --cases …` |

`run_app.sh` exit 3 with `metroOwned:false` = someone else's Metro holds 8081. Ask the user:
restart it under the skill (then `--restart-metro`), or continue without network triage (record
the gap "network calls not visible").

Which build: `build_check.py` decides, never a guess. JS reaches the app through Metro; native
code (packages, config plugins, `app.json`, patches) only through a build. After a branch switch
the installed build can lack a native module the JS now imports: the app crashes at launch or,
worse, runs and tests old native code (2026-10-04: a branch added Firebase, HMS push and
expo-notifications; none were in node_modules or the build).

- `install` non-empty → node_modules does not match the lockfile. Installing changes the user's
  node_modules (other branches then need an install too), so ask: "Install and rebuild
  (Recommended)", "Use the installed build anyway" (record the gap in run-info `notes`), "Stop".
  After the install run `build_check.py` again.
- `rebuild: true` → `run_app.sh … --build` (`--prebuild` too when `prebuild` is true: the native
  folder is git-ignored, Expo CNG, and new config plugins must be applied). A build takes minutes,
  so say why (`reasons`) and ask unless the user already agreed.
- `rebuild: false` → relaunch. `rebuild: null` (no build record on this device yet) → relaunch, and
  add `reasons[0]` to run-info `notes`; the first `--build` records the fingerprint for next time.

Otherwise the script relaunches the installed build after Metro is ready, which avoids the
stale-embedded-bundle trap. Every successful `--build` records the native fingerprint
(`~/.cache/test-story/builds/`) that the next `build_check.py` compares against.

## Metro log

- `run_app.sh` starts `CI=1 npx expo start` with all output in `<runDir>/artifacts/metro.log`.
- In dev builds, JS `console.*` lines land there, e.g. ZATCA `LoggerService`:
  `DEBUG [" [2026-09-30T13:10:05.036Z] [HttpClient] [DEBUG] ", "→ [DEV] GET https://…", "{…}"]`
  and `"← [DEV] 200 /v1/…", "<body>"`. Timestamps are UTC; `run_flow.sh` records UTC start/end.
- The first API call proves logging works: `grep -c HttpClient metro.log` > 0 after the smoke flow.
- Config log lines can contain secrets (ZATCA ConfigService prints `clientSecret` and payment
  keys). Never copy metro.log lines into a report without masking (hard rule 8).
- Android logs also reach `adb logcat | grep ReactNativeJS`.

## Language

Find the switch in code (i18n `changeLanguage`, a settings screen, a language card). Record:
where the control is, whether text switches live, whether native RTL (`I18nManager.forceRTL`)
needs a cold relaunch, whether the session survives. ZATCA: Menu tab → `العربية` / `English`;
text switches live; RTL on next cold launch; session kept. Unknown → ask the user once.

The backend localises from `Accept-Language`; server texts in the report are judged in the run's
language.

## Assisted login

1. Screenshot (`xcrun simctl io <udid> screenshot` / `adb exec-out screencap -p`) and ask the user
   to log in on the device and reply when done.
2. Poll `dump_hierarchy.sh … --find "<post-login marker>"` every ~10 s (each dump takes 5–30 s).
   ZATCA marker: `^(بياناتي|My Information)$`; logged out the same tab reads `الحساب` / `Account`.
3. A screen asking for OTP or a choice → ask the user; never type credentials yourself.
4. Proceed only once `found` is true.

## Clean state

`clearState` + `clearKeychain` (iOS keychain keeps tokens). Proven to log ZATCA out.

## Deep links

`xcrun simctl openurl <udid> "<url>"` / `adb shell am start -a android.intent.action.VIEW -d "<url>"`,
or `openLink:` in a flow (no confirmation prompt on iOS for the app's own scheme).
