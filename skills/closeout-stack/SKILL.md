---
name: closeout-stack
description: Closes out a working session in a fixed order (commit, optional ship, session save, handoff, lessons, retro audit, docs refresh, compound) and always ends with a copy-pasteable resume prompt so the next session starts with full context. Use when someone signals end of session, ship intent or a context pivot, with phrases like "wrap up", "close out", "closeout", "end of session", "end of day", "I'm done", "time to stop", "pivot", "clear my context", "start fresh", "new chat", "clean slate", "switching projects", "write a handoff", or after /review-stack says the work is ready to ship. It also satisfies the closeout row of the development-protocol checklist. It is the session-persistence step, not a design or UI skill.
---

# Closeout Stack: End-of-Loop Session Orchestrator

Run a fixed end-of-session pipeline. This skill is a **thin orchestrator.** It calls other skills
(`/commit`, `/ship`, `/compound`) in a set order, with gates and idempotency, and it owns one
contract: **the final message always contains a copy-pasteable resume prompt.**

**Philosophy.** Never reimplement what another skill already does. Orchestrate, gate and
guarantee. The one thing this skill owns is the resume-prompt contract in Step 10.

## Where this sits in the checklist

This skill satisfies the `closeout` row of the development-protocol checklist, the last row. The
checklist refuses to pass `closeout` while any earlier required row is open. The close interval
has three duties: re-check fresh main, carry every unknown forward as unknown, and leave a
receipt a stranger can read. Step 9.5 records the row.

Closeout runs at the end of every session, not only at the end of a work item. Mid-work (pivot
or end of day), leave the `closeout` row alone and name the next open row in the resume prompt.

## Peer skills (do not confuse them)

| Skill                 | Phase           | When                                            |
| --------------------- | --------------- | ----------------------------------------------- |
| `/research-stack`     | Before planning | Gather outside context                          |
| `/brainstorm-stack`   | Before planning | Adaptive questioning                            |
| `/planning-stack`     | Planning        | Produce the plan                                |
| `/build-stack`        | Execution       | Implement the plan                              |
| `/review-stack`       | Verification    | Quality-gate the build                          |
| `/design-stack`       | UI craft        | Frontend design work                            |
| `/compound`           | Learning        | Git-history retro and learnings                 |
| **`/closeout-stack`** | **End of loop** | **Persist the session, emit the resume prompt** |

## Files this skill writes

All inside the project, so a teammate's clone has them:

| File                                             | Step | What it is                               |
| ------------------------------------------------ | ---- | ---------------------------------------- |
| `.devproto/sessions/<YYYY-MM-DD>-<slug>.md`      | 5    | One session log per day and project      |
| `.devproto/handoffs/<YYYY-MM-DD>-<slug>.md`      | 6    | The handoff the next session reads first |
| `.devproto/feedback.md`                          | 7    | Standing corrections from the user       |
| `.devproto/learnings/<YYYY-MM-DD>-compound-*.md` | 9    | Written by `/compound`                   |

Templates for the session log, the handoff and the resume prompt are in
`references/templates.md`.

---

## Step 0: Parse intent and mode

From the user's words, extract:

- **MODE**: `--mode=eod` (end of day), `--mode=pivot` (clearing context to keep working), or
  `--mode=ship` (shipping and stopping).
- **FLAGS**:
  - `--ship` / `--no-ship`: force Step 4 on or off
  - `--no-commit`: skip Step 3 (the pipeline stops if the working tree is dirty)
  - `--no-save`: skip Step 5 (session save)
  - `--no-handoff`: skip Step 6 (rare; you usually want it)
  - `--no-memory`: skip Step 7 (lessons from the user)
  - `--no-retro`: skip Step 7.5 (retro audit)
  - `--no-wiki`: skip Step 8 (docs refresh)
  - `--no-compound`: skip Step 9 (`/compound`)
  - `--dry-run`: print the pipeline plan and write nothing
  - `--resume-only`: skip everything except Step 1 and Step 10, and emit a resume prompt from the
    current state

The full flag matrix and the idempotency rules are in `references/flags-and-idempotency.md`.

### Mode auto-detection

With no `--mode` flag, check these in order. The first match wins.

