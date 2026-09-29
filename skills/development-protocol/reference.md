# Development Protocol reference

The standing rules behind the checklist. Read once per session.

## Standard commands

The full sequence, one line per row, for copy-paste when a session needs the whole flow at once:

```text
/pathway <project> go
/brainstorm-stack
/research-stack <unknowns>
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

No interval is complete because a command ran. It is complete when the result is readable,
repeatable, and tied to the artifact or commit it claims to prove.

The repository's own documented test and release commands always win over any example here.

## Independent review

The builder does not grade its own work. Options, strongest first:

1. A different model family reads the diff and the proof (for example Claude builds, Codex or
   another provider reviews, or the reverse).
2. A fresh session of the same model with only the diff, the spec and the test output.
3. A teammate.

Ask the reviewer for findings ranked by severity, each with a concrete failure case. Record every
finding and what happened to it: fixed, rejected with a reason, or deferred with an owner.

## Evaluation standard

Use this whenever the work claims one version is better than another (a prompt, a model, a
ranking, an agent loop).

- 5 runs per arm for a decision. 3 is the minimum for exploring.
- Report pass@k (can one run succeed) and pass^k (did all k succeed).
- Use paired bootstrap confidence intervals. State the smallest effect the test could detect.
- Freeze the task set, grader, rubric and scoring code before the final run.
- Keep a holdout set and a negative control. Drop cases that cannot tell the versions apart.
- When a judge compares two outputs, hide which is which and swap their order.
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
Write down the reason, scope, owner and next proof in the handoff. An exception lowers
confidence. It does not create a pass.
