---
name: design-stack
description: Runs UI and UX design work through one pipeline, from intent interview and real reference research to design decisions, generated code, working-journey verification, independent craft critique and an optional fix loop. Use when designing a new screen, page or component, refactoring UI to a design system, critiquing a screenshot, Figma frame or live dev server, installing registry components, setting up a design system, or generating DTCG tokens or a DESIGN.md. Triggers on "design a", "build a page", "make a screen", "refactor the layout", "critique this UI", "this looks off", "looks AI-generated", "find a component", "set up tokens", "design system for", "DESIGN.md". Modes --new, --refactor, --critique, --generate, --system, --token, --system-to-design-md; options --variants N, --iterate, --council, --live, --persist, --fast.
---

# Design Stack

A multi-step design pipeline, the design counterpart of `/planning-stack`. It turns a goal into a
brief, a built interface and proof that the interface works, with a fresh critique at the end.

> **Project filing**: files this skill writes into the project itself (code, notes, assets)
> go where the project's ICM router (`CLAUDE.md`) and room `CONTEXT.md` say; see `/icm`.
> Checklist evidence under `.devproto/` stays where the checklist expects it. Other paths
> below are defaults for when no room names one; in a staged repo `.planning/` holds tool
> state only.

Read `references/quality-floor.md` once per design task. It sets the fidelity floor and leaves
style open. Its **Understand and reproduce the production method** section applies to every
reference you adopt: Steps 4, 6 and 7 recover, build and test the method behind a reference. A
screenshot alone cannot finish those steps. The pipeline records functional and accessibility
proof; aesthetic checks are advisory.

**Philosophy.** A thin orchestrator. Use the project's own design system first. Delegate critique
to a fresh reviewer. Install components from public registries instead of rewriting them.

**Optional integrations.** Design-file export (for example Figma), component registry tooling,
browser automation (for example Playwright), semantic component search and image generation are
all optional. Each has a fallback (see "Graceful degradation"). A missing tool never waives Step 7
proof.

It satisfies the `design` row of the development-protocol checklist (see "Record it" below).

---

## Step 0: Parse intent

From the user's words extract:

**GOAL:** the design objective (everything except flags).

**MODE** (one; auto-detect if missing):

| Mode                    | Use for                                                                                                                                      |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `--new`                 | Design from scratch                                                                                                                          |
| `--refactor`            | Rework existing UI to conform to the system                                                                                                  |
| `--critique`            | Review rendered UI (Step 8 procedure)                                                                                                        |
| `--generate`            | Find and install a registry component                                                                                                        |
| `--system`              | Define or update the design-system spec (`.interface-design/system.md`)                                                                      |
| `--token`               | Emit DTCG `tokens.json` (`npx -y @google/design.md@0.1.1 export --format dtcg DESIGN.md > .interface-design/tokens.json`; template fallback) |
| `--system-to-design-md` | Extract the pipe tables in `.interface-design/system.md` into a lint-checkable `DESIGN.md` with `scripts/extract_design_md.py`               |

**Input flags:**

- `--figma <url>`: start from a design frame (needs a design-file integration)
- `--screenshot <path>`: start from an image file
- `--live`: connect to the running dev server (browser automation)
- `--persona <who>`: the target user for the interview

**Creative flags** (added 2026-09-04; see `references/image-assets.md`):

- `--boards`: Step 4b. One reference board per section, prompted with the project's DESIGN.md
  tokens verbatim as brand context. Palette findings are advisory and never block a render.
  Re-roll budget 2 per section. Writes `.planning/design/boards/<section>.png` and
  `<section>.prompt.json`, plus a spend line for any paid run.
- `--assets`: Step 6.5. The asset kit for the screen (section plates, icons, empty-state
  illustration, Open Graph card) into `public/kit/`, each slot listed in `ASSETS.md`. The asset
  check must pass before Step 7 counts.

**Aesthetic flags:**

- `--style <query>`: choose a non-default aesthetic (`references/style-query-guide.md`)
- `--variants N`: generate N visual variants and rank them (default 4, max 8;
  `references/variant-generation.md`)
- `--iterate [max]`: critique, fix, re-render loop (default max 3)
- `--council`: several model families review a contested decision (`references/critique.md`)

