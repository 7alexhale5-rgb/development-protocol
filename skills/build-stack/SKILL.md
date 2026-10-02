---
name: build-stack
description: Runs the build phase of an approved plan with small verified slices, per-batch checks, independent review perspectives and context management, then drives the work to a verified, committable state. Use after a plan exists and someone says "implement", "build this", "start coding", "execute the plan", "build the plan", or "/build-stack path/to/plan.md". Sizes the work (bug fix, small, medium, large), checks the plan approval first, and records the build row of the development-protocol checklist. Flags --no-verify, --large, --no-handoff, --review, --audit, --tdd.
---

# Build Stack: build-phase orchestrator

You are running a structured build phase. It takes a plan from any source, sequences the work in
small slices, runs a check after each slice, and drives the result to a verified state that is
ready to commit. It sits between `/planning-stack` (before) and `/review-stack` (after).

**Philosophy:** thin orchestrator. Do not copy logic from other skills; call them. In the LARGE
path, hand the typing to helper agents if your agent supports them. For BUGFIX, SMALL and MEDIUM
work, write the code directly.

**Proof rule.** Keep each build slice small, run its focused check, and record any use of
`--no-verify` as an exception with a reason. A build is done when its result is readable,
repeatable and tied to the files or commit it claims to prove. A command that ran is not proof.

The method and bounded-improvement contract in `../development-protocol/reference.md` governs
this skill and its perspective templates. Choose execution from dependencies and risk, not
file count alone. Preserve approval of unchanged work and existing authorization.

For UI work, read the "Design and UI proof" section of the `/development-protocol` skill's
`reference.md`. It sets the fidelity floor and how to measure the result. Scale the measurement to
the task.

## Checklist row

This skill satisfies the `build` row of the development-protocol checklist. `DEVPROTO` means
`python3 <development-protocol skill folder>/scripts/devproto.py`.

Before you start, run `DEVPROTO --project <repo> status --id=<work-id>`. The `build` row can only
pass after every earlier row (`planning`, `premortem`, `audit-setup` and the rest) is closed. If an
earlier row is open, close it first or mark it `na` with a reason where the tool allows.

When the build is done and Full Verify passes, save the diff and record the row:

Capture a complete snapshot before recording the row:

1. Consume the intake baseline created by `DEVPROTO start` before any phase edits, in
   `.devproto/evidence/<work-id>-build-base.txt`, using exactly `base <sha>` and
   `work-id <work-id>` lines. This is supporting evidence, not another ledger.
   On resume read this file and verify its work ID and commit; never overwrite its
   baseline, recalculate it at closeout or substitute a branch merge-base. Missing
   legacy baseline remains a scope gap until genuine evidence is recovered.
2. Use a temporary Git index (`GIT_INDEX_FILE`), seeded with `git read-tree HEAD`.
   Enumerate the union of `git ls-tree -rz --name-only HEAD` and tracked plus
   nonignored untracked files from `git ls-files -z -co --exclude-standard`.
   The HEAD list retains staged deletions. Exclude `.devproto/`, validate the complete path list for
   secrets, and add those explicit paths to the temporary index. Include tracked
   deletions. Never change the user's real index.
3. Write `git diff --cached --binary <baseline-sha>` from that temporary index to
   `.devproto/evidence/build.diff`. This includes committed, staged, unstaged and new files.
4. Record the read-only snapshot procedure as an evidence instrument. The verifier
   must rebuild the same snapshot in another temporary index and compare it byte
   for byte with `build.diff`, then run the focused tests. Delete only temporary
   indexes created by this procedure. A changed implementation must invalidate proof.

```text
DEVPROTO --project <repo> step --id=<work-id> --step build --result pass \
  --evidence .devproto/evidence/build.diff --verify "<compare the current snapshot with build.diff, then run focused tests>" \
  --instrument .devproto/evidence/<work-id>-build-base.txt \
  --instrument <the main test file you relied on>
```

