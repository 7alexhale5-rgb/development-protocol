---
name: pathway
description: Tells a project which engineering pathway to run next (govern, research, data, security, design, implementation, quality, field, observability, techdebt, release, docs), tracks every pathway against one shared work id, and will not let the outcome close until each owed pathway is proved on a real file or marked not applicable with a reason. Use when someone asks "what should I do next on this project", "what's left", "keep going until it's done", "run the next step", "go", types /pathway followed by a project and go or loop, or wants a measured pilot across several projects. Loop mode runs determine, execute, prove, advance continuously, with autonomy earned by the proof rate.
---

# Pathway: the next best move for a project

The single front door to the pathway router and its itinerary. The user should never have to
remember command flags. You run them. Keep all output in plain English: names of real things, no
jargon, no status icons.

Two tools, both Python 3.9+ standard library, called by full path:

- `PATHWAY` means `python3 <folder containing this SKILL.md>/scripts/pathway.py`. It keeps the
  itinerary in `<project>/.devproto/pathway/<work-id>.json`.
- `DEVPROTO` means `python3 <development-protocol skill folder>/scripts/devproto.py`. It keeps the
  step checklist in `<project>/.devproto/<work-id>.json`.

Use environment-variable references in verifier commands instead of inline credentials. Stored
commands and output are redacted; only their digest retains the original command identity.

Both use the **same work id**. The itinerary says which kinds of engineering work this outcome
owes. The checklist says which steps of the proof loop are done. Every call below takes
`--project <folder>`; add `--json` when you need to read fields.

## Checklist row

This skill satisfies the `pathway` row. `next --id=<work-id>` needs an outcome that already
exists; on a brand-new work id (row 1, nothing started yet) run START first, then ASK, then record
the answer:

```text
PATHWAY --project <repo> start --goal "<goal>" --id=<work-id>   # only if <work-id> has no outcome yet
mkdir -p .devproto/evidence
PATHWAY --project <repo> scope --id=<work-id> > .devproto/evidence/pathway-scope.json
DEVPROTO --project <repo> step --id=<work-id> --step pathway --result pass \
  --evidence .devproto/evidence/pathway-scope.json --verify "python3 -m json.tool .devproto/evidence/pathway-scope.json >/dev/null"
```

The scope output contains only the goal, tier, required pathways and n/a reasons. Proof progress
and next recommendations stay in the separate `next` report. Re-record this row only at intake
or when that scope changes. An ordinary LOG or ASK must not replace its evidence with a
changing progress report.

## Parse the arguments

- If the first token is `pilot` or `pathway-pilot`, the mode is **PILOT**.
- The pathway catalog, in the order the router walks it (foundation first): govern, research,
  data, security, design, implementation, quality, field, observability, techdebt, release, docs.
- **First token = project.** A folder path. If the user gives a bare name, look for a folder with
  that name next to the current repository. If none matches, ask which project, and nothing else.
- **Strip modifiers first.** Pull every `--` token out of the argument string and hold it aside
  before classifying the verb. A modifier is never part of the intent text. Skipping this step is
  what turns `/pathway myapp go --max` into a START that opens an outcome whose goal is literally
  "go --max". Recognised modifiers: `--max` (below) and `--auto=<tier>` (LOOP only). An
  unrecognised `--flag` is an error: say so in one line and stop. Never fall it through to START.
- **Remaining text = intent** (optional). Classify by first match wins:
  - empty: **ASK** (recommend only, read-only).
  - exactly `go`, `run`, `execute` or `proceed` (one reserved verb, nothing after it once modifiers
    are stripped): **EXECUTE**. Run the currently recommended pathway's full execution profile
    once, with the authority of the user pasting it now, then prove, log and hand back the next
    command. This is the keystone verb. Almost every hand-off block tells the user to paste
    `/pathway <project> go`.
  - `done`, `close`, `finish` or `wrap`: **CLOSE**.
  - a pathway name followed by a file path, or "logged/finished `<pathway>`, proof `<path>`":
    **LOG**.
  - `loop` (optionally `--auto=recommend|safe|build`): **LOOP**. Run EXECUTE continuously on one
    shared work id, with autonomy earned by the proof rate.
  - anything else, a goal sentence of two or more words: **START** (open tracked work with that
    goal).

