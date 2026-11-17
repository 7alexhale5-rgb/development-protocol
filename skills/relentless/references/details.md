# Relentless: full details

Moved word for word from SKILL.md on 2026-11-16, when SKILL.md became a one-page summary. Read the section you need.

## The tool

Every command below is `python3 <relentless skill folder>/scripts/sweep.py`, shortened
here to `sweep`. It needs only Python 3.9 or newer and a POSIX shell (macOS or Linux).
**The ledger lock is POSIX-only:** it takes an exclusive lock with `fcntl.flock`, a module
that does not exist on native Windows Python. Run it on macOS, Linux, or Windows through
WSL; a plain Windows `python3` will fail to import the script.

Ledgers live in the project, at `<repo>/.sweeps/<slug>/`. The repo is the git root of the
folder you run from, or that folder itself outside git. Pass `--project <path>` to any
command to use another project's store, or set `SWEEP_HOME` to put the whole store
somewhere else. The ledger you are in is found automatically when you own exactly one open
sweep; otherwise name it with `--slug`.

Each ledger folder holds `ledger.json` (the whole state), `RESUME.md` (rewritten on every
change) and a `.lock` file. Commit the ledgers if the team should share a paused sweep;
ignore `.sweeps/**/.lock`, `.sweeps/**/*.tmp`, and `.sweeps/stop-hook.log` either way.
The hook diagnostic log is excluded because a later hook failure can append to it
after final review; it is not release proof. Closed and abandoned sweeps
move to `.sweeps/_closed/`.

**Session ownership.** A ledger belongs to the session that last changed it. The id comes
from `SWEEP_SESSION_ID`, then `CLAUDE_CODE_SESSION_ID`, then `CODEX_THREAD_ID`. Claude Code
subagents share their parent's id. With no id, ownership is unbound and no Stop hook acts
on the ledger; file-read proof is still required for a verified close.

## Evidence

A visit at L2 or above needs `--evidence`: the specific thing you saw that proves the depth.
Name the lines that matter, the caller you followed, the command and what it printed.
"Looked fine" is not evidence. The same goes for findings, a rule borrowed from Trail of
Bits' audit-context-building skill: every claim cites a line, or it becomes an open
question. Record an uncited one as `sweep finding "OPEN: ..."` so nobody mistakes it for a
result.

The ledger checks this. At `close`, every file-path item at L2 or above is matched against
the file reads in the transcript of the session that visited it, subagents included: read
tool calls paired with successful results, and successful shell commands that name the file
and return its full text. Requests without results and denied reads do not count. Numbered
partial Read results can combine to cover all lines; one partial read cannot prove L2.
A truncated shell result cannot prove whole-file coverage. Unrecognized or binary result
formats do not gain full coverage automatically. A visit with no full read behind it makes
`close` refuse and name the file. Marking items to quiet the hook defeats the whole point:
the ledger is the proof the user relies on, and a false one is worse than an honest
"partial".

The read audit knows Claude Code's transcript format and location. `SWEEP_TRANSCRIPTS`
points it at another root containing compatible `*/<session-id>.jsonl` receipts. File items
without a visiting session or readable transcript make `close` and `verify` refuse; evidence
strings alone cannot substitute for captured successful reads. Non-file items are counted
as unauditable and reported separately.

**Retain the proof.** Keep visiting-session transcripts while the ledger is used for current
verification. `verify` re-audits them; pruning or rotating them makes a fresh verification
fail even when the ledger and project are unchanged. A past recorded pass remains historical
evidence, not a replacement for missing proof.

### Strict Codex read proof (opt-in)

`CODEX_THREAD_ID` binds ownership; it never proves a read. Enable the native output checker
when recording each Codex file visit, then close the sweep:

```text
SWEEP_CODEX_READ_PROOF=1 python3 <relentless skill folder>/scripts/sweep.py visit --slug <slug> <file> --depth 2 --evidence "complete successful file output"
SWEEP_CODEX_READ_PROOF=1 python3 <relentless skill folder>/scripts/sweep.py close --slug <slug>
```

It finds exactly one canonical UUID transcript under `<home>/.codex/sessions/`
(`SWEEP_CODEX_TRANSCRIPTS` overrides). All session metadata must match that UUID.
It accepts this narrow `functions.exec` shape, with no other calls or options:

```javascript
const r=await tools.exec_command({cmd:"cat /absolute/canonical/file"});text(r)
```

The tool output must succeed and equal the current complete UTF-8 file bytes. Requests
alone, failed or truncated results, arbitrary JavaScript, batched calls, conflicting
session IDs, and changed or deleted targets cannot pass. The fixture contract matches
Codex CLI 0.158.0-alpha.2.1; recheck real output if the host format changes.

One successful read never grants dependency tracing or runtime depth. Do not backfill old
visits, manufacture receipts, or use `--force` to claim a verified close. With this option
unset during a new Codex file visit, its provider stays unknown and close refuses.
Enable it, perform a fresh complete read, and record a new real visit with `visit --force`
(the revisit option, never `close --force`). Previously required Codex proof remains
required after the flag is removed. The Claude successful-result lane stays unchanged.

