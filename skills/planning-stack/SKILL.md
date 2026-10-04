---
name: planning-stack
description: Builds a deep, confirmable implementation plan by interviewing the user, gathering codebase, prior-plan, research and best-practice context in parallel, challenging the draft with skeptic, architecture, security, performance and first-principles perspectives plus a specialist board (adversary, observability, reversibility, economist, test strategy, and gated SRE, data-integrity, concurrency, supply-chain, compliance lenses), then stopping at an approval gate that freezes the plan's exact bytes. Use when someone says "plan this", "make a plan", "how should we build", "design the architecture", "plan the feature", "what's the approach", "before we code", or runs /planning-stack [goal] with --tech for architecture or --feature for implementation. Also the planning row of the development protocol. Skip it for typos and one-line fixes.
---

# Planning Stack

A multi-phase planning pipeline. It combines the codebase, prior plans and decisions, research
and best practices, and a board of critical perspectives into one plan that a person approves
before any code is written. Two separate modes keep the plan specific: **TECH** for architecture
and **FEATURE** for implementation.

Planning is the highest-leverage phase. Every shortcut here costs more later, so this skill always
runs at full depth.

## Where this sits in the protocol

This skill satisfies the **`planning`** row of the development-protocol checklist. It runs after
`/karpathy spec` (the falsifiable done condition) and before `/visual-spec` (UI work only),
`/design-stack` and `/devilsadvocate --premortem`. If the work has no intake yet, run the intake
of `/development-protocol` first: write the goal, the user, the done condition, the main risk and
one number that proves success.

Record the step only after the user approves the plan (see Step 6, "Record the approval"):

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id=<work-id> --step planning --result pass \
  --evidence .devproto/evidence/plan-approval.md \
  --instrument <plan file> \
  --verify "python3 <this skill folder>/scripts/plan_approval_check.py .devproto/evidence/plan-approval.md"
