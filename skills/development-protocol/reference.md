# Development Protocol reference

The standing rules behind the checklist. Read once per session.

## Standard commands

The full sequence, one line per row, for copy-paste when a session needs the whole flow at once:

```text
/pathway <project> go
/brainstorm-stack
/research-stack <unknowns> --focus <tags>
/planning-stack --deep
/visual-spec
/design-stack
/devilsadvocate --premortem
/audit-setup
/build-stack --review
/review-stack --audit
/simplify
/commit
/ship
/compound
/closeout-stack
```

Skip a row the checklist marks conditional (see the 17-row table in `SKILL.md`) rather than
running it out of habit. This block is a fast-recall aid; `SKILL.md`'s "Invoke" section and the
17-row table are the source of truth for when each row is required.

## The interval loop

| Interval    | Required action                                                                                                                                       | Proof to keep                                                 |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Intake      | Write the goal, user, owner, done condition, risk, and one measurable outcome.                                                                        | A brief with a done condition that can fail.                  |
| Pre-build   | Inspect branch, worktree, dirty files, recent history, target code, and the test commands that exist. Run the repository's own checks if it has them. | A recorded baseline and the chosen verification command.      |
| Build slice | Work in an isolated branch or worktree. Make one small change at a time. Run a focused check after each batch.                                        | The diff plus focused test output.                            |
| Verify      | Run the full local suite, review the diff, get an independent critic, and test the real artifact.                                                     | Test receipt, review result, and a read-back of the artifact. |
| Ship        | Check the exact commit that will merge. Require green CI, the current head SHA, and the repository's release checks.                                  | CI link or receipt tied to that commit.                       |
| Close       | Re-check a fresh copy of merged main, update the handoff, and record unresolved work as unknown.                                                      | Fresh-checkout result and a closeout note.                    |

Every plan, proof, receipt and handoff an interval writes is filed by the project's ICM map: the
routing table, then the room's `CONTEXT.md` Outputs (`/icm`). Checklist evidence stays under
`.devproto/`. Close includes the ICM walk test (`icm_check.py <project>` in the `icm` skill
folder); a broken layout is recorded like any other exception.

No interval is complete because a command ran. It is complete when the result is readable,
repeatable, and tied to the artifact or commit it claims to prove.

The repository's own documented test and release commands always win over any example here.

## Risk lanes

The task size from `docs/STANDARD.md` picks one of three lanes. The lane decides which rows carry
work and where a person looks.

| Lane                                                         | Rows that carry work                                                                                                | Where a person looks                                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Small (Trivial, Bug fix)                                     | The always-required rows (pathway, build, review, commit, ship, closeout), with verify done by the repo's own CI on the pull request | Nowhere extra. The pull request merges when CI is green and the rows pass.           |
| Normal (Feature, UI or UX)                                   | Small, plus spec, planning, visual spec and design for UI, and one independent reviewer                             | The spec before build and the pull request evidence at merge.                        |
| Irreversible (Big or architecture, or any irreversible step) | Every row                                                                                                           | The spec, the pull request evidence, and a named go-ahead for the irreversible step. |

Irreversible means a live-data migration, money movement, customer data leaving its repo, an
external send, or production infrastructure. It is checked first and overrides size, however
small the diff.

Pick the lane at intake and record it with the goal. At `start`, pass `--optional <row>` for each
row outside the lane, then mark it `na` with the reason `lane: <name>`, so every row stays
visible. The always-required rows cannot be made optional, so they carry work in every lane. A
lane can move up mid-task, never down: when it moves up, record the rows the new lane adds with
real evidence (a row marked `na` can be recorded again with `--result pass`).

## Permission mode

If your agent has a classifier-based auto mode (Claude Code's auto mode reviews each action in
place of a prompt), it can be the default for every interval. Other agents keep their own
approval settings. The rules below hold either way.

- Build and verify run without prompts. The classifier still blocks force pushes, secret leaks,
  data leaving the trusted boundary, and production changes. Never use a bypass-all-permissions
  mode outside a throwaway sandbox.
- Ship: on every repo that deploys, `main` changes only through a pull request. Enforce it with
  branch protection or rulesets, then push to a branch and open a pull request. Merging with a
  failing required check (an admin override) needs a person to name that pull request.
- A production deploy, a remote migration, or a production environment change runs only when a
  person named that project and action. Otherwise the step stops and is recorded as waiting on
  them.
- External sends (email, chat, calendar invites) stay behind the team's own guard. Hooks run
  before the classifier, so auto mode never loosens that rule.
