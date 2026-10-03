---
name: commit
description: Creates one clean, well-messaged git commit from the current changes. Reviews the diff, matches the repo's commit style, stages specific files only, refuses to stage secrets, shows the files and message for a yes/no/edit confirmation before committing, and never pushes. Use when someone says "commit this", "make a commit", "commit my changes", "write a commit message", types /commit with an optional message hint, or after /simplify reports clean in the development protocol.
---

# Commit: stage and commit changes

Create a clean, well-messaged git commit. Commit locally only. Pushing is `/ship`'s job.

## Checklist row

This skill satisfies the `commit` row of the development-protocol checklist. After the commit
lands (step 8), renew verification, independent review and read-only simplification on
that exact committed candidate first. Only then save the commit as evidence and record
the row with a verifier that only reads:

```text
git log -1 --format='%H %s' > .devproto/evidence/commit.txt
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id=<work-id> --step commit --result pass --evidence .devproto/evidence/commit.txt \
  --verify 'test "$(git rev-parse HEAD)" = "$(cut -d" " -f1 .devproto/evidence/commit.txt)"'
```

The verifier fails if anything moves HEAD after the commit, which is what you want: a new commit
means this row must be recorded again.

The mutable checklist and receipts under `.devproto/` must stay outside release commits.
Keep them locally excluded or in an external evidence store. Do not commit a receipt after
recording it: that changes HEAD and invalidates its own binding. Commit any static metadata
before recording the final implementation receipt.

## Steps

1. **Check git status:**

   ```bash
   git status
   ```

   If there are no changes to commit (ignoring `.devproto/`) and an existing protocol
   commit needs receipt renewal, proceed directly to Step 8 with that existing SHA.
   Otherwise tell the user there are no changes and stop.

2. **Review the diff**, both staged and unstaged:

   ```bash
   git diff
   git diff --cached
   ```

3. **Check recent commit style** for consistency:

   ```bash
   git log --oneline -10
   ```

4. **Draft a commit message:**
   - Summarize the nature of the changes (new feature, bug fix, refactor, docs, and so on).
   - Keep the first line under 72 characters.
   - Add a body paragraph if the changes are non-trivial.
   - Match the style of recent commits in the repo (prefixes like `feat:` or `fix:`, tense,
     capitalization).
   - If the user gave a message hint as the argument, work it in.
   - If the team adds a co-author trailer for agent-written commits, end with it.

5. **Stage the changes:**
   - Stage specific files (`git add <file>`), never everything at once.
   - Never stage files that look like secrets: `.env` files, credentials, private keys, API keys
     or tokens.
   - Inspect the COMPLETE final index with `git diff --cached --name-status -z`
     and `git diff --cached`, including entries staged before this skill ran.
   - Require its paths and hunks to match the approved scope exactly; scan every
     staged blob for secrets. An already-staged secret also blocks the commit.
   - Preserve unrelated staging with a reviewed binary patch in private temporary
     storage, then unstage only those unrelated paths without changing worktree
     content. Restore their staging after the scoped commit and verify equality.
     If staging cannot be preserved safely, stop without committing.
   - If you are unsure about a file, ask the user.

6. **Present the commit for confirmation.** Show the user:
   - the files being committed
   - the proposed commit message
   - then ask: "Commit this? (yes/no/edit)"

7. **Handle the answer** before running `git commit`:
   - **yes**: run `git commit`.
   - **no**: stop without committing.
   - **edit**: ask what to change, revise the message, and present it again (back to step 6).

8. **After committing**, show the result:
   ```bash
   git log --oneline -1
   git status
   ```
   Before recording any commit row, run verification and required independent review
   of this exact committed candidate. Re-record review, then re-pass simplify with
   `/simplify --check` on the same complete BASE..HEAD scope. Record the commit row
   above only after these prerequisites pass, using the existing SHA. Do not create
   another commit to record receipts. If read-only simplification finds a defect,
   fix, test, commit and repeat verification and review before recording commit.

## Important

- NEVER commit without the user's confirmation.
- NEVER stage `.env`, credential or secret files.
- NEVER use `git add -A` or `git add .`. Stage specific files.
- NEVER amend earlier commits unless explicitly asked.
- NEVER push. Only commit locally.

## Next

In the development protocol, `/ship` comes next: sync with the base branch, run the tests, push,
open the pull request, and wait for checks on the exact commit.

After the final commit, run focused/full verification and required independent review
against this exact committed candidate. Re-record review, perform `/simplify --check`,
and re-pass commit with proof of this existing SHA, without making another commit.
Shipping checks through commit and revalidates the candidate. Any later mutation or
merge requires renewing those receipts; never edit an old review's commit or hash.
