# Interview question bank (Step 1.6)

Ask 8 to 15 focused questions across these six categories. **Category 1 runs first**, and its
search runs before any question is asked. Ask two or three related questions at a time, in
conversation, and stop when the user says "that's enough" or "just go".

For UI, page, app or client builds, also run `/visual-spec`. Its workflow interview goes much
deeper (people and places, each workflow step by step, where the record and the physical world
drift, wants versus proposals versus unknowns, security and rights, integrations, offers,
content evidence) and produces the Visual Spec Pack.

---

## 1. Placement and filing (2 to 3 questions, asked FIRST)

### The duplicate search: run it before proposing any new folder, package or module

Never propose a new home for work without running this. Measured on 2026-09-16: a new folder was
created, given a README and an index entry, while a project of nearly the same name already
existed, was registered, and had six commits that same day. The filing rules had been read an
hour earlier. A naming rule that lives in attention fails. This one is a command:

```bash
slug="<slug>"                                  # fill in before running
old_path="<old path>"                          # fill in before running

# 1. Does a home already exist, at any depth, under any spelling?
find . -maxdepth 4 -type d -iname "*$slug*" -not -path "*/node_modules/*" -not -path "*/.git/*"
# (for a new top-level project, run the same find in the folder that holds your projects)

# 2. Is it already registered? Check the project's own index: workspace config, package list,
#    README table of contents, a projects manifest if your team keeps one.
grep -rniE "$slug" README.md package.json pnpm-workspace.yaml pyproject.toml 2>/dev/null

# 3. Was it retired under this name before?
git log --all --oneline -- "*$slug*" | head
ls archive/ _archive/ 2>/dev/null | grep -i "$slug"

# 4. Would a move break anything keyed on the path? Import paths, CI job paths, deploy config,
#    tool caches or session stores that are keyed by folder name.
grep -rn "$old_path" --include="*.json" --include="*.y*ml" --include="*.toml" \
  --include="*.ts" --include="*.js" --include="*.py" --exclude-dir=node_modules . 2>/dev/null | head
```

### Then ask

- **"Does this deserve its own workspace, or does it belong in one that exists?"** The test: do
  you switch mental modes between these tasks? Writing versus building is two workspaces.
  Drafting versus editing is one workspace with a process inside it. Default to no: if you are
  not sure something deserves its own workspace, it does not.
- **"Where does the output land, so it is already filed when it is finished?"** Output that
  lives only in a chat window still has to be copied somewhere. Deliverables go to a
  deliverables folder, drafts stay in the working folder until approved, stable rules and
  templates go to reference and template folders.
- **"What stays the same between runs, and what changes every run?"** The stable half becomes
  context. The changing half becomes per-run material.

### Naming is computed, not chosen

Follow the project's naming convention (for example kebab-case), derived from what the thing
already is. A project that already declares a name, in `package.json`, `pyproject.toml` or a git
remote, has an identity. Renaming an identity breaks every reference to it. Read the name. Do not
invent one, and do not ask the user to invent one.

### If the work touches an existing tree

Gate the migration rather than performing it:

1. Inventory first.
2. Inspect internal and external references to every path that would move.
3. Check case-insensitive name collisions (macOS and Windows file systems ignore case).
4. Present the old-to-new map for approval.
5. Copy and verify before removing anything.

Do not archive files that look unused without checking what consumes them.

---

## 2. Scope boundaries (2 to 3 questions)

- "Should this affect <related system> or only <target>?"
- "What is explicitly out of scope?"
- "Is this a standalone change or part of a larger effort?"

## 3. Edge cases and failure modes (2 to 3 questions)

- "What happens if <input> is empty, missing or malformed?"
- "How should this behave when <dependency> fails?"
- "Are there rate limits, size limits or timeout constraints?"

## 4. Technical constraints (2 to 3 questions)

- "Any performance requirements (response time, memory, cost)?"
- "Does this need to work with <existing system or API>?"
- "Are there backward compatibility concerns?"

## 5. Tradeoffs (1 to 2 questions)

- "Speed of delivery or thoroughness: which matters more here?"
- "Is this a prototype, an MVP, or production-grade?" (This also names the done tier:
  Demoable, Live, or Production-secure.)

## 6. Validation (1 to 2 questions)

- "How will you know this works correctly?"
- "Are there existing tests, or should we write new ones?"

---

Carry every answer forward as **INTERVIEW_CONTEXT**. Attribute answers to the person who gave
them: in the plan, "the user said X" is a reported claim, not a verified one.
