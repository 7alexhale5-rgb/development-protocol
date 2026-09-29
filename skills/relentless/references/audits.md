# Audits

A set of checks run against a set of targets: "is every hook safe when it crashes", "does
every route check auth", "which scheduled jobs still point at dead paths".

## Build the universe from the live system

- Enumerate targets from what actually runs, not from the documentation: the settings file
  as the agent harness reads it, the routes the server registers, the jobs the scheduler has
  loaded, the environment that is deployed. Where they disagree, the running system wins. A
  document is a claim about the system, and the older claim loses.
- Then cross targets with checks. One item per pair, with ids like
  `hooks/foo.py#fails-open` and `hooks/foo.py#has-test`. A shell loop over both lists,
  piped into `add --stdin`, keeps it mechanical.
- Record the target list as a stored command where you can, so `close` can re-run it and
  catch a target that appeared mid-audit.

## Traps

- **Config versus behaviour.** A setting that says X while the process does Y is the
  finding, not a footnote.
- **Two hosts.** Two agents (Claude Code and Codex, say) can each run a different copy of
  the same file. Audit both, or say which one you covered.
- **A check that cannot fail.** A green result that has only ever been green proves nothing.
  Break the target on purpose, watch the check go red, then restore it.

## What the depths mean here

- L2: the code or config read.
- L3: the effective behaviour traced: what runs, with what input, from where.
- L4: exercised. The target was run or broken on purpose and the result seen. Evidence is
  the command and its output.

Audits default to an L3 floor. Use L4 for the checks the audit exists to prove.

## Done conditions

- "Every Stop hook in the settings file crossed with {fails open, stands down when it should,
  has a test}, each at L3; failures listed with the line that fails."

## Pairs with

`/review-stack` for the code the audit flags, and `/audit-setup` when the targets are the
agent's own instructions, skills and hooks.