| Signal                                                                                     | Mode      |
| ------------------------------------------------------------------------------------------ | --------- |
| User names a different project than the current folder ("switch to X", "let's do Y now")   | **pivot** |
| Explicit pivot phrases: "pivot", "clear to continue", "fresh context", "still working but" | **pivot** |
| Most recent `/review-stack` verdict in the conversation is SHIP IT                         | **ship**  |
| Branch has unpushed commits AND tests are green AND the user hinted at shipping            | **ship**  |
| User said "done for the day", "wrap up", "eod", "end of session"                           | **eod**   |
| User typed a manual chain like "save, handoff, compound" (any subset)                      | **eod**   |
| Nothing else matches                                                                       | **eod**   |

Report the mode before running:

> **Closeout mode: eod | pivot | ship.** Running the closeout pipeline. Steps that ask before
> running: <list>.

---

## Step 1: State probe

Run these in every repository this session touched, not only the current folder. Asking from
the wrong folder returns a clean-looking answer about a folder nobody worked in.

```bash
repo="<the repository this session touched>"                   # fill in before running
devproto_dir="<the development-protocol skill folder>"          # fill in before running
cd "$repo"
git branch --show-current
git status --porcelain | wc -l                          # uncommitted file count
git log -1 --format='%h %s'                              # last commit
git rev-list --left-right --count @{upstream}...HEAD 2>/dev/null   # behind, ahead
git stash list | wc -l                                   # stashes hold one copy only
ls .devproto 2>/dev/null && python3 "$devproto_dir/scripts/devproto.py" --project . list
```

If a work item is open, also run `devproto.py --project . status --id=<work-id>` and note its
`next_step`.

Add the fields only the agent can see:

- **Session files changed**: every file written or edited in this conversation
- **Session commits**: `git log --oneline --since="<session start>"`
- **Test state**: if a test command ran this session, its last result (pass or fail, and count)

Store the merged result as **STATE_PAYLOAD**. Every later step reads it.

### 1b: Is it safe to close?

Answer four questions. Only the first two can be checked by a command.

1. **Saved.** Does the work exist outside the conversation? Every file edited this session is on
   disk, and nothing important lives only in chat.
2. **In two places.** Is it committed _and_ pushed, or bundled? Check
   `git status --porcelain` is empty and `git rev-list --count @{upstream}..HEAD` is 0. No
   upstream means not pushed. A stash is one copy. If pushing is not possible, a
   `git bundle create <file> --all` copied off the machine counts as a second place.
3. **Proven.** Did you run it and read the output? _(You must answer this honestly.)_
4. **Written down.** Could a stranger continue tomorrow? _(You answer this. Step 6 is what
   makes it true.)_

Store `safe_to_close` (true or false) and `safe_to_close_reasons` (the failing questions).
Suggesting a close while work sits in one place is the specific failure this check prevents.

> **1b is a label on the exit, not a gate on the pipeline.** A not-clear verdict changes exactly
> two things: the exit-menu default in 10e, and one line in the 10b report. It changes
> **nothing else**. Steps 2 to 10 run in full.
>
> Never skip, defer or mark "pending" the save (5), the handoff (6) or compound (9) because the
> verdict came back not-clear. Those steps are what _create_ the second copy. Halting them
> because work is in one place leaves it in one place and ends the session with nothing written
> down. Measured on 2026-07-26: 2 of 4 test runs made exactly this inversion and stopped
> persisting at the safety check. If you find yourself writing "skipped (safety check)" or
> "awaiting decision" next to save or handoff, you have inverted the step. Run them.

The safe order, and the only part of it that is a law:

> review → merge → push → clean up → archive

Never delete anything until the second copy is proven. The rest is preference.

---

## Step 2: Review gate check

Look back through the conversation for a `/review-stack` verdict (or any independent review):

| Last verdict                       | Action                                                                                                                              |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| SHIP IT / READY TO SHIP            | Proceed normally.                                                                                                                   |
| FIX THEN SHIP / SHIP WITH CAVEATS  | Proceed. Put the remediation items under Blockers in the resume prompt.                                                             |
| NEEDS WORK or BLOCKED (unresolved) | Block Step 4 shipping; retain the blocker and continue saving evidence, handoff and learning. |
| No review found, MODE=ship         | Block Step 4 shipping until required independent review is verified.                                      |
| No review found, MODE=eod or pivot | Continue persistence; any later choice to ship must first apply the MODE=ship review rule.                                                                                                                   |