## `--max`: the whole chain at the hardest setting

One flag for "do this at the hardest setting." `--max` is a **rigor modifier only**. It never
changes which verb runs, never starts work on its own, and never grants authority. Strip it, run
the verb the remaining text selects, and raise rigor while doing it.

| You type                          | Verb that runs (unchanged by the flag) | What `--max` adds        |
| --------------------------------- | -------------------------------------- | ------------------------ |
| `/pathway <project> --max`        | ASK (read-only, same as bare)          | Effects 1 and 2 below    |
| `/pathway <project> go --max`     | one EXECUTE turn                       | Effects 1 and 2 below    |
| `/pathway <project> loop --max`   | LOOP                                   | Effects 1 and 2 below    |
| `/pathway <project> <goal> --max` | START                                  | tier `production-secure` |

**Effect 1: arm every pathway the default tier drops.** The default tier is `live`, which does not
seed `security`, `research` or `techdebt`. Under `--max` the outcome must not close without them.
How depends on whether the outcome exists yet:

- **New outcome (START):** pass `--tier production-secure` to `PATHWAY start`.
- **Existing outcome:** add the missing pathways by work id, one call each:
  `PATHWAY cover --id <id> --pathway <security|research|techdebt> --add`. Adding never touches a
  proof already earned. Read `<id>` from `PATHWAY next --json`.
  **Never re-run START to change the tier of an existing outcome.** The default work id includes
  the day's date, so the same goal on a different day produces a different id and silently opens a
  second outcome, orphaning every proof on the first. This was measured on 2026-08-09: one goal
  hashed to two different ids on its creation date and on a later date. `PATHWAY start` now
  returns the existing open outcome when the goal text matches exactly, but a reworded goal still
  slips past that guard.

