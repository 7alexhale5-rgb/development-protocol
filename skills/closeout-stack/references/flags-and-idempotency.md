# Closeout Stack: Flags and Idempotency

## Flag matrix

| Flag            | Step affected | Effect                                                                                        |
| --------------- | ------------- | --------------------------------------------------------------------------------------------- |
| `--mode=eod`    | Step 0        | Default. Ask before ship, run compound automatically, default exit is Stop.                   |
| `--mode=pivot`  | Step 0        | Skip ship. Ask before compound. Default exit is Archive and resume in a fresh session.        |
| `--mode=ship`   | Step 0        | Ship automatically. Run compound automatically. Default exit is Stop.                         |
| `--ship`        | Step 4        | Force ship.                                                                                   |
| `--no-ship`     | Step 4        | Force skip.                                                                                   |
| `--no-commit`   | Step 3        | Stop the pipeline if the tree is dirty.                                                       |
| `--no-save`     | Step 5        | Skip the session save.                                                                        |
| `--no-handoff`  | Step 6        | Skip the handoff. Step 10 builds the resume prompt from STATE_PAYLOAD.                        |
| `--no-memory`   | Step 7        | Skip lessons from the user.                                                                   |
| `--no-retro`    | Step 7.5      | Skip the retro audit and the handoff's Retro Findings section.                                |
| `--no-wiki`     | Step 8        | Skip the docs refresh.                                                                        |
| `--no-compound` | Step 9        | Skip report generation; cannot waive required compound proof or certify closeout.             |
| `--dry-run`     | All           | Print the planned steps. Write nothing. Emit a sample resume prompt to show the format.       |
| `--resume-only` | 1, 10         | Only the Step 1 probe and the Step 10 output. The escape hatch when you only need the prompt. |

## Quick reference by mode

| Mode                   | Ship? | Compound? | Default exit                 | Use when                             |
| ---------------------- | ----- | --------- | ---------------------------- | ------------------------------------ |
| `--mode=eod` (default) | asks  | auto      | Stop                         | Wrapping up for the day              |
| `--mode=pivot`         | skip  | asks      | Archive, resume from handoff | Clearing context to keep working     |
| `--mode=ship`          | auto  | auto      | Stop                         | After /review-stack says SHIP IT     |
| `--resume-only`        | n/a   | n/a       | n/a                          | Emergency: just emit a resume prompt |

The mode is detected automatically when no flag is given (see Step 0 in `SKILL.md`).

## Idempotency rules

| Step          | Rule                                                                                                                                                                                                                              |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 3 commit      | Skip if the tree is clean or a commit was already made this turn.                                                                                                                                                                 |
| 4 ship        | `/ship` handles its own state and will not open a duplicate pull request.                                                                                                                                                         |
| 5 save        | Merge into today's project file under `## Update HH:MM`. Never create a second file for the same date and project.                                                                                                                |
| 6 handoff     | If a handoff for the same slug was written minutes ago, ask whether to update it or write a new one.                                                                                                                              |
| 7 lessons     | Read `.devproto/feedback.md` before writing. Add dated lines to an existing rule. Never duplicate a rule.                                                                                                                         |
| 7.5 retro     | If `## Retro Findings` already exists in the handoff, add a `### Update HH:MM` subsection inside it instead of rewriting the section. This dedupes within a session only. Findings in a new session are surfaced fresh by design. |
| 8 docs        | Only fire when the 3-session threshold is met AND the doc is missing or stale.                                                                                                                                                    |
| 9 compound    | Avoid duplicate report generation when today's learning file exists; after shipping prerequisites pass, validate current work coverage and execute and record fresh pending compound proof as Step 9 requires before closeout.    |
| 9.5 checklist | Re-recording the same row with the same evidence is harmless. New evidence reopens later rows, which is the point.                                                                                                                |

Running `/closeout-stack` twice in one session must not duplicate any write.