**Why the reference scan runs by default (2026-08-28).** It used to sit behind `--deep`, so the
everyday path designed from remembered products instead of real ones. Measured the same day: the
category guides named well-known products as exemplars, and not one contained a step to go and
look at them. The step that fixes this existed and was switched off. A few cents of reference
research is cheaper than a screen that looks like every other generated screen.

**Depth and persistence flags:**

- `--deep`: on by default since 2026-08-28 (reference scan, stronger-model critique,
  alternatives). Passing it is harmless.
- `--fast`: the old default. Skips the component scan (source selection and mapping still run)
  and uses a one-viewport critique. For a quick pass on something already designed, never for a
  new screen.
- `--persist`: save the decision record to `.interface-design/decisions/`
- `--no-critique`: skip Step 8 (ignored when critique is mandatory; see `references/critique.md`)
- `--no-cache`: skip the Step 0.5 context check
- `--no-interview`: skip the Step 2 interview

### Flag applicability

| Flag           | --new | --refactor | --critique | --generate | --system | --token | --system-to-design-md |
| -------------- | ----- | ---------- | ---------- | ---------- | -------- | ------- | --------------------- |
| --figma        | yes   | yes        | yes        | -          | -        | -       | -                     |
| --screenshot   | yes   | yes        | yes        | -          | -        | -       | -                     |
| --live         | yes   | yes        | yes        | -          | -        | -       | -                     |
| --style        | yes   | yes        | yes        | -          | yes      | yes     | -                     |
| --variants N   | yes   | -          | -          | -          | -        | -       | -                     |
| --boards       | yes   | yes        | -          | -          | -        | -       | -                     |
| --assets       | yes   | yes        | -          | yes        | -        | -       | -                     |
| --iterate      | yes   | yes        | -          | -          | -        | -       | -                     |
| --council      | yes   | yes        | yes        | -          | yes      | -       | -                     |
| --deep         | yes   | yes        | yes        | yes        | yes      | yes     | yes                   |
| --fast         | yes   | yes        | yes        | yes        | yes      | yes     | yes                   |
| --persist      | yes   | yes        | yes        | yes        | yes      | yes     | yes                   |
| --persona      | yes   | yes        | yes        | -          | -        | -       | -                     |
| --no-interview | yes   | yes        | -          | -          | -        | -       | -                     |
| --no-critique  | yes   | yes        | -          | -          | -        | -       | -                     |
| --no-cache     | yes   | yes        | yes        | yes        | yes      | yes     | yes                   |

### Mode auto-detection

| Words in the request                                     | Mode                    |
| -------------------------------------------------------- | ----------------------- |
| "new", "create", "build", "design a", "make a"           | `--new`                 |
| "refactor", "rework", "update", "fix layout"             | `--refactor`            |
| "critique", "review", "feels off", "looks bad"           | `--critique`            |
| "add a button", "install", "find a component"            | `--generate`            |
| "set up tokens", "design system for", "brand guidelines" | `--system`              |
| "generate tokens", "DTCG", "style dictionary"            | `--token`               |
| "DESIGN.md from system.md", "extract tokens"             | `--system-to-design-md` |

If it is still ambiguous, infer from the target (a screenshot or URL is `--critique`, an empty
screen is `--new`, an existing component is `--refactor`), state the pick in one line, and go.
Ask only when two modes would produce materially different work and nothing on disk decides it.

**Conflicting flags.** If a flag is not "yes" for the chosen mode in the table, stop with:
`Error: Flag X has no effect in mode Y; remove it or change mode.` Also reject these pairs:
`--critique` with `--generate`, `--critique` with `--variants N`, `--token` with `--variants N`,
`--system` with `--iterate`.

Keep `GOAL`, `MODE` and `FLAGS` for the whole run.

---

## Taste priming

Agents design generically when they work from intent words alone. Craft jumps when real
reference shots and named tokens enter the context first.

Before Step 0.5, pull 2 or 3 concrete references keyed to the goal: the project's own DESIGN.md
tokens, a team design library if the project points to one, and live products or source studies
that fit the brief. For pre-design pattern research (how shipped products solve this flow, with
usability evidence), run `/research-stack --focus ui-ux` (add `a11y` when the flow has forms or
dialogs). Show them once, inline:

