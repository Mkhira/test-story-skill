#!/usr/bin/env bash
# format_md.sh <file.md> [...]
# Formats the committed outputs (test-cases.md, test-report-<runId>.md) with the project's own
# Prettier, so a CI `prettier --check .` passes when the user commits them. Runs only when the
# project declares prettier in package.json (installed or not: npx fetches the declared range).
# No prettier in the project → no-op. flow_sync.py hashes cases whitespace-normalised, so
# formatting never triggers flow regeneration. Run from the project root.
# Prints JSON {formatted:[…], prettier:"<version>|none"}.
set -u
SPEC=$(python3 -c 'import json; p=json.load(open("package.json")); d={**p.get("dependencies",{}),**p.get("devDependencies",{})}; print(d.get("prettier",""))' 2>/dev/null)
if [ -z "$SPEC" ]; then echo '{"formatted":[],"prettier":"none"}'; exit 0; fi
if [ -x ./node_modules/.bin/prettier ]; then P=(./node_modules/.bin/prettier); else P=(npx --yes "prettier@$SPEC"); fi
"${P[@]}" --write --log-level warn "$@" >/dev/null || { echo '{"error":"prettier failed"}'; exit 1; }
"${P[@]}" --check --log-level warn "$@" >/dev/null || { echo '{"error":"still not prettier-clean"}'; exit 1; }
python3 -c 'import json,sys; print(json.dumps({"formatted":sys.argv[2:],"prettier":sys.argv[1]}))' "$("${P[@]}" --version)" "$@"
