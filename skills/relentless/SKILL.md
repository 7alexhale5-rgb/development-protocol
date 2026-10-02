---
name: relentless
description: Keeps a coverage ledger for exhaustive sweeps, so an agent never ends a big job because it feels done. Use it whenever the work means covering everything, such as finding every call site or usage, auditing all files, hooks, routes or configs, reading a whole codebase or corpus, migrating every reference, building a complete list, sweeping all sources on a topic, or resuming a sweep another session paused. Trigger words include every, all, each, entire, exhaustive, complete list, full audit, sweep, leave nothing out, don't stop until, make sure nothing is missed, keep going, and pick up where it left off. It enumerates the universe from a command first, takes each item to a depth floor with evidence, defers only with a reason, audits reads before it closes, and keeps a resume prompt current so a usage limit loses nothing. Use it alongside /review-stack or /research-stack when they do the domain work. Skip it for single lookups, samples or quick answers.
---

# Relentless: sweeps that do not stop on a feeling

When a job means covering everything (every file, call site, source, record or check),
agents tend to stop when they feel they have enough. The feeling is usually wrong, and
nobody can check it, argue with it, or hand it to the next agent. This skill replaces it
with arithmetic: a ledger of the whole universe, a depth every item must reach, evidence
behind every claim, and a resume prompt that is always current. An optional Stop hook
holds the count at the end of every turn.

Coverage is a fraction, not a feeling. The user decides when a sweep is done, and they
decide it from the ledger's numbers, not from your sense that the rest will look the same.

## When it applies

Use it when the honest answer depends on not missing items: "find every place X happens",
"audit all the hooks", "is Y used anywhere", "migrate every call site", "the complete list
of Z", a literature or competitor sweep, or "pick up the sweep where it stopped".

