---
name: icm
description: Files every project file by the ICM folder method (Interpretable Context Methodology), so a path tells an agent what a file is for and it loads only the context the task needs. A root CLAUDE.md router with a routing table, one CONTEXT.md contract per room with Inputs, Process, Outputs and Human check, six workspace forms, naming rules, and a stdlib checker for the walk test (exit 0 holds, 1 broken, 2 could not measure). Use whenever an agent creates, moves, renames or files anything inside a project, such as plans, proofs, research, notes, exports, scripts or drafts; when someone asks "where does this file go", "file this", "organize this repo", "set up the project map", "add a routing table", "write a CONTEXT.md", "is the folder layout right", "run the walk test" or "ICM"; when a new folder or room is needed; and at closeout to prove the layout still holds. Skip it for files whose location a tool fixes, such as package manifests and entry points.
---

# ICM: where every file goes

The idea in one line: **the folder is the architecture.** A path tells the agent what a file is
for, so it loads only the context the task needs.

This skill is the one home for the folder rules in this stack. Other skills point here and never
restate them. The method is the Interpretable Context Methodology (ICM), also published as the
Model Workspace Protocol (MWP): "Interpretable Context Methodology: Folder Structure as Agentic
Architecture", Jake Van Clief and David McDermott, arXiv 2603.16021. Read the paper before
arguing with a rule. The `NN_kebab-name` stage names, the `_` meta prefix, the line limits and the
walk test come from the method's own repos and talks; looser versions of it circulate too.

## When this applies

Every time an agent creates, moves, renames or files anything inside a project: code notes,
plans, proofs, research, exports, scripts, drafts. Note collections are projects too; their
`CLAUDE.md` is the map. Outside a project (a folder that holds many projects), your team's own
filesystem rules govern; inside a project, this does.

## The layers

1. **Router: `CLAUDE.md`** at the project root, with `AGENTS.md` a symlink to it (one copy,
   read by both Claude Code and Codex). A project whose agents read only one of the two may
   keep just that file as the map; the walk test accepts either and warns when `CLAUDE.md` has
   no `AGENTS.md` beside it. Add the symlink when both agents work in the project. Two or three
   sentences on the work, then where to go: a routing table (`| Task | Go to | Read | Skills |`)
   or a "Where to go" list of `*/CONTEXT.md` links, plus the naming convention. Aim for about
   60 lines; past one screen, room content is hiding in it.
2. **Workspace context: root `CONTEXT.md`** when the project has three or more rooms: purpose
   and boundary, the chosen form and why, how a run or record starts, stable versus changing
   material, where status is recorded, and the first useful test.
3. **Rooms: one `CONTEXT.md` per working folder.** One folder, one job. A room is one mental
   mode: if you think differently doing two kinds of work, they are two rooms. If you are not
   sure something deserves its own room, it does not.
4. **Tools: skills**, wired into the routing rows that need them. Write a skill only when a
   task repeats.

## The room contract

Every room `CONTEXT.md` is at most 80 lines and has these four headings:

- `## Inputs`: working inputs for this run and stable reference inputs, each with an exact
  path; the entry condition; what to do when an input is missing (stop, ask, or write NOT FOUND).
- `## Process`: numbered, concrete actions on the named inputs.
- `## Outputs`: each output's exact path, format and required fields.
- `## Human check`: who compares what against which source, what pass means, what happens on
  failure, and where the pass is recorded. A generated file existing is not approval.

Spend about 80% of the text on the work and 20% or less on telling the agent how to behave.

A blank room contract to copy:

```markdown
# <Room name>: <one job>

One job: <what this room produces>. Paths relative to the project root.

## Inputs

- `<path>`: <what it is>. Missing: <stop | ask | write NOT FOUND>.

## Process

1. <concrete action on a named input>.

## Outputs

- `<path>`: <format and required fields>.

## Human check

<Who> compares <what> against <which source>. Pass: <condition>. Fail: <what happens>.
Recorded in <where>.
```

## Pick the form (six)

