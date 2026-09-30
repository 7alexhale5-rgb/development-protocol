# /compound --metrics: Weekly Engineering Retrospective

Git-history weekly metrics with saved snapshots, a per-person breakdown, a compare mode and a
global mode. It analyzes commit history, work patterns and code quality signals. It is
team-aware: it identifies the person running it, then covers every contributor with specific
praise and one growth suggestion each.

## Preamble (run first)

```bash
_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
echo "BRANCH: $_BRANCH"
```

`$_BRANCH` is the current branch. If it prints `unknown`, the current folder is not inside a git
repository, and only `global` mode can run.

## Arguments

- `/compound --metrics`: last 7 days, current repository (default)
- `/compound --metrics 24h`: last 24 hours
- `/compound --metrics 14d`: last 14 days
- `/compound --metrics 30d`: last 30 days
- `/compound --metrics compare`: current window against the prior window of the same length
- `/compound --metrics compare 14d`: compare with an explicit window
- `/compound --metrics global`: every repository under a parent folder (7 days default)
- `/compound --metrics global 14d`: global with an explicit window
- `/compound --metrics <project-name>`: run the repository retro from outside that project.
  Resolve the name as a sibling folder of the current repository, or accept a path.

## Instructions

Parse the argument to find the time window. Default to 7 days. Report all times in the user's
**local timezone**. Use the system default. Do not set `TZ`.

**Midnight-aligned windows.** For day (`d`) and week (`w`) units, compute an absolute start date
at local midnight, not a relative string. Example: today is 2026-04-20 and the window is 7 days,
so the start date is 2026-04-13. Use `--since="2026-04-13T00:00:00"` for git log. The explicit
`T00:00:00` makes git start at midnight. Without it, git uses the current wall-clock time and the
window silently shifts every time you run it. For weeks, multiply by 7 (`2w` is 14 days). For
hours (`h`), use `--since="N hours ago"`, because midnight alignment does not apply below a day.

**Argument validation.** If the argument is not a number followed by `d`, `h` or `w`, the word
`compare` (optionally with a window), the word `global` (optionally with a window), or a
project name that resolves to a folder, show this usage and stop:

```text
Usage: /compound --metrics [window | compare | global | project-name]
  /compound --metrics              last 7 days, current repository (default)
  /compound --metrics 24h          last 24 hours
  /compound --metrics 14d          last 14 days
  /compound --metrics 30d          last 30 days
  /compound --metrics compare      this period against the prior period
  /compound --metrics compare 14d  compare with an explicit window
  /compound --metrics global       every repository under a parent folder (7d default)
  /compound --metrics global 14d   global with an explicit window
  /compound --metrics my-service   retro for the sibling folder my-service (7d)
```

**If the first argument is `global`:** skip the repository retro (Steps 1 to 14). Follow
`global-retro.md` instead. The optional second argument is the window (default 7d). This mode
does not need a git repository.

**If the first argument is `compare`:** follow Compare Mode in `compare-and-tone.md`.

**If the first argument is a project name:** change into that folder before Steps 1 to 14. If
the folder does not exist, stop and tell the user.

### Non-git context (optional)

Some context never reaches git: meetings, decisions made in chat, calendar events.

```bash
[ -f .devproto/retro-context.md ] && echo "RETRO_CONTEXT_FOUND" || echo "NO_RETRO_CONTEXT"
```

If `RETRO_CONTEXT_FOUND`, read `.devproto/retro-context.md`. The user writes this file by hand.
Use it in the narrative where it fits. Also read `.devproto/sessions/` and `.devproto/handoffs/`
entries dated inside the window, if they exist.

### Step 1: Gather raw data

First find the default branch, fetch it, and identify the current user:

```bash
# Detect the default branch
DEFAULT=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
[ -z "$DEFAULT" ] && DEFAULT=$(git rev-parse --abbrev-ref HEAD)
git fetch origin "$DEFAULT" --quiet 2>/dev/null || true

# Who is running the retro
git config user.name
git config user.email
```

The name from `git config user.name` is **"you"**, the reader. Every other author is a teammate.
Orient the narrative around that: "your" commits and teammate contributions.

For a repository with no remote, use `HEAD` wherever the commands below say
`origin/$DEFAULT`, and skip the fetch.

