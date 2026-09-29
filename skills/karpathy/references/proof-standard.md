# What counts as proof

The one definition. Everything in this skill that asks for proof points here instead of restating
it. (The rule was once stated in three files in three different wordings; by 2026-08-04 the copies
had drifted and one cited a rule number that no longer pointed at anything. One rule, one place.)

## The definition

**Proof is an artifact that exists independently of the claim, produced by running the thing, and
read back after the fact.**

Three parts, all required:

1. **A real artifact.** A row in the database, a deployed asset, a file on disk, a measured number,
   captured output. Not a description of one.
2. **An executed check.** The command actually ran: the test, the probe, the fetch, the checklist's
   `--verify` command.
3. **Read back.** Someone looked at what the check produced. A green exit code nobody opened is not
   proof. It is an assumption with a checkmark on it.

And one condition on where the check runs: **proof that only exists while an agent is in the room
expires when the session ends.** For code, the check must also run on the pull request with nobody
present, and the CI check-run on the head commit is what gets read back (see below).

## What is not proof

- **Code changed.** The diff is the claim, never the evidence for it.
- **A document that says so.** A doc is a claim with a date. If it contradicts the running system,
  the doc is stale.
- **A subagent's report.** That is a claim too. Check it against the running system.
- **Silence.** A job that reported nothing may have done nothing. No error is not the same as a
  result.
- **A green number you did not reconcile.** On 2026-08-04 a suite reported "50 passed" while the
  script was being edited mid-run, and "1 failed" for a test whose own log said it passed. Both
  numbers were confidently wrong, in opposite directions. Count the run's own lines and check they
  agree with its summary.

## Why the third part matters most

The first two parts are easy to satisfy and easy to fake by accident. The third is what actually
catches things, and it is the one that gets skipped under time pressure.

Every significant failure found in one audit on 2026-08-04 met parts 1 and 2 and failed part 3:

- a weekly reconciliation job that ran for eighteen weeks, exited 0 every time, and reconciled
  nothing;
- an extractor that wrote nothing while its caller read "nothing returned" as "nothing to save";
- a health check whose verdict changed between runs because it measured the network, not the
  schema.

Each produced an artifact. Each ran. Nobody read the result back.

## Proof that survives the session

Every verifier that runs only while an agent is present (skills, local hooks, review passes,
hand-typed receipts) expires when the session ends. So:

1. **CI is line one; agent review is line two.** A non-trivial repo carries a workflow that runs its
   tests and type check on every pull request, with no agent present.
2. **The tree that runs in production is the tree that carries the proof.** The default branch is
   the production branch, the platform deploys from Git, and a manual CLI promotion is a rollback
   tool, never the normal path.
3. **A receipt is derived, never authored.** Evidence files are written by a measuring script and
   re-checked in CI. The verifiers must be able to fail (a self-test changes each receipt and
   checks the verifier goes red) before they are trusted to pass.

### What it looked like when it failed (measured 2026-09-04, one product repo)

| Symptom                                                   | Measured                                                                                             |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Nine verifier scripts, three browser walks, an a11y suite | zero CI workflow files                                                                               |
| Receipts dated 8 days earlier                             | the quality receipt claimed 115 tests; 5,773 ran                                                     |
| A verifier with an "at least" check                       | a receipt could under-claim forever and still read green                                             |
| A tech-debt verifier counted headings                     | eight dead exports scored the same as eight hundred                                                  |
| Production deployed by CLI from a branch                  | the default branch was 454 files behind what users ran; an outside audit measured the default branch |
| A dependency bot opened a security fix                    | nobody merged it; no required check, no auto-merge                                                   |
| Across a fleet of repos                                   | 17 of 79 ran tests on pull requests                                                                  |

### The minimum set, by repo class

| Repo class        | PR-time gate                                                                | Protection                                      | Prod equals default branch      | Receipts                                       |
| ----------------- | --------------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------- | ---------------------------------------------- |
| throwaway / spike | none required                                                               | none                                            | n/a                             | n/a                                            |
| own product       | `ci`: type check, tests with a coverage gate, build, undeclared deps, audit | require `ci`, no force-push, no branch deletion | deploy from Git, default branch | measured, and re-verified in CI                |
| client / prod     | same, plus auto-merge for patch and minor dependency updates                | same                                            | same, plus a post-deploy probe  | same, plus live receipts re-stamped at release |

`/audit-setup` scaffolds this gate.

### Traps measured while building it

- Read CI status **for the head commit**, not the latest run you can see. A "watch the checks"
  command can reprint a previous run's result.
- CI logs often force colour, so `Tests 5773 passed` arrives wrapped in ANSI escape codes. Strip
  them before reading numbers.