**Effect 2: escalate the critic set, subject to the send rule.** Normally each pathway's stack
names one second-model critic. Under `--max`, run the `/karpathy verify` dual cascade: two
reviewers from **different model families** read the same diff with the same brief, and a
stronger model adjudicates the union of their findings on the real artifact. If one family is
unavailable (not installed, rate-limited, or blocked for this repo by the team's rules), run the
other AND add a fresh-context reviewer (a subagent, if your agent supports it) with an adversarial
brief, then **say the model-family gap out loud**. A reviewer from the same family as the
adjudicator is one family, not two. Never silently drop a pass. Briefs must require DRY (no
repeated logic), KISS (simplest thing that works), YAGNI (nothing speculative), SOLID, surgical
diffs, plus correctness, edge cases and security.
**This is an external send.** A second-family critic ships the diff to a hosted service, so it
follows the same rule as everything else in LOOP: pause and ask before the first send of a
session, and never send code from a repo the team's rules keep off outside services. `--max` does
not pre-authorize it.

**Effect 3: nothing else changes, including stickiness.** `--max` is **not saved**. Nothing in the
itinerary records that an outcome is running at max, and `production-secure` cannot stand in for
it because ordinary outcomes reach that tier too. So repeat the flag in the hand-off block while a
session is running at max, and know it is a within-session convention, not an enforced one. A
fresh session cannot recover it. The irreversible rails hold unchanged: `/ship`, CLOSE,
production flag flips, external sends and force-push never fire on their own, with or without
this flag.

**Grammar.** Only a `--` token **outside** the goal text counts as a modifier. A `--max` inside a
quoted goal is goal text. Repeating `--max` is harmless. `--max` combines with `--auto=` on LOOP.
PILOT ignores it.

## The hand-off block (required on every output)

Every `/pathway` response (ASK, START, EXECUTE, LOG, CLOSE, and every LOOP turn) **ends with
exactly one fenced code block holding the single command the user pastes next.** Nothing comes
after it. This is the whole point of the skill: the user copies the next move and never composes
it from memory. One block, one command, one paste, never a menu. If you would offer a choice, pick
the safest default, put only that in the block, and name the alternative in prose above it.

**Carry `--max` into the block within the session.** If this session is running at max rigor,
every hand-off block repeats the flag (`/pathway <project> go --max`). Dropping it silently
downgrades the next turn's critic set.

Shape (always this):

> **Next, copy and paste this:**
>
> ```
> /pathway <project> <verb>
> ```
>
> _(one plain-English line: what pasting it will do)_

What goes in the block, by situation:

| Situation                                        | Block holds                                                                             | The one line says                                                                              |
| ------------------------------------------------ | --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Recommendation ready, work tracked, trust = pass | `/pathway <project> go`                                                                 | "runs <pathway> end to end, proves it on <real_artifact>, logs it, hands you the next command" |
| Project not tracked yet (no open outcome)        | `/pathway <project> <your one-line goal>`                                               | "names the outcome and starts tracking; the one time you type a goal, I take it from there"    |
| Trust = fail                                     | `/pathway <project> go`                                                                 | "re-proves the pathway whose evidence changed (that IS the next move), then resumes"           |
| Pilot cohort created                             | `/pathway <first-target-project> go`                                                    | "runs the first assigned pathway from the measured pilot cohort"                               |
| Just finished and logged a pathway               | `/pathway <project> go`, or `/pathway <project> done` if every pathway is proved or n/a | "starts the next pathway" or "closes the outcome"                                              |
| Close blocked                                    | the one fix command                                                                     | "clears <the one blocker> so the outcome can close"                                            |

## What the router returns

`PATHWAY next --id <id> --json` gives you everything a turn needs. Read it; do not re-derive it.

- `coverage.line`: "3 of 7 pathways proved; remaining: security, observability, docs." This is the
  spine. The recommendation is the next step on it.
- `recommended_pathway` and `why`.
- `card`: `skill` (the primary skill), `execution_stack` (primary skill, supporting skills, critic),
  `execution_tools`, `one_percent_move` (the smallest move that makes real progress),
  `verifier_good` (what "done" looks like), `real_artifact` (the file that proves it), and
  `auto_eligible`.
- `trust`: `fail` when a proved pathway's evidence file changed or vanished after its proof. That
  pathway reopens and becomes the recommendation until it is proved again.
- `confidence`: `high` only when the development-protocol checklist for the same work id exists
  and has no blocked rows.
- `proof_rate`, `suggested_autonomy_tier` and `autonomy_rationale` (see LOOP).

## ASK: "what should I do next?"

1. Run `PATHWAY --project <repo> next --json`. Omit `--id` only when no outcome is selected yet.
   With one open outcome the router picks it. With several it lists them and you ask which. Once
   you know the id, pin every later call to it.
2. Tell the user, in plain English:
   - **Coverage first**, from `coverage.line`.
   - **The next move**: `recommended_pathway` plus `card.one_percent_move`.
   - **Why**: `why`.
   - **What done looks like**: `card.verifier_good` and the real artifact (`card.real_artifact`).
   - **The skill to run**: `card.skill`.
   - **Where the evidence came from**: the itinerary file and, if present, the checklist file. If
     the project has no outcome yet, say so plainly; the one good move is to start it.
3. Record the `pathway` row only if it is missing or its stable scope has changed.
   Routine progress does not require re-recording intake evidence.
4. End with the hand-off block: `/pathway <project> go` when work is tracked, or
   `/pathway <project> <your goal>` when it is not. That single line is the user's whole next
   action. Do not also list the LOG or CLOSE syntax; `go` and the next hand-off block carry it.
5. Change nothing else in ASK mode.

## EXECUTE: `go` (do the recommended thing now, full authority, no deviation)

The user pasted `/pathway <project> go`. Their paste **is** the authority for this one step. They
are present and explicitly triggering it, so run the recommended pathway now. Do not re-recommend.
Do not present a menu.

1. **Determine.** `PATHWAY next --id <id> --json`. On a fresh invocation, the first result selects
   the work id; pin every later call to it. Read `recommended_pathway`, the `card`, `trust`,
   `confidence`. `go` re-derives the recommendation here, so it works the same from a fresh
   session with no memory of this one. If there is no open outcome, there is nothing to execute:
   emit the START hand-off block and stop.
2. **Trust gate.** If `trust` is `fail`, the real next move is to re-prove the stale pathway (the
   router already recommends it). Find out why its evidence changed before you re-prove it.
3. **Honor the locked plan. No deviation.** If an approved plan or spec for this work already
   exists on disk (for example a `.devproto/evidence/plan.md` or a spec file the user approved),
   resume at implementation. Do NOT re-plan. Re-planning already-approved work is the deviation
   this verb forbids.
4. **Execute the profile.** Walk the card's `execution_stack` in order (primary skill, supporting
   skills, second-model critic) with its `execution_tools`. Record each checklist row the stack's
   skills satisfy as you go, so a fake "done" has nowhere to hide.