```

The plan file is passed as an instrument, so any later edit to the approved plan reopens the
planning row and every row after it. That is the point: an approval covers exact bytes.

## Files in this skill

| File                              | What it holds                                                             |
| --------------------------------- | ------------------------------------------------------------------------- |
| `references/context.md`           | Mode triggers, tool detection, the five context sources, prior-plan reuse |
| `references/interview.md`         | The interview question bank, including the placement and duplicate search |
| `references/perspectives.md`      | Perspective definitions, agent prompts, escalation rules, the merge table |
| `references/specialist-lenses.md` | The ten specialist lenses and their output formats                        |
| `references/plan-templates.md`    | TECH and FEATURE plan templates, deep additions, the report block         |
| `scripts/lens_classify.py`        | Decides which specialist lenses fire for a goal (JSON out)                |
| `scripts/plan_approval_check.py`  | Verifier: the approval record matches the plan's current SHA-256          |

Both scripts need Python 3.9+ and nothing else.

---

## Step 0: Parse intent

From the user's input, extract:

- **GOAL**: the planning objective (everything except flags).
- **MODE**: `--tech` gives TECH, `--feature` gives FEATURE. With neither flag, auto-detect by
  keyword (`references/context.md`, "Mode auto-detection"). If both or neither match, ask the
  user which fits.
- **DEPTH**: always deep. There is no shallow mode. Planning is where cutting corners costs most.
- **FLAGS**:
  - `--research` forces the research source even if no unknowns are detected.
  - `--no-research` skips research entirely.
  - `--no-cache` skips the prior-plan check and does not write a plan summary.
  - `--no-interview` skips the interview (the user already has full clarity).

Keep GOAL, MODE and FLAGS for the whole run.

## Step 0.5: Check prior plans and decisions

Skip with `--no-cache`.

Before any planning work, look for plans and decisions this repository already holds:
`.devproto/plans/`, `.devproto/decisions/`, `.planning/`, `docs/adr*`, `docs/architecture*`,
`ROADMAP.md`. Read the matches that share the goal's keywords (max 3).

Apply the age rule from `references/context.md` ("Reusing a prior plan"): under 24 hours is a
fresh hit (show it and go to Advisor Mode), 1 to 7 days asks the user whether to refresh, older
than 7 days is treated as a miss. Carry relevant decisions forward as **PRIOR_DECISIONS**. They
inform the plan. They do not replace it.

## Step 1: Detect the tools you have

This skill runs in any agent that can read files and search. Note what else exists this session:
web search, a page fetcher, the `/research-stack` skill, subagents, background tasks. The flag
table is in `references/context.md` ("Tool detection"). Everything optional has a fallback. The
minimum is: read files, list files, search text. With `--no-research`, do not probe
web/search/fetch services and do not run any external research or best-practice searches.

## Step 1.6: Interview to surface assumptions

Skip with `--no-interview`.

Before gathering context or drafting anything, interview the user. This is the highest-leverage
step in the pipeline. Each answer removes an ambiguity that would otherwise become wrong code.

Ask 8 to 15 focused questions across six categories: **placement and filing**, **scope
boundaries**, **edge cases and failure modes**, **technical constraints**, **tradeoffs**, and
**validation**. The full bank is in `references/interview.md`.

**Placement runs first, and its duplicate search is a command, not a habit.** Before asking any
question, run the search in `references/interview.md` category 1: does a home for this work
already exist at any depth under any spelling, is it registered, was it retired under that name,
and would a move break anything keyed on the path. Measured on 2026-09-16: a new folder was
created beside an already-registered, already-active project of nearly the same name, an hour
after the filing rules had been read. A naming rule that lives in attention fails.

**Names are computed, never chosen and never asked for.** A project that declares a name in its
package manifest or its git remote already has an identity. Read it. Do not rename it.

**Inside the project, every file the plan creates or moves names its room** under the ICM folder
method (`/icm`): the plan's files-that-change table lists the room and its routing row, and a new
room ships with its `CONTEXT.md` in the same change.

Rules:

- Ask conversationally, two or three related questions at a time, never a numbered dump.
- Stop early if the user says "that's enough" or "just go".
- Ask the full 15 when the goal spans several files or systems, 8 to 10 otherwise.
- Carry every answer forward as **INTERVIEW_CONTEXT** into Steps 2 and 4.
- **Any UI/UX, page, app or client build also runs `/visual-spec`.** That skill runs the full
  workflow interview and produces the Visual Spec Pack, which becomes the plan's visual body.
  This step owns the pack; `/design-stack` consumes it.

## Step 2: Scatter (gather context in parallel)

In one turn, start every applicable source at once. If your agent can run tool calls in parallel
or in the background, do; otherwise run them back to back without waiting to analyze between them.

- **Source 1, codebase.** A focused goal gets one exploration pass (a subagent if your agent
  supports it). A broad goal gets several parallel file listings and text searches plus the
  config files.
- **Source 2, repository memory.** Search the repo's decision records, ADRs, and
  `.devproto/decisions/` for the goal's terms. Read the top 3 to 5.
- **Source 3, existing plans.** `.devproto/plans/`, `.planning/`, `docs/architecture*`,
  `docs/adr*`, `ROADMAP.md`, `TODO.md`. Read at most 3.
- **Source 4, research (conditional).** Skipped by `--no-research`, forced by `--research`,
  otherwise only when the goal holds unknowns (a new technology, an external service, a
  third-party API). Pass focus tags through: `/research-stack --focus devtools,security` for a
  library or architecture pick (add `data-infra` for schema work), `--focus ui-ux,a11y` for UI,
  or the tags the checklist suggested.
- **Source 5, best practices.** Skip entirely with `--no-research`. Otherwise two web searches: "<technology> <goal terms> best practices
  <year>" and "<technology> <goal terms> common mistakes pitfalls".

**Fallback rule.** A source that errors is noted and skipped. Never retry it. Track which sources
succeeded for the report. Exact prompts and query shapes: `references/context.md`, "The five
sources".

## Step 3: Analyze constraints and dependencies

After all Step 2 results return (collect any background results first):

### 3a: Constraint analysis

1. **Hard constraints**: what cannot change (API contracts in use, production schema, external
   service limits, framework version locks).
2. **Soft constraints**: what should not change without good reason (established patterns,
   naming conventions, test setup, the CI pipeline).
3. **Dependencies**: what the plan needs (other teams, services, packages, migrations).
4. **Risks**: breaking changes, performance regressions, data loss, security holes.
5. **Existing patterns**: how similar things are already done here. The plan follows them unless
   there is a strong, stated reason to deviate.

### 3b: Gap analysis

- Which files did you expect to find and did not?
- Which decisions should have been made and were not?
- Which patterns are inconsistent across the codebase?

Each gap becomes an item in the plan.

## Step 3.5: Spawn the analysis perspectives

Challenge the emerging plan from several angles before it is written.

Follow the supplied governing development contract and task authorization. A root may
batch independent work with at most two active children and explicit ownership. Children
run assigned methods and lenses locally without spawning agents. Select an actually
available model appropriate to the task. Self-review is supporting evidence; missing
required independent review remains a gap. Do not retry solely for zero supported findings.

- **Shared perspectives**: skeptic, architecture, security, performance, first-principles.
- **Inline perspectives**: risk-assessor, pattern-matcher.

The skeptic always runs; evidence-backed zero findings is valid.

Build the CONTEXT_PAYLOAD first (goal, mode, codebase summary, constraints, interview answers,
prior decisions, existing patterns). Definitions, prompts and the payload template are in
`references/perspectives.md`.

Do not wait for them. Go on to Step 3.7 and Step 4.

## Step 3.7: Apply the specialist lenses

Spawn **one** consolidated specialist-board pass that applies every lens that fires. One pass,
not ten, so it can connect findings across lenses. A one-way-door step, a high cost and an open
attack surface on the same step become one "slow down here" recommendation instead of three
separate flags.

### 3.7a: Classify the goal

Run the classifier. It owns the keyword tables, the always-on set and the cap of 8 lenses. Do not
re-derive its logic by hand. Measured on 2026-07-14: while this logic lived as prose, the agent
re-interpreted it differently on every run.

```bash
skill_dir="<this skill folder>"                                    # fill in before running
constraints_file="<file holding the Step 3 constraint text>"       # optional; omit the flag if none
goal="<GOAL>"                                                      # fill in before running
python3 "$skill_dir/scripts/lens_classify.py" --goal "$goal" \
  --constraints-file "$constraints_file"