Set STATE_PAYLOAD.release_blocked initially true until fresh through-commit and current
candidate-review checks pass. Set it true again on any failed shipping prerequisite,
stale proof, missing check, or /ship failure. Recheck both prerequisites immediately
before every outward merge, push or deployment, including production drift repair
and artifact publication. A conversation verdict never substitutes for these checks.
Set STATE_PAYLOAD.review_blocked for missing or failed required review. It blocks `/ship`, push and release. Continue the
persistence steps so evidence and the resume prompt are saved; never mark this closeout
shipped. Passing headlines with unresolved required findings also remain blocked.

---

## Step 3: Commit

Skip if:

- The working tree is clean (`git status --porcelain` is empty)
- `--no-commit` is set
- A commit was already made this turn

Otherwise run `/commit`. Capture the new hash into **STATE_PAYLOAD.last_commit**.

**Failure handling.** If the commit itself fails (a pre-commit hook error, an auth error), stop
the pipeline. Dirty state makes everything downstream fragile. Show the error. **Still jump to
Step 10** and emit a resume prompt that names the failure.

If `--no-commit` is set and the tree is dirty, carry it into the resume prompt as
`Blockers: uncommitted changes, <N> files`.

## Step 3.5: Release gates (only if the team has them)

If the project has a release checklist or launch gate (a required sign-off, an accessibility
audit, a client approval record), run it before Step 4 and carry any failing control into the
resume prompt under Blockers. If the gate cannot be run by a command, mark it `gate: manual` in
the report. Never mark a manual gate as passed on a person's behalf.

## Step 3.5: Renew the committed candidate locally

After Step 3 creates or preserves the final commit, run Full Verify, required independent
review, read-only simplify and proof of that existing commit, in checklist order. Renew
all affected receipts with fresh current-SHA evidence. Inspect their actual result; no
idempotent receipt proves a new execution. Recompute review_blocked and release_blocked
from these current checks. Clear them only when required findings and gaps are resolved
and through-commit/current-candidate checks pass. Failed or unavailable preparation
keeps outward actions blocked while session persistence continues. This local sequence
runs even when the preliminary Step 2 flags are true; it never pushes, merges or deploys.

## Step 4: Ship (gated)

```text
IF STATE_PAYLOAD.review_blocked OR STATE_PAYLOAD.release_blocked:
    SKIP ship; retain the required-review failure and continue persistence
ELIF --no-ship OR MODE=pivot:
    SKIP (log: "Skipped ship: mode=pivot or --no-ship")
ELIF --ship OR MODE=ship:
    RUN /ship
ELSE:  # MODE=eod and no explicit flag
    ASK: "Ship this to a pull request now? (y / n / skip-closeout)"
    ON 'y': RUN /ship
    ON 'n' or 'skip': continue to Step 5
```

**Non-abort rule.** If `/ship` fails (tests fail, push rejected, pull request creation error), do
**not** stop the closeout. Continue to Step 5. The session still needs saving and handing off.
Set **STATE_PAYLOAD.release_blocked=true** and add the failure to **STATE_PAYLOAD.failures**. Step 10 will put
`STATUS: partial, /ship failed: <reason>` at the top of the resume prompt.

On success, capture **STATE_PAYLOAD.pr_url**.

### 4.5: Production matches main

When review_blocked or release_blocked, this step is read-only: report drift, keep local evidence and
backups, and never merge, push or deploy. Any later outward action requires renewed
candidate verification and required independent review first.


Run this on **every** ship-mode closeout, not only when a claim spans repositories. Widened on
2026-09-04 after a production site ran a branch 454 files ahead of `main` for five days, and an
outside audit measured the wrong tree.

Why it exists: hosting platforms that auto-deploy usually deploy only the configured production
branch, typically `main`. A manual "deploy to production" from a command line promotes whatever
the local checkout points at, on any branch. So "I deployed it" and "the merged code is in
production" are different claims. A real case: an endpoint returned 404 in production for days
because the work lived on a side branch that was never merged, while a manual deploy had made it
look live.

Check:

```bash
touched_path="<a path this session changed>"   # fill in before running
if ! git remote get-url origin >/dev/null 2>&1; then
  echo "no origin remote: nothing deployed from here, skip this check"
else
  default_branch="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"
  default_branch="${default_branch:-main}"
  git fetch origin "$default_branch"
  git rev-parse "origin/$default_branch"
  git log --oneline "origin/$default_branch" -1 -- "$touched_path"
fi
```

If there is no `origin` remote at all (a local-only repo), production drift cannot be checked from
here; write `prod==main: not verified (no origin remote)` and move on. Otherwise, find the commit
production is running. Use whichever the project has:

- A version or health endpoint that reports the build SHA (`curl -s <prod-url>/version`)
- A response header with the build SHA
- The hosting CLI's inspect command for the production deployment (optional tool; for example
  `vercel inspect <prod-url>` prints the source commit)

If the production commit is not `origin/<default_branch>` (or does not contain the touched path's
latest commit), repair only through the authorized release flow after fresh prerequisite checks;
otherwise add to
`STATE_PAYLOAD.failures`: `prod drift: <repo> production runs <sha>, <default_branch> tip is
<sha>`. If no way to read the production commit exists, write `prod==<default_branch>: not
verified (no version source)`. Unknown is not pass.

---

## Step 5: Session save

Write, or merge into, `.devproto/sessions/<YYYY-MM-DD>-<project-slug>.md` using the session
template in `references/templates.md`.

### Idempotency rule (load-bearing)

```text
path = .devproto/sessions/<YYYY-MM-DD>-<project-slug>.md
IF path exists:
    read the existing file
    insert a new "## Update HH:MM" section immediately before "## Related"
    overwrite
ELSE:
    write a fresh file from the template
```

**Never create a second file for the same date and project.** Two files split every later
search.

Frontmatter:

```yaml
---
date: <YYYY-MM-DD>
type: session
project: <project-slug>
tags: [session, <project-slug>, closeout]
mode: <eod|pivot|ship>
---
```

Body, pulled from STATE_PAYLOAD: a 2 to 3 sentence summary, changes (files with line ranges),
decisions, artifacts (commit, pull request; write the handoff path as `<TBD step 6>` and fill it
after Step 6), and pending next actions.

Skip with `--no-save`. Log the path for the report.

---

## Step 6: Handoff

Write `.devproto/handoffs/<YYYY-MM-DD>-<slug>.md` from the handoff template in
`references/templates.md`. The handoff is the full-context document. The resume prompt in
Step 10 is the short pointer to it. Capture **STATE_PAYLOAD.handoff_path**.

A good handoff lets a stranger continue without this conversation. It must have:

- **Goal**: the one-sentence goal and its done condition
- **State**: branch, last commit, ahead or behind, test result with the command that produced it
- **Done this session**: what changed, with file paths
- **Proven**: each claim with how it was proven (the command and what it printed)
- **Unknowns**: everything not verified, stated as unknown, never rounded up to done
- **Next**: the exact next skill and task, and the next open checklist row if a work item exists
- **Blockers**: or "none"

**Idempotency.** If a handoff for the same slug was written in the last few minutes of this
session, ask: "A handoff was written <N> minutes ago. Update it or write a new one?" On update,
add a `## Update HH:MM` section.

If writing the handoff fails, add it to `STATE_PAYLOAD.failures` and continue. Step 10 still
fires, with a best-effort resume prompt built from STATE_PAYLOAD alone.

Skip with `--no-handoff`. When skipped, Step 10 builds the resume prompt from STATE_PAYLOAD
directly.

---

## Step 7: Lessons from the user

### 7a: Extract corrections and confirmations

Scan this session for:

- User corrections ("no, don't do that", "stop doing X", "never...")
- User confirmations of a non-obvious approach ("yes exactly", "that's the right call")

For each, read `.devproto/feedback.md` first. If no entry covers the same rule, append one:

```markdown
## <rule in one line>

- <YYYY-MM-DD>: <what happened, in one or two lines>
```

If an entry exists, add a new dated line under it. Never create a duplicate entry.

### 7b: Propose instruction-file changes