- An automatic dead-code fixer removed exports that auth code and client hooks imported, because
  those files were not declared entry points. Never auto-fix dead code on a dependency graph you
  have not checked; declare the entry points and read the report.
- A push to a preview branch is a build, not a deploy. Log only pushes to the production branch as
  deploys.
- Pin CI actions by commit SHA. A workflow that runs with elevated rights on pull requests is
  acceptable only when it never checks out the pull request's code, and a comment says so.
- Use an unfiltered pull-request trigger with a job-level condition, so a required check never sits
  pending forever on a PR that the path filter skipped.
- No `|| true` and no "continue on error" in a gate. A gate that cannot fail is not a gate.

## Measuring outcomes and strength of proof (design and other substantive work)

Apply this section to all design work through the existing brief and verification
notes. Keep the effort proportional: a small visual edit needs its intended
improvement, relevant source context and affected rendered/interaction checks.
It does not need a full experiment, new scorecard or extra approval round.
Substantive workflows need the full journey, saved-result read-back and recovery
where relevant. Research-only and static artifacts are assessed as those artifacts,
without inventing runtime evidence for features they describe.

### Define success before viewing results

State the user, task, expected usable result, material errors and acceptance
criteria before the candidate is graded. Tie evidence to revision, environment,
input and rubric version. Select relevant library studies, read their source
methods and record which decision they changed. Preserve project identity.
Freeze comparison criteria and held-out cases before candidate outputs are seen.
Measure a comparable baseline before intervention; if changes already happened
or no valid baseline exists, label the work prospective-only and report absolute
acceptance. Do not invent a before/after gain or weaken controls for a baseline.

### Keep critical failures visible

Unauthorized access, lost or silently corrupted data, materially unsupported
claims, wrong material calculations and false completion block acceptance of
the affected scope. Required but untested checks are unknown, never passes.
Do not average these failures away with appearance, speed or a high score.
A score is evidence, never permission to send, spend, grant access or deploy.

### Separate quality from evidence

For a substantive assessment, keep separate rows for research, code,
configuration, data, design/usability and workflow/handoff as applicable.
Quality may be recorded as U (unknown), 0 (fails), 1 (substantial correction),
2 (usable with specified minor correction), or 3 (meets the written criteria
without correction on the assessed case). Link the supporting artifact and
next corrective action. There is no universal weighted score or aesthetic grade.

Describe evidence separately: assertion/plan; inspectable source or local check;
observed complete journey in a named environment; or repeated relevant cases
with independent checking. Controlled fixtures and local-only results remain
labelled. Repeated local checks do not establish an untested live provider.
Automated correctness and model agreement cannot establish human usability.
A top case rating does not mean perfect, generally reliable or release-approved.

### Measure useful outcomes

Choose the smallest relevant set of outcome measures for the task:

- First-pass usable results: fully correct outcomes without unplanned repair,
  divided by all attempted cases, including failures and abandoned cases.
- Human correction effort: time finding and repairing errors per attempted case;
  retain failed cases and distinguish human time from automated work.
- Time to accepted result: elapsed time including retries and correction;
  report unfinished cases separately rather than counting them as fast successes.
- Material errors: cases with material factual, scope, calculation or persistence
  defects divided by all attempted cases.
- Independent handoff success: a recipient unfamiliar with the chat can identify
  the next task, scope, dependencies, access boundaries and acceptance test.
- Cost per accepted result: all attributable run, retry and review costs divided
  by accepted results; undefined when none are accepted. Unknown costs stay unknown.

Set useful improvement targets after baseline measurement and before examining
candidate results. Time or cost gains count only if correctness, boundaries and
user completion do not regress. Report numerator/denominator, case count and run
count separately. For variable AI comparisons, follow the team's eval standard for
repeated fresh runs, paired uncertainty, blind/swapped judgement, untouched cases,
negative controls and judge calibration. Uncalibrated substantive AI ratings are
advisory. A single-project result does not establish cross-project improvement.
Keep essential safety regressions even when both approaches pass; they protect
users rather than distinguish candidates. Repeating deterministic checks is not
an independent sample of user outcomes. Call inconclusive comparisons inconclusive.

### Make failures change the result

Prioritize critical, frequent or costly failures. Reproduce the affected case,
fix its cause, rerun that case and affected regressions, then check fresh cases.
Once a held-out case guides a fix, it becomes a development case; replace it for
the next unbiased comparison. Preserve failures as well as successes. Retest after
changes invalidate evidence. Keep a fix only when the intended outcome improves
without material regressions. Report the next highest-value repair, not a rising
total score. Routing checks verify setup; actual project evidence verifies results.
