---
name: brainstorm-stack
description: Runs an adaptive questioning session before planning, to pin the goal, surface the decisions only the user can make, and cut rework. Scans the repo and past notes first, has a skeptic challenge the framing, then asks open questions area by area and writes a context document that /planning-stack picks up. Use before planning any complex feature, architecture change or unclear request, or when the user says "brainstorm", "let's discuss", "gather context", "before we plan", "help me think this through", "what should we decide first", or "interview me". Flags --quick, --deep and --for-plan.
---

# Brainstorm Stack: Adaptive Pre-Planning Questioning

You are running an adaptive questioning session. The goal is to gather context, surface the
decisions that matter, and reduce rework before any plan exists. This replaces an open-ended
"let's discuss" phase with a structured, conversational exploration that ends in a concrete
context document.

## Checklist row

This skill satisfies the `brainstorm` row of the development protocol checklist. When Step 5 has
written the context document, record it:

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id <work-id> --step brainstorm --result pass \
  --evidence .devproto/evidence/brainstorm.md \
  --verify "python3 <development-protocol skill folder>/scripts/_shared.py --evidence .devproto/evidence/brainstorm.md --section 'Key Decisions' --section 'Project Boundary'"
```

The verifier only reads the file and rejects empty sections. Review the decisions against the
user's goal before recording a pass; nonempty text alone does not prove useful decisions.

---

## Step 1: Parse Intent

From the user's input, extract:

- **TOPIC**: the subject to brainstorm (everything except flags).
- **DEPTH**: how deep to question:
  - `--quick`: 3 to 5 questions, a fast pass.
  - default: 8 to 12 questions, standard exploration.
  - `--deep`: 15 to 20 questions, plus suggestions for research.
- **FLAGS**:
  - `--for-plan`: shape the output as input for `/planning-stack`.
- If there is no TOPIC, ask: "What are we brainstorming? Give me the problem or feature in a
  sentence."

Keep TOPIC, DEPTH and FLAGS for the whole session.

---

## Step 2: Context Scan (run in parallel)

Run all of these at once if your agent can make parallel tool calls. Otherwise run them one after
another, quickly.

### 2a: Codebase scan

Search the current repository for files and text that match TOPIC keywords:

- File names: source and docs files (`**/*.{ts,tsx,js,jsx,py,go,rs,md}`) filtered by TOPIC words.
- Content: search for TOPIC keywords to find existing code, TODO comments, and prior art.

### 2b: Past notes and decisions

Look for earlier thinking on the same topic inside the repo:

- `.devproto/evidence/` (earlier brainstorms, briefs, research, plans).
- `.planning/`, `docs/`, `docs/adr/` or `decisions/` (architecture decision records), `ROADMAP.md`.
- Recent history: `git log --oneline -30 -- <paths that matched in 2a>` and
  `git log --all --oneline --grep "<keyword>"`.
- If your team keeps notes somewhere else (a wiki, a notes folder), search it too.

Read the full text of the most relevant hits, at most three.

### 2c: Planning artifacts

Look for `**/.planning/**/*.md` and `**/ROADMAP.md`. If found, read the two most relevant files.

### 2d: Summarize

When everything is back, give a short summary:

- **Already exists:** what the codebase and notes already have on this topic.
- **Net new:** what looks like new ground.
- **Prior decisions:** any earlier decisions that apply.

If nothing exists, say so: "Clean slate. No existing code or prior decisions on this topic."

---

## Step 3: Gray Area Identification

From TOPIC and the scan, classify the domain or domains:

| Domain     | Signals                                                          |
| ---------- | ---------------------------------------------------------------- |
| **Visual** | UI, UX, frontend, design, layout, component, page, styling       |
| **API**    | backend, endpoint, integration, webhook, REST, GraphQL           |
| **CLI**    | tooling, script, automation, command, pipeline                   |
| **Data**   | database, schema, migration, model, query, storage               |
| **Docs**   | documentation, content, guide, README, spec                      |
| **System** | architecture, infrastructure, DevOps, deployment, CI/CD, scaling |

Write 3 to 6 specific **decision areas** where the user's input matters. They are not generic
categories. They are specific to TOPIC. Example for "add subscription billing":

1. Pricing model (flat, tiered, or usage-based).
2. Checkout flow (embedded, hosted, or custom).
3. Webhook handling and failure recovery.
4. Free tier and trial behavior.
5. Invoice and receipt delivery.

Show the areas and ask: "Which of these do you want to dig into? Pick numbers, or say 'all'."

---

## Step 3.5: Spawn Perspective Scouts

Before deep questioning starts, challenge the direction. This catches scope creep, a problem framed
wrong, and complexity nobody justified, while it is still cheap to change course.

### 3.5a: Pick perspectives by depth

| Depth     | Perspectives                             |
| --------- | ---------------------------------------- |
| `--quick` | skeptic only                             |
| default   | skeptic                                  |
| `--deep`  | skeptic, scope-checker, first-principles |

The **skeptic always fires.** It asks whether we are solving the right problem and whether the
scope is justified. Its full brief is in `references/skeptic.md` in this folder.

### 3.5b: Prepare the context payload

```text
CONTEXT_PAYLOAD:
  - topic: "{TOPIC}"
  - depth: "{quick|default|deep}"
  - domains_identified: "{domains from Step 3}"
  - decision_areas: "{decision areas from Step 3}"
  - existing_context: "{summary from Step 2}"
  - prior_decisions: "{relevant past decisions found}"
