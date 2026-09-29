---
name: ship
description: One-command release flow for committed work on a feature branch. Checks that the repo carries its own proof (a pull-request test gate, branch protection, dependency updates, production matching the base branch), syncs with the base branch, runs the tests, pushes, opens a pull request, and waits for the checks on the exact pushed commit before saying "shipped". Use after /commit when code is committed and ready, or when someone says "ship it", "open a PR", "push and PR", "send it for review".
---

# Ship: one-command release

Sync, test, push, pull request, then wait for the checks on the exact commit. Picks up after
`/commit`: you already have committed changes on a feature branch.

## Checklist row

This skill satisfies the `ship` row of the development-protocol checklist. The row must pass on
the exact commit that will merge, before closeout. In Step 4c, save the commit SHA, the pull
request link and the check results, then record the row with a verifier that re-reads the checks:

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id <work-id> --step ship --result pass --evidence .devproto/evidence/ship.txt \
  --verify "gh pr checks <pr-number>"
```

`gh pr checks` exits non-zero while any check is failing or pending, so the row cannot pass on a
red or unfinished run. Without the GitHub CLI, use your CI system's command-line tool, or record
the row as `blocked` with the reason "checks not verifiable from here" and tell the user. Never
record a pass from a web page you read by eye.

---

## Step 0: Pre-flight

### 0a: Verify state

```bash
git status --porcelain -- . ':!.devproto'
git branch --show-current
git log --oneline -3
```

(The `':!.devproto'` part ignores the checklist's own files, which change after every step.)

**Abort if:**

- Uncommitted changes exist: "You have uncommitted changes. Run `/commit` first."
- On `main` or `master`: "You're on the base branch. Create a feature branch first."
- No commits ahead of base: "Nothing to ship. Your branch has no new commits."

### 0b: Detect the base branch

```bash
git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null \
  || { git rev-parse --verify --quiet origin/main >/dev/null && echo origin/main; } \
  || { git rev-parse --verify --quiet origin/master >/dev/null && echo origin/master; } \
  || echo unknown
