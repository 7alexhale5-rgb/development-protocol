# Closeout Stack: Templates

The resume prompt (Step 10c), the session save (Step 5) and the handoff (Step 6).

## Contents

1. Resume prompt schema, rules and examples
2. Session save template
3. Handoff template

---

## 1. Resume prompt

The final message of every closeout must contain a fenced code block in this schema. At most 8
lines. The user pastes it into a fresh session to resume with full context.

### Schema

```text
cd <project path> && Resume <PROJECT>: <next task>.
Read handoff: .devproto/handoffs/<YYYY-MM-DD>-<slug>.md
Last commit: <hash>, <subject>
State: <N tests>, branch <name> <ahead/behind>, <key stat>
Files: <N changed> (<top 2 or 3 paths, then "..." if more>) | none
NEXT: <specific skill invocation and task>
Apply: <N> retro findings, see §Retro Findings      <- OPTIONAL, only when Step 7.5 found some
Blockers: <list | none>
```

### Rules

- **Fenced code block.** Wrap it in plain triple backticks so one-click copy works.
- **Line 1** changes into the project folder AND states the resume intent on the same line. Use
  the real path, starting with `~/` when it is under the home folder.
- **Line 2** names the handoff file so the new session can read the full context.
- **Line 3** has the last commit hash if code was committed this session. If nothing was
  committed, write `Last commit: (none this session, uncommitted: <N> files)`.
- **Line 4** carries concrete state: test count, branch status (ahead or behind), and one
  project-specific number (LOC, routes, tables, migrations, open checklist rows).
- **Line 5** lists this session's change surface. It matters when "Last commit" does not show the
  full picture (several commits, dirty-state closeouts, doc-only edits before a commit). Write
  `Files: none` if nothing changed.
- **Line 6** names the specific next skill invocation (for example
  `/build-stack slice 3: audit trail export` or `/planning-stack the retry router`). Never just
  "continue". If a checklist work item is open, name its next row.
- **Apply line (optional).** Emit it ONLY when Step 7.5 produced findings AND wrote them into the
  handoff. It goes between `NEXT:` and `Blockers:`. It is a visual cue, not a separate contract:
  the next session sees the findings anyway when it reads the handoff on line 2. Leave it out
  when Step 7.5 was silent, skipped or failed.
- **Blockers line** lists blockers or says `Blockers: none`. Unknowns that block the next step
  belong here too.

### Partial-failure variant

If any closeout step failed, add a line at the TOP:

```text
STATUS: partial, <step> failed: <one-line reason>
cd <project path> && Resume <PROJECT>: <next task>.
...
```

### Example: healthy close, no retro findings

```text
cd ~/code/billing-service && Resume billing-service: slice 3, audit trail export.
Read handoff: .devproto/handoffs/2026-04-14-billing-audit-export.md
Last commit: a26689e, feat(audit): log filters and csv export
State: 2375 tests passing, branch main ahead 3, 20 commits since the last release
Files: 7 changed (web/app/admin/audit/page.tsx, web/app/api/audit/route.ts, web/lib/audit-filters.ts, ...)
NEXT: /build-stack slice 3, audit trail export (3 files, about 180 LOC)
Blockers: none
```

### Example: healthy close, with retro findings

```text
cd ~/code/billing-service && Resume billing-service: slice 3, audit trail export.
Read handoff: .devproto/handoffs/2026-04-14-billing-audit-export.md
Last commit: a26689e, feat(audit): log filters and csv export
State: 2375 tests passing, branch main ahead 3, 20 commits since the last release
Files: 7 changed (web/app/admin/audit/page.tsx, web/app/api/audit/route.ts, web/lib/audit-filters.ts, ...)
NEXT: /build-stack slice 3, audit trail export (3 files, about 180 LOC)
Apply: 2 retro findings, see §Retro Findings
Blockers: none
```

### Example: partial close, ship failed