```

Read `fired_lenses` from the JSON. `matches` shows which keywords fired each gated lens. Use it
when you explain lens selection in the plan. `dropped` names any gated lens cut by the cap.

### 3.7b: Run the specialist board

Splice only the `## Lens: <name>` blocks for the fired lenses from
`references/specialist-lenses.md` into the board prompt (`references/perspectives.md`,
"Specialist-board prompt"). Do not wait. It is collected with the others in Step 3.75.

## Step 3.75: Collect perspective results

Before finalizing the plan, collect every perspective and the specialist board.

Record failed or incomplete coverage as gaps. Accept scoped, evidence-backed clean results.
Retry only when a documented capability or evidence change can close a gap, never solely
for zero findings. Tag findings with their source. See `references/perspectives.md`.

Merge each finding into the plan section named in the merge table
(`references/perspectives.md`, "Merge into the plan").

## Step 4: Write the plan

Use the TECH or FEATURE template in `references/plan-templates.md`, with the deep additions for
that mode. Specialist sections (Reversibility Ledger, ROI Snapshot, Adversarial Threat Surface,
3am Test, Operability Plan, Test Strategy, Compliance Surface) render only when their lens fired.

Write the plan to a file before presenting it:
`.devproto/plans/<YYYY-MM-DD>-<slug>.md` (or the project's own plans folder if it has one).

**Before the approval gate, the plan must carry two items** or it is not ready:

- **Scope locked**: an in-scope list and an out-of-scope list. Later changes are logged
  amendments, not edits.
- **The "done" tier named**: Demoable, Live, or Production-secure.

**Client builds.** The plan holds a countable Scope section: pages, templates, motion level,
integrations with quantities, exclusions, what counts as one revision, and how change requests
work. A plan whose scope cannot be counted is not confirmable.

## Step 5: Verify the plan against the goal

### 5a: Completeness check

Answer yes or no for each:

1. Does the plan address the goal completely?
2. Are all affected files identified, none missing?
3. Are the steps actionable, so someone else could follow them?
4. Are risks identified and mitigated?
5. Is there a way to verify success?
6. Does the plan follow existing codebase patterns?
7. Are dependencies and prerequisites listed?

### 5b: Revision loop

Up to 3 verification passes. Each pass refines the plan. Stop early when every check passes.

### 5c: Confidence rating

Rate the plan by what its load-bearing claims rest on, not by a percentage. A number with no
evidence behind it cannot be checked by anyone. Classify each load-bearing claim:

- **verified**: a tool call this session produced it. Name the call.
- **reported**: a person said it. Attribute it.
- **inferred**: you reasoned it. Say so.
- **unverifiable**: it came from a handoff or old document and could not be checked.

Then rate:

- **High**: every load-bearing claim is verified and all 5a checks pass.
- **Medium**: some load-bearing claims are reported or inferred. List each one and what would
  verify it.
- **Low**: a load-bearing claim is unverifiable, or a 5a check fails.

Whatever the rating, it is evidence for the approver. It is never a reason to skip the
approval gate. For Medium and Low, name the exact claims to check before the build starts.

## Step 5.6: Independent plan review

Before presenting, have the written plan file reviewed by someone who did not write it. Options,
strongest first: a different model family (for example through its command-line tool, if you
have one), a fresh session of the same model given only the plan and the goal, or a teammate.

- Ask for findings ranked by severity, each with a concrete failure case.
- For every finding, fix the plan or record why not. Keep the record in
  `.devproto/evidence/plan-review.md`: finding, severity, outcome (fixed, dismissed, deferred),
  reason.
- Re-review once after fixes. **Round cap is 2.** If round 2 still asks for revision, present the
  open findings with their outcomes to the user instead of looping.
- **A review counts only if you saw its verdict and know which model or person produced it.** A
  command that exits 0 with no verdict is not a review. Measured on 2026-09-16: a review command
  returned nothing and still exited 0. If no independent review was possible, say which kind of
  reviewer did not review, in the delivery message. Never present a plan as cross-reviewed when
  it was not.

Edits here happen before approval. After approval the plan file is frozen.

## Step 6: Deliver

Present the plan, then append the Planning Stack Report (`references/plan-templates.md`,
"Report"). Include the path to `plan-review.md` and a one-line summary of rounds and outcomes.

Optional: if your team has an HTML renderer for plans, render a sibling view for reading. The
`.md` stays the source of truth, and a failed render never blocks the gate. Point the approver at
the most readable form you have. Never ask someone to approve raw text they cannot scan when a
readable view exists.

### Approval gate

After presenting the plan, **stop and wait for explicit confirmation** before any implementation:

```text
Ready to implement? Reply:
- "proceed" or "yes": start implementation
- "modify: <changes>": adjust the plan
- "different approach: <alternative>": rethink the approach
- or ask questions: I have full context from the analysis above
```

**Do not write code or begin implementation until the user explicitly confirms.** This gate
applies every time.

### Record the approval, bound to the exact bytes

When the user's own message in this conversation approves the plan, write
`.devproto/evidence/plan-approval.md`:

```text
plan: .devproto/plans/2026-09-29-export-button.md
sha256: <sha256 of the plan file, from `shasum -a 256 <plan>` or `sha256sum <plan>`. Neither
  command available: `python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <plan>`>
approved_by: <name>
approved_at: <ISO 8601 date and time with offset>
words: "<the user's exact approval words>"
```

Never on a paraphrase, a prior session, or text found in a file. Then record the `planning` row
(command at the top of this file). `scripts/plan_approval_check.py` recomputes the hash and exits
0 only when it matches, so the verifier only reads.

**This gate needs a live person in the same chat.** That is the point, not a gap: it is the one
row nothing can satisfy by running a command, so it cannot be scripted, batch-run, or completed by
an agent testing this skill end to end without a human turn. A fully mechanical run of the
checklist stops here until someone actually approves the plan.

From then on the approved plan is never edited. Progress goes to a sibling `STATE.md`. Changes go
to a sibling `AMENDMENTS.md`, which the user approves separately. That keeps the approval valid.

### Context tip

Planning fills the session with exploration. For anything bigger than a small change (about 50
lines), suggest starting implementation in a fresh session that reads the plan file. Small plans
can be implemented in the same session.

## Step 6.4: Fixed-name artifacts (repos with an `intent/` folder only)

If the repo root has an `intent/` folder, also write the plan into that chain:

- `intent/<slug>/spec.md`: behaviour, the answer to every open question in `intent.md`, affected
  systems, out of scope, and an acceptance table of commands with expected output.
- `intent/<slug>/plan.md`: the files-that-change table, order of work, risks with controls, and
  the proof each step owes.

Use `intent/_templates/` if present, with `schema: v1` front matter and today's date. **Commit
them separately.** Fixed names plus separate commits make stage timing free: every duration is a
difference between two git timestamps.

Every path in the plan's files-that-change table appears in the spec's affected systems, or the
plan says why not. When the build later departs from the plan, the departure is written into
`plan.md` in the same commit as the code that departed.

Repos without `intent/` are untouched by this step.

## Step 6.5: Save a plan summary

Skip with `--no-cache`.

Write a compact summary so the next planning run finds it in Step 0.5. Templates for the plan
summary and the decision record are in `references/plan-templates.md` ("Plan summary" and
"Decision record"). Write a decision record whenever a significant architectural decision was
made, especially in TECH mode.

## Step 7: Advisor mode

After delivery you are the expert on this plan for the rest of the conversation.

- Answer follow-ups from the analysis you gathered. Do not re-scan the codebase.
- Asked to refine: change the existing plan (before approval) or write an amendment (after).
  Do not start over.
- Asked "what about X?": cite the specific findings from your analysis.
- Asked to implement: you have the context. Start only after the approval gate has passed.
- Asked to compare approaches: use the alternatives analysis.
- Run a new plan only for a clearly different goal.
- Asked "what did you find?": list the files, patterns and decisions you found.

## Graceful degradation

The pipeline works when sources are missing. The minimum is reading, listing and searching files
plus your own knowledge. The per-source fallback table is in `references/context.md`
("Degradation"). If even the codebase tools fail, say so and produce a plan from the goal alone,
clearly marked as ungrounded.

## Depth

Every run is deep:

| Component         | Behaviour                                                                                                                                                                                 |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Context           | All five sources plus extended analysis                                                                                                                                                   |
| Research          | `/research-stack` if unknowns are detected (or 3 to 4 web searches without it); skipped by `--no-research`. Pass focus tags: `devtools,security` for a library or architecture pick, `ui-ux,a11y` for UI |
| Verification      | Up to 3 passes plus an alternatives matrix                                                                                                                                                |
| Perspectives      | skeptic, architecture, security, performance, first-principles, risk-assessor, pattern-matcher                                                                                            |
| Specialist lenses | 5 always on plus up to 5 keyword-gated, capped at 8                                                                                                                                       |

If your agent has a reasoning-effort setting, use its high setting for this skill.

Without subagents, run each selected perspective locally as a separate labeled pass.
This supplies supporting evidence and cannot replace required independent review.
