---
name: compound
description: Runs an engineering retrospective from git history and writes down the learnings, so the next plan starts smarter. Use it weekly, after a milestone, after /ship, or when the development-protocol checklist reaches its compound row. Triggers on "retro", "compound", "what did we learn", "weekly review", "document learnings", "what did we ship", "engineering retrospective", "retro numbers". The --metrics mode gives weekly git numbers with a per-person breakdown, a compare mode and a cross-project global mode. This is cross-session learning from git history. It is not the per-session transcript audit that /closeout-stack runs.
---

# Compound: Retrospective and Forward Learning

Look at what was built. Pull out what was learned. Write it down where the next `/planning-stack`
will find it. The idea comes from compound engineering: each unit of work should make the next
unit easier. A learning that stays in a chat window compounds nothing.

## Where this sits in the checklist

This skill satisfies the `compound` row of the development-protocol checklist. The row records
reusable learning before closeout. Pass it with the learning report as evidence and a verifier
that only reads that report (see Step 7).

## Two modes

| You type                         | What runs                                                                                               |
| -------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `/compound` (plus scope flags)   | The learning flow below, Steps 0 to 7                                                                   |
| `/compound --metrics [argument]` | The git metrics retro. Read `references/retro-metrics.md` and follow it end to end. Stop when it stops. |

`--metrics` takes `24h`, `14d`, `30d`, `compare [Nd]`, `global [Nd]`, or a project name. Use it
for "weekly retro", "what did we ship", "engineering retrospective" and "retro numbers".

---

## Step 0: Determine scope

Ask, or detect from the request:

| Flag                | Scope                                                                                                                 |
| ------------------- | --------------------------------------------------------------------------------------------------------------------- |
| (default)           | Current repository, last 7 days                                                                                       |
| `--project <path>`  | One other repository                                                                                                  |
| `--global [folder]` | Every git repository under a parent folder with recent activity. Default folder: the parent of the current repository |
| `--milestone`       | The current milestone in the project's plan files, if one exists                                                      |
| `--days N`          | Override the time window (default 7)                                                                                  |

Say the scope back in one line before gathering data: "Compounding `billing-service`, last 7
days."

---

## Step 1: Gather data

### 1a: Git analysis

For each repository in scope:

```bash
project_path="<the repository to retro>"      # fill in before running
days_ago="<N> days ago"                       # replace <N> with the Step 0 window
cd "$project_path"

# Commits in the window
git log --oneline --after="$days_ago" --format="%h %s (%an, %ar)"

# Totals: file changes, insertions, deletions; binary changes have no LOC count
git log --after="$days_ago" --numstat --format="" \
  | awk -F '\t' 'NF >= 3 {f++; if ($1 == "-" || $2 == "-") {b++; next} i+=$1; d+=$2} END {printf "file changes: %d, +%d, -%d, binary: %d\n", f, i, d, b}'

# Most changed files (hotspots)
git log --after="$days_ago" --name-only --format="" | sort | uniq -c | sort -rn | head -10

# Merged branches
git log --after="$days_ago" --merges --oneline

# Reverts (a sign of something hard)
git log --after="$days_ago" --oneline --grep="^Revert"
```

### 1b: Session context (if the project keeps it)

Git shows what changed. It does not show what was hard, what was surprising, or why a choice
was made. Look for that in the repository's own notes, dated inside the window:

```bash
start_date="<the window's start date, e.g. 2026-09-22>"    # fill in before running
devproto_dir="<the development-protocol skill folder>"     # fill in before running

# Session saves, handoffs and learning notes written by /closeout-stack and earlier /compound runs
find .devproto/sessions .devproto/handoffs .devproto/learnings -name '*.md' -newermt "$start_date" 2>/dev/null

# Open and closed work items on the checklist
python3 "$devproto_dir/scripts/devproto.py" --project . list
```

Read the handoffs first. Their `## Retro Findings` and `## Unknowns` sections are the richest
source of "what was hard". If the project has none of these files, say so and continue from git
alone.

### 1c: Planning artifacts (if they exist)

Read the plan and state files the project keeps (for example `.devproto/<work-id>/`, a
`plan.md`, a roadmap, or a state file). Check which phases finished and which done conditions
were met, and which were not.

---

## Step 2: Analyze patterns

From the data, identify:

1. **What shipped.** Concrete deliverables, each with a commit reference.
2. **Velocity.** Commits per day, lines per day, pull requests merged. This is context, not a
   performance score.
3. **Hotspots.** Files changed most often. These are refactoring candidates.
4. **Patterns.** Themes that repeat in commit messages: bug fixes, test additions, refactoring.
5. **Decisions made.** Architecture choices visible in the diff: new dependencies, schema
   changes, API changes.
6. **What was hard.** Inferred from revert commits, many attempts at the same file, and long
   gaps between commits. Label these as inferred in the report.
7. **Test health.** The ratio of test files to implementation files in the diff.

---

## Step 3: Extract learnings

For each significant pattern or decision, write a learning in this shape:

```markdown
#### Learning: <title>

**Context**: <what happened, with a commit or file reference>
**Decision**: <what we chose>
**Rationale**: <why>
**Reuse**: <when a future plan should apply this again>
```

A learning without a **Reuse** line is a diary entry. Cut it or finish it.

### Categorize learnings

| Category                     | Where it is stored                                                                                       | Who reads it                                     |
| ---------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| **Architecture decisions**   | `docs/decisions/<date>-<slug>.md`, or the project's existing decision-record folder                      | `/planning-stack` when it checks prior decisions |
| **Conventions and patterns** | The project's agent instruction file (`CLAUDE.md`, `AGENTS.md` or similar), only after the user confirms | Every session                                    |
| **Pain points**              | `.devproto/learnings/<date>-compound-<scope>.md`                                                         | The next `/closeout-stack`, future you           |
| **Reusable solutions**       | `.devproto/learnings/<date>-compound-<scope>.md`, under a Reusable heading                               | `/planning-stack` and `/research-stack`          |

---

## Step 4: Deliver the report

```markdown
## Compound Report: <date range>

### What Shipped

<bulleted list with commit refs>

### By the Numbers

- <N> commits across <N> projects
- <+N / -N> lines (<net> net)
- <N> pull requests merged
- <N> hotspot files (more than <threshold> changes)

### Learnings

<numbered list of extracted learnings, each with its category>

### Hotspots (potential refactoring)

| File   | Changes | Concern                         |
| ------ | ------- | ------------------------------- |
| <path> | <N>     | <why this might need attention> |

### Health Signals

- Test ratio: <test_lines / total_lines>%
- Revert count: <N>
- Longest gap: <duration> (possible blocker or context switch)

### Decisions to Document

<list of decisions that should be persisted for future planning>
```

If the Docs Health or Agent Setup Health checks below raise a flag, put those flags first in
the report, above What Shipped.

---

## Step 5: Persist

### 5a: Write the report

```text
Write: .devproto/learnings/<YYYY-MM-DD>-compound-<scope-slug>.md
---
date: <YYYY-MM-DD>
type: compound
scope: <project name or "global">
window: <N>d
tags: [compound, retrospective, <project>]
---

<full report from Step 4>
```

If a file with today's date and the same scope exists, add a `## Update HH:MM` section to it.
Do not create a second file for the same day and scope. Two files for one day split every later
search.

### 5b: Write decisions (only the significant ones)

For each decision worth keeping:

```text
Write: docs/decisions/<YYYY-MM-DD>-<decision-slug>.md
---
date: <YYYY-MM-DD>
type: decision
project: <project>
tags: [decision, <topic>]
---

# Decision: <title>

<learning format from Step 3>
```

If the project already has a decision-record folder (often `docs/adr/`), use it and follow its
numbering instead.

### 5c: Suggest instruction-file updates (if conventions were found)

If a pattern suggests a convention should be written down, ask:

> "I noticed <pattern> across <N> commits. Want me to add this as a convention to
> <project>/CLAUDE.md?"

Only suggest. Never write to an agent instruction file without the user's yes. That file is
read every session, so a wrong line there costs every future session.

---

## Step 5.5: Docs health (weekly cadence)

A retrospective is a natural weekly moment to catch docs that drifted from the code.

1. **Moved or deleted files still named in docs.** List paths the window renamed or deleted,
   then search the docs for the old names:

   ```bash
   days_ago="<N> days ago"                       # replace <N> with the Step 0 window
   gone=$(mktemp)
   git log --after="$days_ago" --diff-filter=DR --name-status --format="" \
     | awk '{print $2}' | sort -u > "$gone"
   grep -rnF -f "$gone" docs/ README.md 2>/dev/null
   rm -f "$gone"
   ```

