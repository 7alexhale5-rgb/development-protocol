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
| Irreversible        | Checked first; overrides size. See below                                          |
| Trivial             | Under 10 lines, one file, no design decision: a typo, a rename, a log line        |
| Bug fix             | A bounded fix in one to a few files with a clear way to reproduce it              |
| Feature             | Several files, new behavior a user can see, some design choices                   |
| Big or architecture | Two or more features, crosses systems, changes a schema or contract, hard to undo |
| UI or UX            | Any screen or component a user touches. Combine with the size above               |

**Irreversible** work is a live-data migration, money movement, customer data leaving its repo,
an external send, or a change to production infrastructure. It runs the big lane plus a named
go-ahead from a person for the step that cannot be undone, however small the diff.

When unsure between two sizes, pick the larger. Over-planning a small task costs minutes.
Under-planning a big one costs a rewrite.

## Step 2: run the lane, start to finish

| Size                | Spec                                                                                     | Build                               | Verify                                          | Close                   |
| ------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------- | ----------------------------------------------- | ----------------------- |
| Trivial             | skip                                                                                     | just edit                           | run it and look                                 | `/commit`               |
| Bug fix             | `/planning-stack`                                                                        | `/build-stack`                      | `/review-stack`                                 | `/commit`, then `/ship` |
| Feature             | `/karpathy spec`                                                                         | `/build-stack`                      | `/karpathy verify`                              | `/closeout-stack`       |
| Big or architecture | `/research-stack --focus devtools,security` then `/karpathy spec` then `/devilsadvocate` | `/build-stack --large`              | `/review-stack --audit`                         | `/closeout-stack`       |
| UI or UX            | `/research-stack --focus ui-ux,a11y` then `/visual-spec` then `/design-stack`            | `/design-stack` then `/build-stack` | `/design-stack --critique` then `/review-stack` | `/closeout-stack`       |

Focus tags aim research at one area. Add `data-infra` to the big lane when a schema or data store
is involved. Launch work runs `/research-stack #launch` (seo, perf, a11y, content). When the
research row turns on, the checklist suggests tags from the goal's words; confirm them at the
research scope gate, never apply them silently.

Work handed to a desktop Project's cloud threads (a coordinator plus threads) instead of a local
session runs this same lane through the `development-protocol` plugin. A person merges after a
second-model review.

### Risk lanes: where a person looks

The size picks the lane. The lane decides which rows carry work and where a person spends
attention.

| Lane                                                    | Rows that carry work                                                                                     | Where a person looks                                                             |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Small (Trivial, Bug fix)                                | The rows the checklist always requires, with verify done by the repo's own CI on the pull request        | Nowhere extra. The pull request merges when CI is green and the rows pass.       |
| Normal (Feature, UI or UX)                              | Small, plus spec, planning, visual spec and design for UI, and one independent reviewer                  | The spec before build and the pull request evidence at merge.                    |
| Irreversible (Big or architecture, or any irreversible step) | Every row                                                                                                | The spec, the pull request evidence, and a named go-ahead for the irreversible step. |

Pick the lane at intake and record it with the goal. A lane can move up mid-task, never down.
Rows outside the lane are made optional at `start` and marked n/a with the reason
`lane: <name>`, so every row stays visible. The rows the checklist always requires (pathway,
build, review, commit, ship, closeout) stay required in every lane.

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
- **File by the map.** Every file the lane creates or moves goes where the project's routing
  table and room `CONTEXT.md` say (`/icm`). Check the layout with its walk test at close.
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
