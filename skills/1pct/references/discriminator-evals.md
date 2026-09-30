# Discriminator evals

Manual scenarios for the "Trigger discrimination" section of `../SKILL.md`. There is no
automated harness: skill behaviour is observed in fresh agent sessions. Re-run the set after
any change to the discriminator, to the red-flag patterns in `../hooks/1pct-check.py`, to
`/planning-stack`'s interface (the REPLAN handoff), or after a model upgrade.

## What is tested

At activation the skill picks one of three branches:

- **EXECUTE**: apply the doctrine at once on the approved plan (a crisp question on a real
  fork is still EXECUTE)
- **REPLAN**: invoke `/planning-stack` first, then resume the doctrine on the new plan,
  with or without `--no-interview`
- **SOFT_REFRAME**: soft signal #6, a one-line "interrogating assumption X" in context, with
  no full replan

Each eval checks that a branch fires for its scenario and does NOT fire for a neighbouring
one.

| ID  | Scenario                                                       | Expected branch                           |
| --- | -------------------------------------------------------------- | ----------------------------------------- |
| E1  | Pure hedging on a clear plan                                   | EXECUTE                                   |
| E2  | Falsified precondition (signal #1)                             | REPLAN, with the interview                |
| E3  | 3+ same-type tool failures after 1 fix (signal #3)             | REPLAN, no interview                      |
| E4  | Shotgun debugging: 3 unrelated tools, no diagnosis (signal #6) | SOFT_REFRAME, not a full replan           |
| E5  | "This isn't working" in a **strategy** context                 | EXECUTE: signal #4 must NOT fire          |
| E5b | "This isn't working" in a **code** context                     | REPLAN, no interview: signal #4 MUST fire |
| E6  | 3 distinct failed fixes on one root issue (signal #2)          | REPLAN, with the interview                |
| E7  | 5 consecutive discards in an autonomous loop (signal #5)       | REPLAN, with the interview                |

E5 and E5b are a discrimination pair, and both must pass. Testing one polarity alone cannot
tell "the discriminator correctly held signal #4 back" from "the regex missed by luck".

## How to run one

1. Open a **fresh** session, so no earlier context leaks signal state.
2. Run the eval's setup exactly as written. Setup matters more than the activation phrase.
3. Send the activation phrase as a normal user message. Mention `/1pct` or not, as you would
   in real use.
4. Note which branch the agent takes, then walk every expected and anti behaviour.
5. **PASS** only if every expected behaviour is seen AND no anti behaviour occurs.

## Non-determinism

The same input can pass once and fail later. For each eval:

- Run it **3 times** in 3 fresh sessions and require a **2 of 3** majority to call it green.
- **1 of 3**: run it 5 more times. Under 2 of 5 across those reruns is a **failing eval**:
  the discriminator needs work. It is not flake.
- **0 of 3**: fail outright.

This stops a borderline eval from being waved through as "flaky" while the skill degrades.

## Setup traps (each one was caught in review)

- **E2** needs a fixture file the agent actually reads in the session. A user asserting the
  precondition is broken tests obedience, not detection from observation.
- **E3** needs real failures inside the time window. Stale or narrated failures make signal
  #3 silently not fire, and the eval returns a false EXECUTE.
- **E4** needs three real tool calls on the same target before the activation turn. A
  single message where the user describes the shotgun pattern diagnoses it for the agent.

## The evals

### E1: pure hedging (EXECUTE)

- **Setup**: paste: "Earlier we agreed on this plan: Step 1: X (done). Step 2: Y (done).
  Step 3: Z (done). Step 4: implement function foo() in src/foo.ts. Last turn you asked
  'Ready to proceed with step 4?'. Stop asking, just do it."
- **Expected**: no `/planning-stack`; no "ready to proceed?" and no plan restatement; step 4
  (foo() in src/foo.ts) is implemented in the same turn with no ceremony, menu or re-summary.
- **Anti**: the REPLAN branch; a re-summary before acting; an A/B/C offer when the plan
  names one next step. An A/B offer is legitimate only when the plan IS ambiguous AND a
  scout cannot settle it.

### E2: falsified precondition (REPLAN, with the interview)

- **Setup**: create a fixture the agent will read:

  ```text
  === Approved plan ===
  Step 1: Verify table_t schema (DONE, yesterday)
  Step 2: INSERT INTO table_t (id, name) VALUES (1, 'foo')
  Step 3: SELECT * FROM table_t WHERE id = 1

  === Live schema observation (just now) ===
  Database tables present: users, orders, products
  table_t: NOT FOUND
  ```

  Save it as `e2-context.txt` in a scratch folder. Message 1: "Read e2-context.txt". After
  the read, message 2: "continue with the plan, keep going".

- **Expected**: the mismatch is detected from the file (table_t expected, observed missing);
  `/planning-stack` runs WITHOUT `--no-interview`; the handoff carries the objective, the
  completed step 1, and the falsified precondition as expected versus observed; the doctrine
  state is passed ("1% mode active: produce a concrete executable plan"); after the new plan
  is confirmed, execution resumes with no "ready to proceed?".
- **Anti**: skipping the interview (it would carry the stale assumption forward); running
  step 2 as written; treating it as a simple confirm-and-continue stop sign (signal #1
  escalates to REPLAN); missing it because the user never said "precondition".

### E3: mechanical failure loop (REPLAN, no interview)

- **Setup**: in a scratch TypeScript project with a real type error, drive the agent through
  it: "run the type check" (fails), "fix it" (one fix, e.g. an import change; the check
  still fails with the same error), "run it again" (fails a third time). All within a few
  minutes. Then send: "we keep failing the same tsc error in this build".
- **Expected**: the agent counts 3+ same-type failures with a fix in between and valid
  preconditions, so signal #3 fires; `/planning-stack --no-interview` runs;
  the handoff carries the failed fix, its diff and the error type.
- **Anti**: a fourth fix attempt; keeping the interview (the preconditions hold); treating
  it as a soft re-frame (signal #3 is hard); missing it because the failures were not
  counted.

### E4: shotgun debugging (SOFT_REFRAME)

- **Setup**: several turns with real tool calls, all on one failing test:
  1. "A test in src/foo.test.ts is failing. Run the tests to see what." (a shell call)
  2. "Try changing the assertion in src/foo.test.ts line 12 to match the actual output."
     (an edit)
  3. "Read src/foo.ts to see what the function returns." (a read)
  4. Activation, and it must stay neutral: "keep going". Do not name the pattern.
- **Expected**: 3 unrelated tools on one symptom with no diagnosis between them is noticed
  as signal #6; a one-line re-frame ("Interrogating assumption X first, then continuing");
  a read or search aimed at the hidden assumption (what the test expects versus what the
  function returns); then execution continues. No `/planning-stack`, and no stop-sign
  escalation to the user.
- **Anti**: a full REPLAN; a fourth unrelated tool with no diagnosis; "should I keep
  trying?"; failing to notice because the activation phrase did not name the pattern.

### E5: strategy frustration (EXECUTE, signal #4 must NOT fire)

- **Setup**: paste: "Earlier we agreed on a code plan: steps 1 to 4 done, step 5: write the
  landing page copy in src/components/Landing.tsx. But honestly, this isn't working. The
  messaging isn't landing with the audience."
- **Expected**: signal #4 needs a code-context word (code, test, deploy, build) plus an
  observed tool failure, and has neither, so the branch stays EXECUTE. Either continue the
  code plan or, if the strategy doubt overrides it, ask once (a real fork, not a violation).
  Acceptable labels: EXECUTE, or EXECUTE with a clarifying question.
- **Anti**: firing signal #4 on a bare "this isn't working"; invoking `/planning-stack` over
  strategy doubt; treating ambiguous intent as a stuck signal; labelling it SOFT_REFRAME
  when no shotgun-tool pattern exists.

### E5b: code-context stuck (REPLAN, no interview; signal #4 MUST fire)

- **Setup**: first make one deploy or build command fail for real in the session (so there
  is an observed tool failure). Then paste: "Earlier we agreed: step 4 is deploy to
  production. I failed to deploy again. This isn't working. The same build error remains."
- **Expected**: the regex matches ("failed to" followed by "again"), the recent failure
  corroborates it, so signal #4 fires; `/planning-stack --no-interview` runs;
  the handoff carries the failed attempt, the error pattern and the user's words.
- **Anti**: not firing (which would mean E5's pass was luck); keeping the interview;
  treating it as a confirm-and-continue stop sign.

### E6: three failed fixes on one root issue (REPLAN, with the interview)

- **Setup**: several turns on one failing test in src/foo.test.ts:
  1. "Test in src/foo.test.ts is failing. Fix it." (fix 1, e.g. change the assertion; still
     failing)
  2. "Still failing." (fix 2, e.g. change the function's logic; still failing)
  3. "Still failing." (fix 3, e.g. add a retry wrapper; still failing)
  4. Activation: "keep going".

  The three fixes must target the SAME root cause. Three fixes for three different bugs is
  not signal #2.

- **Expected**: signal #2 fires (three failed fixes on one root cause: stop and question the
  architecture); `/planning-stack` runs WITHOUT `--no-interview`; the handoff carries the
  three attempts, their diffs, why each failed, and "questioning the approach, not
  attempting fix #4".
- **Anti**: fix number four; skipping the interview (the root cause is unclear); treating it
  as a soft re-frame; confusing three different bugs with three attempts on one.

### E7: autonomous loop discards (REPLAN, with the interview)

- **Setup**: run inside a keep-or-revert loop (`/build-stack --tdd` or
  `/research-stack --auto-refine`) until five iterations in a row are discarded. To
  simulate, paste: "You are inside /build-stack --tdd, iteration 6 for src/foo.ts. The loop
  log shows 5 consecutive DISCARD outcomes: iterations 1 to 5 were each reverted because the
  metric did not improve or got worse. Continue."
- **Expected**: signal #5 fires (five straight discards is the anti-stall threshold);
  `/planning-stack` runs WITHOUT `--no-interview` (architecture-level doubt); the handoff
  carries the five-iteration discard log and "original approach failing systematically,
  need a fresh strategy".
- **Anti**: a sixth iteration; calling it a transient flake; skipping the interview; using
  the loop's own "try the opposite" tactic without escalating. That tactic is right inside
  the loop, but signal #5 says the loop itself is the wrong vehicle.

## Baseline (2026-04-23, simulated)

The first pass ran each eval once in a simulated session: a small, cheap model was given
the discriminator, the scenario and the activation phrase, and asked for a four-line
decision (branch, signal fired, first action, rationale). About 105,000 input tokens in all.
It validates that the discriminator is clear, not that it works in a real session.

| ID  | Result  | Note                                                                                                                                                                  |
| --- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E1  | PASS    | Default branch; no ceremony, menu or re-summary.                                                                                                                      |
| E2  | PASS    | Kept the interview for precondition doubt.                                                                                                                            |
| E3  | PASS    | Exact match, interview skipped.                                                                                                                                       |
| E4  | PASS    | The first try refused and asked for more context: the model did not trust narrated tool history as real. A rerun framed as "treat this as real session state" passed. |
| E5  | PARTIAL | Signal #4 correctly did not fire, and asking on the fork was right, but the branch was mislabelled SOFT_REFRAME. The fix was the label rules above, not the logic.    |
| E5b | UNVERIFIED | The original phrase did not match signal #4. That baseline claim is withdrawn; corrected fixture needs the fresh-session protocol. |

E6 and E7 were added after the baseline and have no recorded run yet. Lessons kept from it:
a simulation needs real-feeling tool history (E4), and branch labels need rules of their own
(E5). For a deployment-grade verdict, use the 3-run protocol above in real sessions.

## An automated harness (not built)

The rough shape, if you want this in CI: a runner that starts N sessions per eval through
your agent's non-interactive mode, pre-seeds each with the setup turns, sends the activation
phrase, and captures the reply; a judge model stronger than the one under test scores PASS
or FAIL against the expected and anti behaviours, blind to which eval it is scoring; the
runner then folds the 3 runs per eval into PASS, FLAKY or FAIL.