```text
> Taste prime:
> Tokens: {colors.background} (ground), {colors.foreground} (ink), {spacing.6} (gutter)
> References: <live URL or file> (why it fits), <live URL or file> (why it fits)
> Anti-references: <what not to do, from earlier critiques in .interface-design/decisions/>
```

Load this into `DESIGN_CONTEXT_FULL` so Steps 3 to 7 can compare the build against real
references. Step 0.5 adds project-specific tokens on top. If nothing matches, say
`> Taste prime: no reference match; using first principles from the quality floor` rather than
skipping silently.

---

## Steps 0.5 to 9

Each step has detailed notes (inputs, outputs, tools, failure modes) in
`references/pipeline-phases.md`. That file is the source of truth when you need more than the
one-line contract below.

| Step                   | Purpose                                                                                                                                                                                                                                                                         | Skip when                                                   | Key outputs                          |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------ |
| 0.5 Context check      | Load earlier design decisions from the repo, `.interface-design/system.md`, and `DESIGN.md` (YAML tokens). **Precedence:** an explicit DESIGN.md returns early; the category fallback runs only without one and is never merged over explicit tokens.                           | `--no-cache`                                                | `PAST_DECISIONS`, `DESIGN_MD_TOKENS` |
| 1 Runtime probe        | Detect optional integrations, the dev-server port, and Tailwind, shadcn and Next.js markers, all at once                                                                                                                                                                        | never                                                       | `RUNTIME_FLAGS`                      |
| 2 Intent interview     | Five questions: who, verb, feel, focal point, constraint. **A new screen, page, product or client build runs `/visual-spec` instead** and produces the visual spec pack before Step 5 (rule set 2026-09-04). If a plan already carries a pack, consume it; do not re-interview. | `--no-interview`, `--critique`, or an obvious small fix     | `INTENT_ANSWERS`, the spec pack      |
| 3 Context load         | Read in parallel: the quality floor, DESIGN.md and system.md, the craft checklist, any team design library, `--style` results, and the Figma, screenshot or live inputs                                                                                                         | never                                                       | `DESIGN_CONTEXT_FULL`                |
| 4 Reference scan       | Relevant source studies and production methods, plus 3 to 5 reference components from registries (and optional semantic search)                                                                                                                                                 | `--fast` skips the component scan only; source mapping runs | `REFERENCES`                         |
| 4.5 Variant generation | N variants (free HTML mocks or a paid image service), ranked by a stronger vision model; the winner is the visual reference                                                                                                                                                     | unless `--variants N`                                       | `CHOSEN_VARIANT`                     |
| 4b Reference boards    | One board per section with the committed pick: theme, ground, type, hero architecture, section system, four signature components. Re-roll budget 2                                                                                                                              | unless `--boards`                                           | `BOARDS`                             |
| 5 Design decisions     | Choose color, type, spacing, radii, motion, layout, components and states, each with a reason. Choose from the brief and rendered references; explore freely. DESIGN.md tokens are constraints, referenced by name. `--council` escalates a contested choice                    | never                                                       | `DESIGN_BRIEF`                       |
| 6 Generate             | By mode: `--new` writes components or installs from registries, `--refactor` edits existing files, `--generate` installs only, `--system` writes `.interface-design/system.md`, `--token` writes `tokens.json`, `--system-to-design-md` writes DESIGN.md                        | `--critique` (continue to Step 7)                           | files created or changed             |
| 6.5 Asset kit          | Plates, icons, empty states and an Open Graph card in `public/kit/`, each listed in `ASSETS.md`. The asset check must pass or Step 7 does not count                                                                                                                             | unless `--assets`                                           | `ASSET_KIT`                          |
| 7 Verify               | Source-to-build trace; code, configuration and data checks; the full primary journey with recovery; axe accessibility, Lighthouse, size budget, screenshots at 390, 768 and 1440, contrast, `tsc --noEmit`, DESIGN.md lint. Aesthetic observations stay advisory                | never; unavailable runtime proof stays incomplete           | `VERIFY_REPORT`                      |
| 8 Critique             | A fresh reviewer runs the five craft tests through Handoff Contract v1 (`references/critique.md`)                                                                                                                                                                               | `--no-critique` (unless mandatory)                          | `CRITIQUE_REPORT`                    |
| 8.5 Iterate loop       | Fix the top HIGH finding, re-render, critique again; stop at max rounds, at 0 HIGH, or when the same finding repeats twice                                                                                                                                                      | unless `--iterate`                                          | `ITERATION_LOG`                      |
| 9 Persist and deliver  | With `--persist`, write `.interface-design/decisions/{date}-{goal}.md`. Always deliver a summary: mode, depth, variants, iterations, files, verify results, critique, cost                                                                                                      | never                                                       | the final report                     |

