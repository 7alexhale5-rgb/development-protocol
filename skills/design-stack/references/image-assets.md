# `--boards` and `--assets`: reference boards and asset kits

Added 2026-09-04. Both flags follow the same contract at two sizes. `--boards` (Step 4b) makes
one reference board per section before design decisions. `--assets` (Step 6.5) makes the files
the finished screen ships with.

## The contract

1. **Creative reference first.** Read `references/quality-floor.md`. Palette and font
   observations are advisory; they never stop generation.
2. **Project context in every prompt.** Carry the project's identity and task into a rich visual
   concept. Tokens are the starting brand context, not a cage. Color, type, imagery, depth and
   motion are creative choices. Do not inject a universal banned list and do not force flat,
   quiet layouts. Save each prompt beside its image as `<name>.prompt.json` (model, aspect,
   prompt, source URL).
3. **One spend line per paid run.** Append to `.planning/design/spend-log.txt`: date, mode,
   project, files written, account balance before and after, amount spent, and `ok` or
   `PARTIAL`. Read the balance from the service yourself before a phase; the log is a record,
   not the balance. If a balance cannot be read, write `unknown`, never `0`. An unknown booked as
   zero hides real spend.
4. **Budget.** Ask the user before a phase whose estimated cost passes the team's threshold. Run
   a dry run first on a new screen: print every prompt, spend nothing.
5. **Assets live in the repo.** Never ship assets through a vendor's hosted site builder for
   anything a client hosts. Assets are files in the project (`public/kit/`) on the project's own
   domain, each listed in `ASSETS.md`. Step 7 does not count until the asset check below passes.

## Generators

**Free (default).** Build boards as quick HTML compositions rendered and screenshotted in a
browser. Build assets code-native where possible: SVG icons drawn to the project's stroke and
grid, CSS or SVG section plates, a hand-built SVG empty-state illustration, and an Open Graph card
rendered from HTML at 1200 by 630 and screenshotted. Code-native assets stay sharp, editable and
license-clean.

**Paid (optional).** Any image generation service your team has an account with, for
photography-like plates, painterly illustration or textures. Needs an API key; check prices first.
Icons need a model that supports a transparent background.

## Prompt template

```text
Create {what}. Use these project tokens as the starting brand context: {name hex, ...}.
Project typefaces: {faces from DESIGN.md, or "choose a face suited to the brief"}.
{Creative direction: <direction from the brief>.}
Use deliberate hierarchy, optical alignment, coherent color and finished detail.
Explore imagery, expressive type, light or dark surfaces, depth and gradients when they improve
the brief. Choose the composition for this task; do not default to repeated identical cards or a
generic template. Keep text readable and the intended interaction clear. Do not invent customer
quotes, performance claims or live data.
```

Where `{what}` is, by kind:

| Kind    | What                                                                                                                                      | Aspect          |
| ------- | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `board` | a high-fidelity reference board for the {section} section of {product}, with a convincing product composition and useful interface detail | 16:9            |
| `plate` | a compelling section image for the {section} section of {product}, with a focal point and space for the intended content                  | 16:9            |
| `icon`  | a distinctive icon for "{name}", coherent with the product identity and readable at small sizes, on a transparent ground                  | 1:1             |
| `empty` | an expressive empty-state illustration for the {screen} screen of {product}, making its purpose and next step clear                       | 4:3             |
| `og`    | a polished Open Graph card for {product}, with a strong visual idea and readable hierarchy at sharing size                                | 16:9 (1200x630) |

Read the tokens from DESIGN.md's YAML front matter. If the front matter is missing, malformed, or
has a color that is not a quoted hex value, stop before generating: an input error is not a
creative choice, and a prompt built on half-parsed tokens wastes the spend.

## `--boards` (Step 4b)

One board per section named in the brief (for example `hero, pricing, comparison table`). Boards
are structural references for the committed pick per section: theme, ground, type, hero
architecture, section system, and four signature components. They are never shipped. They live in
`.planning/design/boards/<section>.png` with `<section>.prompt.json` beside each.

Re-roll budget: 2 per section. After that, stop and say so rather than rolling until something
looks acceptable.

## `--assets` (Step 6.5)

Slots are `kind:name`: `plate:hero`, `icon:leads`, `empty:tracker`, `og`. Files land in
`public/kit/` as `<kind>-<name>.png` (or `.svg` for code-native), and each slot is a line in
`ASSETS.md`:

```text
- slot: plate:hero file: kit/plate-hero.png source: generated (prompt in kit/plate-hero.prompt.json)
- slot: icon:leads file: kit/icon-leads.svg source: hand-built SVG
```

## Asset check

Run from the project root. It must print `asset check: pass` before Step 7 counts:

```sh
fail=0
# Every file in public/kit/ is listed in ASSETS.md (no orphans).
for f in public/kit/*; do
  [ -e "$f" ] || continue
  case "$f" in *.prompt.json) continue ;; esac
  rel="${f#public/}"
  grep -q "file: $rel" ASSETS.md || { echo "orphan: $f"; fail=1; }
done
# Every slot in ASSETS.md has its file (no blank slots).
grep -o 'file: [^ ]*' ASSETS.md | cut -d' ' -f2 | while read -r rel; do
  [ -s "public/$rel" ] || echo "missing: public/$rel"
done | grep . && fail=1
# Every kit file is referenced from the source (no unused assets).
for f in public/kit/*; do
  [ -e "$f" ] || continue
  case "$f" in *.prompt.json) continue ;; esac
  name="$(basename "$f")"
  grep -rqs --exclude-dir=node_modules --exclude-dir=public --exclude=ASSETS.md "$name" . || { echo "unused: $f"; fail=1; }
done
[ "$fail" -eq 0 ] && echo "asset check: pass" || echo "asset check: FAIL"
```

The script cannot judge "no stock placeholders". Check that by eye: every slot shows the
project's real subject, not a generic stock photo or a gray box.

## Failure handling

- A generation fails mid-run: keep what was written, still read the after-balance, and log the
  run as `PARTIAL` with the count actually written. A failed run can still have spent money.
- An unknown slot kind: stop before any paid call.
- The dry run is mandatory on a new screen and makes no vendor calls, reads no balance and writes
  no spend line.

## What this replaced

The earlier version injected one house look and rejected ideas by palette. The current direction
opens creative exploration while keeping real brand context and honest spend accounting.
