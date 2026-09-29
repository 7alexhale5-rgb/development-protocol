# `--variants N`: several visual directions, ranked

Generate N visual variants of the screen, have a stronger vision-capable model rank them against
the brief, and use the winner as the visual reference for Step 6. Default N is 4, maximum 8.

Variants are visual direction only. They are not production UI and the ranking proves nothing
about code, configuration, data or the user journey (Step 7 still does that).

## Two ways to make the variants

**Free (default when no image service is set up): quick HTML mocks.** Write N small,
self-contained HTML files, each a deliberately different take on the same brief (different
composition, type pairing, density or color strategy, all within the project's tokens). Render
each at the target viewport with browser automation and save a screenshot. This costs nothing,
keeps text crisp and real, and the winner is already half-built.

**Paid (optional): an image generation service.** Any text-to-image API your team has an account
with. Useful when the direction depends on imagery, illustration or texture that HTML cannot fake
quickly. Needs an API key in the environment; check the per-image price before a run.

## Flow

### 1. Build the prompt (or mock brief)

From `DESIGN_CONTEXT_FULL` and `INTENT_ANSWERS`:

```text
Design a {artifact} with these constraints:

Purpose: {intent.verb}
Target user: {intent.who}
Feel: {intent.feel}
Dominant element: {intent.focal}

Aesthetic: {
  with --style: the style chosen from the style query
  otherwise: the project's DESIGN.md tokens, verbatim: ground = colors.background,
  cards = colors.card, ink = colors.foreground, primary = colors.primary, the color
  ramp by hex, the typefaces by name. These are project context, not a universal
  style restriction; explore from the approved creative direction.
}

Format: {aspect ratio for the use: 16:9 landing, 3:4 mobile, 1:1 card}

Include: {specific elements from the brief}

Exclude: placeholder copy, invented business facts, imagery unrelated to the task.
Choose palette, type, depth and composition from the brief; apply no blanket style bans.
```

### 2. Make N variants

HTML route: write `variant-1.html` to `variant-N.html` under
`.planning/design/variants/<timestamp>/`, render each, save `variant-i.png` beside it.

Paid route: fire the N requests in parallel, poll each until done, save `variant-i.png`, and save
the exact prompt and settings as `variant-i.prompt.json`. Handle these outcomes explicitly,
because each has happened:

| Outcome                     | Handling                                                  |
| --------------------------- | --------------------------------------------------------- |
| missing key or bad setup    | stop the variant step before any request                  |
| 401 or 403                  | stop the variant step; tell the user the key was rejected |
| completed but no image URL  | count that variant as failed                              |
| download failed             | count that variant as failed                              |
| prediction failed           | count that variant as failed                              |
| no result after about 2 min | time out that variant and count it as failed              |

Rate limits vary by service; space the calls if you get throttled.

### 3. Rank with a stronger model

Attach all variants as images and ask:

```text
I generated {N} variants for: {goal}. Rank them against:
1. The project's design system and the quality floor (attached)
2. Intent fit (user: {intent.who}, feel: {intent.feel}, focal point: {intent.focal})
3. Craft: the five craft tests (swap, squint, composition, content, structure)
4. Coherent craft and task relevance: specific content, useful hierarchy, intentional
   composition. No blanket palette or layout bans.

Return:
- Best: #N, and why in 2 sentences
- Second best: #N, and what it catches that the winner misses
- Rejected: each other variant, with one sentence why

Be opinionated. No hedging.
```

### 4. Set the chosen variant

`CHOSEN_VARIANT` is the winner's file path. Step 6 uses it as the visual reference. If the ranking
says none match the brief, the prompt needs work; fall back to generating directly from the brief.

## Cost

The HTML route costs only model time. The paid route costs roughly the service's per-image price
times N, plus one ranking call. Four variants is the usual sweet spot between variety and cost.
Warn the user before a paid run and stop to ask if it would pass the team's budget.

## Prompt patterns by mode

**`--new` hero section**

```text
A hero section for {product}. Use the project tokens and the approved direction as context.
Choose headline hierarchy, actions, imagery and composition to serve {intent.verb}.
Carry the chosen reference's craft into an original concept with real project content.
Aspect ratio 16:9.
```

**`--new` dashboard**

```text
A dashboard for {product}. Dense data with a clear hierarchy.
{DESIGN.md mono face} for numbers, {DESIGN.md body face} for labels.
Ground {colors.background}, cards {colors.card}.
Choose action emphasis, navigation and composition from the real workflow.
Aspect ratio 16:9, desktop.
```

**`--refactor` comparison**

```text
The current UI (attached: screenshot-1) has these issues: {HIGH findings}.
Make {N} variants that fix them while keeping the overall structure.
Each variant is a full-screen mockup at the current aspect ratio.
```

## Failure matrix

| Scenario                | Action                                                                                               |
| ----------------------- | ---------------------------------------------------------------------------------------------------- |
| 0 of N variants succeed | Drop the variant step with a message; Step 6 generates from the brief directly                       |
| 1 to N-1 succeed        | Continue with what arrived; log which indices failed and why                                         |
| Ranking fails           | Use the first successful variant as an **unranked** reference; log its index and that ranking failed |
| Service rejects the key | Drop the variant step, tell the user, continue without variants                                      |

## DTCG token template (fallback for `--token`)

The primary path is `npx -y @google/design.md@0.1.1 export --format dtcg DESIGN.md`. When that is
unavailable, write this structure, filled from DESIGN.md (the values below are placeholders):

```json
{
  "$schema": "https://design-tokens.github.io/community-group/format/tokens.schema.json",
  "$description": "Generated by /design-stack --token for {project}",
  "color": {
    "primary": {
      "$value": "#f97316",
      "$type": "color",
      "$description": "Brand accent"
    },
    "surface": {
      "base": { "$value": "#09090b", "$type": "color" },
      "raised": { "$value": "#18181b", "$type": "color" }
    },
    "text": {
      "primary": { "$value": "#f4f4f5", "$type": "color" },
      "secondary": { "$value": "#a1a1aa", "$type": "color" },
      "tertiary": { "$value": "#71717a", "$type": "color" }
    }
  },
  "size": {
    "spacing": {
      "unit": { "$value": "4px", "$type": "dimension" },
      "xs": { "$value": "4px", "$type": "dimension" },
      "sm": { "$value": "8px", "$type": "dimension" },
      "md": { "$value": "16px", "$type": "dimension" },
      "lg": { "$value": "24px", "$type": "dimension" }
    },
    "font": {
      "xs": { "$value": "0.75rem", "$type": "dimension" },
      "sm": { "$value": "0.875rem", "$type": "dimension" },
      "base": { "$value": "1rem", "$type": "dimension" },
      "lg": { "$value": "1.125rem", "$type": "dimension" }
    }
  },
  "font": {
    "sans": {
      "$value": "<typography.body.fontFamily>, ui-sans-serif, system-ui, sans-serif",
      "$type": "fontFamily"
    },
    "mono": {
      "$value": "<typography.mono.fontFamily>, ui-monospace, monospace",
      "$type": "fontFamily"
    }
  }
}
```

Compile with Terrazzo (`npx tz build`) or Style Dictionary (`npx style-dictionary build`) if the
project has a config for either.

## Caveats

- Generated images are not production UI. They are references for the build.
- Generated images often garble text. The HTML route does not.
- Slower, higher-fidelity image models are worth it only when imagery carries the direction.