---

## Creative exploration and visual follow-through

Read `references/quality-floor.md` before taste priming. Use project references to choose a
direction. Library tokens and components are raw material, not the design.

Build a strong rendered concept and carry its composition, richness and detail into the working
interface. Prefer useful progress views, comparisons, evidence, diagrams and contextual actions
when they explain the work better than lists. Use grounded AI features where they serve the task.

Palette, font, shadow, dark-theme, radius and type-count rules no longer veto ideas. Style scores
and cliche detectors, if your team has them, are optional diagnostics. Do not switch on a strict
aesthetic ban unless the current brief explicitly asks for that contract. Keep contrast, keyboard
access, responsive behavior and real task completion checks.

Compare the latest render with the accepted direction, fix weak areas, and pursue one useful
improvement beyond it. Do this inside the existing flow, with no extra approval or paperwork
round.

## Depth tiers

| Tier                       | Context                          | Reference scan                  | Variants   | Critique                       | Iterate | Relative cost |
| -------------------------- | -------------------------------- | ------------------------------- | ---------- | ------------------------------ | ------- | ------------- |
| default (was `--deep`)     | project system, refs, style data | yes                             | no         | stronger reviewer, 3 viewports | no      | low           |
| `--fast` (was the default) | project system, quality floor    | sources only, no component scan | no         | standard reviewer, 1 viewport  | no      | lowest        |
| `--variants 4`             | plus refs                        | yes                             | 4 parallel | stronger reviewer              | no      | medium        |
| `--iterate --council`      | everything                       | yes                             | no         | stronger reviewer plus council | up to 3 | highest       |

Give the default, `--generate` and `--critique` your agent's highest reasoning effort; `--fast`
can use a normal level.

---

## Graceful degradation

| Missing                            | Fallback                                                                                                     |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Design-file integration            | Skip the Figma input path; ask for a screenshot or live URL                                                  |
| Registry integration               | `npx shadcn add` with the registries in `references/registries.md`, or fetch the registry JSON directly      |
| Browser automation                 | Ask the user for screenshots; runtime journey proof stays incomplete, never a pass                           |
| Semantic component search          | Registries and web search                                                                                    |
| Image generation account           | The free HTML-mock and code-native routes (`references/variant-generation.md`, `references/image-assets.md`) |
| Multi-model council                | One extra reviewer from a different model family; if none, skip `--council` and say so                       |
| Dev server not running             | Run static checks; try the project's documented safe local start. Missing runtime proof stays incomplete     |
| Style database                     | The free fallback in `references/style-query-guide.md`                                                       |
| npm (for DESIGN.md lint or export) | Mark the lint unverified; use the DTCG template for `--token`                                                |
| Earlier decisions                  | Continue with the current brief only                                                                         |

**Minimum viable draft:** this skill, the ability to read and edit files, and the quality floor.
A verified working delivery also needs the Step 7 proof that applies. Missing tools or runtime
access do not waive it.

---

## Examples

```bash
# Critique a live dev server and save the findings
/design-stack "critique the admin login" --critique --live --persist

# New landing page with a non-default aesthetic, 4 variants, 2 fix rounds
/design-stack "landing for a luxury wellness client" --new --style "warm editorial refined" --variants 4 --iterate 2 --persist

# Install a chat component from a registry
/design-stack "AI chat with streaming" --generate

# DTCG tokens from a brand prompt
/design-stack "tokens from brand: navy + coral + editorial" --token --persist

# Lock an existing prose design system into a lint-checkable DESIGN.md
/design-stack "" --system-to-design-md
```