```

Strip the `origin/` prefix. If the answer is unknown, ask: "What's your base branch?"

### 0c: Detect the test command

Check in order:

1. `package.json` has `scripts.test`: `npm test` (or `bun test`, `pnpm test`, `yarn test`, matching
   the lockfile)
2. `Makefile` has a `test` target: `make test`
3. `pyproject.toml`: `pytest`
4. `Cargo.toml`: `cargo test`
5. If none is found, note "No test command detected. Skipping tests." and say so in the final
   report.

### 0d: Rails check (does the repo carry its own proof?)

A repo whose checks only run while an agent is in the room has no proof of its own. Answer five
questions from the repo, and from the git host when you can reach it. This is report-only; it
never edits anything.

1. **pr-gate.** Does a workflow run tests or a typecheck on `pull_request`?
   ```bash
   ls .github/workflows/ 2>/dev/null
   grep -lE "pull_request" .github/workflows/*.y*ml 2>/dev/null
   ```
   Read each matching workflow. It is a gate only if a step actually runs the test tool. These do
   NOT count: a step under `continue-on-error: true`, a command ending in `|| true`, a comment
   that mentions a test tool, or a `pull_request` trigger with a `paths:` filter (a required check
   that never reports blocks the merge forever). Follow indirection one level: a step that runs
   `npm run check` counts if `package.json` shows `check` runs the tests, and a step that runs
   `bash bin/run-tests.sh` counts if that script runs them. Lessons: on 2026-09-05 a real gate
   read as "no gate" because the workflow only said `npm run check`; on 2026-09-18 another did
   because the workflow called a checked-in shell script.
2. **protection.** Does the base branch require that check to pass? Optional, needs the GitHub
   CLI:
   ```bash
   gh api repos/{owner}/{repo}/rules/branches/{base}
   gh api repos/{owner}/{repo}/branches/{base}/protection
   ```
   Read both. A ruleset and classic branch protection are separate mechanisms, and either can
   enforce the rule. Lesson from 2026-09-08: reading only rulesets reported a branch that
   required three checks the classic way as "unprotected". A required-checks rule with an empty
   list, or one that does not name the gate job, is weak, not protected.
3. **dependency updates.** Does `.github/dependabot.yml` (or the team's equivalent, such as a
   Renovate config) exist?
4. **prod == main.** If the project deploys, is the commit running in production an ancestor of
   `origin/{base}`? Get the production commit from your hosting provider's CLI or dashboard, then
   `git merge-base --is-ancestor <prod-sha> origin/{base}`. A production deploy with no commit
   attached came from someone's laptop, and that is drift too.
5. **receipts.** Are the checklist's evidence files current? Run
   `python3 <development-protocol skill folder>/scripts/devproto.py --project . status --id <work-id>`;
   any step it reopened has evidence that changed after it passed.

Why this step exists: on 2026-09-04 one project had nine verifier scripts, zero CI workflows,
evidence eight days stale, and production 454 files ahead of its main branch. Every gate ran only
while an agent was in the room.

**A repo with no pr-gate gets a finding, not a silent ship.** Say so in one sentence and offer
`/audit-setup` to add a CI workflow that runs the tests on pull requests, plus dependency update
config, and to print the branch-rule command. **prod != main (DRIFT)** means production runs code
the base branch does not have. Name it, and fix the branch layout before opening a pull request
that would widen the gap.

---

## Step 1: Sync with base

```bash
git fetch origin {base_branch}
git merge origin/{base_branch} --no-edit
```

**If there are merge conflicts:**

1. List the conflicting files.
2. Ask: "Merge conflicts in {N} files. Want me to resolve them, or do you want to handle it?"
3. If the user says resolve: fix the conflicts, stage, and commit with the message
   "merge: resolve conflicts with {base_branch}".
4. If the user says handle: stop and wait.

**If the merge is clean:** continue without comment.

---

## Step 2: Run tests

```bash
{detected_test_command}
```

Timeout: 300 seconds (5 minutes).

**If tests pass:** continue.

**If tests fail:**

1. Show a failure summary (the first 3 failures).
2. Do not open a menu; a failing test has one safe default. Say "tests failed, fixing" and
   attempt the fix, re-running the tests (at most 2 attempts). If both attempts fail, stop
   shipping and report the failures with their output. Pushing anyway is a decision a person
   makes in words. Never offer it as an option and never do it on your own.

---

## Step 3: Push

```bash
git push -u origin {current_branch}
```

If the push fails (for example, it would need a force push), ask before using
`--force-with-lease`. Never use a plain `--force`.

---

## Step 4: Open the pull request

### 4a: Generate the pull request content

Look at every commit on the branch:

```bash
git log --oneline {base_branch}..HEAD
git diff --stat {base_branch}..HEAD
```

Write:

- **Title:** short (under 70 characters), describes the change.
- **Body:** summary bullets, test plan, any notes (including any rails finding from Step 0d).

### 4b: Create the pull request

Optional flags: if `--reviewers @a,@b` was passed, add `--reviewer a,b`; if `--draft`, add
`--draft`. Put them in `{flags}` below.

```bash
gh pr create --title "{title}" {flags} --body "$(cat <<'EOF'
## Summary
{2-4 bullet points from the commit analysis}

## Test Plan
- [x] Tests pass locally
- [ ] {any manual verification needed}

---
Shipped via `/ship`
EOF
)"
```

Without the GitHub CLI (or on another git host): push, print the compare URL the host gives you,
and ask the user to open the pull request there. Record the ship row as `blocked` until the
checks can be read.

### 4c: Wait for the checks on the HEAD commit, then report

Never write "Shipped" while the pull request's checks are pending or red. Read the check runs
attached to the exact commit you pushed. Do not rely on `gh pr checks --watch` alone, which can
reprint an earlier run.

```bash
sha=$(gh pr view {n} --json headRefOid --jq .headRefOid)
gh run watch $(gh run list --branch {branch} --limit 1 --json databaseId --jq '.[0].databaseId') --exit-status
gh api "repos/{owner}/{repo}/commits/$sha/check-runs" --jq '.check_runs[] | "\(.name)\t\(.status)\t\(.conclusion)"'
```

Save the evidence, then record the checklist row (above):

```bash
{ echo "sha $sha"; gh pr view {n} --json url --jq .url;
  gh api "repos/{owner}/{repo}/commits/$sha/check-runs" --jq '.check_runs[] | "\(.name)\t\(.status)\t\(.conclusion)"'; } \
  > .devproto/evidence/ship.txt
```

If the repo has no pull-request gate (Step 0d), say "no check ran" in the report. That line is the
finding, and the ship row stays `blocked` with that reason until a gate exists. If a person
accepts the gap, write that down in the handoff as an exception; it is still not a pass.

```
Shipped.
├─ Branch: {branch} -> {base}
├─ Synced: {merge status}
├─ Tests: {pass/fail/skipped} (local)
├─ Checks: {CI success on {sha[0:7]} | no pull-request gate in this repo}
├─ PR: {PR URL}
└─ Next: /closeout-stack (its retro step records this session's learnings; /compound is the weekly cross-session retro, not a link in this chain)
```

---

## Flags

| Flag                        | Effect                           |
| --------------------------- | -------------------------------- |
| `--skip-tests`              | Skip Step 2 entirely             |
| `--draft`                   | Create the pull request as draft |
| `--no-sync`                 | Skip Step 1 (merge with base)    |
| `--reviewers @user1,@user2` | Request reviewers on the PR      |

`--skip-tests` is an exception, not a pass: say so in the report and in the pull request body,
and the local test line reads "skipped".
