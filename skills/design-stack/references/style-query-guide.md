# `--style`: choosing a non-default aesthetic

`--style <query>` tells `/design-stack` to look past the project's current default aesthetic and
choose from a wider set of styles, palettes and type pairings. Use it when the project default
does not fit the audience.

```bash
/design-stack "landing page for a luxury wellness brand" --new --style "warm pastel editorial luxury refined"
```

The query is free text. More descriptive is better. Combine adjectives across style, color and
typography.

## Where the options come from

**With a style database (optional).** The open-source `ui-ux-pro-max` skill ships searchable CSV
files of UI styles, palettes and font pairings with a keyword search script. If it is installed,
one `--style` query becomes three searches:

```bash
# Find the installed search script; the path varies by install method.
SEARCH=$(find ~ -path '*ui-ux-pro-max*/scripts/search.py' 2>/dev/null | sort -V | tail -1)
[ -z "$SEARCH" ] && echo "--style: no style database found; using the free fallback" >&2

python3 "$SEARCH" "warm editorial refined" --domain style
python3 "$SEARCH" "warm editorial" --domain color
python3 "$SEARCH" "editorial refined" --domain typography
```

Its domains:

| Domain          | Use                                                                                   |
| --------------- | ------------------------------------------------------------------------------------- |
| `style`         | UI style families (glassmorphism, brutalism, claymorphism, bento, flat) with CSS cues |
| `color`         | Palettes indexed by product type and mood                                             |
| `typography`    | Font pairings with web-font imports and usage notes                                   |
| `landing`       | Landing page structures and call-to-action strategies                                 |
| `ux`            | Practices and anti-patterns                                                           |
| `product`       | Recommendations by product type                                                       |
| `chart`         | Chart types and libraries                                                             |
| `icons`         | Icon set recommendations                                                              |
| `app-interface` | App layout patterns                                                                   |
| `ui-reasoning`  | Design rationale entries                                                              |

**Free fallback (no database).** Write the query into the brief, then find 3 live references
that match it (award galleries, product sites, type specimen pages) and extract their palette,
type pairing, spacing rhythm and signature component. Record each source URL. This is slower but
grounded in real work rather than a table row.

Either way, results feed Step 5 (design decisions) as the alternative to the project default.

## Example queries by project type

| Project               | Query                                        | Likely direction                                                            |
| --------------------- | -------------------------------------------- | --------------------------------------------------------------------------- |
| Luxury wellness brand | `"warm pastel luxury refined calming"`       | soft or tactile styles, warm pastels, serif pairings                        |
| Kids learning app     | `"playful bright approachable friendly"`     | flat or clay styles, primary brights, rounded sans                          |
| Enterprise B2B SaaS   | `"corporate clean professional trustworthy"` | flat or minimal, corporate blues, a workhorse sans with a plex mono         |
| Indie game studio     | `"brutalist raw maximalist loud"`            | brutalism, high contrast, display serif plus mono                           |
| Personal portfolio    | `"editorial magazine personality custom"`    | editorial minimalism, monochrome plus one accent, editorial serif           |
| Fintech trading       | `"dense data-heavy precise trustworthy"`     | minimal, neutral plus green and red for data only, mono plus geometric sans |
| Web3 product          | `"futuristic neon dark technical"`           | glass or cyber styles, neon on dark, mono plus techno display               |

## When to use it

Use `--style` when:

- the client brand clashes with the project's current default
- the audience is consumer, luxury, creative or editorial
- the aesthetic is part of the brief ("warm", "playful", "brutalist")
- the client supplied a mood board or brand guidelines

Skip it when:

- the product already has its own design system that fits (DESIGN.md wins)
- it is a standard developer tool, admin panel or internal dashboard where the existing system
  is right

## How the result appears in the brief

```text
## Aesthetic direction (from --style "warm editorial refined")

Project default (not chosen for this brief):
- dark neutral ground, geometric sans, one saturated accent

Chosen alternative:
- Style: editorial minimalism, serif display, generous whitespace, muted palette
- Colors: cream ground (#faf7f0), forest accent (#2d5016), charcoal text (#2a2a2a)
- Type: a high-contrast display serif with a neutral text sans
- Spacing: 8px base unit for an editorial rhythm

Why: the audience expects a magazine feel, not a developer-tool feel.
```

The rationale goes into `DESIGN_BRIEF` and into the decision file with `--persist`.

## Combining flags

```bash
# Full exploration
/design-stack "hero section for a wellness brand" --new \
  --style "warm pastel luxury refined" --variants 4 --iterate 2 --council --persist

# Critique against a non-default aesthetic
/design-stack "review brand landing" --critique --live --style "warm editorial refined"
```

## Caveats

- Keyword search needs specific words. "Nice" or "modern" returns mediocre matches.
- The databases are in English; other-language queries will not match.
- Conflicting adjectives ("minimal maximalist") return incoherent results.
- Always check returned palettes against WCAG AA contrast. No style database guarantees
  accessibility.