The verifier must only read. It must not rewrite `build.diff`. If a check could not run, record
`--result blocked --reason "<what>"` instead of a pass. Unknown is not pass.

---

## Step 0: Parse intent

From the user's input, extract:

- **GOAL**: the implementation objective (everything except flags).
- **FLAGS**:
  - `--no-verify`: record skipped checks with reason, scope, owner and next proof. The work
    remains unverified and cannot be marked complete or shipped.
  - `--large`: force the helper-agent path, whatever the file count.
  - `--no-handoff`: skip handoff doc generation when context runs low.
  - `--review`: run a full review with `/review-stack` after the build. Auto-on for LARGE.
  - `--audit`: run the full audit pipeline after the build (chains to
    `/review-stack --audit --auto`). Includes runtime checks, accessibility, bundle analysis and a
    remediation report. Implies `--review`.
  - `--tdd`: enforce test-driven development. Write tests first (red), implement to pass (green),
    then refactor. Sets `IS_TDD` to true. Detect tooling in Step 3; use an isolated executable
    regression check or retain a required-proof gap when a framework is absent.
- **PLAN SOURCE**: where the plan lives (found in Step 1).

Keep GOAL and FLAGS for the whole run.

---

## Step 1: Load the plan

If an explicit plan path was supplied, resolve and read that exact file first.
If it is missing or unreadable, stop with that error; never substitute a newer plan.
Only when no path was supplied, check these sources in order.

### 1a: Conversation context

Look for a plan made earlier in this conversation (from `/planning-stack` or a manual
discussion). Signs:

- Markdown with "## Implementation Steps", "## Files to Modify" or "## Files to Create".
- Task-list items already created from a plan.
- An active plan in your agent's plan mode, if it has one.

### 1b: Planning files

Search the repository for:

```text
**/.planning/PLAN.md
**/.planning/*/PLAN.md
**/plans/*.md
.devproto/evidence/plan.md
```

If you find more than one, read them and pick the most recent by file date or content date.

### 1c: Check the approval before building

A plan is only in force once the person who owns the work has approved its exact text. Record
that approval in `.devproto/evidence/plan-approval.md` using the existing planning-stack
record format. Resolve a project-relative plan path from the repository root, and compute its SHA256
at approval. Preserve that path and hash when an unchanged checkout moves:

```text
plan: <project-relative plan path, or absolute path for a plan outside the project>
sha256: <SHA256 of the exact approved bytes>
approved_by: <owner>
approved_at: <timestamp>
words: <their exact approval words>
```

Pass the planning row with the plan as an instrument and the existing read-only checker:

```text
DEVPROTO --project <repo> step --id=<work-id> --step planning --result pass \
  --evidence .devproto/evidence/plan-approval.md \
  --verify "python3 <planning-stack skill folder>/scripts/plan_approval_check.py .devproto/evidence/plan-approval.md" \
  --instrument <plan path>
```

Before building, run `status`:

- The `planning` row is passed and unchanged: proceed.
- The `planning` row reopened: compare the current plan hash with its approved hash.
  A changed plan or amendment needs the owner's approval of the new exact text before
  re-passing. Never rewrite the approved plan hash under an old quote. Only identical
  plan bytes with changed non-plan evidence may recover proof without another approval.
- No approval on record: if the owner approved this plan in the current conversation, write the
  approval file now (quote their message) and pass the row. Otherwise STOP until they approve,
  whatever the plan's age.

A plan's age is not approval. Preserve approval evidence for its exact text.

If the plan folder has an `AMENDMENTS.md`, treat it the same way. An amendment is only in force
once the owner's approval of its exact text is recorded in the same format, with its own
path, hash and approval record checked by plan_approval_check.py. Stop if it changed or has no approval. Re-record the planning row with both the plan
and AMENDMENTS.md as instruments, and a verifier executing both approval-record checks.
A later amendment edit must reopen the row.

