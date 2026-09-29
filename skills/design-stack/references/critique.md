# Critique: the Step 8 procedure

Step 8 of `/design-stack` hands the rendered UI to a fresh reviewer. The reviewer should not be
the agent that built it: use a subagent if your agent supports one, a model from a different
family, or a person. A reviewer that did not write the code sees what the author has stopped
seeing.

## Handoff Contract v1

The envelope Step 8 passes to the reviewer. Changing it is a contract change: bump
`contract_version` and update SKILL.md Step 8 in the same edit.

```text
contract_version: 1
{
  "screenshot_paths": string[],      // absolute paths from Step 7 (390, 768, 1440 wide)
  "mode": "critique",                // fixed: the reviewer only critiques
  "intent_answers": object | null,   // Step 2; null with --no-interview or direct --critique
  "design_brief": string | null,     // Step 5; null when entered via --critique
  "source_files": string[],          // 1 to 3 relevant source files, or [] (enables the structure test)
  "flags": {
    "deep": boolean,
    "council": boolean,
    "style": string | null,          // the --style query, or null
    "persist": boolean,
    "blur": boolean,
    "live": boolean,
    "no_cache": boolean
  }
}
```

## Flag effects

| design-stack flag | Effect on the critique                                                         |
| ----------------- | ------------------------------------------------------------------------------ |
| default           | One reviewer, 3 viewports, the five craft tests                                |
| `--fast`          | One viewport (1440), a standard-strength reviewer                              |
| `--deep`          | A stronger reviewer, all 3 viewports, automated accessibility summary          |
| `--council`       | Several reviewers from different model families in parallel (see below)        |
| `--blur`          | Blur the screenshot first (`filter: blur(20px)`) and lead with the squint test |
| `--style <q>`     | Judge against the queried aesthetic, not the project default                   |
| `--persist`       | Save the findings with the Step 9 decision file                                |
| `--no-cache`      | Do not load earlier critiques as context                                       |

## Getting the screenshot

1. A file path ending in `.png`, `.jpg` or `.webp`: read it directly.
2. `--live <url>`: open it with browser automation, apply the blur if `--blur`, capture at 390,
   768 and 1440 wide (1440 only with `--fast`).
3. `--figma <url>`: export the frame as PNG through a design-file integration if you have one;
   otherwise ask for a screenshot.

## Context the reviewer gets

- The screenshots.
- The project's DESIGN.md and `.interface-design/system.md`, so it can name drift in real tokens
  ("`{spacing.6}` used where the system says `{spacing.4}`"), not "spacing feels off". A creative
  choice does not need a library's permission; a token bug does need the token named.
- `references/quality-floor.md`.
- The intent answers and brief, when present.
- `--style` results, when present.
- 1 to 3 source files, when available, for the structure test.

## The five craft tests

Run all five. Run the structure test only when source code was provided; otherwise report
"4/5 tests run".

### 1. Swap test

If the typeface, layout or colors were swapped for the most common alternatives, would anyone
notice? The places where a swap would not matter are the places the design defaulted.

Look for: a hero that could sit on any site, an untouched stock component with no character,
stock "sign in here" copy, a palette chosen by habit rather than for this audience.

- HIGH: several areas could be swapped unnoticed
- MEDIUM: one key area (hero, primary action, navigation) is a default
- LOW: intentional-looking but could be stronger

### 2. Squint test (lead with it under `--blur`)

Blur your vision. Is the hierarchy still there? Does anything jump out harshly?

Look for: the focal point and whether it actually dominates (size, position, contrast); elements
competing with it; areas that shout when they should whisper. Quiet and bold can both show craft.

- HIGH: no focal point survives the blur
- MEDIUM: the focal point is weak or attention is split
- LOW: one minor competing element

### 3. Composition test

Does the layout have rhythm? Dense areas giving way to open ones, heavy balancing light, a clear
focal point for the one thing the user came to do?

Look for: spacing that ignores the system's scale, everything given equal weight, no breathing
room around the primary action, content floating centered in a void, monotonous even spacing that
ignores content priority.