Run all of these at once. They do not depend on each other. `SINCE` is the midnight-aligned start
computed above (for example `2026-04-13T00:00:00`, or `N hours ago` for an `h` window):

```bash
SINCE="<the midnight-aligned start computed above>"   # fill in before running

# 1. Every commit in the window: hash, author, email, date, subject, and shortstat
git log origin/$DEFAULT --since="$SINCE" --format="%H|%aN|%ae|%ai|%s" --shortstat

# 2. Per-commit test and total LOC with author
git log origin/$DEFAULT --since="$SINCE" --format="COMMIT:%H|%aN" --numstat

# 3. Commit timestamps for session detection and the hourly histogram
git log origin/$DEFAULT --since="$SINCE" --format="%at|%aN|%ai|%s" | sort -n

# 4. Most changed files (hotspots)
git log origin/$DEFAULT --since="$SINCE" --format="" --name-only | grep -v '^$' | sort | uniq -c | sort -rn

# 5. Pull or merge request numbers from commit messages (GitHub #NNN, GitLab !NNN)
git log origin/$DEFAULT --since="$SINCE" --format="%s" | grep -oE '[#!][0-9]+' | sort -t'#' -k1 | uniq

# 6. Per-author file hotspots (who touches what)
git log origin/$DEFAULT --since="$SINCE" --format="AUTHOR:%aN" --name-only

# 7. Per-author commit counts
git shortlog origin/$DEFAULT --since="$SINCE" -sn --no-merges

# 8. Backlog file, if the project keeps one
cat TODOS.md 2>/dev/null || true

# 9. Test file count
find . \( -name '*.test.*' -o -name '*.spec.*' -o -name '*_test.*' -o -name '*_spec.*' \) 2>/dev/null | grep -v node_modules | wc -l

# 10. Regression test commits in the window
git log origin/$DEFAULT --since="$SINCE" --oneline --grep="test(qa):" --grep="test(design):" --grep="test: coverage"

# 11. Test files changed in the window
git log origin/$DEFAULT --since="$SINCE" --format="" --name-only | grep -E '\.(test|spec)\.' | sort -u | wc -l
```

### Step 2: Compute metrics

Present these in a summary table:

| Metric                                                                             | Value                                                  |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------ |
| **Features shipped** (from the changelog and merged pull request titles)           | N                                                      |
| Commits to the default branch                                                      | N                                                      |
| Weighted commits (commits times average files touched, capped at 20 per commit)    | N                                                      |
| Contributors                                                                       | N                                                      |
| Pull requests merged                                                               | N                                                      |
| **Logical SLOC added** (non-blank, non-comment lines; the main code-volume metric) | N                                                      |
| Raw LOC: insertions                                                                | N                                                      |
| Raw LOC: deletions                                                                 | N                                                      |
| Raw LOC: net                                                                       | N                                                      |
| Test LOC (insertions)                                                              | N                                                      |
| Test LOC ratio                                                                     | N%                                                     |
| Version range                                                                      | vX.Y.Z to vX.Y.Z                                       |
| Active days                                                                        | N                                                      |
| Detected sessions                                                                  | N                                                      |
| Average raw LOC per session-hour                                                   | N                                                      |
| Test health                                                                        | N total tests, M added this period, K regression tests |

**Why this order.** Features shipped comes first because it is what users got. Commits and
weighted commits show intent to ship. Logical SLOC shows real new function. Raw LOC comes last
because AI assistance inflates it: ten lines of a good fix is not less shipping than ten
thousand lines of scaffold.

Then show a **per-author leaderboard** right below:

```text
Contributor         Commits   +/-          Top area
You (Sam Rivera)         32   +2400/-300   src/
alice                    12   +800/-150    app/services/
bob                       3   +120/-40     tests/
```

Sort by commits, highest first. The current user always appears first, labeled "You (name)".

**Backlog health (if `TODOS.md` exists).** From command 8, compute:

- Total open items (exclude a `## Completed` section)
- P0 and P1 count (critical and urgent)
- P2 count (important)
- Items completed this period (in the Completed section with dates inside the window)
- Items added this period (cross-check git log for commits that changed `TODOS.md` in the window)

Add a row to the table:

```text
| Backlog health | N open (X P0/P1, Y P2), Z completed this period |
```

