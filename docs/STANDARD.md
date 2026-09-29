# The AI-native development standard

This is how software work gets done on this team, by people and agents alike. It fits on one page
on purpose. The skills in this repo carry the detail.

## The one rule

**Done means proven.** A step is done when its result is readable, repeatable, and tied to the
file or commit it claims to prove. A plan is not proof. A command that ran is not proof. A green
check from yesterday is not proof of today's commit.

## The spine

Every task flows left to right:

```text
SPEC  ->  BUILD  ->  VERIFY  ->  CLOSE
```

- **Spec.** Pin the goal, then plan it. `/karpathy spec`, which unfolds into `/research-stack`
  when there are unknowns, `/brainstorm-stack`, `/planning-stack`, and
  `/devilsadvocate --premortem`.
- **Build.** `/build-stack` is the one constant at every task size. It loads the plan, works one
  slice at a time, checks after each slice, and sets up repo checks with `/audit-setup`.
- **Verify.** `/karpathy verify` runs `/review-stack`, gets a second opinion from a different
  model or a person, and proves the change on the real thing.
- **Close.** `/closeout-stack` commits, ships, writes the handoff, records lessons with
  `/compound`, and leaves a resume prompt for the next session.

`/development-protocol` walks all four and keeps the checklist. `/pathway` starts each piece of
work and picks the lane.

## Step 1: classify the task (first match wins)

| Size                | Looks like                                                                        |
| ------------------- | --------------------------------------------------------------------------------- |
| Trivial             | Under 10 lines, one file, no design decision: a typo, a rename, a log line        |
| Bug fix             | A bounded fix in one to a few files with a clear way to reproduce it              |
| Feature             | Several files, new behavior a user can see, some design choices                   |
| Big or architecture | Two or more features, crosses systems, changes a schema or contract, hard to undo |
| UI or UX            | Any screen or component a user touches. Combine with the size above               |

When unsure between two sizes, pick the larger. Over-planning a small task costs minutes.
Under-planning a big one costs a rewrite.

## Step 2: run the lane, start to finish

| Size                | Spec                                                           | Build                               | Verify                                          | Close                   |
| ------------------- | -------------------------------------------------------------- | ----------------------------------- | ----------------------------------------------- | ----------------------- |
| Trivial             | skip                                                           | just edit                           | run it and look                                 | `/commit`               |
| Bug fix             | `/planning-stack`                                              | `/build-stack`                      | `/review-stack`                                 | `/commit`, then `/ship` |
| Feature             | `/karpathy spec`                                               | `/build-stack`                      | `/karpathy verify`                              | `/closeout-stack`       |
| Big or architecture | `/research-stack` then `/karpathy spec` then `/devilsadvocate` | `/build-stack --large`              | `/review-stack --audit`                         | `/closeout-stack`       |
| UI or UX            | `/visual-spec` then `/design-stack`                            | `/design-stack` then `/build-stack` | `/design-stack --critique` then `/review-stack` | `/closeout-stack`       |

## The checklist

`/development-protocol` records every piece of work as 17 rows in `.devproto/` inside the repo.
Each row maps to one skill. A row passes only with an evidence file and a verifier command that
exits 0. Conditional rows turn on from the goal's words and must be passed or marked n/a with a
written reason.

| #   | Row         | Skill                         | Required                   |
| --- | ----------- | ----------------------------- | -------------------------- |
| 1   | pathway     | `/pathway`                    | always                     |
| 2   | brainstorm  | `/brainstorm-stack`           | unless trivial             |
| 3   | research    | `/research-stack`             | when the goal has unknowns |
| 4   | spec        | `/karpathy spec`              | unless trivial             |
| 5   | planning    | `/planning-stack`             | unless trivial             |
| 6   | visual-spec | `/visual-spec`                | UI work                    |
| 7   | design      | `/design-stack`               | UI work                    |
| 8   | premortem   | `/devilsadvocate --premortem` | unless trivial             |
| 9   | audit-setup | `/audit-setup`                | unless trivial             |
| 10  | build       | `/build-stack`                | always                     |
| 11  | verify      | `/karpathy verify`            | unless trivial             |
| 12  | review      | `/review-stack`               | always                     |
| 13  | simplify    | `/simplify`                   | unless trivial             |
| 14  | commit      | `/commit`                     | always                     |
| 15  | ship        | `/ship`                       | always                     |
| 16  | compound    | `/compound`                   | unless trivial             |
| 17  | closeout    | `/closeout-stack`             | always                     |

## Gates that apply to every lane above trivial

- **Plan before multi-file work.** Once a plan is approved, build it. Do not ask again at every
  phase boundary.
- **Look at git before the first write.** `git status`, recent history, and the target files.
  Someone may have changed them since you last looked.
- **Verify the real artifact.** The saved row, the deployed page, the measured number. "Tests
  pass" is necessary, not sufficient.
- **The repo carries its own gate.** A pull-request check runs on the head commit with no agent
  present. A repo without one gets `/audit-setup` first.
- **The builder does not grade its own work.** Review comes from a different model family, a fresh
  session, or a teammate.
- **Keep a written ledger on long tasks.** Past about ten steps, write down goal, done, next, open
  questions and constraints, and re-read it at each phase.
- **Unknown is not pass.** A check that could not run is reported as not verified, with the reason.
- **A score is evidence, never permission.** A green check does not authorize a send, a spend, a
  production deploy or an access grant that needs a person.

## Where the rest lives

| Need                                               | Read                                       |
| -------------------------------------------------- | ------------------------------------------ |
| Install and first run                              | `docs/SETUP.md`                            |
| A normal day with the stack                        | `docs/DAILY-USE.md`                        |
| Something is off                                   | `docs/TROUBLESHOOTING.md`                  |
| Changing or adding a skill                         | `docs/PORTING.md`                          |
| The detailed interval, review and evaluation rules | `skills/development-protocol/reference.md` |