- HIGH: no rhythm, every element the same weight
- MEDIUM: uneven spacing or the wrong emphasis
- LOW: a small polish issue

### 4. Content test

Read every visible string as the user. Does the screen tell one coherent story? Could a real
person be looking at exactly this data? Incoherent content breaks the illusion faster than any
visual flaw.

Look for: lorem ipsum, "Button", "Click here", placeholder names; tone that clashes with the
audience (casual on enterprise, jargon on consumer); numbers that do not add up, 1970 timestamps;
copy that says what instead of why the user cares; missing context (an empty chart with no helper
text, a bare form).

- HIGH: placeholder text is visible, or the tone clashes with the persona
- MEDIUM: generic but not wrong
- LOW: tone slightly off

### 5. Structure test (needs source)

Find the CSS lies: negative margins undoing a parent's padding, `calc()` workarounds, absolute
positioning to escape the layout flow, `!important` stacks, magic numbers. The right answer is
almost always simpler than the hack.

- HIGH: layout only works because of a hack that breaks at another viewport
- MEDIUM: a workaround that should be a layout primitive
- LOW: a stray magic number

After each test, ask: "If someone said this lacks craft, what would they point to?" Fix that
first.

## Report format

```text
# Craft critique: {target}

## Findings (ranked by severity)

### HIGH: {test name}
- Issue: {specific observation}
- Why it matters: {one sentence tied to the user's task or the quality floor}
- Fix: {actionable change}
- File: {path:line, if source was provided}

### MEDIUM: {test name}
(same structure)

### LOW: {test name}
(same structure)

## Accessibility (automated with --deep)
- Contrast (WCAG AA): pass | warn | fail
- Keyboard navigation: pass | warn | fail
- Visible labels: pass | warn | fail

## Summary
- Tests run: 5/5 (or 4/5 without source)
- Total findings: N
- Most critical theme: {one line}
- Confidence: {50 to 99}%
```

If the report says "passes 5/5 craft tests, no findings", the critique step is done. That is a
statement about craft only; Step 7's functional proof still stands on its own.

## Acting on findings

| Severity | Action                                                                               |
| -------- | ------------------------------------------------------------------------------------ |
| HIGH     | Fix before ship. Applied automatically with `--iterate`; otherwise shown to the user |
| MEDIUM   | Should fix. Batch with other fixes                                                   |
| LOW      | Nice to fix. Record it in the decisions and ship without it                          |

## When to skip the critique

`--no-critique` is reasonable for:

- pre-deploy verification only, where Step 7's accessibility and performance checks are enough
- rapid batches of many small fixes
- a manual design review already scheduled
- a critique already run on the same revision this session

## When critique is mandatory

Ignore `--no-critique` and say so when the change is:

- shipping to a client
- the first render of a new screen
- a change to the primary action, the hero or the navigation
- the output of a `--variants` run
- about to merge a `--iterate` sequence

## `--council`: several model families

When a decision is contested, ask reviewers from different model families the same question in
parallel and merge the answers, marking where they disagree. Use your team's multi-model tool if
it has one (an aggregator API such as OpenRouter works); otherwise run one extra reviewer from a
different family. Keep the context under about 2,000 characters.

**From Step 5 (a contested design decision):**

```text
Should {decision axis} lean toward {option A} or {option B} for {goal}?

Project default: {the current token or pattern}
Context: {intent.feel}, {intent.constraint}, {intent.focal}

Defend or push back on the default. Name any taste trade-off the system does not cover.
```

**From Step 8 (parallel craft critique):**

```text
Run the five craft tests (swap, squint, composition, content, structure) on this UI.

Screenshot: {path}
Goal: {goal}
Context: {relevant excerpt of DESIGN.md and the quality floor}

Each of you: run all five tests independently. Return findings with severity (HIGH, MEDIUM,
LOW), file:line if source was given, and a fix.
```

The council is an optional enhancement. On any failure (no key, rate limit, network), continue
with the single reviewer, note "council unavailable", and never block the pipeline on it.
