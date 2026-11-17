---
name: relentless
description: A checklist for big "cover everything" jobs, so an agent cannot stop because it feels done. Use it when the work means every file, call site, record, source or check, such as finding every use of something, auditing all of a thing, building a complete list, migrating every reference, or picking up a sweep another session paused. Trigger words include every, all, each, entire, complete list, full audit, sweep, leave nothing out, don't stop until, keep going, and pick up where it left off. Skip it for one lookup, a sample or a quick answer.
---

# Relentless: a checklist for "cover everything" jobs

Agents quit big jobs when they feel done, and that feeling is usually wrong. This
skill swaps the feeling for a checklist: write down every item first, tick each one
off with proof, and say plainly what is left. The user decides when a job is done,
from the numbers.

Skip it for one lookup ("where is `load_config`?"), a sample ("five examples") or an
opinion. A checklist costs time; do not spend it on a small question.

## The tool

`sweep` below means `python3 <relentless skill folder>/scripts/sweep.py`. It needs
Python 3.9+ on macOS, Linux or WSL. Checklists live in the project at
`<repo>/.sweeps/<name>/`. Store options, session ownership and file layout are in
`references/details.md`.

## The steps

1. **Start it, with a finish line you can check.**
   `sweep init --slug <project>-<topic> --goal "..." --done "..."`
   "Every .py file under src/ read" is checkable. "Reviewed well" is not. Add
   `--depth 3` to raise the bar, and `--done-cmd '<check>'` when a command can prove
   the end state; `close` runs it.
2. **List every item first, from a command, not from memory.**
   `sweep add --from-cmd 'git ls-files "*.py"'`. The tool runs it again at the end,
   so items added mid-job still count. An empty list is refused unless you pass
   `--allow-empty`, because it is usually a broken command.
3. **Work through the list.** `sweep next -n 20` gives the next items. Read each one,
   then tick it: `sweep visit <id> --depth 2 --evidence "<what you read or ran>"`.
4. **Write findings down as you go:** `sweep finding "<what is true>" --evidence "<file:line>"`.
   A finding kept only in your head is lost when the chat is.
5. **Skip an item only on purpose:** `sweep defer <id> --why "<reason>"`. Skipping more
   than a quarter of the list means the job was not done.
6. **Finish:** `sweep close`. It refuses while items are open, and checks that every
   file you ticked was really opened. `--force` only on the user's word.
7. **If you must stop:** `sweep checkpoint --why "<reason>"`. A resume note is kept
   current anyway, so a usage limit loses at most one item.

## How deep "done" is for each item

| Depth | Means |
| ----- | ----- |
| 1 | a search hit only: a lead, not proof |
| 2 | read the whole item (the normal bar) |
| 3 | also followed what it connects to |
| 4 | ran or tested it for real |

Use 2 by default, 3 when meaning depends on neighbours, 4 when the question is
"does it work". "Looked fine" is never evidence: name the line, the command or the
output.

## Big lists

Hand batches of 10 to 40 items to helper agents only when each item needs real
reading. Each helper ticks its own items; you open the job and you close it, and you
spot-check a few of their ticks.

## Reporting

End with the line from `sweep status`, such as "47 of 52 read, 3 open, 2 skipped",
then the findings with proof and every skip with its reason. Say "all" or "every"
only after `close` passed without `--force`. If you stopped early, say so and give
the resume note's path.

## Resuming

Asked to continue? Run `sweep status` and read the resume note. Trust the checklist
over your memory of the chat, and build on findings already in it.

## Guides by kind of job

Read the one that fits before step 2:
`references/codebase.md` (files and call sites), `references/lists.md` (companies,
people, records), `references/research.md` (sources on a topic),
`references/audits.md` (checks against a live system), `references/migrations.md`
(every use of an old thing). Everything else, including the optional stop hook,
Codex read proof and how the tool is tested: `references/details.md`.
