# Test cases – {{Feature}} – {{Story title}}

Run: {{runId}} · Platform: {{iOS|Android}} · Env: {{env name}} ({{API base URL}}) · Status: AWAITING APPROVAL
Story: {{story path or "pasted"}} · Feature folder: {{feature path}}

> Edit anything below, fill every `{{fill}}`, set any case to `skip`, then reply **approved**.
> Nothing runs and no code changes until then.

## 1. Acceptance criteria

| AC | Given / When / Then | Story source | Code | Status |
| --- | --- | --- | --- | --- |
| AC-1 | Given …, when …, then … | "exact story sentence" | path/File.ts:42 | Implemented |

## 2. Spec gaps (please answer)

- SPEC-GAP-1 (AC-x): {{question}}

## 3. Static findings (from code, before any run)

| # | Kind | Detail | Code |
| --- | --- | --- | --- |
| SF-1 | Missing implementation / Undocumented behaviour / Unhandled API error / Missing translation / Hard-coded string | … | path:line |

## 4. Test data (real test-environment values you enter; never invented)

| Key | Meaning | Value | Used by |
| --- | --- | --- | --- |
| VALID_TIN | TIN that exists in the test env | {{fill}} | TC-01, TC-04 |

## 5. Figma screens

| Screen | Figma link or flow description | Proposed by skill |
| --- | --- | --- |
| {{ScreenName}} | {{fill}} | (only when a Figma file link is given) |

## 6. testIDs to add

| File | Element | Proposed testID |
| --- | --- | --- |
| path/Screen.tsx:31 | TIN input | {{feature}}-{{screen}}-{{element}} |
| shared/components/…/Component.tsx | testID pass-through prop | (needed by …) |

## 7. How the flows reach the feature

- Language switch: {{strategy}}
- Path: {{deep link or tap path}} · wait for: {{element}}

## 8. Message sources (exact texts the cases assert)

| Message | en | ar | Source | Used by |
| --- | --- | --- | --- | --- |
| NID prefix error | National ID must start with 1 | يجب أن يبدأ رقم الهوية الوطنية بـ 1 | app i18n `signup.validation.nidPrefix` / CMS `e-signup/…` / server | TC-04 |

## 9. Test cases

### TC-01 – {{title}}
- Covers: AC-1 · Type: Positive · Priority: P1 · Mode: Auto
- Preconditions: {{state}}
- Data: {{KEY}}
- Steps: 1. … 2. …
- Expected: {{observable result; quote texts from section 8 as en: "…" · ar: "…"}}
- Figma: {{ScreenName or none}}
- Tags: none
- Status: approved