If a correction is a standing project rule (not a one-off preference), propose adding it to the
project's agent instruction file (`CLAUDE.md`, `AGENTS.md` or similar). Only propose. Write it
only after the user says yes. Keep edits surgical: one rule at a time.

Skip Step 7 entirely with `--no-memory`, or when this session had no corrections or
confirmations.

---

## Step 7.5: Retro audit

Audit this session's transcript for findings worth carrying into the next session. **Write the
findings into the handoff** (`STATE_PAYLOAD.handoff_path`) under a `## Retro Findings` section.
The next session reads the handoff first, so it sees them automatically.

How it differs from Step 7:

- **Step 7** captures what the USER corrected.
- **Step 7.5** captures friction the AGENT hit on its own: stale docs, instructions that did not
  match reality, silent failures.

### Skip conditions

Skip, and set `STATE_PAYLOAD.retro_findings = null`, if any of these hold:

- `--no-retro` is set
- Step 6 was skipped or failed (there is no handoff to write into)
- Remaining context is too low for a real audit. Rough check: the conversation has used an
  unusually large share of context AND no clear friction is visible in the recent transcript.
  Skip with a one-line note in the 10b report. A silent skip is better than a corrupted audit.

### Audit

Audit the transcript across six categories. The category definitions, the strict silence rule,
the anti-patterns, the output format and failure isolation are in
`references/retro-audit.md`. Read it before auditing.

**Emit a finding only if it traces to a specific moment in the transcript. Silence is a valid
result.**

Set `STATE_PAYLOAD.retro_findings = {count: N, in_handoff: true}` when findings exist, and
`null` when silent.

---

## Step 8: Docs refresh (conditional)

For work-id closeout, inspect documentation read-only and save proposed changes under
`.devproto/learnings/`. Do not refresh shipped docs after the candidate was reviewed.

For each **topic** touched this session (the project, or a major feature area):

```text
topic_session_count = number of files in .devproto/sessions/ that mention <topic>
doc_path            = the project's doc for <topic> (for example docs/<topic-slug>.md)
doc_is_stale        = doc_path does not exist
                      OR its last commit is older than the newest session file that mentions <topic>

IF topic_session_count >= 3 AND doc_is_stale:
    IF work-id closeout: save a proposed update under .devproto/learnings/ only
    ELSE: refresh or create the doc in a separate verified work item
ELSE:
    skip silently
```

The threshold stops over-writing docs. Most sessions touch topics that do not meet it. That is
fine. Skip entirely with `--no-wiki`, or when the project keeps no docs folder.

---

## Step 9: Compound

Mode-gated:

| Mode  | Action                                                                           |
| ----- | -------------------------------------------------------------------------------- |
| ship  | Run `/compound --days 1` automatically.                                          |
| eod   | Run `/compound --days 1` automatically.                                          |
| pivot | **Ask**: "Run /compound for this partial session? (y/n, default n)". On n, skip. |

Skip with `--no-compound`.

**Idempotency.** If `.devproto/learnings/<YYYY-MM-DD>-compound-*.md` exists for today and this
project, skip silently. Compound already ran this cycle.

Non-critical: log a failure, never stop the pipeline.

## Step 9.4: Persist final artifacts and refresh safety

When review_blocked or release_blocked, retain approved artifacts locally with verified backups. Do not
push, merge or deploy them. Renew final candidate proof and required independent review
before any later outward action; local persistence does not clear the review blocker.


After all session logs, handoffs, lessons and documentation writes, inspect status again.
Classify every generated artifact as committed and pushed, intentionally local with a
verified backup, or still unpersisted. For a work-id closeout, retain all new reports,
decision drafts and proposed doc changes under `.devproto/`; do not mutate reviewed
source or create another commit in this checklist. Any later promotion into shipped
docs is a separate work item with its own review and release checks. For standalone
persistence, commit and push only after fresh release checks; preserve unrelated work.
Keep mutable `.devproto/` receipts outside Git to avoid invalidating their own HEAD binding.
If metadata changes HEAD, refresh affected release evidence before recording closeout.

Re-run Step 1b after the final writes and remote update. Replace `safe_to_close` and its
reasons with this fresh result; never reuse the initial value. List every local-only or
uncommitted artifact, its backup, and any remaining risk in the handoff and final report.
A failed persistence step keeps safety false while Step 10 still emits the resume prompt.