5. **Irreversible rails still hold.** `/ship`, CLOSE, production flag flips, external sends and
   force-push NEVER fire on their own under `go`. Pause and ask for those, then continue.
6. **Prove and log.** When the work is genuinely done, LOG the real artifact against the work id.
   No artifact, no log, no advance.
7. **Advance and report coverage.** Re-run Determine and emit the next hand-off block. Lead the
   turn with `coverage.line`. When `coverage.open` is empty, the next move is
   `/pathway <project> done`.

## START: "begin tracking this goal"

1. Resolve the project folder.
2. **Pick the "done" tier**, meaning how finished this outcome must be. The tier sizes the
   **itinerary**: the pathways that MUST be covered before the outcome can close.
   - **demoable**: runs end to end and you can show it (govern, implementation, quality).
   - **live**: real users touch it (adds data, observability, release, docs). _Default._
   - **production-secure**: untrusted actors or compliance (adds research, security, techdebt).
     The goal's own words also pull in `design` (UI words), `research` (unknowns) or `data`
     (schema, migration, import, export). The research card suggests focus tags
     (the ones `devproto.py` derives from the goal, or none); confirm them at research-stack's scope
     gate before passing `--focus`, never apply them silently. If the user did not say, infer the tier from the goal and
     state your pick in one line. Do not interrogate.
3. Run:
   ```text
   PATHWAY --project <repo> start --goal "<goal>" --tier <tier>
   DEVPROTO --project <repo> start --goal "<goal>" --id <work-id from the line above>
   ```
   The second line enrolls the same work id in the development-protocol checklist, so the full
   proof loop runs alongside the itinerary.
4. Immediately run ASK with the new id pinned. Show the **seeded itinerary** in plain English:
   "this outcome needs 7 pathways: govern, data, and so on. I walk them in order, and it cannot
   close until each is proved on a real file or marked not applicable with a reason."
5. Tell the user the work id once; every pathway logs against it. End with the hand-off block.

## LOG: "I finished a pathway, here's the proof"

1. Get the work id: `PATHWAY next --json` and read `work_id`. Once known, keep passing it so a newer
   outcome cannot replace it. If there is no open outcome, switch to START first (ask for the goal
   if none was given).
2. Proof needs BOTH: a **real file that exists** AND a verifier command that exits 0. A person
   saying "it's done" is attestation only; it never proves a pathway by itself. Never invent
   either. If the user gave no artifact or verifier, ask for it.
3. Write the evidence first, then run:
   ```text
   PATHWAY --project <repo> log --id=<work-id> --pathway <pathway> \
     --evidence <file> --verify "<command that re-checks the file and only reads it>"
   ```
   The router fingerprints the evidence file. A verifier that exits non-zero, or one that rewrites
   the evidence, records the pathway as blocked with the reason.
4. Re-run ASK so the user sees the next best pathway.

## CLOSE: "done with this outcome"

1. Get the work id (as in LOG).
2. Run `PATHWAY --project <repo> close --id=<work-id>`. Closed itineraries keep
   content-addressed evidence copies under `.devproto/pathway/completed/`; later tasks
   may reuse live report paths without reopening history. Missing or changed archived
   proof remains explicitly unverified, and restoration recovers it. A read never
   reseals history using a new task's live report. To change an old outcome, explicitly
   run `PATHWAY --project <repo> reopen --id=<work-id> --reason "<approved new scope>"`
   and reopen its matching checklist when applicable; original history remains saved.
   Each executed pathway records the observed source candidate. Closing cannot relabel
   old proof after code changes, and checklist closeout requires the same candidate.
   A progressed open itinerary created before checklist intake can use the same explicit
   `reopen --reason` command to reset and enroll fresh proof. Its prior rows remain saved
   as incomplete history, without inventing a completion receipt. Association and generation
   checks run before this reset changes either record. Keep proof files under `.devproto`
   so writing new evidence does not change the source candidate being verified.
   Prefer a new work ID for an independent outcome.
