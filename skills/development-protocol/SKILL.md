---
name: development-protocol
description: Run any software work through one proof loop that sequences the whole stack, pathway, brainstorm, research, spec, planning, visual spec, design, premortem, audit setup, build, verify, review, simplify, commit, ship, compound and closeout, with a checklist that only passes a row when an evidence file exists and a verifier command exits 0. Use when starting, resuming or checking any feature, bug fix, refactor or release; when someone says "run the development protocol", "build this properly", "take this start to finish", "is this done", "is it ready to ship", "what's left"; or when you want consistent results instead of typing six slash commands. Skip it for questions that change no code.
---

# Development Protocol

One rule runs through every row: **a row is done when its result is readable, repeatable, and tied
to the file or commit it claims to prove.** A plan is not proof. A command that ran is not proof. A
receipt from yesterday is not proof of today's commit.

This skill is the conductor. Each row hands off to a bundled skill that owns the method. You do not
have to remember the slash commands or their order; this skill runs them in sequence, records proof
after each one, and reports back.

Read these once per session:

- `reference.md` in this folder: the interval table, review rules, evaluation standard, UI proof.
- `docs/STANDARD.md` and `docs/WORKFLOW.md` in the repo you installed from, if present.

## Invoke

```text
/development-protocol <project folder> "<goal>"
/development-protocol <project folder> resume
/development-protocol <project folder> status
/development-protocol <project folder> loop <n> "<what to improve>"
```

If no folder is given, use the current repository. If no goal is given, ask for one sentence that
names who it is for and what "done" looks like.

## Before the first row: prepare

Most of the result comes from preparation. Before `start`:

1. Gather context: what exists, what was tried, links, constraints, who it is for.
2. If the goal depends on facts you do not hold, say so. The research row will run.
3. Survey git: `git status`, `git log --oneline -20`, the target files. Another session may have
   changed them.

## The checklist tool

It lives next to this file at `scripts/devproto.py`. Python 3.9+, standard library only. Below,
`DEVPROTO` means `python3 <folder containing this SKILL.md>/scripts/devproto.py`.
`--project` and `--json` go before the subcommand.

```text
DEVPROTO --project <repo> start --goal "<goal>" [--id <id>] [--require <row>] [--optional <row>]
DEVPROTO --project <repo> status --id <id>
DEVPROTO --project <repo> step --id <id> --step <row> --result pass \
    --evidence <file> --verify "<command that only reads it>" [--instrument <test file>]
DEVPROTO --project <repo> step --id <id> --step <row> --result na --reason "<why>"
DEVPROTO --project <repo> step --id <id> --step <row> --result blocked --reason "<what>"
DEVPROTO --project <repo> check --id <id> [--through <row>]
DEVPROTO steps           # the 17 rows and the skill for each
DEVPROTO --project <repo> list
DEVPROTO --project <repo> doctor
```

How it behaves:

- Rows pass in order. A row cannot pass while an earlier row is open.
- `pass` runs the verifier in the project folder with no input. Exit 0 passes; anything else is
  recorded as `blocked` with the exit code and the last 2,000 characters of output. A timeout kills
  the verifier and everything it started.
- That stored `output_tail` is redacted before it is written, because the work item's JSON file
  under `.devproto/` is git-trackable by default: `_shared.py` `redact()` replaces anything that
  looks like an API key, GitHub or Slack token, AWS key, bearer token, or private-key block with
  `[REDACTED]` first, then the result is truncated to 2,000 characters. Redaction runs on both
  `devproto.py` and `pathway.py`. It is a pattern match, not a guarantee: a secret in a shape the
  patterns do not cover can still leak into a verifier's failure output, so treat `.devproto/`
  files as reviewable before sharing or committing them, not as pre-cleared.
- The evidence file and each `--instrument` file are fingerprinted. If one changes later, that row
  and every later passed row reopen. Pass the test file or grader as an instrument so a weakened
  test cannot keep an old pass. Re-recording an earlier row with new evidence also reopens later
  passed rows.
- Write the evidence first, then verify it with a command that only reads it. A verifier that
  rewrites its own evidence is recorded as blocked.
- Required rows cannot be marked n/a. The goal's words set which rows are required, and `start`
  prints which word changed which row. Fix a wrong match at `start` with `--require` or `--optional`.
- Evidence inside the project is stored with relative paths so the checklist works on any clone.
  Put evidence in `.devproto/evidence/` unless the project has its own place. The tool writes
  `.devproto/.gitignore` for its own lock and temp files.
- It is a guard against claiming "done" by accident, not against deliberate tampering. `status`
  prints each row's verifier so a person can see a weak one (like `true`).

## The 17 rows

Run each row by invoking its skill, then record the row. Where a row does not apply, mark it n/a
with a reason; do not skip silently.