```

### 3.5c: Run the perspectives

If your agent supports subagents, spawn each perspective as a background subagent in one parallel
block. A fast, cheap model is enough for these. If your agent has no subagents, run each
perspective yourself as a separate, clearly labeled pass before you ask the first question. Do not
blend them into your own view.

**skeptic** (always):

```text
You are the skeptic reviewing a brainstorm session BEFORE deep questioning begins.
Follow the skeptic brief (references/skeptic.md): focus areas, output format, rules.

## Context
{CONTEXT_PAYLOAD}

## Special focus for brainstorming
- Are we solving the right problem? Or a symptom?
- Is the scope justified, or are we gold-plating?
- Are these decision areas the RIGHT ones, or are we missing the real decisions?
- Is this brainstorm even needed, or is there enough context to plan now?

## Output
Use the Brainstorm Format. Each finding: Title [warn|info], Area, Challenge, Recommendation.
At most 3 findings. Return ONLY the findings as markdown. No preamble, no summary.
Start directly with the first finding.
```

**scope-checker** (`--deep` only):

```text
You are checking whether a brainstorm topic has the right scope.

## Topic
{TOPIC}
## Decision areas identified
{decision_areas}
## Existing context
{existing_context}

## Task
1. Is the topic too broad? Should it be split into several brainstorms?
2. Is the topic too narrow? Are we missing the bigger picture?
3. Are there hidden dependencies or prerequisites that should be brainstormed first?
4. Does the existing code or notes already answer some of these questions?
Return structured findings. No preamble.
```

**first-principles** (`--deep` only):

```text
You are the first-principles analyst reviewing a brainstorm topic BEFORE deep questioning begins.
Follow the first-principles brief (references/first-principles.md): the 5-phase protocol
(decompose, challenge axioms, ground truth, reconstruct, delta), the confabulation self-check,
output format, and severity levels.

## Context
{CONTEXT_PAYLOAD}

## Output
Use the Brainstorm Format. Start with the confabulation self-check, then go directly into findings.
Return ONLY the self-check and findings as markdown. No preamble, no summary.
```

---

## Step 3.75: Collect Perspective Results

Collect every perspective's output before questioning begins.

```text
FOR each perspective result:
  IF result is empty or an error:
    -> Log "{name}: failed, skipping" and say so to the user.
  ELIF result is "No findings." AND the perspective is the skeptic:
    -> This should not happen. The skeptic always returns at least one finding.
       Retry once with a stronger model.
  ELIF the retry also returns "No findings.":
    -> Accept it as clean. Note "{name}: clean (verified 2x)".
  ELIF result has findings:
    -> Weave them into the questioning plan:
       - skeptic says "wrong problem"  -> add a question about the problem definition
       - skeptic says "scope too big"  -> ask scope boundary questions early
       - scope-checker says "split"    -> suggest splitting before you continue
    -> Tag each finding you use: [perspective:{name}]
```

### Adjust the questioning plan

If perspectives raised concerns, tell the user:

> **Perspective check:** The skeptic raised {N} points before we dive in:
> {brief summary of the key challenges}
>
> I'll weave these into the questions. Let's go.

If all came back clean:

> **Perspectives:** Clean. Topic and scope look solid. Let's dig in.

---

## Step 4: Adaptive Questioning Loop

For each selected area, ask 2 to 4 focused questions. Scale by depth:

- `--quick`: 1 to 2 questions per area, 2 to 3 areas at most.
- default: 2 to 3 questions per area.
- `--deep`: 3 to 4 questions per area, and follow tangents.

If your agent has a structured question tool (multiple choice with a free-text option), use it for
questions that have clear options. Use plain open questions for everything else.

### Question design principles

- **Follow the thread.** If an answer reveals something interesting, dig deeper before moving on.
- **Challenge vagueness.** "What does 'simple' mean to you here?" "When you say 'fast', what is the
  target?"
- **Make the abstract concrete.** "Walk me through how a user would actually do this."
- **Surface assumptions.** "What are you assuming about X that we should check?"
- **Present trade-offs.** "Approach A gives you X but costs Y. Approach B gives you..." Then ask
  which matters more.

### Anti-patterns (do NOT do these)

- **No checklist walking.** Do not ask one question from each category by rote. Follow the
  conversation.
- **No corporate speak.** Be direct. "What happens when it breaks?" not "How should the system
  handle failure scenarios?"
- **No interrogation.** This is collaborative. React to answers, share what you notice, push back
  when something seems off.
- **No yes/no questions.** Every question is open. "How should..." not "Should we..."

### Flow control

After each area, check: "Anything else on [area]? Or move to the next one?"

**Scope guardrail.** If the user starts expanding beyond TOPIC, capture it:

> "Good idea. I'm noting that as a deferred item so we don't lose it. For now, let's stay on
> [TOPIC]."

Record the deferred item for the context document.

### Deep mode addition

For `--deep`: after all rounds, review any unresolved technical questions and suggest:

> "There are [N] open technical questions. Want me to run `/research-stack` on any of these before
> we plan?"

Name the focus tags that fit each question (for example `--focus devtools,security` for a
library pick, `--focus ui-ux,a11y` for a screen), so the research run is aimed.

---

## Step 5: Generate the Context Document

When questioning is done, compile every answer into this structure:

```markdown
# Brainstorm: [TOPIC]

