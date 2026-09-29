# Global Retro: Detailed Flow

Read this when the user runs `/compound --metrics global`. It covers every git repository under
one parent folder and needs no repository of its own.

## Contents

- Global Step 1: Compute the time window
- Global Step 2: Discover projects
- Global Step 3: Run git log on each repository
- Global Step 4: Compute the global shipping streak
- Global Step 5: Compute the context-switching metric
- Global Step 6: Aggregate and write the narrative
- Global Step 7: Load history and compare
- Global Step 8: Save the snapshot

---

## Global Step 1: Compute the time window

Use the same midnight-aligned logic as the repository retro. Default 7 days. The second
argument after `global` is the window (`14d`, `30d`, `24h`).

## Global Step 2: Discover projects

Ask for the parent folder, or default to the parent of the current folder. Walk it for folders
that contain a `.git/` folder:

```bash
PARENT=${PARENT:-$(cd .. && pwd)}
for proj in "$PARENT"/*/; do
  name=$(basename "$proj")
  # Skip folders that hold archives or notes, not code
  case "$name" in
    _archive|archive|node_modules|.*) continue ;;
  esac
  if [ -d "$proj/.git" ]; then
    echo "REPO: $name -> $proj"
  fi
done
```

If the user keeps projects nested one level deeper (for example one folder per team or client),
walk one more level. Say which depth you used.

If no repository has commits in the window, say: "No commits under `<parent>` in the last
<window>. Try a longer window: `/compound --metrics global 30d`." Then stop.

## Global Step 3: Run git log on each repository

For each repository, detect the default branch: try `git symbolic-ref refs/remotes/origin/HEAD`,
then `main`, then `master`, then `git rev-parse --abbrev-ref HEAD`. Use it as `$DEFAULT` below.

**Local-only repositories** (no remote): skip `git fetch` and use `git log HEAD` in place of
`git log origin/$DEFAULT`.

**Repositories with a remote:**

```bash
repo_path="<path to this repository>"   # fill in before running
git -C "$repo_path" fetch origin --quiet 2>/dev/null
```

Then:

```bash
repo_path="<path to this repository>"   # fill in before running
start_date="<the window's start date, e.g. 2026-09-22>"   # fill in before running

# Commits with stats
git -C "$repo_path" log origin/$DEFAULT --since="${start_date}T00:00:00" --format="%H|%aN|%ai|%s" --shortstat

# Commit timestamps for sessions, streak and context switching
git -C "$repo_path" log origin/$DEFAULT --since="${start_date}T00:00:00" --format="%at|%aN|%ai|%s" | sort -n

# Per-author commit counts
git -C "$repo_path" shortlog origin/$DEFAULT --since="${start_date}T00:00:00" -sn --no-merges

# Pull or merge request numbers from commit messages
git -C "$repo_path" log origin/$DEFAULT --since="${start_date}T00:00:00" --format="%s" | grep -oE '[#!][0-9]+' | sort -t'#' -k1 | uniq
```

Skip repositories that fail (deleted paths, network errors) and note "N repositories could not
be reached." Never drop them silently: an unreachable repository is an unknown, not a zero.

## Global Step 4: Compute the global shipping streak

For each repository, get commit dates, capped at 365 days:

```bash
repo_path="<path to this repository>"   # fill in before running
git -C "$repo_path" log origin/$DEFAULT --since="365 days ago" --format="%ad" --date=format:"%Y-%m-%d" | sort -u
```

Union the dates across every repository. Count backward from today: how many consecutive days
have at least one commit to any repository? If the streak reaches the cap, show "365+ days".

## Global Step 5: Compute the context-switching metric

From the Step 3 timestamps, group by date. For each date, count the distinct repositories with
commits. Report:

- Average repositories per day
- Maximum repositories per day
- Which days were focused (1 repository) and which were fragmented (3 or more)

## Global Step 6: Aggregate and write the narrative

Put the **shareable personal card first**, then the full project breakdown. The card is built to
be screenshotted: everything someone would want to share, in one clean block.

---

**Shareable summary** (first line, before everything else):

```text
Week of Apr 14: 5 projects, 138 commits, 250k LOC across 5 repos | Streak: 52d
```

### Your Week: <user name>, <date range>

This is the **personal card**. It holds only the current user's stats: no team data and no
project breakdowns.

Filter every repository's git data by the identity from `git config user.name`. Total across all
repositories.

Render it as one clean block. Use a left border only. A model cannot reliably align a right
border. Pad repository names to the longest name so the columns line up. Never truncate a
project name.

```text
╔═══════════════════════════════════════════════════════════════
║  <USER NAME>, week of <date>
╠═══════════════════════════════════════════════════════════════
║
║  <N> commits across <M> projects
║  +<X>k LOC added · <Y>k LOC deleted · <Z>k net
║  <N>-day shipping streak
║
║  PROJECTS
║  ─────────────────────────────────────────────────────────
║  <repo_name_full>        <N> commits    +<X>k LOC    <solo/team>
║  <repo_name_full>        <N> commits    +<X>k LOC    <solo/team>
║  <repo_name_full>        <N> commits    +<X>k LOC    <solo/team>
║
║  SHIP OF THE WEEK
║  <PR title>: <LOC> lines across <N> files
║
║  TOP WORK
║  • <one-line description of the biggest theme>
║  • <one-line description of the second theme>
║  • <one-line description of the third theme>
║
╚═══════════════════════════════════════════════════════════════
```