3. If it closed, inspect `DEVPROTO --project <repo> status --id=<work-id> --json`.
   For a completed checklist, run `DEVPROTO --project <repo> check --id=<work-id>
--historical`; this checks retained past proof and cannot certify a new candidate.
   For an active checklist, run ordinary `DEVPROTO --project <repo> check --id=<work-id>`.
   Report both answers. Missing, invalid, or unknown historical proof remains a gap;
   itinerary closure alone does not clear the checklist. Do not reopen completed work
   merely to make the ordinary current-candidate command pass.
4. If it did not close, tell the user in plain English exactly what blocks it and the one thing to
   fix. **The coverage gate is usually the blocker.** `coverage.open` lists pathways still owed
   proof. For each, either run it (`/pathway <project> go`) or, if it genuinely does not apply,
   mark it:
   `PATHWAY cover --id=<work-id> --pathway <name> --na --reason "<why it does not apply>"`.
   Nothing closes until every itinerary pathway is proved with an artifact or n/a with a reason.
   That is the guarantee that no necessary pathway was skipped.

## LOOP: "keep making the next best move until this outcome is done"

The all-inclusive mode: the Karpathy method (spec, verifier, environment) run continuously. One
project, one shared work id. The user supplies the goal and the go-ahead; the loop does determine,
execute, prove, advance, turn after turn, until the outcome closes. ASK, START, LOG and CLOSE
become the loop's internal states, and the user stops typing verbs.

On EXECUTE the loop runs the whole stack for the chosen pathway: its full `execution_stack` and
`execution_tools` profile, wrapped in `/karpathy verify`, not a single command.

**Autonomy is earned by the proof rate, never assumed.** Read `suggested_autonomy_tier` and
`autonomy_rationale` from `PATHWAY next` and apply them. Never re-derive the rule by hand; the
router recomputes it on every call, so it is never stale.

- **Tier 1, Recommend** (default; returned whenever the proof rate is under 0.50, OR trust is not
  `pass`, OR confidence is not `high`): stage the exact `card.skill` command, then STOP for the
  user's go.
