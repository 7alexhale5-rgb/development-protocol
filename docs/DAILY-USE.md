# A normal day with the stack

## Morning: pick up where you left off

```text
/development-protocol . status
```

Or paste yesterday's resume prompt into a fresh session and run `/development-protocol . resume`.

## Starting new work

1. Write a prepared prompt: goal, who it is for, what done looks like, links, constraints.
2. Run `/development-protocol . "<goal>"`.
3. Let the spec half (pathway through premortem) run properly. Answer its questions. This is where
   the result is decided.
4. Let the build run its three to five phases without interrupting.
5. Read the review. Every finding gets fixed or answered.

## By task size

| Task                  | Do this                                                                            |
| --------------------- | ---------------------------------------------------------------------------------- |
| Typo, one line        | edit, run it, `/commit`                                                            |
| Bug fix               | `/development-protocol . "Fix <bug>"` (it skips what a small fix does not need)    |
| Feature               | `/development-protocol . "<feature>"`                                              |
| Big or risky          | `/research-stack` first, then `/development-protocol`                              |
| A screen or component | the protocol turns on `/visual-spec` and `/design-stack` from UI words in the goal |

## Running several things at once

- One primary session per effort; worker sessions per component, each with a handoff prompt, each
  reporting back to the primary. See `docs/WORKFLOW.md` section 3.
- Give each concurrent worker its own worktree or clone and its own branch. Branch names
  alone do not isolate a shared checkout. Say in the team chat what you are changing.

## Before you stop

```text
/closeout-stack
```

It commits, checks CI, writes the handoff, records lessons, and prints a resume prompt. Copy it.

## Handy commands

| Command                               | What it does                                                |
| ------------------------------------- | ----------------------------------------------------------- |
| `/pathway . next`                     | what to work on next                                        |
| `/karpathy spec` / `/karpathy verify` | pin the goal / prove the result                             |
| `/review-stack --audit`               | full review with runtime checks                             |
| `/relentless`                         | exhaustive sweeps with a coverage ledger                    |
| `/1pct`                               | stop hedging on approved work and do the next step          |
| `/compound`                           | what we learned this week                                   |
| `/compound --metrics global`          | cross-project retro over every repo under one parent folder |

`/compound --metrics global` writes its comparison snapshots outside any one repo, at
`~/.devproto/retros/global-<date>-<seq>.json` in your home folder, because the retro spans many
projects and no single `.devproto/` owns it. It reads the last 5 snapshots back to show trends
week over week. Nothing else in this stack writes outside a project's own `.devproto/` folder.