| #   | Row         | Skill                         | Required          | Good evidence and verifier                                                                                       |
| --- | ----------- | ----------------------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------- |
| 1   | pathway     | `/pathway`                    | always            | work brief with goal, user, owner, done condition, risk, one number; `grep -q "Done when" <brief>`               |
| 2   | brainstorm  | `/brainstorm-stack`           | unless trivial    | decisions and open questions; grep for the decisions heading                                                     |
| 3   | research    | `/research-stack`             | goal has unknowns | cited report (pass the suggested `--focus` tags); `validate_report.py structure`                                 |
| 4   | spec        | `/karpathy spec`              | unless trivial    | the failing acceptance test or spec file; run it and expect the planned failure; pass the test as `--instrument` |
| 5   | planning    | `/planning-stack`             | unless trivial    | the plan with 3 to 5 phases, each with a gate number; grep for the phase table                                   |
| 6   | visual-spec | `/visual-spec`                | UI work           | the spec pack; its check script exits 0                                                                          |
| 7   | design      | `/design-stack`               | UI work           | design notes and screenshots at desktop and phone width                                                          |
| 8   | premortem   | `/devilsadvocate --premortem` | unless trivial    | failure table with a guard per row                                                                               |
| 9   | audit-setup | `/audit-setup`                | unless trivial    | CI and quality config in the repo; its status check                                                              |
| 10  | build       | `/build-stack`                | always            | the diff; the focused tests                                                                                      |
| 11  | verify      | `/karpathy verify`            | unless trivial    | second-model critic result plus the real-artifact read-back                                                      |
| 12  | review      | `/review-stack`               | always            | review report; the full suite                                                                                    |
| 13  | simplify    | `/simplify`                   | unless trivial    | simplify report; the full suite                                                                                  |
| 14  | commit      | `/commit`                     | always            | commit record; compare it to `git rev-parse HEAD`                                                                |
| 15  | ship        | `/ship`                       | always            | merge SHA and CI link; `gh pr checks <n>` or your CI's CLI                                                       |
| 16  | compound    | `/compound`                   | unless trivial    | the learnings note                                                                                               |
| 17  | closeout    | `/closeout-stack`             | always            | handoff with Proven and Unknowns; tests on fresh main                                                            |

"Trivial" means the goal says typo, copy edit, one-line, trivial or tiny fix. UI words turn on
visual-spec and design. Words like research, unknown, investigate, evaluate, compare, regulation or
spike turn on research. When research is on, `start` and `status` also suggest focus tags from the
goal (for example `/research-stack --focus ui-ux,a11y` for UI work, `--focus devtools,security`
for architecture, `#launch` for a launch); pass them through. Before each row, run `status` and act
on `next_step`.

**A local-only repo (no `origin` remote, no pull request) cannot reach 17/17 pass, by design.**
`ship`'s verifier is a PR check (`gh pr checks <n>` or equivalent); with no remote there is no pass
path, only `blocked` with a reason. Rows must close in order, so that correctly blocks `compound`
and `closeout` too. This is not a bug in the tool or a broken run -- it is what "the checklist
proves the real thing happened" means. Push a branch and open a pull request to unblock rows 15 to
17; until then, `check` (rows 1 to 14) is the honest stopping point.

## How to run it

1. `start` the work item. Read the rule notes it prints and fix wrong matches now.
2. Rows 1 to 8 are the spec half. Do them properly; they decide most of the outcome. Use the
   strongest model available for these rows.
3. Build in three to five phases, never more. Each phase ships one runnable thing against its gate
   number. Do not stop to show partial work between phases unless blocked.
4. If the work splits into independent components, write one handoff prompt per component and run
   them as separate sessions or subagents that report back here. Each worker commits only its own
   files on its own branch.
5. Rows 11 and 12 need a reviewer that did not write the code: a different model family, a fresh
   session with only the diff and spec, or a person. Record which one reviewed.
6. Before merge, gate with `check --through commit`. Rows `ship`, `compound` and `closeout` can only
   be proven after the merge.
7. At the end, `check` must exit 0. Answer "is it done?" from `check`, never from memory.

## Loop mode

`/development-protocol <repo> loop <n> "<what to improve>"` runs the protocol again on the same
target up to n times (5 to 10 is typical). Each pass: review what exists, list gaps, errors and
simplifications, research the gaps, fix them through the rows, and record a new work item with the
id `<base>-loop<k>`. Stop early when a pass finds nothing worth fixing, and say so.

## If context runs low

Before a session runs out of room, write a resume prompt into `.devproto/handoffs/`: goal, work id,
rows done, next row, open questions, constraints, the exact files. Print it in a code block for the
person. A fresh session runs `/development-protocol <repo> resume` and continues from `status`.

## Rules that do not bend

- **Unknown is not pass.** A check you could not run is `blocked` or open, with the reason. Tell the
  person "not verified". Do not round it up.
- **Exceptions lower confidence; they do not create a pass.** Skipped tests, `--no-verify`, missing
  CI or an unavailable third-party service each get a written reason, scope, owner and next proof in
  the handoff.
- **Tie proof to the artifact.** Name the commit SHA, file, URL or environment.
- **Critical failures block the scope they touch.** Unauthorized access, lost or silently corrupted
  data, wrong money math, claims the evidence does not support, and false completion cannot be
  averaged away.
- **A score is evidence, never permission.** A green check does not authorize a send, a spend, a
  production deploy or an access grant that the team's rules reserve for a person.
- **Try three genuinely different approaches before reporting blocked**, and name the one thing
  still blocking.

## Report

After each row and at the end, give a short plain summary: what changed, what was proven and how,
what is still unknown, and the next row. Name real things ("the login test passed on commit
a1b2c3d"), not row numbers.

## Verify the install

```text
DEVPROTO --project <repo> doctor
```

Every `PASS` line should pass. `WARN skill_installed:<name>` means a stack skill is not installed
beside this one; install the full repo. `WARN project_is_git_repo` means the folder is not a git
repository; the checklist still works, but ship and closeout need other verifiers.
