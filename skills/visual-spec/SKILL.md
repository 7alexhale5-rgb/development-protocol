---
name: visual-spec
description: Produces a Visual Spec Pack before any UI is built, by interviewing the owner until every workflow has a start, an end, an owner, a record and a failure path, then drawing a tagged process mind map, current-state workflow flowcharts, rendered screens with real example data, one wireframe per screen with its security contract, an entity map and a navigation map, and gating the result with a script that fails a pack missing any part. Use for any page, app, dashboard, client build or UI/UX redesign, or when someone says "spec the screens", "wireframe this", "map the workflow", "what should each screen do", "visual spec", "pre-fab the design" or runs /visual-spec. The visual-spec row of the development protocol.
---

# Visual Spec

A Visual Spec Pack shows, before any pixel or component exists, what the people do today, what
each screen will be, what it may show and to whom, and how the screens connect. It is the
planning and pre-fabrication standard for every design, UI/UX, page or application build.

The standard was set on 2026-09-04 after a client pack proved its worth. The owner's words: the
agent should interview fully, to be able to write a detailed, complete outline, wireframe and map
of the whole design and workflow, and we should always plan this well.

## Where this sits in the protocol

This skill satisfies the **`visual-spec`** row of the development-protocol checklist, after
`planning` and before `design`. For work with no UI, mark the row not applicable with the reason.

- `/planning-stack` Step 1.6 (the interview) hands UI work here. For any UI/UX, page, app or
  client build, the pack is the plan's visual body, not an optional attachment.
- `/design-stack` consumes the pack. It produces one only when a screen arrives with no plan.
- `/karpathy spec`: the pack is the spec's visual half.
- `/brainstorm-stack` hands UI work to `/planning-stack`, which runs this interview.
- No scaffold for a new client build before the commercial answers (question 6) and at least the
  home-screen wireframe exist.

This paragraph settles ownership: `/planning-stack` produces the pack through this skill,
`/design-stack` consumes it. Early versions of the standard placed it in two positions; that
caused confusion and was fixed on 2026-09-05.

Record the row when the gate passes and the owner has reviewed every view:

```text
python3 <this skill folder>/scripts/spec_pack_check.py <pack folder> \
  > .devproto/evidence/visual-spec-check.txt
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id=<work-id> --step visual-spec --result pass \
  --evidence .devproto/evidence/visual-spec-check.txt \
  --instrument <pack folder>/manifest.json --instrument <pack folder>/review-ledger.md \
  --verify "python3 <this skill folder>/scripts/spec_pack_check.py <pack folder>"
```

The manifest holds a SHA-256 for every source, screen PNG, and HTML artboard.
A changed asset fails the gate; updating its hash changes the proof instrument and reopens the row. The review ledger is an instrument too: a new correction reopens it.

## Files in this skill

| File                         | What it holds                                                                                         |
| ---------------------------- | ----------------------------------------------------------------------------------------------------- |
| `references/pack-format.md`  | Exact file formats, naming rules, a complete worked example that passes the gate, the render skeleton |
| `scripts/spec_pack_check.py` | The acceptance gate. Python 3.9+, standard library only                                               |

---

## What a pack is

One folder, `<project>/.planning/visual-pack/` unless the project has its own place, holding
Mermaid sources (`.mmd`, numbered `01-`, `02-` ...), rendered screens, a `manifest.json` with a
SHA-256 per source, an `index.md` and a rendered `index.html`. Mermaid is a text format for
diagrams that renders in a browser. The pack has eight parts:

1. **Process mind map** of the whole domain. Every leaf is tagged **R** (reported by the client),
   **W** (wanted by the client), **P** (proposed by us) or **U** (unknown until a walkthrough).

