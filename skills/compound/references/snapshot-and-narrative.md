# Snapshot Schema and Narrative Structure

Detail for Step 13 (the JSON snapshot) and Step 14 (the narrative) of `retro-metrics.md`.

## Contents

- Step 13 JSON schema
- Step 14 narrative structure

---

## Step 13 JSON schema

Write the JSON file to `.devproto/retros/${today}-${next}.json` with this schema:

```json
{
  "date": "2026-04-20",
  "window": "7d",
  "metrics": {
    "commits": 47,
    "contributors": 3,
    "prs_merged": 12,
    "insertions": 3200,
    "deletions": 800,
    "net_loc": 2400,
    "test_loc": 1300,
    "test_ratio": 0.41,
    "active_days": 6,
    "sessions": 14,
    "deep_sessions": 5,
    "avg_session_minutes": 42,
    "loc_per_session_hour": 350,
    "feat_pct": 0.4,
    "fix_pct": 0.3,
    "peak_hour": 22,
    "ai_assisted_commits": 32
  },
  "authors": {
    "Sam Rivera": {
      "commits": 32,
      "insertions": 2400,
      "deletions": 300,
      "test_ratio": 0.41,
      "top_area": "src/"
    },
    "Alice": {
      "commits": 12,
      "insertions": 800,
      "deletions": 150,
      "test_ratio": 0.35,
      "top_area": "app/services/"
    }
  },
  "version_range": ["1.16.0.0", "1.16.1.0"],
  "streak_days": 47,
  "tweetable": "Week of Apr 14: 47 commits (3 contributors), 3.2k LOC, 38% tests, 12 PRs, peak: 10pm"
}
```

**Conditional fields.** Include `backlog` only if `TODOS.md` exists. Include `test_health` only if
test files were found (command 9 returned more than 0). If a field has no data, leave it out
entirely. Do not write zeros for data you did not measure: a zero reads as a measurement.

Test health, when test files exist:

```json
  "test_health": {
    "total_test_files": 47,
    "tests_added_this_period": 5,
    "regression_test_commits": 3,
    "test_files_changed": 8
  }
```

Backlog, when `TODOS.md` exists:

```json
  "backlog": {
    "total_open": 28,
    "p0_p1": 2,
    "p2": 8,
    "completed_this_period": 3,
    "added_this_period": 1
  }
```

---

## Step 14 narrative structure

Write the narrative straight into the conversation. The only file this mode writes is the JSON
snapshot.

**Shareable summary** (first line, before everything else):

```text
Week of Apr 14: 47 commits (3 contributors), 3.2k LOC, 38% tests, 12 PRs, peak: 10pm | Streak: 47d
```

### Engineering Retro: <date range>

**Summary table** (from Step 2)

**Trends vs last retro** (from Step 12, loaded before the save; skip on the first retro)

**Time and session patterns** (Steps 3 and 4): peak hours, session length trends, estimated
hours per day, and each teammate's timing pattern.

**Shipping velocity** (Steps 5 to 7): what the commit type mix means, pull request size
distribution, fix chains (a fix followed by fixes of the fix), version bump discipline.

**Code quality signals**: test LOC ratio trend, and whether the same files keep churning.

**Test health**:

- Total test files: N (command 9)
- Test files changed this period: M (command 11)
- Regression test commits: list the `test(qa):`, `test(design):` and `test: coverage` commits
  from command 10
- If the prior retro has `test_health`, show the delta: "Test files: <last> → <now> (+<delta>)"
- If the test ratio is under 20%, flag it: "Tests are what make fast AI-assisted coding safe.
  Worth investing here."

**Focus and highlights** (Step 8): the focus score with what it means, and the ship of the week.

**Your week** (Step 9, the deepest section): your commits, LOC, test ratio, session patterns,
peak hours, focus areas and biggest ship. Then "What you did well" (2 or 3 points anchored in
commits) and "Where to level up" (1 or 2 actionable points).

**Team breakdown** (Step 9, skip for a solo repository): for each teammate, sorted by commits:

- What they shipped (2 or 3 sentences)
- **Praise**: 1 or 2 specific things anchored in real commits
- **Opportunity for growth**: 1 specific suggestion framed as an investment

  Praise examples: "Cleaned up the whole auth module in 3 small pull requests: textbook
  decomposition." "Added integration tests for every new endpoint, not only the happy paths."

  Growth examples: "Test coverage on the payment module is 8%. Worth investing before the next
  feature lands." "Most commits land in one burst. Spacing the work out reduces
  context-switching fatigue."

  AI collaboration note: if many commits carry AI co-author trailers, report the percentage
  neutrally as a team metric.

**Top 3 team wins**: the highest-impact things shipped: what, who, and why it matters.

**3 things to improve**: specific, actionable, anchored in real commits. "To get even better,
the team could..."

**3 habits for next week**: small (under 5 minutes each), with at least one aimed at the team.

**Week-over-week trends** (from Step 10, when it applies).
