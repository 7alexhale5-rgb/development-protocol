# Pipeline phase execution notes

Detailed notes for each step of `/design-stack`: inputs, tools, outputs and failure modes. Read
this when the one-line contract in SKILL.md is not enough.

`references/quality-floor.md` sets the fidelity floor and leaves style open. Library defaults and
aesthetic scores are advisory; judge the rendered and working result.

## Contents

- [Step 0: Parse intent](#step-0-parse-intent)
- [Step 0.5: Context check](#step-05-context-check)
- [Step 1: Runtime probe](#step-1-runtime-probe)
- [Step 2: Intent-first interview](#step-2-intent-first-interview)
- [Step 3: Context load](#step-3-context-load)
- [Step 4: Reference scan](#step-4-reference-scan)
- [Step 4.5: Variant generation](#step-45-variant-generation)
- [Step 4b: Reference boards](#step-4b-reference-boards)
- [Step 5: Design decisions](#step-5-design-decisions)
- [Step 6: Generate](#step-6-generate)
- [Step 6.5: Asset kit](#step-65-asset-kit)
- [Step 7: Verify](#step-7-verify)
- [Step 8: Critique](#step-8-critique)
- [Step 8.5: Iterate loop](#step-85-iterate-loop)
- [Step 9: Persist and deliver](#step-9-persist-and-deliver)
- [Global error handling](#global-error-handling)

## Step 0: Parse intent

**Inputs:** the argument string after `/design-stack`.

**Tools:** read the words; ask one question only if two modes would produce materially different
work and nothing on disk decides it.

**Outputs:** `GOAL`, `MODE`, `FLAGS`.

**Failure modes:**

- Conflicting mode flags (for example `--critique --generate`): stop and ask the user to pick one.
- Empty goal: ask "what are we designing?" (`--system-to-design-md` needs no goal).
- Unknown flag: warn and continue with defaults.
- A flag not valid for the mode (see the matrix in SKILL.md): stop with
  `Error: Flag X has no effect in mode Y; remove it or change mode.`

## Step 0.5: Context check

**Inputs:** `GOAL` keywords and the project folder.

**Tools:** read files. Search the repo for earlier design decisions:
`.interface-design/decisions/*.md`, `.devproto/evidence/design*.md`, and any `docs/design/`
folder.

**Outputs:** `PAST_DECISIONS` (up to 3 relevant entries), `DESIGN_MD_TOKENS`,
`DESIGN_MD_RATIONALE`, `SYSTEM_MD_PROSE`.

**Skip when:** `--no-cache`.

**Per-project DESIGN.md detection.** Look for, in order, and stop at the first hit:
`DESIGN.md` at the project root, `docs/DESIGN.md`, `docs/DESIGN-SYSTEM.md`. Parse its YAML front
matter into `DESIGN_MD_TOKENS` (namespaces `colors`, `typography`, `rounded`, `spacing`,
`components`). Keep the markdown body as `DESIGN_MD_RATIONALE` for Step 5. Also read
`.interface-design/system.md` if present: it is the prose layer that refers to DESIGN.md tokens by
name.

Failure modes:

- No DESIGN.md: note `DESIGN.md not found, using the category fallback` and go to the fallback.
- DESIGN.md front matter is malformed YAML: stop Step 0.5 with the error and the line. Do not
  continue silently on half-parsed tokens.
- No past decisions: continue with empty context (normal for a new project).

**Category fallback (only when DESIGN.md is absent).** Classify the project against these
categories using signals from the repo. A category needs **at least 3 matching signals** to
classify. Subtract anti-signals. On a tie, report `category=ambiguous` with both candidates and
ask (or take the first if `--no-interview`).

| Category                | What it is                                                                  | Signals (files, dependencies, routes, code)                                                                                                                                                                                                                                     | Anti-signals                                                        |
| ----------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| saas-dashboard          | Dense multi-tenant operations surface: sidebar, command palette, tables     | `app/(dashboard)/`, `components/ui/data-table.tsx`, `middleware.ts`; `cmdk`, `@tanstack/react-table`, `@tanstack/react-query`, `next-themes`, `sonner`, `react-hook-form`, `zod`, 5+ `@radix-ui/*`; routes named login, settings and billing; `tenant_id` or `org_id` in schema |                                                                     |
| multi-llm-synthesis     | Side-by-side streaming model panels with a synthesis surface                | `lib/providers/`, `lib/synthesis/`, `app/api/synthesize/`; 3+ LLM SDKs (`openai`, `@anthropic-ai/sdk`, `@google/generative-ai`, ...); `ai`; `Promise.allSettled` over models, `streamText(`                                                                                     |                                                                     |
| marketing-landing       | Hero-led, photo-driven, one call to action per section                      | `app/(marketing)/`, `astro.config.mjs`, `public/og-*`, `public/hero-*`; `framer-motion`, `@vercel/og`, `astro`, `sharp`; routes named home, pricing, about and contact; `generateMetadata`, `next/image`                                                                         | `app/(dashboard)/`, `middleware.ts`, database migrations, auth SDKs |
| conversational-agent-ui | Chat threads with inline tool use, slash commands, approval gates           | `app/api/chat/route.ts`, `tools/`, `slash-commands.ts`; `ai`, `@ai-sdk/*`, `react-markdown`, `shiki`, bot SDKs; `useChat`, `streamText` with tools, a webhook route                                                                                                                  |                                                                     |
| trading-analytics       | Dark-default, dense, real-time; charts dominate, color reserved for state   | `lib/marketData/`, `lib/positions/`, `app/api/ticker`; `lightweight-charts`, `recharts`, `ccxt`, `technicalindicators`, `decimal.js`, `bignumber.js`; `tabular-nums`, `Intl.NumberFormat`, `EventSource`                                                                        |                                                                     |
| internal-ops            | Keyboard-first multi-pane operator surface: kanban, live events, cmd-K      | `app/(ops)/`, `app/kanban/`, `lib/sse.ts`; `cmdk`, `@dnd-kit/core`, `react-virtuoso`, `eventsource-parser`; routes named admin, inbox and kanban; `new ReadableStream`, `controller.enqueue`                                                                                    |                                                                     |
| marketplace-listing     | The deliverable is the assets a platform shows (thumbnails win), not a page | `listings/`, `assets/thumbnails/`, `app-store-assets/`; `sharp`, image tooling, templating (`handlebars`, `jinja2`); `*.template.md`                                                                                                                                            | `next`, `vite`, `react`, `app/page.tsx`, `components/ui/`           |

On classification, write the category's typical DNA (the "what it is" column, expanded into color
role, type, density and layout choices) into `DESIGN_MD_TOKENS_FALLBACK`, and set
`BRIEF_RECOMMEND_DESIGN_MD = true` so Step 5 says "this project should author an explicit
DESIGN.md to lock its tokens."

**Precedence is locked:**

- Explicit `DESIGN_MD_TOKENS` return early. The fallback runs only when they are empty.
- Step 5 reads `DESIGN_MD_TOKENS` first and uses `DESIGN_MD_TOKENS_FALLBACK` only if the first is
  empty. **Never merge fallback defaults on top of explicit DESIGN.md tokens.**
- No category clears 3 signals: log `category=unclassified`, use first-principles defaults in
  Step 5, and recommend writing DESIGN.md before the next run.

## Step 1: Runtime probe

**Inputs:** the tools available in this session and the project folder.

**Tools:** check which optional integrations respond (design-file export such as a Figma
integration, a component registry integration such as shadcn's, a framework dev-tools
integration, browser automation such as Playwright, a screen-recording reader). Check for a dev
server port (`lsof -i :3000` or the port in `package.json`). Check for Tailwind, shadcn
(`components.json`) and Next.js markers.

**Outputs:** `RUNTIME_FLAGS`, one true or false per tool.

**Failure modes:**

- A tool check errors: treat it as unavailable and continue.
- `lsof` permission denied: skip dev-server detection.
- No `package.json`: not a Node project; skip those checks.

**Batch:** run every check at once if your agent can make parallel calls.

## Step 2: Intent-first interview

**Inputs:** `GOAL`, `MODE`.

**Tools:** ask the user. If your agent has a structured question tool, use it.

**Outputs:** `INTENT_ANSWERS` with five fields. Each answer must be concrete, said out loud, not
assumed:

1. **Who is this human?** Not "users". The actual person. Where are they when they open this?
   What is on their mind? A teacher at 7am with coffee is not a developer debugging at midnight.
2. **What must they accomplish?** The verb. Grade these submissions. Find the broken deployment.
   Approve the payment.
3. **What should it feel like?** "Clean and modern" means nothing. Warm like a notebook? Cold like
   a terminal? Dense like a trading floor? Calm like a reading app?
4. **What is the focal point?** The one thing the screen is for, which must dominate through size,
   position or contrast.
5. **What is the hard constraint?** Brand rules, device, data density, accessibility level,
   deadline, existing components that must be reused.

If you cannot answer with specifics, ask. Do not default.

**A new screen, page, product or client build runs `/visual-spec` instead** and produces the
visual spec pack (process maps, wireframes, security map, entity map, navigation map) before Step 5
(rule set 2026-09-04). If a plan already carries a pack, consume it; do not re-interview.

**Skip when:** `--no-interview`, `--critique` mode (the target already exists), or the goal is
obvious ("fix the spacing on X", "add Y to Z").

**Failure modes:** a skipped question is recorded as "not specified". A cancel stops the pipeline
cleanly.

## Step 3: Context load

**Inputs:** `GOAL`, `MODE`, `FLAGS`, `RUNTIME_FLAGS`.

**Tools:** read in parallel where possible:

- `references/quality-floor.md`
- the project's DESIGN.md, `.interface-design/system.md` and component folder
- the craft checklist in `references/critique.md`
- any team design library or reference index the project points to
- `references/style-query-guide.md` results if `--style`
- the Figma frame, screenshot or live page, if given

**Outputs:** `DESIGN_CONTEXT_FULL`.

**Failure modes:**

- A file is missing: note the missing layer and continue.
- Design-file export times out: skip it and warn.
- A screenshot path cannot be read: ask the user to provide it again.
- No style database installed: skip the `--style` enhancement and say so.

## Step 4: Reference scan

**Inputs:** `DESIGN_CONTEXT_FULL` and the component type implied by `GOAL`.

**Production method.** For each adopted quality reference, follow "Understand and reproduce the
production method" in `references/quality-floor.md`. Open the live work and any source study,
inspect available code and media, and use its interactions. Trace each signature effect to its
assets, rendering and state code, and business dependencies. Recover tool instructions and
production inputs. Keep observed facts, proposed reconstruction and tested reconstruction
distinct. Record it in the existing brief and asset record; do not add another form.

**Source mapping.** For each design task, pick the relevant references (live products, source
studies, recipes in the team's library if one exists). In the brief, map each reference to the
mechanism, asset or workflow used in this build and the proof it needs. A screenshot, a catalog
count or a link check does not show the source was used. If nothing fits, record that and use an
attributed source that suits the task.

**Component scan.** Find 3 to 5 reference components:

- The component registries in `references/registries.md` (free, public).
- The project's own component folder first: reuse beats import.
- Optional: a semantic component search service. For example, 21st.dev's Magic integration offers
  four tools, picked by intent (checked 2026-05-18; it needs an account and API key):

  | Tool                               | Tier            | When                                                                                | Returns                                                      |
  | ---------------------------------- | --------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------ |
  | `21st_magic_component_inspiration` | free, unlimited | Default for the scan: semantic search. Args `message`, `searchQuery` (2 to 4 words) | Full component code plus a demo. Ready to adapt in one step. |
  | `logo_search`                      | free            | Company logos or brand icons. Args `queries`, `format` (JSX, TSX or SVG)            | Component name, code and import instructions                 |
  | `21st_magic_component_builder`     | paid credits    | Only with `--variants` when inspiration found no fit                                | New generated code, 2 to 10 credits a call                   |
  | `21st_magic_component_refiner`     | paid            | Only in `--refactor` on an existing file                                            | An improved version of the component                         |

  Free fallback: browse the registry sites or `21st.dev/community/components` with browser
  automation, or search the web for the component category.

**License discipline.** Code from a community library carries its publisher's license. Record the
source URL in the Step 9 report and check the license during review.

**Outputs:** `REFERENCES`: attributed references, their source or recipe links, the mechanism to
prove first, and any missing inputs.

**Skip when:** `--fast` skips only the component scan. Source selection and mapping still run.
This step has run by default since 2026-08-28. It used to sit behind `--deep`, and the everyday
path then designed from remembered products instead of real ones.

**Failure modes:**

- No registry integration: fetch registry JSON directly (`curl https://ui.shadcn.com/r/button.json`)
  or browse with browser automation.
- Semantic search not installed or its key is missing (401): skip it and use registries.
- Search returns 0 hits: widen the query ("dock", not "macos dock filter chip"). Short queries
  match better.
- Source access fails: try the live artifact, delivered code and assets, and official
  implementation guidance. Record what history could not be reached and test your own
  reconstruction. Never swap in defaults silently and claim the reference was understood.

## Step 4.5: Variant generation

**Inputs:** `DESIGN_CONTEXT_FULL`, `INTENT_ANSWERS`, N from `--variants N`.

**Tools:** an image generation service (optional, paid) or the free fallback (N quick HTML mocks
rendered and screenshotted in a browser), then a vision-capable stronger model to rank them. Full
procedure in `references/variant-generation.md`.

**Outputs:** `CHOSEN_VARIANT` (file path) and `VARIANT_RANKING`.

**Skip when:** `--variants N` is not set.

**Failure modes:** see the failure matrix in `references/variant-generation.md`. An unranked pick
is labelled as unranked and proves only a visual direction. If every variant fails, continue to
Step 5 without variants.

**Cost guardrail:** N is at most 8. Warn before a run whose estimated cost passes the team's
limit, and stop to ask if the cumulative cost of the run would pass it.

## Step 4b: Reference boards

**Inputs:** DESIGN.md, the list of sections.

**Tools:** an image generator (optional, paid) or the free fallback. Procedure in
`references/image-assets.md`.

**Outputs:** `BOARDS`: one board per section in `.planning/design/boards/`, each with its prompt
saved beside it. They record the committed pick per section: theme, ground, type, hero
architecture, section system and four signature components. Boards are references, never shipped.

**Skip when:** `--boards` is not set.

**Failure modes:** re-roll at most 2 times per section, then stop and say so. A generator failure
leaves the section without a board; say which.

## Step 5: Design decisions

Define the usable outcome and the material failures before building (see "Measure outcomes" in
`references/quality-floor.md`). For a substantive comparison, keep a baseline and freeze the
criteria before seeing candidates; otherwise label the evidence prospective-only. Keep it
proportional to the scope, inside the existing brief.

**Inputs:** `DESIGN_CONTEXT_FULL`, `INTENT_ANSWERS`, `REFERENCES`, `CHOSEN_VARIANT`, `BOARDS`.

**Tools:** optional multi-model review with `--council` (see `references/critique.md`).

**Outputs:** `DESIGN_BRIEF`: structured markdown with each axis (color, type, spacing, radii,
motion, layout, components, states), the choice, and the reason. "It's common" or "it's clean" is
not a reason; that is a default, not a choice. Swap test: if the choices were swapped for the most
common alternatives and nothing felt different, no real choice was made.

**Failure modes:**

- No council tool or key: warn and skip the multi-model review.
- The project default and a `--style` result conflict: the `--style` result wins for this brief;
  record why.

**DESIGN.md tokens are constraints.** If `DESIGN_MD_TOKENS` loaded in Step 0.5, every token
decision in the brief refers to the loaded namespaces by name:

- color: `{colors.<token>}`, never a literal hex
- type: `{typography.<token>}`
- spacing: `{spacing.<level>}`
- radius: `{rounded.<level>}`
- composite components: `{components.<name>}`

If a decision needs a token DESIGN.md does not define, the brief marks
`// pending DESIGN.md addition: <token-name>` and the addition becomes a Step 9 decision row.
Ad-hoc runs flag and defer; they do not edit DESIGN.md mid-run.

## Step 6: Generate

**Inputs:** `DESIGN_BRIEF`, `MODE`, `RUNTIME_FLAGS`.

Use the production trace from Step 4. Prove the hardest media, interaction or service dependency
in a small working slice first, then expand with the real project assets and contracts. Keep
generated artwork separate from code-native controls and text. Keep the successful generation
inputs, outputs and exact build commands for reuse.

**Tools:** file writes and edits, the component registry CLI (`npx shadcn add`), the DTCG export.

**Outputs:** the list of files created or changed.

**Mode behavior:**

| Mode                    | Writes                                                                                                                                                                                                                                                   |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--new`                 | New component or page files, or registry installs                                                                                                                                                                                                        |
| `--refactor`            | Edits existing files to conform to the system                                                                                                                                                                                                            |
| `--generate`            | Registry install only (`npx shadcn add @registry/name`)                                                                                                                                                                                                  |
| `--system`              | `.interface-design/system.md`                                                                                                                                                                                                                            |
| `--token`               | DTCG `tokens.json` via `npx -y @google/design.md@0.1.1 export --format dtcg DESIGN.md > .interface-design/tokens.json`; the template in `references/variant-generation.md` is the fallback; then optional `npx tz build` or `npx style-dictionary build` |
| `--system-to-design-md` | `DESIGN.md` from `scripts/extract_design_md.py`                                                                                                                                                                                                          |

**Failure modes:**

- `--new` with no target folder: ask where to write.
- `--refactor` and the file is not found: stop and list files that match the pattern.
- `--generate` with no registry integration: use the `npx shadcn add` CLI.
- `--system` with no `.interface-design/`: create it.
- `--token` with no Style Dictionary or Terrazzo config: write `tokens.json` only and say the
  compile step was skipped.

## Step 6.5: Asset kit

**Inputs:** DESIGN.md, the slot list.

**Tools:** an image generator (optional, paid) or the free fallback. Procedure and the asset check
are in `references/image-assets.md`.

**Outputs:** `ASSET_KIT`: files in `public/kit/`, each listed as a slot in `ASSETS.md`.

**Skip when:** `--assets` is not set.

**Gate:** Step 7 does not count until the asset check passes: no stock placeholder, no empty slot,
no orphan file under `public/kit/`, and every file referenced from the screen.

## Step 7: Verify

Report quality separately from evidence strength, required unknowns separately from passes, and
real outcome and repair measures where they apply (`references/quality-floor.md`). Critical
failures block the affected scope whatever the visual score. Keep failed attempts in the record.

**Inputs:** the files from Step 6 and the dev server URL; for `--critique`, the screenshot or
live target from Step 3.

For a critique-only task, Step 7 records the checks run, the proof that was unavailable, and the
checks outside the critique's scope.

**Tools:** browser automation for interactions and screenshots; the repo's test and build
commands; safe read-back of configuration and data; `@axe-core/playwright`; Lighthouse
(`lhci` or `npx lighthouse`); `size-limit`; `tsc --noEmit`.

**Outputs:** `VERIFY_REPORT`, in the project's existing evidence format. Cover each dimension
that applies, with the executed evidence linked and its result:

1. Source-to-build trace: which reference and recipe led to which built piece.
2. Code and build, including the DESIGN.md lint when DESIGN.md exists.
3. Configuration and service contracts.
4. Data.
5. Primary journey and recovery.
6. Visual quality, accessibility, performance, contrast and types.

Mark missing proof unverified. Explain genuinely non-applicable checks. Do not invent another
mandatory receipt format.

Inspect the changed code and effective configuration without exposing secrets. Confirm the
settings, service contracts and permissions support the real task. Check data provenance,
validation, transformations and error handling. Run the full primary journey from user input to
the real result, including saved-state read-back after a reload when anything is persisted, and
one relevant failure and recovery case. Use existing safe test records or approved test
environments. Respect the team's rules on production changes and vendor spend. Label mocked
providers, fixture data and isolated component tests: they do not prove a live integration or a
complete business journey.

Also exercise the signature behavior found in Step 4, including its failure and recovery states.
Compare the rendered working slice with the accepted reference. Record what the proof establishes
and what stays simulated or untested. A compile, a style score or a screenshot cannot prove a
provider call, a saved change, a working media timeline or a completed business action.

Screenshots at 390, 768 and 1440 pixels wide are the default viewport set.

**Skip when:** never for the report itself. For non-runtime deliverables (tokens, a design-system
document), say which runtime checks do not apply. For a working interface with no dev server
running, try the project's documented safe local start. If runtime proof stays unavailable, keep
the static checks and mark the runtime proof incomplete. Never call a working product verified
from screenshots or static checks alone.

**Failure modes:**

- Browser automation cannot reach the dev server: diagnose the documented start and connection
  path, keep static results, report runtime proof incomplete with the next required check, and do
  not claim verified completion.
- axe finds violations: critical and serious ones block; moderate and minor are warnings for style
  work.
- Lighthouse times out (30 second budget): skip the performance check and say so.
- `tsc` errors: surface them. They are real bugs, not style.

**Batch:** run independent static and visual checks together. Keep journey actions and saved-state
read-back in their required order.

**DESIGN.md lint gate** (added 2026-05-07). If DESIGN.md exists, add to the batch:

```bash
npx -y @google/design.md@0.1.1 lint DESIGN.md --format json
```

Output: `{ findings: [{ severity, path?, message }], summary: { errors, warnings, infos } }`.
`design-md-lint` passes when `summary.errors == 0`. Error findings block ship; warnings and infos
are reported but do not fail the gate. Pin the exact version (no caret): the schema is alpha.
Re-check when 0.2.0 ships. If npm is unavailable, mark the lint unverified.

## Step 8: Critique

**Inputs:** screenshots from Step 7, `DESIGN_BRIEF`.

**Tools:** the critique procedure in `references/critique.md`, run by a fresh reviewer (a subagent
if your agent supports it, a different model family, or a person) through Handoff Contract v1.

**Outputs:** `CRITIQUE_REPORT`: findings ranked HIGH, MEDIUM, LOW.

**Skip when:** `--no-critique`, unless critique is mandatory for this change (see
`references/critique.md`).

**Failure modes:**

- The stronger reviewer is unavailable: fall back to a standard reviewer and note the downgrade.
- Screenshot missing: skip the critique, warn, and keep Step 7's missing-proof note.

**Flags passed through:** `--deep`, `--council`, `--blur`, `--style`, `--persist`, `--no-cache`.

## Step 8.5: Iterate loop

**Inputs:** `CRITIQUE_REPORT`, the maximum from `--iterate [max]` (default 3).

**Tools:** edit the files, re-render with browser automation, critique again.

**Outputs:** `ITERATION_LOG`: per round, the finding addressed, the fix, and the new critique.

**Skip when:** `--iterate` is not set, or the report has 0 HIGH findings.

**Proof refresh:** any change in a round invalidates the affected Step 7 results. Before delivery,
rerun the affected checks against the final revision and replace the earlier results in
`VERIFY_REPORT`. A rerun that cannot happen stays incomplete.

**Stop when:**

- 0 HIGH findings remain: success.
- The maximum rounds are reached: stop and report what remains.
- The same finding appears 2 rounds in a row: stop (loop guard).

**Cost guardrail:** each round costs a critique plus a render. Warn before passing the team's
budget; stop and ask if a run would pass it.

## Step 9: Persist and deliver

**Inputs:** everything above: `GOAL`, `INTENT_ANSWERS`, `DESIGN_BRIEF`, `VERIFY_REPORT`,
`CRITIQUE_REPORT`, `ITERATION_LOG`.

**Tools:** write files.

**Outputs:** the delivery summary, always. With `--persist`, also
`.interface-design/decisions/{YYYY-MM-DD}-{goal-slug}.md` with front matter (`date`, `type:
decision`, `project`, `tags`). Carry forward the selected references and source mapping, and the
Step 7 proof with its limits. A required proof that failed or is missing prevents a
"verified working" claim. A visual rank or an aesthetic critique never replaces code,
configuration, data or journey evidence.

**Failure modes:**

- The decisions folder is missing: create it.
- The write fails: deliver the summary in the reply and warn that it was not saved.
- Every earlier output is empty: emit a minimal report saying the pipeline ran dry.

## Global error handling

- **A blocking error at any step:** stop the pipeline, report what succeeded, suggest the fix.
- **Non-blocking errors:** collect them in the report and continue.
- **Budget exceeded:** stop before the next paid step and ask the user.
- **Context running low:** before Step 6, save the brief and state to files so a fresh session
  can resume from them.
