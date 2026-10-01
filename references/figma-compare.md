# Figma comparison (Phase 7)

Judgment on a fixed rubric, never pixel diffs. Findings are `Design deviation` (`DD-nn`) in
`triage.json`, kept apart from Bugs. Figma MCP not connected → skip, set run-info `figma` to
`"not run: Figma MCP not connected"`, continue.

## 1. Map screens to frames

From `test-cases.md` §Figma screens:
- **A frame link** (`…/design/<fileKey>/…?node-id=A-B`): fileKey + nodeId `A:B`.
- **A link to an element, not a screen** (small size, e.g. a 139×40 Button): walk up with
  `get_metadata` on the page (`nodeId` = page id) and use the top-level frame that contains it.
  Tell the user which frame you used.
- **A flow description plus a file link**: list the page's top-level frames with `get_metadata`,
  match by name and content, and state the match's confidence (High / Medium / Low). No file link →
  nothing to search; skip the screen and say so.
- Several frames for one screen (states: empty, before/after registration, error) → pick the one
  matching the test data's state and name the choice.

## 2. Fetch

`get_screenshot(fileKey, nodeId)` (the export comes at the frame's natural size, 1 px per point,
even when `maxDimension` is larger) → download the URL with `curl -L -o` into
`<runDir>/figma/<Screen>_<nodeId>.png` (URLs are short-lived; download
at once). The export is 1 px per Figma point unless it says otherwise; frames are usually 375 pt
wide.

## 3. Capture the app at the same state

- Same language as the frame (Arabic frames → the ar run's screenshots).
- Long frames: capture the app top to bottom (`scrollUntilVisible` / `scroll` + `takeScreenshot`
  per viewport), then compare section by section. Map each app viewport to a Figma y-range for
  `side_by_side.py --figma-crop`.
- Use the screenshots the cases already took when they show the screen; otherwise add a
  `--no-record` capture flow (never add assertions for Figma).

## 4. Rubric (per screen, in this order)

| # | Check | Deviation when |
| --- | --- | --- |
| 1 | Elements present | a Figma element (section, button, icon, card) is missing in the app, or the app shows one Figma does not |
| 2 | Text and labels | a title, label, tab name or button text differs in meaning (not just data values) |
| 3 | Order and layout | sections in a different order; a different arrangement (grid vs list, card vs row) |
| 4 | Colors | a clearly different colour role (primary green vs neutral grey button, error vs info) — not tone shifts from rendering |
| 5 | RTL mirroring (ar) | leading/trailing elements not mirrored, chevrons pointing the wrong way, numbers or icons on the wrong side |

Not deviations: live data values (names, amounts, counts), status-bar content, device width,
font rendering, image assets that depend on data, anything the Figma annotates as an example.

## 5. Record

One finding per difference:
- `classification: "Design deviation"`, `id: DD-nn`, `case`: the case whose screenshot shows it (or
  `"figma-capture"`), `lang`.
- `confidence`: High (unambiguous, e.g. a missing section or a different label), Medium (layout or
  colour role), Low (could be an intentional state difference). The report shows it next to the
  class; keep it out of the title.
- `severity`: Medium for missing or wrong elements and texts, Low for layout, colour and
  mirroring polish; High only when the difference blocks the story's AC.
- `expected`: what Figma shows (with the frame name and node id); `actual`: what the app shows.
- Labels on images are English (Pillow here cannot shape Arabic; the scripts refuse Arabic
  labels). Quote Arabic UI text in `expected` / `actual` instead.
- `evidence.screenshot`: the app screenshot; `evidence.annotated`: the side-by-side from
  `$S/side_by_side.py <app.png> <figma.png> --out <runDir>/figma-dd/DD-nn.png --figma-crop y1,y2
  --app-box … --figma-box … --label "DD-nn: …"` (the prune keeps `figma-dd/` and `figma/`, not the
  app screenshot); `evidence.network`: `"none"`.
- `fixOptions`: update the app to match Figma (usually recommended), or update Figma if the app
  reflects a newer decision — the user decides; `retest`: the capture or case that shows it.

Design deviations are not verified by the bug verifier; the confidence level carries the doubt.
When the Figma frame and the app are in different states (e.g. Figma shows a user with invoices,
the test user has none), record it in run-info `notes`, not as a deviation.
