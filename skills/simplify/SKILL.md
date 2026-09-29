---
name: simplify
description: Reviews the uncommitted diff against four falsifiable tests (surgical changes, simplicity, no speculative features, cleanup of orphans the change created) and fixes violations before commit. Use after /review-stack returns SHIP IT or FIX THEN SHIP, before any non-trivial commit, before opening a pull request, or when someone says "simplify this", "this diff feels too big", "trim it down", "is this overcomplicated", "clean up before commit".
---

# /simplify

Last-stop gate before commit. Reviews the in-progress diff against four common pitfalls of
agent-written code, each distilled to a test you can fail. Fix what fails, leave what passes.

## Checklist row

This skill satisfies the `simplify` row of the development-protocol checklist. Save the report
below as the evidence, re-run the full suite as the verifier, and pass the test files as
instruments so a weakened test cannot keep an old pass:

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id <work-id> --step simplify --result pass --evidence .devproto/evidence/simplify.md \
  --verify "<the project's full test command>" --instrument <main test file>
```

A verdict of "borderline-only" still passes if the suite is green; the borderline items stay in
the report for the reviewer and the user.

## When to use

- After `/review-stack` returns SHIP IT or FIX THEN SHIP
- Manually before any non-trivial commit
- When a diff feels bigger than the request warranted
- Before opening a pull request for review

## What this is NOT

- Not a refactor pass. Do not introduce new abstractions.
- Not a style-guide enforcer. Match existing style even if you would do it differently.
- Not a dead-code purge for the whole codebase. Only orphans your changes created.
- Not a code-quality review. That is `/review-stack`.

## The four tests

Run each test against the current diff, staged and unstaged together. For each violation, fix it
in place. If a violation is borderline, leave it and note it in the report.

### Test 1: Surgical changes. Every changed line traces to the request.

```bash
git diff HEAD --stat
git diff HEAD
```

For every changed file:

- Is this file in scope for the user's request? If not, why is it in the diff?
- Within each file, does every changed line trace to the request?
- Did you "improve" nearby code, comments or formatting that nobody asked about?
- Did you refactor something that was not broken?

**Fix:** revert lines that do not trace to the request. `git checkout -- <file>` for whole files,
or revert single hunks (`git restore -p <file>` walks them one at a time, if your tool can answer
its prompts; otherwise edit the lines back by hand).

**Do not fix:** dead code or formatting issues that were already there before your change.
Mention them in the report; do not delete them.

### Test 2: Simplicity. Could 200 lines be 50?

For each new function, class or module:

- Is this 200 lines that could be 50? Rewrite it.
- Is this an abstraction for code used once? Inline it.
- Is this a configuration or flexibility point nobody requested? Remove it.
- Is this error handling for a case that cannot happen? Remove it.

**Senior-engineer test:** would a senior engineer reading this pull request call it
overcomplicated? If yes, simplify before committing.

### Test 3: No speculative features

Go through every new file, function and flag:

- Did the user ask for this? If not, remove it.
- Is this a "while I was here" addition? Remove it.
- Does it exist "for future flexibility"? Remove it. Add it later if and when it is actually
  needed.

### Test 4: Orphan cleanup. Your mess only.

Your changes may have created orphans: imports, variables or helpers that are now unused. Clean
those up:

```bash
# Quick orphan scan in changed files
git diff HEAD --name-only | xargs -I {} sh -c 'echo "=== {} ==="; grep -nE "^(import|from|const |let |function |def )" {}'
```

- Imports your changes made unused: remove.
- Helper functions your changes left orphaned: remove.
- Variables your changes stopped using: remove.

**Do not touch** orphans that were there before your changes.

After any fix, re-run the project's tests. A simplification that breaks a test is not a
simplification.

## Output format

Report what changed, what you left alone, and why. Save it to `.devproto/evidence/simplify.md`
as well as showing it:

```
## /simplify report

### Fixed
- {file}:{line}: {what was overcomplicated} -> {how simplified}
- {file}:{line}: orphaned import removed (created by this change)

### Left alone (out of scope)
- {file}:{line}: dead code that was already there, not this change's to remove
- {file}:{line}: style mismatch that matches the surrounding code

### Borderline (your call)
- {file}:{line}: {what is questionable, and why it was not removed}

Diff: {N} files, +{added} -{removed} (was: +{prev_added} -{prev_removed})
Tests: {command} -> {pass/fail}
Verdict: clean / fixed / borderline-only
```

## Hand-off

After `/simplify` reports clean or fixed, the next steps are `/commit`, then `/ship`. Run them in
the same turn. Do not put a menu between them. (`/commit` still shows the files and message and
asks for a yes before it commits; that confirmation is part of `/commit`, not a menu.)

## Source attribution

The four tests come from Andrej Karpathy's
[January 26, 2026 post](https://x.com/karpathy/status/2015883857489522876) on common pitfalls
when language models write code (hidden assumptions, overcomplication, side effects, losing sight
of the goal), as distilled into four principles by
[forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills).
This skill keeps the parts you can fail (the surgical-changes test, the 200-to-50 rewrite test,
dead-code restraint) and runs them inside the build flow instead of as a separate plugin.
