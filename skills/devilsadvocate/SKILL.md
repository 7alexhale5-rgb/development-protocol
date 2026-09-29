---
name: devilsadvocate
description: Runs a deep, honest check on research claims and assumptions before anyone acts on them. It sorts every claim into Verified, Plausible, Unverified or Contradicted, names the hallucination type, strips unsupported claims, and filters for the simplest approach that works. A --premortem mode assumes a plan already failed and lists the failure chains, hidden assumptions, warning signs and plan fixes. Use when someone says "verify this research", "devil's advocate", "sanity check", "what's real here", "is this overcomplicated", "objective alignment", or, for the premortem, "premortem this", "find failure modes", "what could go wrong", "stress test this plan", "imagine this failed", after planning and before building.
---

# Devil's Advocate: Objective Alignment

You are running an objective alignment pass on gathered research context. Your job is to be
ruthlessly honest about what is verified, what is assumed, and what is noise. Then write a clean
brief that keeps things as simple as possible without restricting the build.

> **Standalone skill, run by hand.** A lighter skeptic pass already runs inside
> `/brainstorm-stack`. Use this full `/devilsadvocate` when you need the complete claim triage
> (hallucination taxonomy, source checks, simplicity filter) on research output. Common use: after
> `/research-stack`, before acting on its findings.

## Checklist rows

- **`--premortem` mode** satisfies the `premortem` row of the development protocol checklist.
  Save the output to `.devproto/evidence/premortem.md`, then record it:

  ```text
  python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
    --id <work-id> --step premortem --result pass \
    --evidence .devproto/evidence/premortem.md \
    --verify "grep -q 'Top revisions to apply BEFORE building' .devproto/evidence/premortem.md"
  ```

- **Default mode** has no row of its own. Save the brief to
  `.devproto/evidence/alignment-<topic-slug>.md`, next to the research evidence, so the `research`
  row (owned by `/research-stack`) and the plan can cite it.

The verifier only reads the evidence file. It never rewrites it.

---

## Mode: `--premortem`

**Row order.** The `premortem` row is number 8 of 17 in the development protocol checklist, and
rows pass in order: it cannot record `pass` while an earlier row (1 to 7) is still open. Before
running this mode inside a checklist-tracked project, check where you stand:

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> status --id <work-id>
```

If an earlier row is neither `pass` nor `n/a`, do that row (or mark it `n/a` with a reason) first.
Running the premortem standalone, outside a checklist item, is unaffected; this only matters when
the plan is being tracked through the full protocol.

`/devilsadvocate --premortem [path]` runs Gary Klein's premortem instead of claim triage. Assume
the plan shipped 90 days ago and failed. List 3 to 7 failure chains. For each, name the silent
assumption and the warning signs, rank likelihood times danger, and list concrete plan revisions.
The output is a fixed table. Read `references/premortem.md` in this folder and follow it end to
end.

Run both modes on critical plans. They catch different things: the default mode finds invented
claims and unsupported assertions; the premortem finds failure chains the plan glosses over.

---

## Step 1: Identify Input

Look for research context in this order:

1. **The current conversation.** If `/research-stack` ran this session, use its output.
2. **The repo.** Look for saved research and notes: `.devproto/evidence/research*.md`, `.planning/`,
   `docs/research/`, `docs/adr/`. Search them for the TOPIC keywords and read the relevant hits in
   full. If your team keeps research somewhere else (a wiki, a notes folder), search there too.
3. **Nothing found.** Ask: "What context should I verify? Paste the findings, point me to a file,
   or run `/research-stack` first."

Pull out every distinct claim, recommendation, or assertion in the research.

---

## Step 1.5: Confabulation Self-Check

Before triage, name your own biases about this research in one paragraph:

- What am I inclined to **agree with** because it confirms what I already believe?
- What am I inclined to **dismiss** because it is unfamiliar?
- Where might I be **pattern-matching** to something I "know" that does not actually apply here?

State these in the output. This stops silent bias from leaking into the triage.

---

## Step 2: Claim Triage

Put every claim into one of four buckets:

| Category         | Criteria                                                           | Symbol |
| ---------------- | ------------------------------------------------------------------ | ------ |
| **Verified**     | Confirmed by 2 or more independent sources with URLs or citations  | `[V]`  |
| **Plausible**    | One credible source, or matches known patterns                     | `[P]`  |
| **Unverified**   | No source, AI-generated filler, or "many experts say" style claims | `[U]`  |
| **Contradicted** | Sources disagree, or the claim conflicts with known facts          | `[X]`  |

"Independent" means the sources did not copy each other. Two blog posts quoting the same press
release are one source.

### Hallucination taxonomy

For every `[U]` or `[X]` claim, name the failure type:

| Type            | What it is                                        |
| --------------- | ------------------------------------------------- |
| **Intrinsic**   | Contradicts the source it claims to draw from     |
| **Extrinsic**   | Adds information that is in no cited source       |
| **Entity**      | Wrong names, organizations, products, or versions |
| **Attribution** | A real fact credited to the wrong source          |
| **Citation**    | Invented URLs, DOIs, or paper titles              |

### Hallucination patterns to flag

Strip or flag these. They compound downstream if left alone:

- **Vague authority:** "experts recommend", "best practice is", "it's widely known". WHO says this?
  WHERE?
- **Phantom specificity:** exact numbers, dates, or version numbers with no source. Models love
  inventing these.
- **Hedged assertions:** "may", "could potentially", "is likely to". Either it does or it does not.
  Which is it?
- **Recency inflation:** "recently", "the latest trend". When exactly? Is two-year-old research
  being presented as current?
- **Complexity bias:** research that pushes toward the most sophisticated solution when a simpler
  one exists.
- **Consensus manufacturing:** "the community agrees". Does it? Show the thread.

---

## Step 3: Simplicity Filter

For each recommendation or approach in the research, ask:

1. **Is this actually needed?** Or is it interesting but irrelevant to what we are building?
2. **Is there a simpler way?** Research often surfaces the most comprehensive approach, not the
   most appropriate one.
3. **What is the minimum viable version?** Strip it to the smallest thing that solves the actual
   problem.
4. **Who is this advice for?** A recommendation for a 50-person team may not apply to a solo
   builder.

The goal is NOT to reject complexity. It is to make sure complexity is justified by actual
requirements, not by research momentum.

---

## Step 4: Output: Objective Alignment Brief

Present the findings in this format. No softening, no preamble.

```text
## Objective Alignment: [TOPIC]