Skip it for single lookups ("where is `load_config` defined?"), samples ("give me five
examples"), and quick opinions. A ledger costs real time. Spending it on a narrow question
is its own kind of waste.

It pairs with the skills that know a domain. `/review-stack` owns code-quality review and
`/research-stack` owns source gathering. If your team has a list-building tool, it owns how
to build a prospect list. They supply the method. This skill supplies the count.

The line with `/1pct`: 1pct is for an agent that will not act (hedging, asking permission
for approved work). This is for an agent that acts and then quits early.

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
ignore `.sweeps/**/.lock` and `.sweeps/**/*.tmp` either way. Closed and abandoned sweeps
move to `.sweeps/_closed/`.

**Session ownership.** A ledger belongs to the session that last changed it. The id comes
from `SWEEP_SESSION_ID`, then `CLAUDE_CODE_SESSION_ID`, then `CODEX_THREAD_ID`. Claude Code
subagents share their parent's id. With no id, ownership is unbound and no Stop hook acts
on the ledger; file-read proof is still required for a verified close.

## The loop

1. **Open it with a finish line you can check.**
   `sweep init --slug <project>-<topic> --goal "..." --done "..."`. The done condition
   should be falsifiable ("every tracked .py file under src/ read, every hit of the pattern
   classified"), not "reviewed thoroughly". When the end state is a command, pass it too:
   `--done-cmd '! rg -q old_api src/'`. `close` runs it.

2. **Enumerate before you investigate.** Build the universe from a command, not from memory
   or from what you have already seen: `sweep add --from-cmd 'git ls-files "*.py"'`. The
   command is stored, and `close` re-runs it, so items that appear mid-sweep cannot slip
   past. An enumeration that errors is refused, and an empty one needs `--allow-empty`,
   because an empty universe is far more often a broken command than a real zero. The
   domain references below have the right commands and their traps. You can also add ids
   by hand, with `--from-file <path>`, or with `--stdin`.

3. **Work in slices.** `sweep next -n 20` gives the next open items. Take each to the floor,
   then record it: `sweep visit <id> --depth 2 --evidence "<what you read, followed or ran>"`.

4. **Write findings down as you go**, with their proof:
   `sweep finding "<what is true>" --evidence "<file:line, command and output>" --item <id>`.
   Findings that live only in your context die with it.

5. **Leave items only on purpose.** `sweep defer <id> --why "<reason>"` for items that are
   genuinely out of scope (vendored code, a dead source). Never skip silently. Deferring
   more than a quarter of the universe blocks `close`: at that point the sweep was not done.
   If work later covers an item, explicitly use `sweep revive <id> --why "<what changed>"`.
   Visiting alone does not revoke a deferral. Revival keeps the original deferral in the log.

6. **Close it.** `sweep close` refuses while items are open, re-runs the enumeration to
   catch drift, runs `--done-cmd`, and checks that every file you marked as read was
   actually opened in your transcript. `--force` exists for the user's explicit say-so; it
   records which checks it overrode.

7. **If you must stop, say why.** `sweep checkpoint --why "<reason>"`. RESUME.md is
   rewritten on every change anyway, so even a hard stop (usage limit, crash) loses at most
   the item in your hands. Nobody, you included, can see the account's usage limit coming,
   so do not try to time it. Just keep the ledger current.

Other commands: `sweep status` (the coverage line; `--all` includes closed sweeps, `--json`
for machines, `--next N` to list open items), `sweep render --out <file>` (the ledger as
Markdown), `sweep abandon --why "<reason>"` (drop a sweep without claiming any coverage),
and `sweep verify <ledger.json>` (read-only, for checklists; see below).

## Depth

| Level | Name      | Means                                                        |
| ----- | --------- | ------------------------------------------------------------ |
| 0     | listed    | in the universe, nothing read                                |
| 1     | skimmed   | a grep hit or an excerpt: a lead, not evidence               |
| 2     | read      | the whole item read start to finish                          |
| 3     | traced    | its edges followed: callers, imports, tests, config, history |
| 4     | exercised | run, reproduced, or tested against the live thing            |

The default floor is L2. Raise it with `init --depth 3` for behaviour audits and anything
where an item's meaning depends on its neighbours, and to L4 when the question is "does it
work". A floor below L2 needs `--floor-why`, because it counts skimmed items as covered.

Interestingness is not depth. A file that looked boring after a grep is still at L1. A
visit never lowers an item's depth unless you pass `--force`.

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
only for the command being checked:

```text
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
unset, the existing Claude successful-result lane stays unchanged.

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

## Reporting

End with the coverage line from `sweep status` ("47/52 at L2, 3 open, 2 deferred"), the
findings with their evidence, and every deferral with its reason. If the sweep is not
closed, say it is paused and give the RESUME.md path. Words like "all", "every", "complete"
or "nothing else" are only true once `close` has passed without `--force`. Before that, the
numbers are the claim.

## Resuming

If you are handed a RESUME.md, or asked to continue a sweep, run `sweep status` (it lists
unfinished sweeps) and read the resume prompt. After a resume or a context compaction the
ledger is the briefing: trust it over your memory of the chat. Your first change reopens
the sweep and makes it yours. The findings in it are already paid for, so build on them
rather than re-deriving them. Items at the floor were visited with evidence. Re-read one
only if its evidence looks wrong, since `close` will audit the reads anyway.

## Checklist

This skill has no row of its own in the development protocol checklist. It makes another
row's evidence honest when that row's work is a sweep: `review` over every changed file,
`research` to saturation, `audit-setup` across every hook, or a migration inside `build`.
Close the sweep, then pass the archived ledger (the path `close` prints) as that row's
evidence, with `sweep verify` as the read-only verifier:

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id <work-id> --step review --result pass \
  --evidence .sweeps/_closed/<slug>-<stamp>/ledger.json \
  --verify "python3 <relentless skill folder>/scripts/sweep.py verify .sweeps/_closed/<slug>-<stamp>/ledger.json"
```

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
