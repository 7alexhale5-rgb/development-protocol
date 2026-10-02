---
name: karpathy
description: Applies Andrej Karpathy's three-layer method for agentic work (Spec, Verifier, Environment) through the bundled development skills. The spec mode pins the goal and a falsifiable acceptance check before any build. The verify mode sets criteria up front, runs a second-model critic whose review is checked to have really happened, and proves the result on a real artifact that is read back and re-checked in CI. The audit mode checks the agent instructions file, knowledge layout, skills and rule enforcement. Use when starting non-trivial work, when someone says "pin the goal first", "spec this", "what does done look like", "how do we verify this", "get a second opinion on the diff", "prove it works", or "audit my agent setup". The one rule: outsource the typing, not the understanding.
---

# Karpathy Method

Three layers from Andrej Karpathy's 2026 talk on agentic engineering. Each layer **routes to skills
this bundle already has**. This skill makes the method explicit and centred on the goal. It does
not re-teach what those skills and the team's hooks already enforce.

Parse the argument: `spec` | `verify` | `audit`. If it is empty, ask which layer. For a fresh build,
run them in order: spec, then build (`/build-stack`), then verify, with audit as a periodic tune-up.

> **The one thing:** you can outsource your thinking, but not your understanding. Every layer
> below centres on the goal only the user can supply. Do not let the machinery hide the goal.

## Checklist rows

This skill satisfies two rows of the development protocol checklist: `spec` (Layer 1) and `verify`
(Layer 2). Record each one when its layer is done:

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id=<work-id> --step spec --result pass \
  --evidence .devproto/evidence/spec-baseline.json \
  --verify "<read and validate the saved baseline failure, source revision, command, expected failure and test-file hash>" \
  --instrument <the acceptance test file>

python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id=<work-id> --step verify --result pass \
  --evidence .devproto/evidence/verify.md \
  --verify "<the full test suite command>" --instrument <the acceptance test file>
```

Capture the intended baseline failure once, before implementation: exact source revision,
acceptance-test hash, command, nonzero exit, output hash and the expected failed assertion.
Confirm that failure is the intended missing behavior, not a broken runner. Keep this receipt
immutable. Its verifier validates that saved record and artifacts; it does not expect the
current implementation to keep failing. Layer 2 runs the positive acceptance test and suite.

Passing the acceptance test as `--instrument` means a weakened test reopens the row. The verifier
only reads the evidence. It never rewrites it.

Layer 3 (`audit`) has no row of its own. `/audit-setup` owns the `audit-setup` row.

For design work, apply the "Measuring outcomes and strength of proof" rules in
references/proof-standard.md in the existing brief and proof flow. Scale the measurement to the
task.

---

## Layer 1: `spec` (deliver your understanding)

Karpathy: uncover the _goal_ (the decision it drives, not the task), work in small agile scopes,
verify the key decisions. The bundle already does this. Invoke it, do not hand-roll it:

```text
We're starting: $TOPIC.

0. EXTERNAL FACTS (only if the goal depends on them: a new domain, "should we adopt X", market,
   competitor or library facts we do not already hold): run /research-stack FIRST, with
   --focus <tags> when the area is clear (devtools,security for a library pick, ui-ux,a11y for
   UI, market for competitors). It stays its own skill. The spec just uses its cited findings.
   Skip this when the goal is already clear.
1. GOAL before task. If the work is non-trivial or ambiguous, run /brainstorm-stack. Interview the
   user (with a structured question tool if your agent has one) to pin the decision this work
   drives before any plan exists. Do not start from the task statement.
2. SPEC via /planning-stack. Use the ladder cadence:
   - each phase ships one runnable thing end to end, against a falsifiable gate number;
   - a hard test gate sits between phases, and phases never collapse into one;
   - a throwaway v1 comes first;
   - stop when the threshold is met.
   Acceptance criteria must be explicit and checkable. Write the acceptance check itself now,
   before building, and confirm it fails for the planned reason.
   For a UI/UX, page, app or client build, the visual half of the spec comes from /visual-spec.
3. Stress it with /devilsadvocate --premortem before any code.
4. Make the user confirm the key decisions explicitly. Name each fork instead of picking silently.
   Keep scope surgical, deletion before abstraction: every changed line traces to the request.

Write the spec to .devproto/evidence/spec.md (or the project's own planning folder, such as
.planning/). Do NOT build yet. That is /build-stack.
```

What a good spec holds, at minimum:

- **Goal:** the decision or outcome this work drives, in one sentence, and who it is for.
- **Done when:** checkable conditions, each one something a command or a person can fail.
- **Gate number:** one measured number with its threshold (for example "p95 under 300 ms on the
  seeded data set", "0 failing rows in the import check").
- **The acceptance check:** the test or script that proves it, already written and failing.
- **Forks:** each open choice, the options, and who decided.
- **Out of scope:** what this work will not do.

---

## Layer 2: `verify` (the only real lever)

Karpathy: criteria up front, then a second-model critic, then an external signal. Much of this may
already be enforced by the team's hooks and CI. Use this layer to be explicit, not to add
scaffolding twice.

```text
Add the verifier layer to: $TASK.

1. CRITERIA UP FRONT. State exactly what "good" looks like as checkable conditions BEFORE
   building. Not "tests pass". For prompt or LLM changes, capture them as a golden set: a fixed
   list of inputs with the expected output or grading rule for each, run before and after the
   change, with the before-run saved as the baseline.

