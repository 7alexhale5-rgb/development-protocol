# Best-of-N build with hidden tests and a blind judge

Opt-in method for `/build-stack --best-of <n>` (default N is 3, minimum 2). One build can pass
its own tests and still be wrong in a way nobody sees. Best-of-N builds N candidates from the
same spec, drops any that fail tests the builders never saw, and lets a judge who cannot tell
the candidates apart pick among the rest.

**Status: experimental.** The method follows the maintainer's evaluation standard, but its
benefit is not yet proven. A pre-registered experiment (best-of-3 against a single build,
scored on tests that never select anything) decides whether this becomes recommended practice.
Until that result is published here, treat the flag as an option, not a default.

## When to use it

- The spec can be tested from behaviour alone: a pure function, a parser, a validator, a pricing
  or contract rule, a data transform.
- A wrong answer that passes the visible tests would be costly, and the spec is stable.
- You can afford about three to four times the tokens of one build.

Do not use it for UI work, for exploratory work where the spec is still moving, for changes that
touch shared state, or for a small fix where one build plus review is enough.

## The flow

1. **Spec first.** Write the spec as behaviour, not as an implementation. Save it to a file.
2. **Hidden tests.** Write tests from the spec before any build. Put them outside every candidate
   worktree (see "Hidden tests" below).
3. **Initialise the run.**
   `BESTOFN init --run <id> --n 3 --seed <text> --spec <spec file>` where `BESTOFN` means
   `python3 <build-stack skill folder>/scripts/bestofn.py --project <repo>`.
4. **Build N candidates.** One separate worktree per candidate (a copy or a `git worktree`), same
   model and effort, same brief, no sight of each other. See "Builder brief".
5. **Register each candidate.** Save its diff against the shared base and run
   `BESTOFN register --run <id> --candidate c1 --diff <file> --worktree <dir> --tokens <n>`.
6. **Gate.** `BESTOFN isolation --run <id> --hidden-dir <dir>` must exit 0. Then for each
   candidate run `BESTOFN gate --run <id> --candidate c1 --visible "<visible test command>"
   --hidden "<hidden test command>" --cwd <worktree>`. A candidate that fails either command, or
   times out, is out. The hidden command receives the worktree path in `BESTOFN_CANDIDATE_DIR`.
7. **Blind packets.** `BESTOFN blind --run <id>` writes one packet per survivor pair and per
   presentation order under `.devproto/bestofn/<id>/packets/`. Each packet holds the judge
   instructions, the spec and two anonymous diffs labelled X and Y. The key that maps packets
   to candidates is in `private/`, and the judge must never be given it.
8. **Judge.** Give each packet, alone, to a fresh judge session. Each answers `X`, `Y` or `tie`.
   Collect the answers in a JSON file mapping packet id to answer.
9. **Verdict.** `BESTOFN verdict --run <id> --votes <file> [--judge-tokens <n>]`. The winner's diff becomes the build.
   It exits 1 with `winner: null` when no candidate survived, and refuses to run if the survivors
   changed after `blind` (run `blind` again and re-judge).
   Record it as the `build` row evidence in the normal way, and keep the run folder as extra
   evidence. The rest of `/build-stack` (verification, independent review) continues unchanged.

## Builder brief

Give each builder only: the spec, the visible tests, the path to its own worktree and the rules
of the project. Say plainly that a hidden test set exists, that it is not theirs to look for, and
that searching for it voids the run. Do not give a builder another candidate's work, the judge
packet format, the seed or the run folder.

## Hidden tests

The hidden tests are the gate. Their value is that no builder can write to them.

- Keep them in a directory outside every worktree. `isolation` refuses a directory inside, or
  around, a registered worktree.
- Gate output for the hidden command keeps only the exit code, the timeout flag and the time.
  Its text is dropped, so the ledger never teaches a later builder what the tests assert.
- This is separation plus instruction, not a sandbox. A builder with a shell and your home
  folder could look. For work where that matters, run builders in containers that cannot see the
  hidden path, and say so in the run record.
- Pilot finding: on a shared filesystem, instruction alone is not enough. Your own session log
  holds the hidden tests once you write them, and a builder started from a folder that has a
  project instructions file above it can have that file loaded into its context without you
  asking. Keep the hidden tests encrypted or off the machine until every builder has finished,
  start builders from an empty folder, and read each builder's tool calls afterwards for any
  path outside its own worktree.
- A gate command that uses a glob such as `test/*.test.ts` needs a shell, so pass it as
  `sh -c '...'`. The command is split without a shell.
- For an experiment, split the hidden tests into a **gate set** that filters candidates and a
  **score set** that never selects anything. Only the score set can measure whether the delivered
  code is good, because every survivor passed the gate set.

## The verdict rule

The rule is code, so it is repeatable.

- A pair is decided for a candidate only when it wins in both presentation orders.
- If the orders disagree, or either says `tie`, the pair is a tie. A tie goes to the candidate
  with the smaller diff (added plus removed lines). Equal size goes to the lower candidate id.
- The winner is the candidate with the most pairwise wins. If several share the top count, the
  smaller diff wins, then the lower id.
- One survivor wins by default and the run says `only_survivor`. Zero survivors means no winner.
  Stop and tell the person. Never lower the gate to find a winner.

## The judge

- Use a model at least as capable as the one that built the candidates. A weaker judge cannot see
  what a stronger builder got wrong.
- Fresh session per packet, no memory of earlier packets, no access to the key, test results or
  file paths.
- The packet text already tells the judge to rank correctness first, then simplicity, and to
  penalise unnecessary length. That is the whole length rule on the judge side: it is a rubric
  instruction, not a numeric score adjustment. The only numeric length rule is the tie-break
  to the smaller diff. Do not add hints about which side to prefer.
- Watch the order-agreement rate. If a judge agrees with itself across swapped orders less than
  60 percent of the time, it is mostly noise. Report that and distrust the verdict.

## Evidence

Everything stays under `.devproto/bestofn/<id>/` on the branch: `ledger.json` (each candidate's
diff hash, size, tokens, visible and hidden gate results), `diffs/`, `packets/`, `private/key.json`
and `private/survivors.json`, `verdict.json` (with the judge tokens you pass). These files can contain test output from the visible command, so read them before
sharing.

## Measuring whether it helps

`BESTOFN stats --pairs <file> --seed <text>` reads a list of `{"single": x, "best_of": y}` pairs,
one per spec and run, and prints the mean difference with a seeded paired bootstrap 95 percent
interval. Report the interval, not only the mean. Three runs per arm is a first look, and five is
the minimum for a decision. Include a trivial negative-control spec where both arms should tie. If
the control shows a difference, the harness is suspect.

Write the prediction, the measures and the decision rule down and record their hash before the
first candidate is built. Do not change them after seeing results.

## Failure modes

| Failure | What it looks like | Guard |
| --- | --- | --- |
| Position bias | The judge picks X most of the time | Both orders; a win needs both to agree |
| Leak to builders | A candidate passes tests it should not have known | `isolation`, brief rules, a leak probe before trusting a round |
| Judge sees identity | Packet mentions a path, id or test result | Packets are built by the script and checked by a test |
| Saturated spec | The single build already passes every score test | Report it as uninformative, not as a win or loss |
| Cost overrun | Three builds plus judging cost more than the benefit | Record tokens per candidate and per judge call; report cost per accepted change |
| Gate loosened | Nobody survives and the bar is lowered | Zero survivors is a stop, not a prompt to relax the tests |