- A denial is an exception, recorded like any other. Fix it one of three ways: an environment
  entry for a place the team trusts, an allow rule for a routine command, or a person stating
  intent for a one-off. Never route around a denial with a different command shape.
- In Claude Code, auto mode rules are read from the user settings file, not from a project's
  `.claude/` folder. After any change run `claude auto-mode critique` and
  `claude auto-mode config`.

## Independent review

The builder does not grade its own work. Options, strongest first:

1. A different model family reads the diff and the proof (for example Claude builds, Codex or
   another provider reviews, or the reverse).
2. A fresh session of the same model with only the diff, the spec and the test output.
3. A teammate.

Ask the reviewer for findings ranked by severity, each with a concrete failure case. Record every
finding and what happened to it: fixed, rejected with a reason, or deferred with an owner.

An evidence-backed no-findings review is valid. Never demand findings or retry merely because
a review is clean. Fix confirmed material defects and obtain an updated independent review
after a substantive correction. Bind reviews to the complete recorded baseline-to-candidate
diff. Changed evidence requires fresh proof, not automatic reapproval of unchanged scope.

## Evaluation standard

Use this whenever the work claims one version is better than another (a prompt, a model, a
ranking, an agent loop).

- 5 runs per arm for a decision. 3 is the minimum for exploring.
- Report pass@k (can one run succeed) and pass^k (did all k succeed).
- Use paired bootstrap confidence intervals. State the smallest effect the test could detect.
- Freeze the task set, grader, rubric and scoring code before the final run.
- Keep a holdout set and a negative control. Drop cases that cannot tell the versions apart.
- When a judge compares two outputs, hide which is which and swap their order.
- Calibrate semantic judges against independent labels. Bind calibration and scored judgments
  to the same observed judge model, rubric and complete judgment configuration.
- If the instrument, rubric, prompt or scorer changes, the old comparison is void. Re-run it.
- Missing output, timeout, refusal and malformed output are outcomes. Never count them as passes.

## Design and UI proof

Scale this to the task. A small visual edit needs the intended improvement and the affected
screens checked. A full workflow needs the whole journey, a read-back of what it saved, and the
recovery path.

- Define the user, the task, the usable result and the acceptance criteria before looking at the
  candidate.
- Measure a baseline before changing things. If no valid baseline exists, say the result is
  "prospective only" and report absolute acceptance. Never invent a before-and-after gain.
- Check the rendered result at desktop and phone widths, with keyboard only, and in each state:
  empty, loading, error, full.
- Record quality per area (code, data, design, workflow) as U (unknown), 0 (fails),
  1 (needs substantial correction), 2 (usable with a named minor fix), or 3 (meets the written
  criteria on the case tested). No single blended score.
- Keep evidence strength separate from quality: a plan or claim; a local check; a full journey
  observed in a named environment; repeated cases checked independently.

## Exceptions

`--no-verify`, skipped tests, missing CI, and unavailable third-party smoke tests are exceptions.
Write down the reason, scope, owner and next proof in the handoff. Missing required checks
block completion and shipping. An exception never creates a pass.


## Verifier commands and commit receipts

Verifiers run with Bash pipeline failure checks: `false | tee check.log` fails.
Timeouts still stop the full verifier process group. Bash must be on PATH.
The stored command is redacted and paired with a SHA-256 digest of the original.
Use environment-variable references for credentials instead of inline secret values;
redaction is a safeguard, not a way to store secrets. Existing command and output
fields are scrubbed when their checklist is refreshed; older Git history is unchanged.

The commit row and later release rows bind their proof to Git HEAD and branch.
Status and check reopen those rows after either changes. Earlier plan and build
rows remain valid unless their evidence or instruments change. Record commit proof
after committing, with a verifier that only reads the commit. Old Git release
receipts without this binding must be verified again. Non-Git folders remain usable.

## Optional Superpowers methods

These methods support the existing rows. Load installed skills on demand. Availability is
optional; missing required proof remains a gap. This contract governs conflicting vendor menus,
finding quotas, fan-out, cleanup and skipped final reviews.