2. SECOND-MODEL CRITIC. Run the diff (or the plan) past a critic from a DIFFERENT model family
   than the one that wrote it, with a written brief. If you can reach two other families, run
   both on the SAME diff with the SAME brief, in parallel. The builder then ADJUDICATES the union
   of their findings on the real artifact: dedupe, judge each finding on its merits (not on the
   critic's say-so), fix confirmed ones test-first, and dismiss false positives with a one-line
   reason each. Critics are critics, not gates. The builder owns the fix.

3. EXTERNAL SIGNAL. Prove it with the proof standard (references/proof-standard.md): a real
   artifact, an executed check, and the result READ BACK. The third part is the one that gets
   skipped and the one that catches things. Then run /review-stack for its layered gate.

4. PROOF THAT SURVIVES THE SESSION. A check only you ran expires when you leave. The repo must
   run its own gate on the pull request (if it has none, run /audit-setup to add CI). The CI
   check-run on the HEAD commit is the artifact you read back.

Do not re-instruct what the team's hooks already enforce (secret guards, destructive-command
blocks, commit gates). Check they ran; do not duplicate them.
```

### What counts as a real review

A review claim needs proof that the review happened. Lessons measured the hard way:

- On 2026-09-16 a raw review command from a second model's CLI **returned no review and exited 0.**
  On 2026-09-18 the same kind of call failed three different ways in one day. A green exit code
  from a review tool is not a review.
- On 2026-09-02 a read-only reviewer tried to hand the job to a tool its sandbox could not run,
  and produced nothing. The brief must tell the reviewer to read the diff and review it directly.

So a review counts only when all of these hold. If your team has a wrapper that checks them, use it.
If not, check by hand and write what you saw into `.devproto/evidence/verify.md`:

1. **The turn finished.** The output is not empty and was not cut off.
2. **You saw which model answered**, and it is the one you asked for. No silent fallback to another
   model.
3. **The verdict fits a schema:** one of APPROVED, REVISE or BLOCKED, plus findings ranked by
   severity, each with a concrete failure case. APPROVED with open high-severity findings is
   inconsistent and does not count.
4. **The claim cites the run.** Name the run id, log file or saved output. Or say plainly that the
   review did not happen.

### The critic brief

Every critic brief requires the critic to check, and flag any violation before shipping:

- **Correctness**, edge cases, and security.
- **DRY:** is anything duplicated?
- **KISS:** is the complexity justified?
- **YAGNI:** was anything added for a hypothetical future use?
- **SOLID:** are responsibilities separated?
- **SINE:** is every new element strictly necessary?

Also tell it: "Be maximally independent. The author's reasoning is not evidence. Read the diff and
review it yourself; do not delegate to another tool."

### When a critic is unavailable

If a critic is not installed, is rate-limited, or is blocked by the team's rules for this repo
(some repos may not be sent to some providers), run the others and **substitute a fresh-context
critic**: a separate session or subagent of any available model, with only the diff, the spec and
the test output, and the adversarial brief above. Validate it the same way. Then **say the
model-family gap out loud** in the evidence and to the user. Never silently drop a pass.

Why this rule exists (2026-07-11): in a four-critic review, the independent substitute critic found
the two best defects that every other critic missed, an unreachable verdict threshold and tests
polluting a live event queue.

For claims and assumptions (not code), add `/devilsadvocate` as a same-model backstop. For strategy
documents, add a reviewer who reads as the stakeholder would, if your team has one.

---

## Layer 3: `audit` (the environment, the workshop)

Karpathy's four points, checked against what the project actually runs:

```text
Audit the environment for $SCOPE against Karpathy's four points:

1. INSTRUCTIONS FILE. Is the repo's agent instructions file (CLAUDE.md, AGENTS.md, or both, one
   linked to the other) structured as:
   (a) how the repo works (build, test, run commands that actually work),
   (b) the skills and when to route to each,
   (c) where things live (a knowledge map),
   (d) the key working rules?
   Every line should change behavior on most turns. Anything that matters only when one kind of
   task starts belongs behind a pointer to a separate file.
2. KNOWLEDGE BASE. Is durable knowledge landing in the right place? Decisions in ADRs or docs/,
   cross-session state in .devproto/ and handoff notes, deep research in its own folder, secrets
   only in a secret store (never in the repo). Look for orphans: notes nobody links to, stale
   docs that state present-tense facts with no date.
3. SKILLS. Is anything done by hand again and again that should become a skill? Propose it.
   FLOOR COST: every new skill adds its description to every turn's context. Prefer a mode or
   argument on an existing skill over a new skill.
4. RULES TO ENFORCEMENT. Sort the team's rules into ALWAYS, ASK-FIRST and NEVER. For each critical
   NEVER, check whether something enforces it at the tool level: a hook, a pre-commit check, a CI
   job, branch protection. If a critical NEVER has no enforcement, add one. Prose is not
   enforcement. Soft, behavioral rules go into the instructions file.

Check live state first: are the tools and servers the instructions assume actually connected, are
keys valid, is CI green on the default branch. A document is a claim; the running system wins.
```

Write the findings to `.devproto/evidence/environment-audit.md`: each point, what you found (with the
command or file that showed it), and the fix, if any.

---

## Notes on fit

- This is **one** skill on purpose. Three separate skills would add three descriptions to every
  turn's context (an audit on 2026-06-14 flagged that per-turn cost). Modes over proliferation.
- It never re-asks for approval after a plan is approved, it reports in plain language, and when it
  spawns work it picks a model strong enough for the job and a different family for critique.

---

## Design proof

Full rules, including the 0-3 quality scale, the six outcome metrics (with formulas) and the
fix-verify-regress loop, live in **"Measuring outcomes and strength of proof"** in
`references/proof-standard.md`. Read that section, not this pointer, before grading design or other
substantive work. Scale the measurement to the task: a small visual edit needs its intended
improvement and the relevant checks, not a full experiment.
