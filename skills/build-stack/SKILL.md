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

Before you start, run `DEVPROTO --project <repo> status --id <work-id>`. The `build` row can only
pass after every earlier row (`planning`, `premortem`, `audit-setup` and the rest) is closed. If an
earlier row is open, close it first or mark it `na` with a reason where the tool allows.

When the build is done and Full Verify passes, save the diff and record the row:

Capture a complete snapshot before recording the row:

1. Resolve the approved baseline to a commit SHA (merge-base with the remote default
   branch, or HEAD for local work). Save that SHA in the evidence.
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
DEVPROTO --project <repo> step --id <work-id> --step build --result pass \
  --evidence .devproto/evidence/build.diff --verify "<compare the current snapshot with build.diff, then run focused tests>" \
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
    then refactor. Sets `IS_TDD` to true. Needs a test framework, found in Step 3.
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
that approval as a file, for example `.devproto/evidence/plan-approval.md`, with one line such as
`Approved by <name> on <YYYY-MM-DD>: "<their exact words>"`. Then pass the `planning` row with the plan file as an instrument, so
the checklist fingerprints the plan:

```text
DEVPROTO --project <repo> step --id <work-id> --step planning --result pass \
  --evidence .devproto/evidence/plan-approval.md \
  --verify "grep -q 'Approved' .devproto/evidence/plan-approval.md" \
  --instrument <plan path>
```

Before building, run `status`:

- The `planning` row is passed and unchanged: proceed.
- The `planning` row reopened: inspect which evidence or instrument changed. Restore valid
  proof for unchanged approved scope without requesting approval again. If scope changed, show
  the change and obtain any authorization that change requires.
- No approval on record: if the owner approved this plan in the current conversation, write the
  approval file now (quote their message) and pass the row. Otherwise STOP until they approve,
  whatever the plan's age.

A plan's age is not approval. Preserve approval evidence for its exact text.

If the plan folder has an `AMENDMENTS.md`, treat it the same way. An amendment is only in force
once the owner's approval of its exact text is recorded. Stop if it changed or has no approval.

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

If the plan gives a classification, use it. Otherwise detect it:

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

Search for test files at most 4 folders deep, and skip `node_modules`, `.git`, `dist`, `build`,
`.next`, `.venv`, `venv`, `__pycache__`, `coverage` and archive folders.

Use the repository's documented commands and intended package scope. Unrelated vendored tests
do not prove the project works. Retain evidence for each capability flag.

Set `IS_TDD` for features, behavior changes and bug fixes, or explicit `--tdd`. Missing required
tooling is an unmeasured gap; use an isolated executable regression check where suitable.
Conditional checks may be not applicable with a reason. Required missing checks block completion.

---

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

## Step 5: Execute

Pick the path that matches the classification.

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
**When:** after each batch (MEDIUM), or after the fix (BUGFIX).

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

## Step 6.4: Audit preflight (always on)

**Skip if `--no-verify` is set.**

After Full Verify passes and before the review gate, run `/audit-setup`. It prepares the audit
tools `/review-stack` uses: a Lighthouse baseline (median of 3 runs to reduce noise), the axe
accessibility library for Playwright, Playwright's browser dependencies, performance budgets, and
CI gate scaffolding. It is idempotent: a re-run detects a fresh baseline and skips the work when
the build has not drifted.

Run it even when no audit flag is set. It costs seconds when nothing changed and a few minutes on
first install. It guarantees that any later `/review-stack` or `/review-stack --audit`, in this
session or the next, has tooling and a baseline ready.

Note on checklist order: the `audit-setup` row comes before `build` in the checklist. Close it
once before the build starts. This step re-runs the tool to refresh the baseline against the new
code. It does not need a new checklist entry unless the tool's output file changed.

**Failure handling:**

- If `/audit-setup` hits an install error that blocks the build (for example `npm install`
  fails), treat it as a Full Verify failure and surface it to the user.
- If it reports non-fatal warnings (a stale baseline it cannot re-capture right now, a missing
  local env file for the preview URL), note them and go on to Step 6.5. They will not block
  `/review-stack --branch`, but they may block `--audit`.

---

## Step 6.5: Review gate (`--review`, `--audit`, or LARGE)

**Skip if `--no-verify` is set.**

After Full Verify passes, run `/review-stack` for a full independent review. The agent that wrote
the code must not be the only one to review it.

### Standard review (`--review` or LARGE)

```text
/review-stack --branch --plan <plan path from Step 1>
```

To keep the build conversation's context small, run it in a fresh helper agent or a fresh
session instead. The invocation is in `references/perspective-prompts.md` (section "Review gate
invocation").

### Audit review (`--audit`)

If `--audit` is set, run the full audit pipeline instead:

```text
/review-stack --audit --auto --branch --plan <plan path from Step 1>
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

After all tasks are done and all required verification passes:

### 7a: Summary report

Show the tree-format summary. The template is in `references/handoff-format.md` (section
"Summary report").

### 7b: Record the checklist row

Record the `build` row as shown in "Checklist row" above. If verification had open failures,
record `blocked` with the reason. Then run `status` and tell the user the next open row.

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
| Helper agents          | Not supported, for LARGE              | Fall back to the MEDIUM path (sequential batches)       |
| Checklist tool         | `/development-protocol` not installed | Keep the evidence files anyway and report in chat       |
| `/audit-setup`         | Not installed                         | Skip Step 6.4. Note that `--audit` reviews will degrade |

**Minimum viable run:** a bounded change, executed meaningful checks, readable evidence and
an honest remaining-scope report. Missing required proof blocks completion.

---

## Depth summary

| Classification | Checkpoints     | Full Verify     | Context gate     | Perspectives                                   | Audit preflight             | Helper agents | Est. time    |
| -------------- | --------------- | --------------- | ---------------- | ---------------------------------------------- | --------------------------- | ------------- | ------------ |
| BUGFIX         | Regression plus full | Yes | No               | skeptic only                                   | `/audit-setup` (idempotent) | No            | 1 to 5 min   |
| SMALL          | 0               | 1 full          | No               | skeptic, code-quality                          | `/audit-setup` (idempotent) | No            | 5 to 15 min  |
| MEDIUM         | Light per batch | 1 full          | Per batch        | skeptic, code-quality, test-coverage           | `/audit-setup` (idempotent) | No            | 15 to 45 min |
| LARGE          | Delegated       | 1 full          | After collecting | skeptic, code-quality, test-coverage, security | `/audit-setup` (idempotent) | Yes           | 30 to 90 min |

The audit preflight (Step 6.4) runs for every classification, so `/review-stack` always has a
fresh Lighthouse baseline, the axe library and budgets ready. Skip it only with `--no-verify`.