If there is no backlog file, skip the row.

### Step 3: Commit time distribution

Show an hourly histogram in local time:

```text
Hour  Commits  ████████████████
 00:    4      ████
 07:    5      █████
 ...
```

Call out:

- Peak hours
- Dead zones
- Whether the pattern is bimodal (morning and evening) or continuous
- Late-night clusters (after 10pm)

### Step 4: Work session detection

Detect sessions with a **45-minute gap** between consecutive commits. For each session, report:

- Start and end time (local)
- Number of commits
- Duration in minutes

Classify sessions:

- **Deep** (50 minutes or more)
- **Medium** (20 to 50 minutes)
- **Micro** (under 20 minutes, usually a single fire-and-forget commit)

Calculate:

- Total active coding time (sum of session durations)
- Average session length
- LOC per hour of active time

### Step 5: Commit type breakdown

Group commits by conventional-commit prefix (feat, fix, refactor, test, chore, docs). Show as a
percentage bar:

```text
feat:     20  (40%)  ████████████████████
fix:      27  (54%)  ███████████████████████████
refactor:  2  ( 4%)  ██
```

Flag a fix ratio above 50%. That is a "ship fast, fix fast" pattern that can point to review
gaps.

### Step 6: Hotspot analysis

Show the 10 most changed files. Flag:

- Files changed 5 or more times (churn hotspots)
- Test files against production files in the hotspot list
- How often the version file and changelog change (a sign of version discipline)

### Step 7: Pull request size distribution

From commit diffs, estimate pull request sizes and bucket them:

- **Small** (under 100 LOC)
- **Medium** (100 to 500 LOC)
- **Large** (500 to 1,500 LOC)
- **XL** (over 1,500 LOC)

### Step 8: Focus score and ship of the week

**Focus score.** The percentage of commits that touch the single most-changed top-level folder
(for example `src/` or `app/services/`). Higher means deeper focus. Lower means scattered work.
Report it as: "Focus score: 62% (src/)".

**Ship of the week.** Find the single highest-LOC pull request in the window. Show:

- The pull request number and title
- LOC changed
- Why it matters (from commit messages and files touched)

### Step 9: Team member analysis

For each contributor, including the current user, compute:

1. **Commits and LOC**: total commits, insertions, deletions, net
2. **Areas of focus**: the top 3 folders or files they touched
3. **Commit type mix**: their own feat, fix, refactor and test breakdown
4. **Session patterns**: their peak hours and session count
5. **Test discipline**: their own test LOC ratio
6. **Biggest ship**: their single highest-impact commit or pull request in the window

**For the current user ("You"):** give this the deepest treatment. Include all the solo detail:
session analysis, time patterns, focus score. Write it in second person: "Your peak hours...",
"Your biggest ship...".

**For each teammate:** write 2 or 3 sentences on what they worked on and their pattern. Then:

- **Praise** (1 or 2 specific things), anchored in real commits. Not "great work". Say exactly
  what was good. Examples: "Shipped the whole auth middleware rewrite in 3 focused sessions with
  45% test coverage." "Every pull request under 200 LOC: disciplined decomposition."
- **Opportunity for growth** (1 specific thing), framed as leveling up, not criticism, and
  anchored in data. Examples: "Test ratio was 12% this week. Covering the payment module before
  it grows would pay off." "Five fix commits on the same file suggest the first pull request
  needed a review pass."

**Solo repository (one contributor):** skip the team breakdown. The retro is personal.

**Co-author trailers:** parse `Co-Authored-By:` lines in commit messages. Credit those authors
alongside the primary author. AI co-authors are not team members. Count them as a separate
"AI-assisted commits" metric instead.

### Step 10: Week-over-week trends (window of 14 days or more)

Split the window into weekly buckets and show:

- Commits per week (total and per author)
- LOC per week
- Test ratio per week
- Fix ratio per week
- Sessions per week

### Step 11: Streak tracking

Count consecutive days with at least one commit to `origin/$DEFAULT`, going back from today.
Track a team streak and a personal streak:

```bash
# Team streak: every unique commit date (local time), full history
git log origin/$DEFAULT --format="%ad" --date=format-local:"%Y-%m-%d" | sort -u

# Personal streak: only the current user's commits (the "you" identified in Step 1)
git log origin/$DEFAULT --author="$(git config user.name)" --format="%ad" --date=format-local:"%Y-%m-%d" | sort -u
```