**Rules for the personal card:**

- Show only repositories where the user has commits. Skip repositories with 0.
- Sort repositories by the user's commit count, highest first.
- **Never truncate repository names.** Use the full name (`billing-service`, not
  `billing-servi`). Pad the name column to the longest name. If names are long, widen the box.
- Format thousands with "k" (`+64.0k`, not `+64010`).
- Role: "solo" if the user is the only contributor, "team" if others contributed.
- Ship of the week: the user's single highest-LOC pull request across all repositories.
- Top work: 3 bullets that summarize the user's main themes, inferred from commit messages.
  Themes, not individual commits.
- The card must stand alone. Someone who sees only this block should understand the week.
- Do not include teammates, project totals or context-switching data here.

**Personal streak:** use only the user's own commits across all repositories (filter with
`--author`). Keep it separate from the team streak.

---

### Global Engineering Retro: <date range>

Everything below is the full analysis: team data, project breakdowns, patterns. This is the deep
dive that follows the card.

#### All projects overview

| Metric                                                   | Value              |
| -------------------------------------------------------- | ------------------ |
| Projects active                                          | N                  |
| Total commits (all repositories, all contributors)       | N                  |
| Total LOC                                                | +N / -N            |
| Active days                                              | N                  |
| Global shipping streak (any contributor, any repository) | N consecutive days |
| Context switches per day                                 | N avg (max: M)     |

#### Per-project breakdown

For each repository, sorted by commits, highest first:

- Repository name, with its percentage of total commits
- Commits, LOC, pull requests merged, top contributor
- Key work, inferred from commit messages

**Your contributions** (a block inside each project): the current user's own stats in that
repository, filtered by `git config user.name`. Include:

- Your commits over total commits, with a percentage
- Your LOC (+insertions / -deletions)
- Your key work, inferred from your commit messages only
- Your commit type mix (feat, fix, refactor, chore, docs)
- Your biggest ship in this repository (highest-LOC commit or pull request)

If the user is the only contributor, say "Solo project: all commits are yours." If the user has
0 commits in a repository, say "No commits this period." and skip the block.

Format:

```text
**Your contributions:** 47/244 commits (19%), +4.2k/-0.3k LOC
  Key work: chat panel, email blocking, security hardening
  Biggest ship: PR #605, chat panel replaces the admin bar (2,457 insertions, 46 files)
  Mix: feat(3) fix(2) chore(1)
```

#### Cross-project patterns

- Time split across projects (percentages, using your commits, not the total)
- Peak hours across all repositories
- Focused days against fragmented days
- Context-switching trend

#### Ship of the week (global)

The highest-impact pull request across all projects, judged by LOC and commit messages.

#### 3 cross-project insights

What the global view shows that no single-repository retro could.

#### 3 habits for next week

Based on the full cross-project picture.

---

## Global Step 7: Load history and compare

```bash
setopt +o nomatch 2>/dev/null || true
ls -t ~/.devproto/retros/global-*.json 2>/dev/null | head -5
```

**Only compare against an earlier retro with the same `window` value** (7d against 7d). If the
most recent one used a different window, skip the comparison and note: "The prior global retro
used a different window. Skipping comparison."

If a matching retro exists, read it. Show a **Trends vs Last Global Retro** table with deltas for
total commits, LOC, streak and context switches per day.

If none exist, add: "First global retro recorded. Run again next week to see trends."

## Global Step 8: Save the snapshot

```bash
mkdir -p ~/.devproto/retros
```

Find the next sequence number for today:

```bash
setopt +o nomatch 2>/dev/null || true
today=$(date +%Y-%m-%d)
existing=$(ls ~/.devproto/retros/global-${today}-*.json 2>/dev/null | wc -l | tr -d ' ')
next=$((existing + 1))
```

Write the JSON to `~/.devproto/retros/global-${today}-${next}.json`:

```json
{
  "type": "global",
  "date": "2026-04-20",
  "window": "7d",
  "parent": "<the parent folder that was walked>",
  "projects": [
    {
      "name": "billing-service",
      "remote": "<from git remote get-url origin, normalized to HTTPS>",
      "commits": 47,
      "insertions": 3200,
      "deletions": 800
    }
  ],
  "unreachable": [],
  "totals": {
    "commits": 182,
    "insertions": 15300,
    "deletions": 4200,
    "projects": 5,
    "active_days": 6,
    "global_streak_days": 52,
    "avg_context_switches_per_day": 2.1
  },
  "tweetable": "Week of Apr 14: 5 projects, 182 commits, 15.3k LOC | Focus: billing-service (58%) | Streak: 52d"
}
```

Then run the global check in the Verify section of `retro-metrics.md`.
