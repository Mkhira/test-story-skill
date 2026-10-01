# test-story — global end-to-end test skill for Claude Code

`test-story` is a **global Claude Code skill**: install it once in `~/.claude/skills/` and it works
in every React Native (Expo) project on your machine.

Give it a user story and a feature folder. It writes test cases for you to approve, runs them on an
iOS simulator or Android emulator with [Maestro](https://maestro.mobile.dev), in **Arabic and
English**, and writes a bug-and-gap report into the feature folder.

```
/test-story docs/stories/CHECKOUT-001.md checkout
```

## What it does

- **Story → test cases.** Turns the story into numbered acceptance criteria, traces each one to the
  code, flags unclear sentences as spec gaps, and writes `test-cases.md`: happy paths, negatives,
  boundaries, bilingual and RTL checks, accessibility and beyond-the-story cases.
- **You approve first.** Nothing runs and no code changes until you approve. The skill asks for
  test data, spec-gap answers and choices as questions; you never have to edit the file by hand.
- **Arabic first, then you choose English.** All cases run in Arabic. Then you pick: English for
  message checks only (recommended), English for all cases, or skip English.
- **Retest only what failed.** After a fix, `retest` re-runs only the cases and languages that
  failed last time, and the report shows a before → now table.
- **Every failure is classified once:** Bug, Content issue (wrong CMS / server text), Spec gap,
  Design deviation, Test data issue, Environment issue, Flaky or Test error. Each Bug is
  re-checked by an independent subagent before it reaches the report.
- **Evidence you can read.** Failure screenshots with a red box on the problem, the API calls
  from the Metro log (tokens and personal data masked), and the file and line in the code.
- **Figma comparison** (optional, via a Figma MCP): app screens next to their Figma frames, with
  each difference listed.
- **Small on disk.** Maestro's raw output is deleted after each case; a finished run keeps only
  the annotated failures and Figma images (a few MB), and only the newest 5 runs per story.
- **Read-only by default.** The only code change it can make is adding `testID` props, and only
  after you approve them. It never commits or pushes.

## Requirements

| Need | Notes |
| --- | --- |
| [Claude Code](https://claude.com/claude-code) | the skill runs inside it |
| A React Native project built with Expo | `expo` in `package.json` |
| macOS with Xcode and an iOS simulator | for iOS runs |
| Android SDK with an emulator (AVD) | for Android runs (not yet tested) |
| Node.js, Python 3 with Pillow | `pip3 install pillow` (red boxes on screenshots) |
| Maestro and Java 17+ | the skill checks for them and offers to install them |
| Figma MCP | optional, for design comparison |

## Install

```bash
git clone https://github.com/Mkhira/test-story-skill.git ~/.claude/skills/test-story
```

The folder must be named `test-story`. Restart Claude Code; `/test-story` is then available in
every project.

Update later with:

```bash
git -C ~/.claude/skills/test-story pull
```

## Quick start

```text
/test-story <story file or pasted text> <feature folder or name>   # first run
/test-story retest <feature or story folder>                       # re-run only the failures
```

The full guide is in **[HOW_TO_USE.md](HOW_TO_USE.md)**.

## What it writes in your project

```
<feature>/test-stories/<story>/
├── test-cases.md              # the approved test cases (commit it)
├── test-report-<runId>.md     # one report per run (commit it)
├── e2e/                       # Maestro flows, reused and kept in sync (git-ignored)
└── test-runs/<runId>/         # screenshots and run data, local only (git-ignored)
```

The skill adds the two git-ignore entries itself and formats both markdown files with your
project's Prettier when the project has one, so CI format checks pass.

## How a run works

| Phase | The skill | You |
| --- | --- | --- |
| 0. Preflight | checks the project and the tools | pick iOS or Android |
| 1. Intake | story → acceptance criteria and spec gaps | — |
| 2. Analyze | reads the code: implementation, translations, exact message texts, path to the feature | — |
| 3. Test cases | writes `test-cases.md` and asks what it needs | answer, then approve |
| 4. Prepare | adds approved testIDs, boots the device, starts Metro, smoke test | log in if the feature needs it |
| 5. Execute | runs Arabic, then the English you chose | choose English: message checks / all / skip |
| 6. Triage | classifies every failure, gathers evidence, verifies bugs | — |
| 7. Figma | compares screens with Figma frames | give Figma links when asked |
| 8. Report | keeps the evidence, writes and formats the report | read it, commit it |

## Project run skill (optional)

If your project has its own skill that explains how to build and launch the app (for example
`.claude/skills/run-myapp/`), `test-story` reads it and follows it for booting, building, deep
links and the language switch. Without one it uses its own scripts (`npx expo run:ios` /
`run:android`).

## Repository layout

```
SKILL.md        the skill: phases, hard rules, checkpoints
references/     know-how loaded per phase (story parsing, test design, Maestro, triage, Figma, report)
templates/      test-cases.md and Maestro flow templates
scripts/        deterministic helpers; each prints JSON
```

## Status

- Validated end to end on a real feature on iOS (simulator, Arabic and English).
- The latest additions — Arabic-first with the English choice, retest mode, smart retries and run
  clean-up — are tested offline and not yet on a live device.
- Android support is written but has not been run yet.