Never edit the approved plan file during the build. Progress goes to a `STATE.md` next to the
plan. Amendments go to `AMENDMENTS.md` and need the owner's approval.

### 1d: No plan found

If no plan exists anywhere, say:

> "No plan found. Options:
>
> - Run `/planning-stack` first to make one.
> - Describe what you are building and I will write a lightweight plan inline for your approval.
> - Point me to a plan file: `/build-stack path/to/plan.md`."

Stop here until the user gives direction.

### 1e: Extract plan data

From the plan, extract:

- **TASK_LIST**: the ordered list of implementation tasks.
- **FILE_LIST**: every file to create or change, with line references if the plan has them.
- **CLASSIFICATION**: the work size, if the plan states one. Otherwise detect it in Step 2.
- **TEST_PLAN**: test expectations, if present.
- **ACCEPTANCE_CRITERIA**: the success criteria, if present.

For UI work that follows a reference design, also collect the production recipe: where the source
files and assets live, the exact build commands, the signature behaviors, and any backend
contracts the screens depend on. Use that evidence to order the task list. Build the hardest
unknown first, as a small working slice, before expanding the design. Carry the real media and
real behavior through to the final result. A concept image or a missing recipe is not evidence
that the implementation exists.

---

## Step 2: Classify the work

Use risk, coupling and acceptance proof to classify work. File counts below are signals,
not limits. Escalate cross-system, data-loss, permission or money risks to a larger method
when their proof needs exceed the proposed class. Honor an approved classification only
while its assumptions still hold.

| Classification | Criteria                                                                |
| -------------- | ----------------------------------------------------------------------- |
| **BUGFIX**     | 2 files or fewer, fix language ("fix", "resolve", "patch", "correct")   |
| **SMALL**      | 3 files or fewer, straightforward implementation                        |
| **MEDIUM**     | 4 to 10 files, several steps with logical groupings                     |
| **LARGE**      | More than 10 files, OR the `--large` flag, OR cross-module coordination |

Report the classification in one line:

> "Classified as **MEDIUM** (6 files across 3 modules). Will run in batches with light checks."

Or for simpler work:

> "Classified as **BUGFIX**. Reproducing the defect, adding a failing behavior check, then Full Verify."

---

## Step 3: Detect project tooling

Before writing code, find out which checks this project can actually run. Probe the project root:

| Flag            | True when                                                                                                                                                                   |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CAN_BUILD`     | `package.json` has a `build` script (or the language's build tool is configured, for example `cargo`, `go build`, `mvn`)                                                    |
| `CAN_TYPECHECK` | `tsconfig.json` exists at the root (or `mypy`/`pyright` is configured for Python)                                                                                           |
| `CAN_LINT`      | An `eslint.config.*`, `.eslintrc*`, `biome.json`, `ruff.toml` or `.ruff.toml` exists at the root, or `package.json` has a `lint` script                                     |
| `CAN_TEST` | The intended package documents an executable test command, including standard-library tests, with applicable test cases. |

Use that documented command and search its intended package for applicable test files,
at most 4 folders deep. Derive `CAN_TEST` from both results, and skip `node_modules`, `.git`, `dist`, `build`,
`.next`, `.venv`, `venv`, `__pycache__`, `coverage` and archive folders.

Use the repository's documented commands and intended package scope. Unrelated vendored tests
do not prove the project works. Retain evidence for each capability flag.

Set `IS_TDD` for features, behavior changes and bug fixes, or explicit `--tdd`. Missing required
tooling is an unmeasured gap; use an isolated executable regression check where suitable.
Retain the isolated regression script as a build `--instrument`, including when stored under
`.devproto/`, and execute it in the build verifier. An isolated executable regression check
is a retained standalone script invoking the
changed code: it exits nonzero for the reproduced defect and zero after the fix. Save
it in the existing evidence folder and run it before and after the correction.
Conditional checks may be not applicable with a reason. Required missing checks block completion.

---

Re-recording planning for a mid-build amendment reopens later passed rows. Renew visual-spec, design, premortem and audit-setup proof, or valid conditional n/a records, before passing build. Mandatory rows cannot be n/a.

## Step 4: Scaffold

Turn the plan's task list into tracked tasks (your agent's task list or todo tool, or a checklist
in `STATE.md` if it has none). This is how progress stays visible.

For **MEDIUM and LARGE** work, group tasks into batches. A batch is a unit of meaning: related
changes that should be checked together. Examples:

- "Database schema plus migration" is one batch.
- "API route plus handler plus types" is one batch.
- "Component plus styles plus tests" is one batch.

For **IS_TDD** projects, scaffold the test files first (red phase), then the implementation (green
phase).

Report the scaffold:

> **Execution plan:**
>
> - Batch 1: [description] (3 tasks)
> - Batch 2: [description] (2 tasks)
> - Batch 3: [description] (2 tasks)
> - Full Verify after all batches

---

## Step 4.5: Audit preflight (always on)

**Skip if `--no-verify` is set.**

Determine setup applicability first. When package.json is absent, do not invoke the Node initializer. Satisfy the required audit-setup row with executed checks of the applicable test/build/CI setup and evidence explaining why frontend tools do not apply. Never mark a mandatory setup row n/a. For applicable Node projects, Run `/audit-setup` before final Full Verify and independent reviews. If it runs later
or changes files, invalidate those receipts and rerun Full Verify and reviews on the
complete new candidate before completion. It prepares the audit
tools `/review-stack` uses: a Lighthouse baseline (median of 3 runs to reduce noise), the axe
accessibility library for Playwright, Playwright's browser dependencies, performance budgets, and
CI gate scaffolding. Preserving an existing Lighthouse baseline without --force returns nonzero and is
not fresh capture proof. Retain that gap, or use authorized --force with backups before
Full Verify and review when fresh capture is required.

Run it even when no audit flag is set. It costs seconds when nothing changed and a few minutes on
first install. Inspect the actual result; missing required tooling or fresh capture
remains a gap for any later review.

Note on checklist order: the `audit-setup` row comes before `build` in the checklist. Close it
once before the build starts. When a later code change requires fresh capture, rerun this preparation before final verification. A changed output needs renewed setup proof; a nonzero preserved-baseline result is
not a pass. Run mutating preparation before final Full Verify and reviews.

**Failure handling:**

- If `/audit-setup` hits an install error that blocks the build (for example `npm install`
  fails), treat it as a Full Verify failure and surface it to the user.
- If it reports non-fatal warnings (a stale baseline it cannot re-capture right now, a missing
  local env file for the preview URL), retain the gap. Missing required audit proof blocks its row and release; only
  explicitly optional checks may remain unavailable.

---


## Step 5: Execute

Pick the path that matches the classification.

If `--no-verify` is set, finish only the authorized implementation scope, then go to
Steps 7a and 7b. Record the earliest open prerequisite as blocked (only after its earlier rows are terminal); leave build and later rows pending if their prerequisites remain open. Preserve implementation evidence, with reason "built with --no-verify",
remaining checks, scope, owner and next proof. Do not run skipped review stages or claim completion.

### BUGFIX path

1. Reproduce the defect and trace its cause with systematic debugging.
2. Add a focused regression check and observe the intended failure.
3. Implement the minimum correction; pass that check and Full Verify.
4. Continue through independent review and retain gaps. Types and lint alone do not prove a fix.

### SMALL path

1. Do all tasks in order.
2. Mark each task complete as it finishes.
3. After the last task, run **Full Verify**.
4. If Full Verify fails:
   - Auto-fix type errors and lint issues (under 5 lines, deterministic).
   - Investigate test failures and build errors; fix confirmed defects within scope. Retain the
     original failure. Ask the owner only for missing access or decisions.
5. Continue through applicable perspectives, audit and review stages before Step 7.

### MEDIUM path

For each batch:

1. **Implement** every task in the batch.
2. **Mark** the tasks complete.
3. Run the **Light Checkpoint** (types and lint).
   - If it fails and the fix is under 5 lines and deterministic, auto-fix and re-check.
   - Investigate complex failures and repair confirmed defects within scope. Ask only for
     missing access or decisions.
4. Run the **Context Gate** (Step 6).
5. Move to the next batch.

After all batches, run **Full Verify** and handle failures by the SMALL path rules.

### LARGE path

1. Use at most two children for independent isolated tasks with disjoint ownership; no nested
   delegation. Run dependent tasks sequentially. If helpers are unavailable, use native sequential
   execution. Every child receives the shared testing and review contract. Light-check templates
   cannot waive behavior tests. Interrupt completed children.

2. Give each helper its tasks plus the verification instruction in
   `references/perspective-prompts.md` (section "LARGE path: helper verification instruction").
3. Collect results from every helper.
4. Run **Full Verify** on the combined changes.
5. Handle failures by the SMALL path rules.

### Autonomous override: goal loops for full-app builds

Some agents offer a goal loop. You give it a completion condition (typically a product brief plus
a checkbox roadmap), and it keeps running agent turns until a small judging model confirms the
condition holds. If your agent has one, it can replace the LARGE path's helper orchestration for
a full-app build.

Use it when:

- The plan is a standalone build with an exit condition a machine can check (every checkbox is
  checked, the main-journey test is green).
- The plan is about 40 to 80 discrete tasks that fit a checkbox roadmap.
- The user explicitly requested unattended work within existing permissions. All phase proof
  and spending limits still apply; do not enable permission bypass.
- The build is new enough that mid-loop changes of direction are unlikely.

Do not use it when:

- The plan coordinates across systems, writes to shared state, or has per-phase gates that need
  human judgment.
- The acceptance criteria depend on things the judging model cannot see (database rows, deployed
  assets).

Workflow: write `PRD.md` and a checkbox `ROADMAP.md` (40 to 80 items). Set the condition to
"every checkbox in ROADMAP.md is checked AND the test command passes." Launch it. Watch cost and
context. Review the diff before merging. Do not run both the goal loop and the helper fan-out for
the same plan.

### TDD cycle

Apply this cycle when `IS_TDD` is true, including features, behavior changes and bug fixes
without a flag. A missing framework is a gap, not permission to skip proof.

1. RED: run a meaningful behavior check and observe its intended failure.
2. GREEN: implement the minimum correction and pass the check.
3. REFACTOR: simplify while keeping checks green.
4. Verify acceptance cases, error paths and the original regression. Coverage guides investigation;
   there is no blanket percentage requirement.

For behavior-preserving refactors, run characterization checks before editing and verify
invariants afterward. Copy edits, generated output, nonbehavioral configuration and throwaway
probes use the smallest meaningful validator; record why behavior tests do not apply.

Keep one atomic change per iteration. After three unsuccessful fixes, reassess the cause and
approach. Continue authorized investigation. Preserve existing work and failed evidence; never
delete work to reconstruct a test-first history.

---

## Step 5.5: Spawn build perspectives

**Skip if `--no-verify` is set.**
**For BUGFIX, run only the skeptic.**

After Full Verify (end of Step 5), get independent reviews of the implementation from different
angles before you call it complete. These catch problems static checks miss.

Run perspectives in bounded batches with at most two children and no nested delegation. Reuse
final independent reviews rather than duplicate seats. Without helpers, self-review can support
the work but cannot replace required independent review.

### 5.5a: Pick perspectives by classification

| Classification | Shared perspectives                            | Inline perspectives                 |
| -------------- | ---------------------------------------------- | ----------------------------------- |
| BUGFIX         | skeptic (always runs)                          | none                                |
| SMALL          | skeptic, code-quality                          | none                                |
| MEDIUM         | skeptic, code-quality, test-coverage           | plan-conformance (if a plan exists) |
| LARGE          | skeptic, code-quality, test-coverage, security | plan-conformance (if a plan exists) |

The **skeptic** always runs. It asks whether the code is sloppy and whether it matches the stated
intent. Evidence-backed no-findings is valid. Its rules are in
`references/perspective-prompts.md`.

### 5.5b: Prepare the context payload

Build the CONTEXT_PAYLOAD summary. Its schema is in `references/perspective-prompts.md` (section
"Context payload"). It covers the goal, classification, files changed and created, verification
status, plan summary and the diff.

### 5.5c: Run the perspectives

Run selected perspectives in batches of at most two. The focus lists and output formats are in
`references/perspective-prompts.md`. Verify model availability and preserve evidence.

---

## Step 5.75: Collect perspective results

Collect each perspective's output. If one is still running, wait. They should finish in 30 to 60
seconds.

### Review disposition

An empty or failed review is an unmeasured gap. Verify substantive findings against source and
behavior. Accept evidence-backed no-findings without retrying merely to obtain criticism. Fix
material defects; retain reasons for dismissals and optional deferrals.

### Present findings

If any perspective returned findings:

> **Perspective analysis** ({N} findings from {N} perspectives):
> {findings, grouped by severity}
>
> Fix confirmed material defects before completion. Retain optional findings with their disposition.

If every perspective is clean:

> **Perspectives:** {N} reviews, all clean.

### UI quality gate

**Runs automatically when** any file in FILE_LIST ends in `.tsx`, `.jsx`, `.vue` or `.svelte`, or
has `component`, `page`, `layout`, `dashboard`, `modal`, `sidebar` or `form` in its path.

When UI files are part of the build, run a UI critique after the perspectives finish:
`/design-stack --critique` on the changed screens. If that is not available, do the check by hand:

- Open each changed screen at a desktop width and a phone width.
- Use it with the keyboard only. Every control must be reachable, with a visible focus ring.
- Check each state: empty, loading, error, full.
- Check text contrast (4.5:1 for normal text) and touch targets (44 by 44 pixels).
- Compare against the design direction in the plan. Note what drifted.

**Skip if** `--no-verify` is set, or no UI files are in the change.

---

## Step 6: Context gate

**Runs after every batch in MEDIUM, and after collecting helper results in LARGE.**
**Skip if `--no-handoff` is set.**

Check how much of the conversation's context window is left. Use whatever your agent reports (a
context meter, a warning, a token count). If it reports nothing, estimate from the length of the
session so far.

### Decision matrix

| Context left         | Work remaining       | Action                                                    |
| -------------------- | -------------------- | --------------------------------------------------------- |
| Fresh (over 60%)     | any                  | Continue normally                                         |
| Moderate (40 to 60%) | any                  | Continue. Note context use                                |
| Depleted (25 to 40%) | under 50% of tasks   | Compact the conversation if your agent can, then continue |
| Depleted (25 to 40%) | 50% of tasks or more | Write the handoff doc and suggest a fresh session         |
| Critical (under 25%) | any                  | Write the handoff doc now and stop                        |

### Handoff doc

If the gate calls for a handoff, write it with the template in `references/handoff-format.md`
(section "Handoff doc"). It goes in `.devproto/handoffs/` in the repository.

If you cannot tell how much context is left, treat it as Moderate and continue.

---

## Verification definitions

### Light Checkpoint

A fast loop that catches type errors and lint violations early.

| Check | Command                                               | When               |
| ----- | ----------------------------------------------------- | ------------------ |
| Types | `npx tsc --noEmit`, `mypy .`, `pyright` or equivalent | If `CAN_TYPECHECK` |
| Lint  | `npm run lint`, `npx eslint .` or `ruff check .`      | If `CAN_LINT`      |

**Speed:** about 5 to 15 seconds.
**When:** after each MEDIUM batch. BUGFIX uses its regression check and Full Verify.

### Full Verify

A complete check that everything works together.

| Check      | Command                                                                           | When                         |
| ---------- | --------------------------------------------------------------------------------- | ---------------------------- |
| Build      | `npm run build`, `pnpm build` or equivalent                                       | If `CAN_BUILD`               |
| Types      | `npx tsc --noEmit` or equivalent                                                  | If `CAN_TYPECHECK`           |
| Lint       | `npm run lint` or equivalent                                                      | If `CAN_LINT`                |
| Tests      | `npm run test`, `pytest` or equivalent                                            | If `CAN_TEST`                |
| UI journey | Run the main user journey from the plan in a real browser against the running app | If the diff touches UI files |

**The UI journey check degrades loudly, never silently.** If you cannot run it (no browser tool,
no running app), write "UI journey: not run, because <reason>" in the Full Verify output and in
the handoff. Implementation may continue, but missing required runtime proof blocks completion
and shipping. Run the aggregate journey in the root after collecting helper results.

Save the test output to a file (for example `.devproto/evidence/full-verify.log`) so the verify
and review rows have something real to point at.

**Speed:** about 30 to 120 seconds.
**When:** after all tasks are done.

### Auto-fix rules

| Issue type                                  | Auto-fix? | Condition                                                                          |
| ------------------------------------------- | --------- | ---------------------------------------------------------------------------------- |
| Type error (missing import)                 | Yes       | A single import line                                                               |
| Type error (wrong type)                     | Yes       | Under 5 lines, deterministic fix                                                   |
| Lint violation (formatting)                 | Yes       | The linter can fix it (`--fix`)                                                    |
| Lint violation (logic)                      | No        | Surface to the user                                                                |
| Unused imports                              | Yes       | Remove the import line                                                             |
| `console.log` or `print` in production code | Yes       | Remove if `CAN_LINT` and the file is not a debug or dev file. Otherwise surface it |
| `any` or `unknown` type usage               | No        | Surface to the user. Proper typing needs judgment                                  |
| Dead code (unreachable, unused exports)     | No        | Surface to the user. It may be intended public API                                 |
| Test failure | Investigate | Fix confirmed defects within scope; ask only for missing access or decisions. |
| Build error                                 | Maybe     | Auto-fix if it is clearly a type or import issue. Otherwise surface                |

**If `--no-verify` is set:** skipped required checks leave work unverified. Do not mark it
complete, ship it or pass its proof row. Record the missing proof and next check.

---


## Step 6.5: Independent review for every classification

**Skip if `--no-verify` is set.**

After Full Verify, reuse independently executed Step 5.5 reviews only when the retained
complete candidate snapshot still matches all committed, staged, unstaged and new files,
and the package covers recorded BASE..HEAD and acceptance evidence. BUGFIX needs an independent skeptic pass; SMALL
needs skeptic and code-quality lenses. MEDIUM needs its selected lenses. Run them in a child
or fresh session; self-review supplies supporting evidence only. Record missing independent
review as a required gap. A full `/review-stack` runs with `--review`, `--audit`, or LARGE.
The agent that wrote the code must not be the only reviewer. Do not duplicate review seats.

### Standard review (`--review` or LARGE)

```text
/review-stack --work-id=<work-id> --branch --plan <plan path from Step 1>
```

To keep the build conversation's context small, run it in a fresh helper agent or a fresh
session instead. The invocation is in `references/perspective-prompts.md` (section "Review gate
invocation").

### Audit review (`--audit`)

If `--audit` is set, run the full audit pipeline instead:

```text
/review-stack --work-id=<work-id> --audit --auto --branch --plan <plan path from Step 1>
```

This runs all review layers (static, pattern, context, runtime) with all 8 perspectives,
including accessibility and Lighthouse. It produces a remediation report with priority groups,
an auto-fix manifest and a going-public readiness checklist.

### Verdict handling

The review returns a verdict: SHIP IT, FIX THEN SHIP, NEEDS WORK or BLOCKED. For an audit it can
also return READY TO SHIP or SHIP WITH CAVEATS.

- **SHIP IT / READY TO SHIP:** proceed only when required checks pass.
- **FIX THEN SHIP:** fix confirmed defects, rerun checks and obtain updated independent review.
- **SHIP WITH CAVEATS:** only optional gaps may remain.
- **NEEDS WORK / BLOCKED:** investigate and repair within authority; ask only for missing access
  or decisions.

---

## Step 7: Complete

After implementation, when required verification passes or its gaps are explicitly recorded
as blocked, produce the summary and checklist record. Only the passing path is complete:

### 7a: Summary report

Show the tree-format summary. The template is in `references/handoff-format.md` (section
"Summary report").

### 7b: Record the checklist row

Record the `build` row only after earlier rows are terminal. If verification has failures, record the earliest open eligible row as blocked with the reason and leave later rows pending. Then run `status` and tell the user the next open row.

### 7c: Suggest next steps

Match the verification outcome (clean, audit, issues, LARGE). The message templates are in
`references/handoff-format.md` (section "Next steps").

### 7d: Session note (optional)

For MEDIUM or LARGE work that passed verification, write a short note. The template is in
`references/handoff-format.md` (section "Session note"). It goes in `.devproto/notes/`.

### 7e: Visual recap (optional, never blocks)

For MEDIUM and LARGE work, if your team has a tool that renders a change recap as a web page, run
it on the summary. If it fails, the tree summary stands. Skip this for BUGFIX and SMALL.

---

## Graceful degradation

| Component              | If missing                            | Fallback                                                |
| ---------------------- | ------------------------------------- | ------------------------------------------------------- |
| Context meter          | Agent does not report context left    | Treat as Moderate and continue                          |
| Task-list tool         | Not available                         | Track progress in `STATE.md` next to the plan           |
| `package.json` scripts | No build, test or lint scripts | Use documented project commands; record required missing checks as gaps. |
| TypeScript             | No `tsconfig.json`                    | Skip type checking                                      |
| Test framework | No applicable test runner | Use meaningful isolated regression proof or keep required verification blocked. |
| Helper agents          | Not supported, any classification              | Implement sequentially; independent review remains required       |
| Checklist tool         | `/development-protocol` not installed | Keep the evidence files anyway and report in chat       |
| `/audit-setup`         | Not installed                         | Retain the required setup gap in Step 4.5. Note that `--audit` reviews will degrade |

**Minimum viable run:** a bounded change, executed meaningful checks, readable evidence and
an honest remaining-scope report. Missing required proof blocks completion.

---

## Depth summary

| Classification | Checkpoints     | Full Verify     | Context gate     | Perspectives                                   | Audit preflight             | Helper agents | Est. time    |
| -------------- | --------------- | --------------- | ---------------- | ---------------------------------------------- | --------------------------- | ------------- | ------------ |
| BUGFIX         | Regression plus full | Yes | No               | skeptic only                                   | `/audit-setup` (fresh proof or gap) | Independent reviewer | Scope-dependent |
| SMALL          | 0               | 1 full          | No               | skeptic, code-quality                          | `/audit-setup` (fresh proof or gap) | Independent reviewer | Scope-dependent |
| MEDIUM         | Light per batch | 1 full          | Per batch        | skeptic, code-quality, test-coverage           | `/audit-setup` (fresh proof or gap) | Independent reviewer | 15 to 45 min |
| LARGE          | Delegated       | 1 full          | After collecting | skeptic, code-quality, test-coverage, security | `/audit-setup` (fresh proof or gap) | Yes           | 30 to 90 min |

Audit preflight runs for every applicable classification. Inspect fresh capture and
tool availability; missing required proof blocks completion. A skipped preflight remains
unverified. Run mutating setup before final Full Verify and independent review.

Review snapshot and release checks require the Git repository root. For a monorepo
subproject, pass the root as --project and identify package scope in the work brief.