2. **Stale docs.** For each doc that describes a folder, compare the last commit date of the doc
   with the last commit date of the folder it describes:

   ```bash
   doc_topic="<topic>"                           # fill in before running
   doc_folder="<folder the doc describes>"       # fill in before running
   git log -1 --format=%cs -- "docs/$doc_topic.md"
   git log -1 --format=%cs -- "$doc_folder"
   ```

   A doc older than its code on an active project is stale.

3. **Refresh** only the stale docs for code that is still active. Leave archived areas alone.

4. **Report.** Append to the compound report:

   ```markdown
   ### Docs Health

   - Docs checked: <N>
   - Stale: <N> (<N> refreshed this cycle)
   - Broken references to moved or deleted files: <N>
   - Topics with no doc that came up in 3 or more sessions: <list or "none">
   ```

If the project has no docs folder, skip this step and say so in one line.

## Step 5.7: Agent setup health (weekly cadence)

Check the agent's own working setup for drift, bloat and staleness. Code review and docs checks
do not cover this.

### 5.7a: Instruction and memory files

```bash
# Size of each agent instruction file in the repo
wc -l CLAUDE.md AGENTS.md .github/copilot-instructions.md 2>/dev/null
# Learning notes waiting for review
ls -1 .devproto/learnings/*.md 2>/dev/null | wc -l
```

Flag an instruction or memory file when it is within 10% of any line limit your agent applies
when loading it. Lines past that limit are silently not read. Flag a backlog of more than 20
unreviewed learning notes.

### 5.7b: Configuration consistency (if the repo has agent config)

```bash
# Every hook script named in the repo's agent settings must exist
grep -o '"command": "[^"]*"' .claude/settings.json 2>/dev/null \
  | sed 's/"command": "//;s/"//' | while read -r cmd; do
      script=$(echo "$cmd" | awk '{print $NF}')
      [ -f "$script" ] || echo "MISSING: $script"
    done
# Plans older than 14 days with work still open
find .devproto -name 'plan.md' -mtime +14 2>/dev/null
```

Cross-check old plans against `devproto.py list`. An old plan with every row closed is fine. An
old plan with open rows is a stalled item.

### 5.7c: Skill health (if the repo ships skills)

```bash
ls -1d skills/*/ .claude/skills/*/ 2>/dev/null | wc -l
# Skills whose SKILL.md has not changed in more than 60 days
find skills .claude/skills -name SKILL.md -mtime +60 2>/dev/null | wc -l
```

### 5.7d: Append to the report

```markdown
### Agent Setup Health

- **Instructions**: <file> <N> lines (limit <L>), learning backlog <N>
- **Config**: <all hooks valid | MISSING: <list>>, <N> stalled plans
- **Skills**: <N> total, <N> unchanged in 60+ days
- **Verdict**: <CLEAN | ACTION: <top issues>>
```

If any flag fires, surface it as the first item in the report. Do not auto-fix. Report, and let
a person decide what to clean up.

---

## Step 6: Forward feed

After writing, tell the user where things went and what comes next:

```text
Compounded. Learnings stored in .devproto/learnings/ for the next /planning-stack.
Decisions: <N> written to docs/decisions/. Docs: <N> stale, <N> refreshed.

Next:
- /closeout-stack to wrap up the session
- Or keep building. The next /planning-stack reads these learnings.
```

## Step 7: Record the checklist row

The report from Step 5a is the evidence. The verifier only reads it:

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id <work-id> --step compound --result pass \
  --evidence .devproto/learnings/<YYYY-MM-DD>-compound-<scope-slug>.md \
  --verify "grep -q '^### Learnings' .devproto/learnings/<YYYY-MM-DD>-compound-<scope-slug>.md"
```

A report with zero learnings is valid if it says so under `### Learnings` ("None this cycle:
the work repeated known patterns"). An empty heading is not. Padding the list to look
substantial is worse than an honest zero.

If git was unreachable, or the window had no commits, record the row as `blocked` with the
reason, not `pass`. Unknown is not pass.

## Rules

- Anchor every claim in a commit, a file or a note. "What was hard" is inferred from git
  signals, so label it inferred.
- Velocity numbers are context, never a grade of a person.
- Never write to an agent instruction file without confirmation.
- Never auto-fix what the health checks find. Report it.