**Date:** [current date]
**Depth:** [quick|standard|deep]

## Project Boundary

- **In scope:** [specific deliverables agreed during questioning]
- **Out of scope:** [items explicitly excluded]

## Key Decisions

1. [Decision made during questioning, with rationale]
2. [Decision made during questioning, with rationale]
3. [Continue as needed]

## Technical Specifics

- [Concrete detail: tech choice, pattern, constraint, or requirement]
- [Concrete detail]

## Open Questions

- [ ] [Unresolved item that needs research or more thought]
- [ ] [Unresolved item]

## Deferred Ideas

- [Scope item noted but deliberately postponed]
- [If none: "None. Stayed on target."]

## Perspective Findings

- [perspective:skeptic] [finding and what we did with it]
```

If `--for-plan` is set, append:

```markdown
## Context for Planning

**Goal:** [one-sentence implementation goal from the brainstorm]
**Mode suggestion:** [TECH or FEATURE, based on what was discussed]
**Key constraints:** [hard constraints surfaced during questioning]
**Affected systems:** [systems and files found in the scan and questioning]
**Risk areas:** [top 2 or 3 risks identified]
```

### Save it

1. Write the document to `.devproto/evidence/brainstorm.md` (create the folder if needed). If the
   project keeps its own planning folder, you may also save a dated copy there, for example
   `.planning/brainstorms/<YYYY-MM-DD>-<topic-slug>.md`, with this front matter:

   ```yaml
   ---
   date: <YYYY-MM-DD>
   type: brainstorm
   project: <project name>
   depth: <quick|default|deep>
   ---
   ```

2. If `--for-plan` is set and a `.planning/` folder exists, also write the document to
   `.planning/CONTEXT.md`.
3. Read the file back once to confirm it saved what you meant.
4. Record the checklist row (see the top of this file).

### Write the intent file (repos with an `intent/` folder only)

If the repo root has an `intent/` folder, also write `intent/<slug>/intent.md` from
`intent/_templates/intent.md`. Fill in the problem, the outcome, the affected users and systems,
the constraints, and the open questions this brainstorm did not close. Front matter carries
`schema: v1`, today's date, `author: <the person who ran the brainstorm>`, and `status: draft`.
Commit it on its own, because the stage timing is measured as the gap between this commit and the
spec's commit.

Repos with no `intent/` folder are untouched. This step does nothing there, and no folder is
created as a side effect of brainstorming.

### Suggest the next step

By depth:

- `--quick`: "Context captured. Run `/planning-stack` when you're ready to plan."
- default: "Run `/planning-stack` to turn this into an implementation plan." For a UI/UX, page,
  app or client build, add: "After planning, `/visual-spec` pins the visual half of the spec."
- `--deep`: "Run `/research-stack --focus <tags>` on the open questions, then `/planning-stack`
  for a full plan."

If the goal is still fuzzy after this, `/karpathy spec` pins the decision this work drives before
the plan is written. If `--for-plan` was set: "Context written to `.planning/CONTEXT.md`.
`/planning-stack` will pick it up."

---

## Depth Tier Summary

| Tier      | Areas | Questions   | Perspectives                             | Research  | Time      | Use when                                                   |
| --------- | ----- | ----------- | ---------------------------------------- | --------- | --------- | ---------------------------------------------------------- |
| `--quick` | 2-3   | 3-5 total   | skeptic only                             | None      | 2-3 min   | You mostly know what you want and need quick alignment     |
| default   | 3-5   | 8-12 total  | skeptic                                  | None      | 5-10 min  | Standard pre-planning for multi-file features              |
| `--deep`  | 4-6   | 15-20 total | skeptic, scope-checker, first-principles | Suggested | 10-20 min | Complex features, architecture decisions, high uncertainty |

Reasoning effort: for `--deep`, use the highest reasoning effort your agent offers. Default and
`--quick` run at your normal high setting.