- **Tier 2, Execute-safe** (only when all three pass, fresh this turn): run on your own only the
  local, reversible pathways `research, govern, data, security, quality, observability, docs`
  (the card's `auto_eligible` is true for these). Pause mid-pathway the instant a step would touch
  a real database or production surface, send code or data to an outside service, or commit or
  deploy. Those need an explicit grant.
- **Tier 3, Execute-build**: only on an explicit grant from the user for this session. Also runs
  `implementation, techdebt, design` on its own.

`--auto=recommend|safe|build` can only lower the tier the router suggests, never raise it. A user
who wants Tier 3 says so in words.

**Never on its own, at any tier:** `/ship`, CLOSE, production flag flips, external sends. Pause
and ask.

**One iteration:**

1. **Determine.** `PATHWAY next --id <id> --json`. Omit the id only on the first selection; pin it
   for the rest of the loop. Read `recommended_pathway`, the `card`, `confidence`,
   `suggested_autonomy_tier` and its rationale. The router already gated the tier; apply it, do
   not recompute it. If there is no open outcome, run START first (ask for the goal if none was
   given).
2. **Trust gate.** If `trust` is `fail`, the move becomes "re-prove the stale pathway," not new
   work. Surface why its evidence changed. If you cannot explain the change, stop.
3. **Execute.** Run the pathway's best-execution profile, not just one skill: walk the card's
   `execution_stack` (primary skill, supporting skills, second-model critic) and bring in its
   `execution_tools` (for example browser automation for design, a scratch database for data, web
   search for research). That is the `/karpathy verify` discipline applied every turn. By tier:
   stage the profile for the user's go (Tier 1), or run it (Tier 2 or 3 when eligible).
4. **Prove.** When the work is really done, LOG the real artifact against the shared work id. No
   artifact, no advance.
5. **Advance and measure.** Re-run Determine, which recomputes the proof rate. Report the turn in
   plain English: pick, why, what ran, proof, new proof rate.
6. **Loop or close.** Repeat. CLOSE when every pathway is proved or n/a.

**Stop the loop when:** the outcome closes; trust fails and you cannot explain why; the next
pathway needs a person and the user is not present to confirm; no pathway gains proof for three
turns (anti-thrash); or a token or time budget is hit. If running unattended and your agent
supports scheduled wake-ups, use them to self-pace; otherwise drive it turn by turn with the user.
Always name the current tier in the first line of each turn.

## PILOT: "test the full agent dev-team loop on real projects"

Use this before widening autonomy across several projects. It is a measured rehearsal, not a build
pass.

1. Parse projects as a comma-separated list after `pilot` or `pathway-pilot`.
2. Use the remaining text as the pilot goal. If the goal is missing, ask for it. Do not invent one.
3. Run:
   ```text
   PATHWAY --project <where the report should live> pilot \
     --projects <folder-a,folder-b> --goal "<pilot goal>" --json
   ```
4. Report the baseline proof rate, the report file path, and each assignment's project, work id,
   recommended pathway, lead role, critic role, proof gate and review gate. A project with several
   open outcomes comes back as an error row; resolve it with `next --id` before the pilot runs it.
5. The command may open a missing outcome (with the pilot goal) and write the report file. It must
   not touch code, deploy, send, close work, or mark proof or n/a.
6. End with one hand-off block for the safest first target, which the report names
   (`first_target`: the project with failed trust or the lowest proof rate):
   `/pathway <that project> go`.

## Rules

- One shared work id per outcome. Every pathway logs against it, and so does the checklist. Never
  start a second id for the same goal.
- **Coverage is the spine.** START seeds an itinerary sized by the "done" tier; the router walks it
  foundation first; the outcome **cannot close** until every itinerary pathway is proved with an
  artifact or marked `na` with a reason. The router enforces this in code, not by memory, so a
  pathway is never silently skipped or lost between turns. Adding a pathway never clobbers earned
  proof.
- **What counts as proof:** an artifact on disk, a check that was actually executed against it, and
  the result read back. No artifact, no pass.
- `/pathway` itself writes only under `.devproto/`. It never edits code; the skills it runs do.
- Plain English in chat. The command mechanics stay under the hood.
- The router is read-only advice. START, LOG, cover and CLOSE are the only state changes, and only
  on explicit intent. (`next` does save one thing: it reopens a pathway whose evidence changed.)
- LOOP autonomy is earned by the proof rate. Default to Tier 1 and stay there unless the router
  returns `execute-safe`. The router computes that field (proof rate at least 0.50, trust pass,
  confidence high) fresh on every call; never re-derive it by hand.
- LOOP never runs `/ship`, CLOSE, production flag flips or external sends on its own, at any tier.
  Pause and ask.
- One project per loop, one shared work id.
- For trials across several projects, run PILOT first. It assigns lead, critic, proof gate and
  review gate per project, snapshots the baseline proof rate, and writes the report without
  touching code.

### Release and final checklist closure

The canonical catalog keeps its recorded order. Execution defers release until
all other owed pathways, including documentation, are proved or legitimately not
applicable. The release profile commits and ships; it does not run closeout.
After recording release proof, close the fully proved itinerary with the shared
work id, then run `/compound` and `/closeout-stack` for that checklist. Before closing,
renew all stale proof against the final candidate after documentation and the final commit.
The router marks changed-candidate rows stale, excludes them from earned autonomy, and
recommends `renew-proof` through read-only acceptance checks. Validate those checks before
executing them; use a fresh explicit command if a retained command was redacted. Keep proof
artifacts under `.devproto`. Do not repeat implementation, migration, commit, or shipment
profiles merely to renew proof. Record each executed check again and close only when the
router reports no stale or open pathways. Never seal
the checklist before later documentation or another candidate-changing pathway.