Count backward from today. This reads the full history, so a streak of any length is accurate.
Show both:

- "Team shipping streak: 47 consecutive days"
- "Your shipping streak: 32 consecutive days"

### Step 12: Load history and compare

Before saving the new snapshot, look for earlier ones. Repository retros live in
`.devproto/retros/` inside the repository:

```bash
setopt +o nomatch 2>/dev/null || true  # zsh: do not error on an empty glob
ls -t .devproto/retros/*.json 2>/dev/null
```

**If earlier retros exist:** choose the newest earlier snapshot with the same `window`
and `metrics_version` (currently `1`). Search past incompatible recent snapshots. Missing
versions are incompatible; do not assume their metrics used the same definitions. If none
match, omit trends and explain the window or definition mismatch. Otherwise compute deltas and add a
**Trends vs Last Retro** section:

```text
                    Last        Now         Delta
Test ratio:         22%    →    41%         ↑19pp
Sessions:           10     →    14          ↑4
LOC/hour:           200    →    350         ↑75%
Fix ratio:          54%    →    30%         ↓24pp (improving)
Commits:            32     →    47          ↑47%
Deep sessions:      3      →    5           ↑2
```

**If none exist:** skip the comparison and add: "First retro recorded. Run again next week to see
trends."

### Step 13: Save the snapshot

After computing every metric (streak included) and loading history, save a JSON snapshot:

```bash
mkdir -p .devproto/retros
setopt +o nomatch 2>/dev/null || true
today=$(date +%Y-%m-%d)
existing=$(ls .devproto/retros/${today}-*.json 2>/dev/null | wc -l | tr -d ' ')
next=$((existing + 1))
# Save as .devproto/retros/${today}-${next}.json
```

The schema, the optional `test_health` and `backlog` fields, and when to include them are in
`snapshot-and-narrative.md` (Step 13 section).

### Step 14: Write the narrative

The full section order, what each section must contain, praise and growth examples, and the AI
collaboration note are in `snapshot-and-narrative.md` (Step 14 section).

Section order, for quick reference:

1. One-line shareable summary (first line)
2. Summary table (Step 2)
3. Trends vs last retro (Step 12, skip on the first retro)
4. Time and session patterns (Steps 3 and 4)
5. Shipping velocity (Steps 5 to 7)
6. Code quality signals
7. Test health
8. Focus and highlights (Step 8)
9. Your week: personal deep dive (Step 9)
10. Team breakdown (Step 9, skip when solo)
11. Top 3 team wins
12. 3 things to improve
13. 3 habits for next week
14. Week-over-week trends (Step 10, when it applies)

---

## Global mode

Full instructions: `global-retro.md`. It works from any folder and does not need a git
repository. Snapshots go to `~/.devproto/retros/global-<date>-<n>.json`.

## Compare mode, tone and rules

Full instructions: `compare-and-tone.md`. The tone rules and the important rules there govern
every retro, not only compare mode.

---

## Verify

After the retro, confirm the snapshot was written and is valid JSON.

**Repository retros** (default, `24h`, `14d`, `30d`, `compare`, project name):

```bash
setopt +o nomatch 2>/dev/null || true
today=$(date +%Y-%m-%d)
latest=$(ls -t .devproto/retros/${today}-*.json 2>/dev/null | head -1)
if [ -z "$latest" ]; then
  echo "ERROR: no retro snapshot found in .devproto/retros/ for today"
else
  python3 -m json.tool < "$latest" > /dev/null && echo "OK: $latest"
fi
```

**Global retros:**

```bash
setopt +o nomatch 2>/dev/null || true
today=$(date +%Y-%m-%d)
latest=$(ls -t ~/.devproto/retros/global-${today}-*.json 2>/dev/null | head -1)
if [ -z "$latest" ]; then
  echo "ERROR: no global retro snapshot found in ~/.devproto/retros/ for today"
else
  python3 -m json.tool < "$latest" > /dev/null && echo "OK: $latest"
fi
```

If it prints `OK: <path>`, the retro succeeded. If it errors, give the user the path and the JSON
parse error. Do not report a retro as done without this line.