| Form             | Use when                                                  | Shape                                                                                                                                                 |
| ---------------- | --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pipeline         | A repeatable sequence produces a deliverable each run     | `NN_kebab-name` stages at natural review points; each stage's output is the next one's input; a `{run-id}` keeps runs apart. Example: an audit engine |
| Record library   | The same client, case or project accumulates over time    | One same-shaped folder per record, from a template                                                                                                    |
| Knowledge bundle | The output is connected knowledge                         | A small topic router and linked notes with source pointers; no invented sequence                                                                      |
| Umbrella         | Several different workflows share a small reference layer | Each workflow gets its own router and contracts; shared rules are linked, not copied                                                                  |
| Context map      | Who does what and where responsibilities meet             | Typed cards for real teams, processes and data sources. Example: a field-service operation                                                            |
| System map       | An existing folder or repo people or agents edit          | Rooms mapped to the real objects and their source paths. A code repo uses the developer tree: `planning/`, `src/`, `docs/`, `ops/` rooms              |

Compose forms only when the work proves the need. If one input, one instruction and one check
carry the job, a saved prompt is the right answer, not a workspace.

## Conventions

1. **Numbering expresses sequence only.** Never number unrelated topic folders as if they were
   steps. Numbered responsibility rooms are a known anti-pattern; do not copy them.
2. **Factory versus product.** Stable rules, formats and examples go in `_reference/`; blank
   templates in `_templates/`; changing artifacts in their working room. Meta folders start
   with `_`.
3. **One home per fact.** Everything else links to it.
4. **Links point one way.** A room links down to its files and across to `_reference/`; a file
   does not link back up to the room that names it.
5. **Docs over outputs.** Agents learn a pattern from a written doc, never from an earlier
   output.
6. **Every arrow has a verb.** A room reads, uses or writes each file it names.
7. **Status lives in the file:** YAML such as `review_status: pending|reviewed`, reviewer, date.
   Generate an index from those fields; never keep a second hand-written status list.
8. **Naming:** `NN_kebab-name` for stages, kebab-case files, `YYYY-MM-DD-slug.md` for dated
   files, status or version as a suffix (`demo-script_v2.md`). The project's map states its
   choice.
9. More than 8 to 10 files at one level means subfolders. Root files that tooling requires do
   not count.
10. Markdown past about 100 lines is usually two files. Reference files stay under 200.
11. **Tooling paths stay put.** Source packages, manifests, entry points named by a tool
    registration or a scheduler config, and public README or docs links stay where their tools
    expect them. A room routes to them; it does not move them.
12. **`.planning/`** holds tool state in a staged repo (an approval-bound `PLAN.md`, pathway and
    protocol status). Elsewhere it is the planning room with its own contract. Brainstorm notes
    are `.planning/BRAINSTORM.md`, never `CONTEXT.md`, which is reserved for room contracts.
13. **Context files are living.** The change that adds, moves or retires a file also updates its
    room's `## Outputs` and, when needed, the routing row.

## Filing any file: the every-file rule

1. Read the router and pick the room.
2. Read that room's `CONTEXT.md`; put the file where its `## Outputs` say.
3. No room fits: do not drop it at the root. Extend the nearest room's outputs, or add a room
   (a new mental mode) with its routing row, in the same change.
4. No router yet: create `CLAUDE.md` with its routes (and the `AGENTS.md` symlink) before filing
   anything else, and say so in the reply.

## What counts as a project, and where side checkouts go

Recorded 2026-09-30, after a rollout across many repos found each of these cases.

- A project root is the nearest folder with its own `CLAUDE.md`, `AGENTS.md` or `.git`, never a
  container folder that only groups projects. Not projects, even though they may carry a
  `CLAUDE.md`: `templates/` and `profiles/` subtrees (scaffold templates, agent profiles),
  `fixtures/` and `proof/` folders, `*-worktrees` containers and `*-wt` side checkouts, and
  `_`-prefixed meta folders.
- A repo someone else depends on takes ICM edits on a branch (for example `chore/icm-layout`) in
  a side checkout, never on the live tree. Put the checkout at `<repo>-worktrees/icm-layout`
  beside the repo. Move a checkout only with `git worktree move`.
- Names are compared case-exact. On a case-insensitive filesystem (the macOS default)
  `context.md` and `CONTEXT.md` are the same file, so a lowercase `context.md` in a room blocks
  the contract: rename the note first (`git mv`), then write the contract.

## Moving an existing tree