## Step 9.5: Record the closeout row (end of a work item only)

Only when the work item is shipped and merged -- which by this point already required a remote
(shipping is a pull request). Verify fresh default branch in a separate checkout, leaving the reviewed work checkout
and its identity unchanged. Record its actual merged SHA and re-run the suite there.
Detect the branch name rather than assume `main`:

```bash
default_branch="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"
default_branch="${default_branch:-main}"
git fetch origin "$default_branch"
# Create a separate fresh verification checkout of origin/<default_branch>.
# Run the full suite there and bind the handoff to that exact merged SHA.
```

Then record the row. The handoff is the evidence. The verifier reads it and re-runs the suite on
the separate fresh-main checkout. The verifier asserts its HEAD equals the recorded
merged SHA before executing tests there; testing the original feature checkout cannot
certify the merged result:

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id=<work-id> --step closeout --result pass \
  --evidence .devproto/handoffs/<YYYY-MM-DD>-<slug>.md \
  --verify "grep -q '^## Unknowns' .devproto/handoffs/<YYYY-MM-DD>-<slug>.md && test \"\$(git -C <absolute-merged-checkout> rev-parse HEAD)\" = <recorded-merged-SHA> && (cd <absolute-merged-checkout> && <test command>)"
```

If earlier rows are still open, leave closeout pending. Record `blocked` on the earliest
eligible open prerequisite, retaining the closeout gap in the handoff.
Do not attempt to record a downstream blocked row while earlier rows are open. This is a
label, like 1b. It does not stop Step 10.

---

## Step 10: Emit the closeout output [ALWAYS FIRES]

Recheck safety if Step 9.5 changed any artifacts. Report their final persistence state.

> **Why this is strict.** The resume prompt is the only contract the next session inherits. If
> it is missing, the user loses everything this turn produced: no handoff link, no next task, no
> state.
>
> The final message of a closeout turn MUST contain exactly these three elements, in this order,
> with NO other prose:
>
> 1. **Closeout Stack Report**: the tree-format summary (10b)
> 2. **Resume prompt**: a fenced code block in the schema from `references/templates.md` (10c),
>    or the minimal fallback (10d) if state is incomplete
> 3. **Exit menu**: the three options (10e)
>
> No narration before the report. No "let me know if you need anything" after the menu. No
> analysis or summary paragraphs.
>
> **Step 10 always fires.** Even if every other step failed. Even with under 10% context left.
> Even if you cannot read the template file (use 10d). If your team installs an end-of-turn hook
> that checks for the resume prompt, do not rely on it. Emit the prompt the first time.

The excuses that have been used to skip Step 10, and why each is wrong, are in the
rationalizations table in `references/output-templates.md`. Read it when context is tight.

### 10a: Build the report fields from STATE_PAYLOAD

- `commit`: hash and subject from Step 3, or `(none this session, uncommitted: <N> files)`
- `pr_url`: from Step 4, or `none`
- `session_path`: from Step 5
- `handoff_path`: from Step 6
- `failures`: every non-aborting failure
- `next_task`: from the checklist's `next_step`, the plan, the user's last stated intent, or
  "see handoff"

### 10b to 10e: Report, resume prompt, exit menu

Full templates are in `references/output-templates.md`. In short:

- **10b**: tree-format Closeout Stack Report with a pass, skipped or failed mark per step
- **10c**: the resume prompt in a plain triple-backtick fence (no language tag). Put a `STATUS:`
  line first if anything failed
- **10d**: the minimal fallback when STATE_PAYLOAD is incomplete
- **10e**: the three-option exit menu, default chosen by mode (ship: 2, eod: 2, pivot: 1)

---

## Step 11: Walk it to the end [NEXT TURN, not part of the three-element message]

Step 10's contract governs the closeout turn. Step 11 governs the turn **after the user answers
the menu**. The skill used to have no instructions for that turn. It emitted a prompt and
stopped, which left three decisions unstated but dressed up as a finished deliverable: whether
closing was safe, who closes the session, and how the next session starts. Handing someone a
string they must carry is not the same as finishing. Ambiguity costs most here, because this is
the moment the context is about to be thrown away.

**If they chose 1 (Archive):**

1. Re-check `safe_to_close` if anything changed since Step 1b. If it is still not clear, name
   the failing question in one sentence and fix it before archiving. This is the last moment it
   is cheap to fix.
2. Archive, if your agent can close or archive its own session. Use that tool. It should ask for
   confirmation itself, so offering it is safe. If your agent cannot, tell the user the one
   action to take ("close this session and paste the resume prompt into a new one").
3. The conversation ends there, so **the resume prompt must already be in the transcript
   above.** Step 10 guarantees this. Never archive before emitting it.

**If they chose 2 (Stop):** confirm in one line what is safe and what is still one-copy, so
stopping is an informed choice, not a default.

**If they chose 3 (Compact):** keep working. No closeout state is lost. Steps 5 and 6 already
persisted it.

**If they ignore the menu and ask something else:** answer them, then **stop. Do not print the
menu again.** Not at the bottom, not as a reminder, not "whenever you're ready." The menu is
already in the transcript. Repeating it turns an answer into a nag. Measured on 2026-07-26: 1 of
4 test runs answered the question well and then re-appended the menu word for word.

The three-element contract governs the closeout turn **only**. On later turns it does not
apply: no report, no resume prompt, no menu, unless the user asks or runs closeout again.

### Never end on an open question

Whenever a fresh session is recommended, here or anywhere else, offer the whole path: close
out, archive, and start the next session from the handoff. Naming the safest next action and
offering to do it is the deliverable. "Here is a prompt, good luck" is not.

---

## Failure handling (invariant)

| Step fails       | Action                                                                                                                                                         |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1b verdict       | **Not a failure and never a gate.** Changes the 10e default and one 10b line. Steps 2 to 10 run in full.                                                       |
| 3 commit         | The commit command itself errored (not "there is uncommitted work"). Stop the pipeline. Still emit the Step 10 resume prompt, with the failure under Blockers. |
| 4 ship           | **Continue.** Save and handoff still run. The resume prompt starts with a STATUS line.                                                                         |
| 5 save           | Log, continue. The resume prompt notes the failure.                                                                                                            |
| 6 handoff        | Continue. Step 10 builds the resume prompt from STATE_PAYLOAD alone (no handoff link).                                                                         |
| 7 lessons        | Log, continue. Non-critical.                                                                                                                                   |
| 7.5 retro        | Log, set `retro_findings = null`, continue to Step 8. Non-critical. Step 10 fires unchanged.                                                                   |
| 8 docs           | Log, continue. Non-critical.                                                                                                                                   |
| 9 compound       | Log, continue. Non-critical.                                                                                                                                   |
| 9.5 checklist    | Record `blocked` with the reason. Continue.                                                                                                                    |
| 10 resume prompt | **MUST NOT FAIL.** Use the 10d minimal schema if 10c cannot be built.                                                                                          |

**Invariant: Step 10 always fires. Always.**

## Graceful degradation

| Component                       | If missing         | Fallback                                                                  |
| ------------------------------- | ------------------ | ------------------------------------------------------------------------- |
| git                             | Not a repository   | Skip Steps 3, 4 and 9.5. Use the current folder as the project.           |
| `.devproto/` folder             | Does not exist yet | Create it for Steps 5 and 6. Skip the checklist parts of Steps 1 and 9.5. |
| `/commit`, `/ship`, `/compound` | Skill unavailable  | Do the step by hand if it is simple, or skip, log and continue.           |
| Plan or state file              | None               | Derive the NEXT line from the user's last stated intent.                  |
| `references/templates.md`       | Unreadable         | Use the 10d minimal schema.                                               |

Minimum viable pipeline: the state probe plus the resume prompt. Everything else is enhancement.

## Testing this skill

If you test this skill, test the final turn, not only whether it triggers. On 2026-07-26 the
trigger tests stayed green through an entire exit defect. Final-turn cases worth keeping: does
it catch one-copy work before offering to close, does the last turn offer the whole path, and
does it answer a follow-up without re-nagging with the menu.

## Invocation examples

```text
/closeout-stack
/closeout-stack --mode=ship
/closeout-stack --mode=pivot --no-compound
/closeout-stack --dry-run
/closeout-stack --resume-only   # emergency: just give me a resume prompt
```

Pass whatever flags the user gave straight through.