```text
STATUS: partial, /ship failed: typecheck error in web/app/api/audit/route.ts:47
cd ~/code/billing-service && Resume billing-service: fix the typecheck, then retry ship.
Read handoff: .devproto/handoffs/2026-04-14-billing-ship-blocked.md
Last commit: a26689e, feat(audit): log filters and csv export
State: 2375 tests passing, branch main ahead 3, ship blocked on the type checker
Files: 3 changed (web/app/api/audit/route.ts, web/lib/audit-filters.ts, web/tests/audit.test.ts)
NEXT: /build-stack fix the type error at web/app/api/audit/route.ts:47, then /ship
Blockers: type check fails, log at .devproto/evidence/ship-2026-04-14.log
```

---

## 2. Session save template

Path: `.devproto/sessions/<YYYY-MM-DD>-<project-slug>.md`

**Idempotency.** If today's file exists for this project, READ it, merge the new content under a
`## Update HH:MM` heading, then overwrite. Never create a second file for the same date and
project.

### Frontmatter (required)

```yaml
---
date: <YYYY-MM-DD>
type: session
project: <project-slug>
tags: [session, <project-slug>, closeout]
mode: <eod|pivot|ship>
---
```

### Body

```markdown
# Session: <YYYY-MM-DD>, <brief topic>

## Summary

<2 or 3 sentences: what was done, the key state change, the review verdict if there was one.>

## Changes

- `<path>`: <what changed, with line ranges if the edit was surgical>
- ...

## Decisions

- <decision>: <rationale>
- ...

## Artifacts

- Commit: <hash>, <subject> (or "none this session")
- Pull request: <url | "none">
- Handoff: `.devproto/handoffs/<YYYY-MM-DD>-<slug>.md`

## Pending

- <what is next: a specific action, not a generic one>
- ...

## Related

- <links to decisions, plans or earlier sessions; optional>
```

### Second closeout on the same day

When today's file already exists, add a dated update instead of rewriting. Existing sections
stay. New content goes under a fresh `## Update HH:MM` heading right before `## Related`:

```markdown
## Update 16:42

### Additional changes

- `<file>`: <what changed since the last closeout>

### Additional decisions

- ...

### Artifacts

- Commit: <new hash>
- Handoff: `.devproto/handoffs/<YYYY-MM-DD>-<slug>.md` (updated)
```

This keeps one file per date and project while keeping the record of every closeout that day.

---

## 3. Handoff template

Path: `.devproto/handoffs/<YYYY-MM-DD>-<slug>.md`

Write it for a stranger who has the repository and nothing else. Every claim names its source.

```markdown
---
date: <YYYY-MM-DD>
type: handoff
project: <project-slug>
work_id: <checklist work id, or "none">
mode: <eod|pivot|ship>
---

# Handoff: <YYYY-MM-DD>, <brief topic>

## Goal

<One sentence: who it is for and what done looks like. Copy the checklist goal if one exists.>

## State

- Branch: <name>, <ahead N / behind N> against <upstream>
- Last commit: <hash>, <subject>
- Uncommitted: <N files | none>
- Tests: <result> from `<exact command>` at <HH:MM>
- Checklist: <next open row, or "no work item">
- Production: <commit it runs, or "not checked">

## Done this session

- <change>, in `<path>`
- ...

## Proven

- <claim>: proven by `<command>`, which printed <short result>
- ...

## Unknowns

- <anything not verified, stated as unknown, with the check that would settle it>
- (Write "none" only if every claim above has a proof line.)

## Next

- <exact skill invocation and task>
- <why this is next>

## Blockers

- <blocker and who or what can clear it | none>

## Related

- Session log: `.devproto/sessions/<YYYY-MM-DD>-<project-slug>.md`
- <plans, decisions, pull requests>

## Resume prompt

<the same fenced block emitted in Step 10>
```

Step 7.5 adds a `## Retro Findings` section before `## Related` when it has findings.

A handoff with an empty Unknowns section and no proof lines is not a handoff. It is a claim.
