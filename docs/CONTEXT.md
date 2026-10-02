# Docs room: the standard and how to use the stack

One job: keep the user-facing docs true to what the skills and scripts actually do, in plain
English. Paths relative to the repo root.

## Inputs

- `docs/STANDARD.md`: the one-page standard (the spine, task sizes, lanes, the 17-row checklist,
  gates). Its row table must match `devproto.py steps` and `docs/PORTING.md`.
- `docs/WORKFLOW.md`: how work flows day to day (plan first, phases, sessions, second model,
  branches and team).
- `docs/DAILY-USE.md`, `docs/SETUP.md`, `docs/TROUBLESHOOTING.md`: a normal day, install and
  first run, symptoms and fixes.
- `docs/UPDATING.md`: staying current, and the maintainer's re-port loop.
- `docs/PORTING.md`: the porting contract (routed from [skills/CONTEXT.md](../skills/CONTEXT.md)).
- `README.md`: its "Read next" table lists these docs.
- `sync/sources.lock.json`: `doc:STANDARD` and `doc:WORKFLOW` are ported from private sources and
  tracked for drift like skills.

## Process

1. Change behavior in the skill or script first, then the doc that describes it, in the same
   change set.
2. For `STANDARD.md` or `WORKFLOW.md`, a change that comes from the private source is a re-port:
   follow `docs/UPDATING.md` and record it in `UPDATES.md`.
3. Writing rules from `docs/PORTING.md`: short sentences, no em dashes, no emojis, explain a
   technical word the first time. Shell examples use a `name() { ...; }` function, never a
   `D="python3 ..."` variable (breaks on zsh; `tests/test_package.py` checks it).
4. Slash references resolve to bundled skills or agent built-ins only. A personal name may appear
   only in `docs/SETUP.md` and `docs/UPDATING.md` (credit files); elsewhere say "the maintainer".
5. Run `python3 -m unittest discover tests` and `bash tests/sanitization.sh docs`.

## Outputs

- Edited `docs/*.md`, and the `README.md` "Read next" row when a doc is added or renamed.

## Human check

The maintainer follows the changed doc on a fresh clone (or a throwaway home for setup steps).
Pass: every command runs as written and the result matches the doc. Fail: fix the doc or the code
before merge.