For `--system-to-design-md`:

```bash
skill_dir="<this skill folder>"   # fill in before running
python3 "$skill_dir/scripts/extract_design_md.py" .interface-design/system.md DESIGN.md --dry-run  # preview
python3 "$skill_dir/scripts/extract_design_md.py" .interface-design/system.md DESIGN.md
npx -y @google/design.md@0.1.1 lint DESIGN.md --format json                                             # must report 0 errors
```

The extractor reads colors (hex or HSL, converted to hex), the type scale, spacing and radii from
pipe tables under matching headings, synthesizes up to three starter components, and writes the
body sections in schema order. Review the result: it is a starting point, and the lint is the
gate.

---

## Record it in the checklist

This skill satisfies the `design` row. Write the Step 7 report as the evidence, with the
screenshot paths in it, then verify with a command that only reads:

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id=<work-id> --step design --result pass --evidence .devproto/evidence/design.md \
  --verify "python3 <design-stack skill folder>/scripts/verify_design.py --project . report .devproto/evidence/design.md"
```

`.devproto/evidence/design.md` holds, in this order: `## Brief` (intent answers and decisions),
`## References` (sources and what each changed), `## Verify report` (one line per Step 7
dimension, written `- <dimension>: pass|fail|unverified|n/a - <evidence>`, for example
`- primary journey and recovery: pass - saved item read back after reload, journey.log`), and `## Critique`
(findings and what was done). The verifier fails on any `fail` or `unverified` line, so an
unproven dimension can never ride along inside a pass. Save the screenshots beside it as
`design-390.png`, `design-768.png` and `design-1440.png`.

If the primary journey could not be run, record the row as `blocked` with the reason instead of
passing it. For a token-only or document-only deliverable, add `--non-runtime` to the report
verifier and explain each non-applicable runtime check. Do not use it for a working interface.

The report must include these dimension labels (case-insensitive): `source-to-build trace`,
`code and build`, `configuration and service contracts`, `data`, `primary journey and recovery`,
and `visual quality, accessibility, performance, contrast and types`. When DESIGN.md exists,
also include `DESIGN.md lint: pass - <lint evidence>`. Additional dimensions are allowed;
any failed or unverified dimension fails the check. Missing, malformed, duplicate, or empty
entries fail too. Runtime reports require all three screenshots. This checks report completeness;
it does not substitute for executing the checks or reviewing their linked evidence.

---

## Files

| Path                               | Purpose                                                                                  |
| ---------------------------------- | ---------------------------------------------------------------------------------------- |
| `references/quality-floor.md`      | The fidelity floor, proof strength, outcome measures, and the production-method research |
| `references/pipeline-phases.md`    | Step 0 to 9 details: inputs, tools, outputs, failure modes. **Read for details**         |
| `references/critique.md`           | Handoff Contract v1, the five craft tests, report format, council prompts                |
| `references/registries.md`         | Eight public shadcn-format registries, the `components.json` template, a health check    |
| `references/style-query-guide.md`  | `--style` with a style database or the free fallback                                     |
| `references/variant-generation.md` | `--variants N` (HTML mocks or an image service), ranking, failure matrix, DTCG template  |
| `references/image-assets.md`       | `--boards` and `--assets`: prompts, spend log, asset check                               |
| `scripts/extract_design_md.py`     | `--system-to-design-md` extractor (Python 3.9+, standard library)                        |

## Working with other skills

| Skill               | Role                                                                           |
| ------------------- | ------------------------------------------------------------------------------ |
| `/brainstorm-stack` | Before `/design-stack` on a greenfield design goal                             |
| `/research-stack`   | Pattern research `--focus ui-ux` (add `a11y` for forms or dialogs); competitors `--focus market` |
| `/planning-stack`   | For a cross-cutting feature, plan first, then `/design-stack --new` for the UI |
| `/visual-spec`      | Produces the spec pack Step 2 needs for a new screen or product                |
| `/audit-setup`      | Installs the axe, Lighthouse and bundle tools Step 7 uses                      |
| `/build-stack`      | After `/design-stack --new`, runs the full implementation                      |
| `/review-stack`     | Post-implementation review, including a design critique                        |