| Method | Existing row or interval | Use and evidence |
| --- | --- | --- |
| using-superpowers | pathway | Select methods once; record execution choice and existing authority. |
| brainstorming | brainstorm / spec | Resolve unclear goals while preserving settled decisions. |
| writing-plans | planning | Name ownership, dependencies, interfaces, decisions and acceptance checks. |
| executing-plans | build | Run small or coupled tasks with focused checks and retained progress. |
| subagent-driven-development | build | Separate tasks with distinct specification and quality verdicts. |
| dispatching-parallel-agents | research / build / review | Independent investigations or isolated changes with no shared-state conflicts. |
| test-driven-development | build | Observe intended failure, implement minimally, pass tests, then refactor. |
| systematic-debugging | any failed row | Reproduce, trace cause and test one hypothesis. Reassess after three failed attempts. |
| requesting-code-review | verify / review | Review the complete baseline-to-candidate diff, requirements and proof. |
| receiving-code-review | review | Reproduce findings; retain test-first fixes or evidence-backed dismissals. |
| verification-before-completion | every row | Executed checks and readable results tied to the artifact. |
| using-git-worktrees | pre-build | Inspect and reuse isolation; preserve dirty work, unique commits and rewritten history. |
| finishing-a-development-branch | commit / ship / closeout | Authorized integration, exact-head CI and fresh-main proof before cleanup. |
| writing-skills | compound | Real task and pressure trials, held-out cases and negative controls. |
| diagnosing-superpowers | review / compound | Cite session evidence for repeated failures, cost or delay. Keep external reports as local drafts. |

Default to native execution for small or coupled work. Use subagent-driven development for
separable tasks with stable interfaces and independent acceptance checks. Use at most two
children, no nested delegation, explicit ownership and bounded briefs. The root reviews actual
changes and aggregate checks. Interrupt completed children. Dependent tasks run sequentially.

Use vendor task-brief, review-package and progress helpers only when installed and verified;
they are not bundled here. Record the actual task baseline, not HEAD~1 for a multi-commit task.
Retain complete test receipts and resume state. Helper output supports the existing checklist.
Inspect duplicate plugin identities before changing either; evaluate vendor updates in isolation
and use supported installation mechanisms, never cache edits. Evaluate Superpowers 6.4.2's lean
plans without implementation code; availability and reported benchmarks do not prove local benefit.

Behavior changes and bug fixes require red-green-refactor. Start behavior-preserving refactors
with characterization checks. Copy, generated output, nonbehavioral configuration and throwaway
probes use the smallest meaningful validator, with a reason. Preserve existing work and failed
evidence. Missing tools stay unmeasured. After three failed debugging attempts, reassess the
cause; ask the owner only for missing access or decisions.

## Bounded improvement contract

Use one candidate lineage per cycle, at most three revisions, in isolation. Retain rejected
trials and costs; do not reset limits by renaming the work. Freeze baseline, cases, holdout,
negative controls, acceptance tests, grader, scorer, observed models, tool versions, account,
currency, spending and runtime caps before scored trials. Select candidates from confirmed
failures, rejected reviews, drift and measured costs. State one hypothesis and outcome measure.

Run five trials per comparison arm. Retain raw worker and grader output, identity, timestamps,
failures, refusals, missing output, timeouts and settled costs. Require positive paired 95%
confidence intervals excluding zero on both the primary and held-out comparisons, unchanged
negative controls, and no safety failures or correctness regressions. Report detectable effect,
pass@k and pass^k. Missing output and unavailable or uncalibrated judges cannot pass. Instrument
changes invalidate the comparison pool. Candidates cannot edit their tests, scoring or authority.

Require two independent reviews of the exact candidate and executed behavior checks. Rehearse
candidate, rollback and restoration on one isolated target; preserve distinct backups and
readbacks. Reconcile all calls across revisions, judges and critics against a current verified
account budget. A fresh verified balance may replace an expired snapshot without changing
sealed trials, reviews or costs. Unknown costs stay unmeasured; do not repeat spending on resume.

**Measurement capability:** this package records evidence and verifier results using
`devproto.py`; it does not include an executable measurement validator or authorize adoption.
Measured adoption requires an adapter your team installs, independently reviews and proves
against this contract using the existing checklist. Keep proposed improvements unproved
until that adapter supplies the required bindings. Ordinary truthful retrospectives may
complete; a goal, brief or owner request naming adoption or promotion requires proof and
remains blocked without it. Do not create another status ledger.

Review instruments independently before freezing them. Bind executable dependencies;
unsupported closures remain unmeasured. A plan, statistical score or synthetic fixture is not
proof of real agent improvement. Only proved reversible changes within existing authorization
may be adopted. Sends, spending, permissions, secrets, production, destructive actions, model
defaults and vendor updates retain their existing rules. Verify the installed result and restore
the retained baseline if its acceptance check fails.

Run after verified closeout or through a scheduled retrospective your team already runs. Preserve its cadence;
never duplicate schedules. Track dated primary OpenAI, Google, Microsoft, GitHub, browser tools,
Lighthouse and actual dependency sources. Record release date/channel, local availability,
tested compatibility and measured benefit separately. A preview or announcement is not runtime proof.