Inventory first. Find every internal and external reference (scheduler configs, tool
registrations, docs, scripts, other repos). Check case-insensitive collisions at each
destination. Present the exact old-to-new map for the owner's approval, then copy and verify
before removing anything. Never archive an apparently unused file without checking its
consumers.

## Done means the walk test

A fresh agent with no memory can reach the first task from the router plus at most two reads,
knows each contract's inputs, action, output path and review condition, and can tell "created"
from "reviewed" from the files alone. Measure what a script can:

```text
python3 <icm skill folder>/scripts/icm_check.py <project-root>          # human report
python3 <icm skill folder>/scripts/icm_check.py <project-root> --json   # one JSON object
```

Exit codes: **0** the layout holds, **1** something is broken, **2** could not measure (no such
folder, or a folder or guide could not be read). Warnings (a long map, a crowded folder, a
missing `AGENTS.md`) never change the exit code. A 2 is not a pass: report it as not verified.

It checks:

- the map exists (`CLAUDE.md` or `AGENTS.md`) and routes somewhere: a routing table whose data
  rows name a path, or a "Where to go" list naming a room `CONTEXT.md` (or the root
  `CONTEXT.md` carries the routing);
- `AGENTS.md`, when present, is a readable map or points to `CLAUDE.md` (a dangling symlink is
  an error);
- every room `CONTEXT.md` has the four contract headings outside code fences and fits in 80
  lines;
- stage folders (`NN_...`) are named `NN_kebab-name` and each has a `CONTEXT.md`;
- three or more rooms require a root `CONTEXT.md`, and a map with no rooms at all is broken;
- every local link in the map and the context files resolves, case-exact: inline, angle,
  reference, shortcut and collapsed links, plus backtick routes such as `` `src/CONTEXT.md` ``
  in a routing row. Links inside code spans and fences are examples, not links.

It never descends into a nested project (a folder with its own `CLAUDE.md`, `AGENTS.md` or
`.git`) or into dependency, build, cache and archive folders. The JSON report includes a
manifest that binds each guide it read to a SHA-256 of the bytes actually checked, so a proof
can show which version of the map passed. `--origin-root` and `--materialized-root` (always
together) check a tree exported from Git into another folder while resolving links in the
original namespace.

Whether a room is the RIGHT room stays a reading job. The script cannot tell.

## What the method does not prove

The paper's own threats-to-validity section says no controlled comparison against one big prompt
was run, the evidence came from an invite-only, self-selected practitioner community, and only
one model family was tested. Do not quote token savings as measured. ICM supplies no runtime
queues, concurrency or live integrations; when those are real requirements, name the engineering
instead of pretending a folder implements it.

## Enforcement, if your team wants it

The checker is the instrument; where it runs is your choice:

- At closeout (below), every time.
- In CI on pull requests, so the layout is checked with no agent present.
- At session start or on file writes, if your agent supports hooks: report the walk test once,
  and warn when a new file lands at a project root that no routing row names. Existing work
  stays put; a hook never moves files.

## Where this sits in the development protocol

ICM has no row of its own in the 17-row checklist. It runs inside the rows that write files:

- `planning`: `/planning-stack` names the room for every file the plan creates or moves, and a
  new room ships with its `CONTEXT.md`.
- `brainstorm`: `/brainstorm-stack` writes `.planning/BRAINSTORM.md`, never `CONTEXT.md`.
- `build`, `design`, `audit-setup`, `review`: files go where the room's `## Outputs` say; the
  skills' own default paths apply only when no room names one.
- `closeout`: run the walk test and keep its output with the closeout evidence. A broken layout
  is recorded like any other exception (reason, scope, owner, next proof); it never becomes a
  pass.

To keep the result as evidence, write the report first, then add a read-only check of it to the
closeout row's verifier (beside the row's other checks, such as the tests on fresh main):

```text
python3 <icm skill folder>/scripts/icm_check.py <repo> --json > .devproto/evidence/<work-id>-icm.json
grep -q '"exit": 0' .devproto/evidence/<work-id>-icm.json
```

The closeout row is recorded with `devproto.py ... step --step closeout` as `/closeout-stack`
describes. Name the walk-test file in the closeout handoff so the reviewer can find it. If the
checker exits 2, the handoff says "ICM layout not verified" with the reason.
