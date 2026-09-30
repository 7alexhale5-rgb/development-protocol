# .planning — handoff and in-flight state

## Inputs

- Working: `.planning/handoff-codex.md`.

## Process

1. `closeout-stack --mode=codex` (from the two-agent workflow, environment-level) regenerates
   this handoff before a Codex review.
2. Read it before picking up work Codex or another session left mid-flight.

## Outputs

- `.planning/handoff-codex.md`, regenerated per closeout.

## Human check

Alex reads the handoff before resuming work. Pass: it matches `git log` and the actual repo
state. Fail: treat it as stale, regenerate via `closeout-stack --mode=codex`.