## Parallel work

Match the agent count to the check, not to the ambition. A fact one command can settle
(does this string appear anywhere, how many files match) gets one command, not a subagent.
Fan out only when there are sizeable, independent batches that each need real reading, and
only if your agent supports subagents. A fan-out buys wall-clock time, not savings:
Anthropic's multi-agent research write-up measured about fifteen times the tokens of a
single chat.

When you do fan out: you open the sweep and you close it. Give each worker the slug, a
batch of 10 to 40 ids, the floor, and the evidence standard. Workers record their own
visits and findings (the ledger is locked, so concurrent writes are safe) and report back
briefly. Long output goes to a file beside the ledger, and each item comes back as one
short line, because your context is the scarce resource. A read-and-report worker runs fine
on a cheaper model. Their reports are claims, so open a few of the files they marked and
check the evidence matches. In Claude Code, subagents share your session id, so their
ledger work counts toward your stop check.

## The stop check (optional hook)

`hooks/relentless-stop.py` is a Stop hook for agents that support one (Claude Code does).
Wire it for both `Stop` and `StopFailure` in your settings, with the installed path:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 <relentless skill folder>/hooks/relentless-stop.py",
            "timeout": 10
          }
        ]
      }
    ],
    "StopFailure": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 <relentless skill folder>/hooks/relentless-stop.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

It reads the `.sweeps/` store of the project the session runs in. When you try to end a
turn while a sweep you own is open, it blocks and shows the coverage line. You then have
three honest moves: keep going, `close` if the work is finished, or `checkpoint --why` if
you must stop (budget, a blocker, or the user paused or changed topic). It blocks again only
if you made progress since its last block, so it cannot loop. If you stop again with no new
progress, it checkpoints the sweep for you and tells the user it is paused. On a
`StopFailure` (usage limit, API error) it checkpoints every open sweep you own, with the
failure as the reason. It never blocks a sweep another session owns.

It fails open: bad input, an unreadable ledger, a busy lock or any crash lets the turn end,
and the reason goes to `.sweeps/stop-hook.log` (only if that store already exists;
`RELENTLESS_LOG` overrides). It has no disable switch; the release valves are the ledger
commands. By design (decided 2026-09-22) it does not stand down on `stop_hook_active` the
way most Stop hooks should: its re-block needs the at-floor count to strictly rise, and that
count is bounded by the universe, so it cannot fire forever.

Without the hook, the loop still works. You hold yourself to the same rule: never end a
turn with an open sweep you own unless you closed it or checkpointed it with a reason.

To ask the user something mid-sweep, use a question tool that waits inside the turn if your
agent has one (Claude Code: AskUserQuestion). It does not end the turn.

## Checklist

This skill has no row of its own in the development protocol checklist. It makes another
row's evidence honest when that row's work is a sweep: `review` over every changed file,
`research` to saturation, `audit-setup` across every hook, or a migration inside `build`.
Close the sweep before sealing the candidate. Sweep writes remain candidate changes;
never mutate `.sweeps/` after final review. For the review row, retain the archived ledger
as an instrument alongside the canonical review evidence and verifier:

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id=<work-id> --step review --result pass \
  --evidence .devproto/evidence/review.json \
  --instrument .sweeps/_closed/<slug>-<stamp>/ledger.json \
  --verify "python3 <review-stack skill folder>/scripts/verify_review.py .devproto/evidence/review.json --project <repo> --work-id=<work-id> --commit <current-HEAD> && python3 <relentless skill folder>/scripts/sweep.py verify .sweeps/_closed/<slug>-<stamp>/ledger.json"
```

For other applicable rows, sweep evidence supplements that row's required proof; it
cannot replace behavior checks, scope binding or independent review.

`verify` exits 0 only for a sweep closed with every check passed. A forced close, an open
sweep or an unreadable file exits non-zero, and it never writes the ledger.

## Proving the tool

`python3 scripts/sweep.py --selftest` and `python3 hooks/relentless-stop.py --selftest`
exercise every refusal. `python3 scripts/mutants.py` then breaks each guarded branch on
purpose, in memory, and fails if any self-test still passes: a check that has only ever run
green proves nothing. The package's unit tests run all three.

## Domain references

Read the one that fits before you enumerate:

- `references/codebase.md`: files, symbols and call sites in a repo
- `references/lists.md`: companies, people, records from several sources
- `references/research.md`: sources on a topic, to saturation
- `references/audits.md`: targets crossed with checks, against the live system
- `references/migrations.md`: every reference to an old thing, until none remain

### Retained read requirements

Enumeration and visits retain `item_kind`; file visits also retain `proof_provider` and
`read_proof_required`. Later checks use these requirements even after a session change
or removal of the Codex opt-in flag. Missing required files or transcripts fail.
A legacy visit without retained kind/provider is unverified until a new real visit
records and proves it; verification never manufactures provenance. Explicit non-file
items keep their domain evidence and do not require a file transcript.