### Bias Self-Check

[The paragraph from Step 1.5: which biases were identified]

### Verified Context (build on this)

- [V] [Claim: source1, source2]
- [V] [Claim: source1, source2]

### Plausible Context (use with awareness)

- [P] [Claim: source]. Note: [what would confirm or deny this]
- [P] [Claim: source]

### Stripped (do not carry forward)

- [U] [Claim that was unsourced or invented]. Type: [intrinsic/extrinsic/entity/attribution/citation]. Why: [reason]
- [X] [Claim that was contradicted]. Counter: [what actually appears true]

### Simplicity Check

- **Research suggests:** [complex approach]
  **Simpler alternative:** [what might actually work]
  **Complexity justified if:** [condition that would make the complex version necessary]

### Actual Requirements (what we know is true)

1. [Hard requirement grounded in verified context]
2. [Hard requirement]
3. [Hard requirement]

### Open Questions (verify before brainstorming)

- [ ] [Thing we assumed but did not confirm]
- [ ] [Thing that needs real-world validation]

### Blind Spots (what the research did not cover)

- [Topic or angle the research should have covered but did not]
- [Missing perspective, edge case, or domain]
- [Assumption baked in that was never questioned]
```

Save the brief (see "Checklist rows" above) and read the saved file back once.

---

## Step 5: Pipeline Handoff

After delivering the brief:

### If design or visual work

> "Context verified. Run `/brainstorm-stack` to settle the decisions, then `/visual-spec` to pin
> the visual spec before design."

### If technical or backend work

> "Context verified. Run `/brainstorm-stack` to explore decisions, then `/planning-stack` to plan
> the implementation."

### If critical open questions remain

> "There are [N] unverified claims that could change the approach. Want to run `/research-stack`
> on these specific questions first, or proceed with what we have?"

---

## Rules

- **No softening.** If the research is wrong, say it is wrong.
- **No new research.** Work only from what was gathered. If context is missing, say so.
- **Bias toward simplicity.** When in doubt, the simpler path is probably right until proven
  otherwise.
- **Attack the inputs, not the person.** This is not about whether the research was done well. It
  is about what is actually true.
- **Keep all verified context.** Do not throw out good findings in pursuit of minimalism.
- **Be specific.** "This claim is unverified" is useless. "This claim has no source and
  contradicts X" is useful.
- **No implementation.** This step produces a verified context brief, nothing more.

## When NOT to use

- The user already has high-confidence context and just wants to build: go to `/brainstorm-stack`.
- The task is trivial (under about 10 lines of code): skip the whole pipeline.
- The user says "I know what I want, just plan it": go straight to `/planning-stack`.
