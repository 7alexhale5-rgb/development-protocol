# Output templates for build-stack

Loaded by Step 6 and Step 7 of `SKILL.md`. All files go inside the repository under `.devproto/`,
so a teammate or a fresh session can pick them up.

## Handoff doc (Step 6, context gate)

Write this when the context gate calls for a handoff. Path:
`.devproto/handoffs/{YYYY-MM-DD}-implementation-{goal-slug}.md`

```markdown
---
date: { YYYY-MM-DD }
type: handoff
project: { project name }
work_id: { checklist work id, if any }
status: partial
---

# Implementation handoff: {GOAL}

## Completed

{completed tasks, with the files each one changed}

## Remaining

{remaining tasks from the plan, in order}

## Last checkpoint

- Types: {pass/fail/skipped}
- Lint: {pass/fail/skipped}
- Build: {not yet run / pass / fail}
- Tests: {not yet run / pass / fail}

## Files changed so far

{list}

## Exceptions

{any --no-verify, skipped test, or check that could not run: reason, scope, owner, next proof}

## Unknown

{anything not proven yet, stated as unknown, never as done}

## Resume prompt

"Continue implementing {GOAL}. Completed: {list}. Remaining: {list}. Last checkpoint was
{status}. Plan: {plan path}. Checklist work id: {id}. Run the checklist status first."
```

## Summary report (Step 7a)

```text
---
{Implementation Complete | Build Blocked: unverified}
├─ Classification: {BUGFIX|SMALL|MEDIUM|LARGE}
├─ Tasks: {completed}/{total}
├─ Files changed: {count}
├─ Files created: {count}
├─ Verification:
│  ├─ Types: {pass|fail|skipped|N/A}
│  ├─ Lint: {pass|fail|skipped|N/A}
│  ├─ Build: {pass|fail|skipped|N/A}
│  ├─ Tests: {pass|fail|skipped|N/A}
│  └─ UI journey: {pass|fail|not run: reason|N/A}
├─ Auto-fixes applied: {count}
├─ Perspectives: {N} run, {N} with findings
├─ Checklist: build row {pass|blocked|open}
└─ Context left: {Fresh|Moderate|Depleted|Critical} at completion
---
```

## Next steps (Step 7c)

Pick the message that matches the state.

- `--no-verify` or missing required proof:

  > "Build blocked and unverified. Remaining checks: {checks}. Owner: {owner}.
  > Next proof: {command or observation}. The build row stays blocked; do not ship."

- Verification passed cleanly (no audit):

  > "Ready for review and shipping. Suggested next steps:
  >
  > - `/review-stack --branch --plan <plan>` for an independent review (the `review` row)
  > - `/simplify` to cut what the change does not need
  > - `/commit`, then `/ship` to push and open a pull request"

- `--audit` was used and a remediation report exists:

  > "Audit complete. Remediation report has {N} findings.
  >
  > - {auto_count} can be auto-fixed: run the commands in the Auto-Fix Manifest
  > - {manual_count} need manual fixes: see Priority Groups 1 and 2
  > - After fixing: `/review-stack --quick` to re-check
  > - When clean: `/commit`, then `/ship`"

- Verification had issues that were surfaced, not auto-fixed:

  > "Implementation complete, but {N} verification issues need attention:
  > {list}
  > Fix these and I will re-verify. The build row stays open until the checks pass."

- LARGE work:

  > "Large implementation complete. Run `/review-stack` before committing. Work split across
  > helpers benefits from a coherence check by a reviewer that saw none of it being written."

## Session note (Step 7d, optional)

Write for MEDIUM or LARGE when verification passed. Path:
`.devproto/notes/{YYYY-MM-DD}-implementation-{goal-slug}.md`

```markdown
---
date: { YYYY-MM-DD }
type: session
project: { project name }
---

# Implemented: {GOAL}

Classification: {type}, {N} files, verification {status}.
Key decisions: {implementation decisions made during the build, and why}.
```
