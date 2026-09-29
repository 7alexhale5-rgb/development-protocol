# Closeout Stack: Output Templates

The three elements of the final closeout message, plus the ledger of excuses for skipping them.

## Contents

1. 10b: Closeout Stack Report
2. 10c: Resume prompt (standard form)
3. 10d: Minimal fallback (context depleted or state incomplete)
4. 10e: Exit menu
5. Rationalizations to reject

---

## 10b: Closeout Stack Report

```text
---
Closeout Stack Report
├─ Mode: eod | pivot | ship
├─ Steps:
│  ├─ commit:    ✓ <hash> | ⊘ skipped (clean) | ✗ failed
│  ├─ ship:      ✓ <pr_url> | ⊘ skipped (asked/declined) | ✗ failed (<reason>)
│  ├─ prod==main: ✓ <sha> | ⊘ not ship mode | ✗ drift (<sha> vs <sha>) | ? not verified
│  ├─ save:      ✓ <path> | ⊘ skipped
│  ├─ handoff:   ✓ <path> | ⊘ skipped | ✗ failed
│  ├─ lessons:   ✓ <N entries updated> | ⊘ no corrections this session
│  ├─ retro:     ✓ <N findings → handoff §Retro Findings> | ⊘ silent (clean) | ⊘ skipped (<reason>) | ✗ failed (<reason>)
│  ├─ docs:      ✓ <topic> refreshed | ⊘ threshold not met
│  ├─ compound:  ✓ <path> | ⊘ skipped
│  └─ checklist: ✓ closeout passed | ⊘ mid-work (next row: <row>) | ✗ blocked (<open rows>)
├─ Failures: <list | none>
├─ Safe to close: ✓ yes | ✗ not yet (<first failing question>)
└─ Resume prompt: emitted ✓
---
```

Mark each step ✓ (done), ⊘ (skipped, with the reason) or ✗ (failed, with the reason). Use `?`
only for a check that could not be run. Never show ✓ for something that was not checked.

---

## 10c: Resume prompt (standard form)

Plain triple-backtick fence with no language tag, so one-click copy works. Seven lines:

```text
cd <project path> && Resume <PROJECT>: <next task>.
Read handoff: .devproto/handoffs/<YYYY-MM-DD>-<slug>.md
Last commit: <hash>, <subject>
State: <N tests>, branch <name> <ahead/behind>, <key stat>
Files: <N changed> (<top 2 or 3 paths, then "..." if more>)
NEXT: <specific skill invocation and task>
Blockers: <list | none>
```

The `Files:` line matters most for multi-commit sessions and dirty-state closeouts, where "Last
commit" does not show the full change surface. Write `Files: none` if nothing changed.

If `STATE_PAYLOAD.failures` is not empty, put `STATUS: partial, <step> failed: <one-line
reason>` as the first line of the block.

The full schema, line rules and examples are in `templates.md`.

---

## 10d: Minimal fallback (context depleted or state incomplete)

If you cannot read `templates.md`, or STATE_PAYLOAD is empty or incomplete, emit this instead. It
gives the next session enough to recover:

```text
cd <current folder or best guess> && Resume <project or "prior session">: state recovery needed.
Last commit: (run `git log -1 --oneline` to recover)
State: closeout-stack stopped before the full state probe finished
NEXT: /closeout-stack --resume-only to retry, or read the newest file in .devproto/sessions/
Blockers: state recovery needed
```

If a team installs an end-of-turn hook to check for the resume prompt, a workable rule is: a
fenced block whose first content line starts with `cd ` or `Resume ` (or `STATUS:`), and a later
line that starts with `NEXT:`. Both forms above pass it.

---

## 10e: Exit menu

Choose the default by mode:

| Mode  | Default choice                                                      |
| ----- | ------------------------------------------------------------------- |
| ship  | `2. Stop`: shipped; nothing is waiting to be resumed                |
| eod   | `2. Stop`: done for the day; archive whenever                       |
| pivot | `1. Archive`: the next session starts from the handoff, so start it |

A not-clear safety verdict overrides the mode default: option 2, every time. Say so on the line
above the menu in one sentence. Closing is cheap to delay and expensive to get wrong.

```text
Choose how to continue:

  1. Archive  - I close this session and start the next one from the handoff
  2. Stop     - end here, archive later
  3. Compact  - keep talking in this session (only if context still has room)
```

Then stop. No commentary after.

**Why option 1 is an offer, not an instruction.** It used to read "clear the context and paste
the resume prompt above". That is an instruction, not an offer. Archiving and starting the next
session are things the agent can often do itself. Ending on a string the user has to carry
leaves the process half-finished at exactly the moment context is about to be thrown away. If
your agent cannot archive its own session, option 1 becomes the one exact action for the user to
take.

---

## Rationalizations to reject

Every excuse below has been used to skip Step 10. Recognize them when context is tight.

| Excuse                                                   | Reality                                                                                                          |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| "The handoff file already has a resume prompt"           | The next person copies from THIS message, not the file. Emit it here.                                            |
| "The pipeline failed early, I can't build STATE_PAYLOAD" | Use the 10d fallback. Still emit a fenced block.                                                                 |
| "Context is depleted, I'll skip Step 10 to save tokens"  | Step 10 is the cheapest step (about 80 tokens). Skip Step 9 (compound), never Step 10.                           |
| "I'll emit the prompt in my next response"               | There is no next response. The user asked to close out. Emit it now.                                             |
| "The user can read the handoff file directly"            | They asked for a copy-paste prompt. "See the handoff" is a different deliverable.                                |
| "A brief summary first would be helpful"                 | No. The three-element output is the deliverable. The user reads the report. They do not need narration about it. |
| "The block needs a language tag for syntax highlighting" | No. Plain triple backticks. A tag does not break the contract, but it lowers one-click copy quality.             |