2. **Current-state flowcharts**, one per workflow (a small parts business might have five:
   purchasing and receiving, stock control, withdrawals, web orders, dealer purchasing).
   Swimlanes by person. Dotted edges to `UNKNOWN:` and `WANTED:` nodes. Issue nodes in red where
   today's process loses data. Every fact on a node traces to a source (a transcript, an email,
   a workbook answer).
   **Record marker (added 2026-09-05):** a node that is a system of record (accounting software,
   a spreadsheet, a database) carries the `record` class. A node that is a manual channel (a
   paper sheet, a phone call, memory) says so in its label. R/W/P/U says who reported a step;
   the record marker says whether the step's record can be trusted as evidence of what
   physically happened.

3. **Rendered screens, first (added 2026-09-06).** Two layers, two jobs. On 2026-09-06 an owner
   was shown nine block diagrams of screens and could not tell a nav bar from a table from a
   button, because Mermaid's block diagram draws every region as the same rectangle and carries
   field NAMES, not example data (Mermaid has no wireframe type; its issue #1184 is still open).
   The owner's verdict on the diagram-only format: it did not help at all. So:
   - The **rendered screens are the pack's first section and the thing the owner reviews.** One
     artboard (an HTML page drawn at a fixed width) per screen, with real example data, the
     project's design tokens, at the owner's width (390 px for a phone-first screen, 1440 px for
     a desk; both when both are used), and the loading, empty and error states drawn as their
     own artboards, not footnoted.
   - The worked pattern: read colours, type faces and sizes from the project's design token file
     (for example the front matter of `DESIGN.md`); never retype a colour value. Keep one mock
     data set that every screen and every count derives from. Write a `SCREENS.md` that is the
     spec text. Screenshot each artboard to a PNG (with Playwright if you have it, or any
     headless browser, or a manual browser screenshot).
   - Manifest rows for screens carry `screen` (the PNG), `artboard` (the HTML), `width` and
     `states`, plus required `screen_sha256` and `artboard_sha256` hashes. The gate refuses
     missing assets, missing hashes, or changed bytes.
   - If your team has a design canvas tool, publish the artboards there so the owner can move
     and retype things by hand. The canvas is the review surface; the pack page is the record.
   - Owner-set sizes apply on top of the design tokens (for example, a shop floor that asked for
     17 px body text and 44 px touch targets).

4. **Proposed wireframes**: one Mermaid `block-beta` per screen (A, B, C ...), two columns, with
   the classes `header`, `field`, `action`, `note`, `quiet`. The wireframe is a MAP: it binds a
   screen to its workflow step, its security contract and its one action. It is never the thing
   the owner judges by eye. Notes carry the honest caveats ("rule still needs walkthrough", "do
   not silently return a used part to stock", "not connected in this wireframe"). **One primary
   action per screen** (the Von Restorff effect: the one thing that looks different is the one
   remembered), with two declared exceptions in the manifest row: `"actions": "menu"` for a home
   or index screen that only routes, and `"actions": "none"` for a preview or read-only screen.
   Each wireframe row's `concept` field points at its rendered screen. "none yet" is allowed
   only until the screen exists, and the owner's review does not start until it does.

5. **Map table**: each wireframe, the workflow view(s) it draws on, its rendered screen (or "none
   yet"), and what the **security contract must cover**: who may see cost, who approves, device
   identity versus operator identity, offline behaviour and release.

6. **Information relationships**: a `flowchart LR` entity map of every noun a screen must be
   able to trace (for an inventory app: part, supplier, purchase order, line, receipt, location,
   movement, operator, station, job, customer, order, package, shipment, accounting reference,
   posting receipt). Unknown lifecycles use the `note` class.

7. **Screen-to-process navigation**: a `flowchart TB` from a HOME node to every screen. Follow
   the work, not disconnected dashboards. Shared receipt states: never confuse "saved" with
   "posted".

8. **Plain-English Summary**, the last heading of `index.md`, with six fixed headings: What we're
   building; Why this piece; The surprise; The real problem I caught; Where we are right now;
   The one thing left. Written for a smart non-engineer: no file paths, no jargon.

Names are corrected on the record (the manifest row notes the correction, "A -> B, per <who>"),
and the original text is kept in `raw/`. Keep personal data in the pack to what the work needs.

---

## The interview that earns it

Run it before drawing anything. The pack is only as good as the interview.

Ask in groups of two or three questions, conversationally (with a multiple-choice question tool
if your agent has one), until every workflow has a **start, an end, an owner, a record and a
failure path**.

**Stopping rule (added 2026-09-05):** stop after two consecutive question rounds that add no new
step, node or UNKNOWN to any diagram. There is no fixed question count. This adapts the
saturation finding of Guest, Bunce and Johnson (Field Methods, 2006: 94% of themes appeared
within the first six interviews) to a single owner.

**Phone adaptation:** contextual inquiry's live narration. The owner stands at the station and
describes each step as they would do it, and you cross-check it against what they said earlier.
An in-person walkthrough of the real place replaces this whenever possible.

**Question bank, in order:**

1. **People and places.** Who does what, where (rooms, buildings, devices), and who is named in
   the problems. Which device is shared; which identity is personal.
2. **Each workflow, step by step.** Trigger, decision, action, record, handoff. For each step:
   who, with what tool (paper, a spreadsheet, accounting software, email), and what gets written
   down.
3. **Where the record and the physical world drift.** A real finding from the first pack: a
   weekly transcription is not a physical count. What is never written down? Which
   discrepancies repeat?
4. **What they want (W), in their words**, kept separate from what we propose (P). Never merge
   the two.
5. **Unknowns (U)**: everything not established. Named as unknown, never guessed.
6. **Commercial and strategy context** (for a website or client-facing product): the primary
   offer, the primary buyer, the buying moment, the one goal of the site, what a visitor must
   believe within five seconds, the main trust objection, the proof available, the motion
   direction, who approves, the launch date, the scope boundary.
7. **Security and rights**: who may see cost, history, customer data; who approves corrections;
   shared station versus personal operator; offline behaviour and release.
8. **Integrations and history**: the existing systems (accounting, shipping, the store platform),
   what must stay accessible, retention, migration rules.
9. **Offers, pricing, seasonal rules**: capture as reported figures ("18 percent base discount")
   and mark the formula UNKNOWN until confirmed. Show previews only until then.
10. **Content evidence**: what real photography, specifications and documents exist. Generated
    media must never invent parts, products or steps.

---

## Build and render

**Save the source at draw time.** The first pack's views were lost because they were shown in
chat by a diagram display tool, called in a loop, and never written to disk. They were recovered
from an 81 MB session log. The rule: write each view to `<pack folder>/NN-slug.mmd` and its row
to `manifest.json` (file, title, sha256, and for wireframes `workflow`, `concept`, `security`,
`actions`) BEFORE displaying it. A display call is not a file. Keep the raw first draft in `raw/`
when names or facts are corrected later, and note the correction in the manifest row.

Compute each hash with `shasum -a 256 <file>`, `sha256sum <file>`, or
`python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <file>`.
Update the manifest every time a source, rendered PNG, or HTML artboard changes.
Rehashing records new bytes; it does not grant approval. Request a new owner review.

**Render** an `index.html` that works offline: rendered screens first, then each `.mmd` in
manifest order inside `<pre class="mermaid">`, then the Plain-English Summary. Put a copy of
Mermaid's `mermaid.min.js` (from the `mermaid` npm package, version 10 or later) in a `vendor/`
folder beside the page. If you cannot vendor it, load it from a CDN and say the page is not
offline. The skeleton is in `references/pack-format.md`. If your team already has a pack
renderer, use it. Regenerate `index.html` whenever a source changes, and open it for the owner in
the same turn.

**Render gate.** Prove the diagrams parse by opening the rendered page in a browser and looking,
or with a pure Node parser. Do not cite a `mermaid-cli` log as proof: it drives a headless browser
and fails on missing binaries. One run showed 18 of 18 "failures" that were all one missing
headless browser. Mermaid 9.x cannot draw block diagrams or mind maps; use 10 or later.

---

## Acceptance gate

Run the gate and paste its output:

```bash
skill_dir="<this skill folder>"    # fill in before running
pack_folder="<the spec pack folder>"   # fill in before running
python3 "$skill_dir/scripts/spec_pack_check.py" "$pack_folder"
```

Exit 0 pass, 1 a rule fails, 2 no pack or an unusable manifest. **A 2 is never a pass.** It
checks: manifest hashes; R/W/P/U on every mind-map leaf; a class on every flowchart node; an
UNKNOWN per workflow (or `"unknowns": "none"` in the manifest row); one action block per
wireframe unless the row declares `"menu"` or `"none"`; `workflow` and `security` on every
wireframe row; every wireframe reachable from HOME in the navigation map; that a mind map, a
workflow flowchart, a wireframe and an entity map all exist (so a near-empty folder cannot pass);
and the Plain-English Summary as the last heading of `index.md`. It prints a JUDGED list for what
it cannot check.

When the gate first ran on a real pack (2026-09-05), it scored 38 pass and 1 fail after a
second-model review fixed seven parser gaps. The fail was real: two screens could not be reached
from home.

**The pack is done when:**

- Every workflow the client mentioned has a current-state flowchart with R/W/P/U tagging and at
  least one UNKNOWN, or an explicit "no unknowns" line.
- Every proposed screen has a rendered screen, a wireframe, a row in the map table and a
  security-contract entry.
- The entity map covers every noun that appears on any wireframe (judged).
- The navigation map reaches every screen from a home screen, or each unreached screen is named
  as an open exception with an owner and a date. An unnamed gap is a fail; a named one is a
  decision still due.
- `manifest.json` lists every source with its SHA-256, and `index.html` renders offline and was
  opened in the same turn.
- The client has been asked to "check the pictures against what you remember and mark anything
  wrong" before the build starts, and the review ledger has a line for every view.

---

## Client review ledger (added 2026-09-05)

"Mark anything wrong" needs a record, or a correction is only a memory. Keep
`<pack folder>/review-ledger.md`: one numbered line per view, the reviewer's name, the date, and
`correct` or `wrong: <their words>`. Include the exact `screen_sha256` and
`artboard_sha256` reviewed for each screen. A line for older hashes does not approve newer bytes.
Before recording the proof, compare those hashes with the manifest. Comments left on a shared page count only once copied here.

Before the build, read each corrected item back to the client in their own words and record
their confirmation. This is teach-back: repeating our words back does not count. A view with no
ledger line has not been reviewed. (Sources: the resolve-and-approve trails of design review
tools, the AHRQ teach-back method, aviation read-back.)

---

## Measuring whether the pack works (added 2026-09-05)

Record two numbers per project at closeout, one JSON line per project in
`.devproto/visual-spec-metrics.ndjson`:

```json
{
  "project": "<name>",
  "date": "<YYYY-MM-DD>",
  "screens": 9,
  "change_requests_after_signoff": 2,
  "first_pass_tickets": 14,
  "total_tickets": 17
}
```

1. **Change requests after client sign-off, per screen.** The leading indicator. Requirements
   research puts most rework on late requirement change.
2. **QA first-pass rate** on client-facing tickets (passed review on first submission).

Do not claim the pack "reduced rework" until at least three projects with a pack and three
without are recorded, and report the difference with a confidence interval (the evaluation
standard in the development-protocol reference). As of 2026-09-05 this metric was defined, not
measured. Say so if it is still true.

---

## Report to the user

End with what the pack now shows, the gate's pass and fail counts, the JUDGED items still open,
which views the owner has reviewed, and the next step (usually: the owner marks the rendered
screens, then `/design-stack`).
