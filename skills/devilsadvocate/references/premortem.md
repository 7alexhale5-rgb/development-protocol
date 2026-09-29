# /devilsadvocate --premortem

# Premortem: Failure Enumeration Before It Happens

You are running Gary Klein's premortem technique on a plan, decision, or recommendation. The
technique flips the framing. Instead of asking "what could go wrong?" (which a model tends to
optimize away), you assume the plan **already failed** and write the post-mortem. This forces
concrete failure chains, surfaces hidden assumptions, and turns optimism bias into a forcing
function.

> **Why this exists:** language models show optimism bias on plan review. Asked "is this a good
> plan?", a model finds reasons to say yes. The premortem flips the prompt so the same model
> produces the failure modes it would otherwise explain away. Sources: Klein, _Sources of Power_
> (1998); Kahneman, _Thinking, Fast and Slow_, chapter 24 (2011).
>
> **Not the same as the default `/devilsadvocate` mode.** That mode is open-ended claim triage.
> The premortem is procedural enumeration with a fixed output table. Use both on critical plans.
> They catch different things.

---

## Step 1: Identify the Target

Find the plan, decision, or recommendation in this order:

1. **The current conversation.** If `/planning-stack` or `/research-stack` ran this session, use
   its output.
2. **A path the user gave.** If the user said "premortem this <path>", read that file.
3. **The newest plan in the repo.** Check `.devproto/evidence/plan.md`, then the project's planning
   folder (for example `.planning/`), then any plan files your agent saves. Take the most recently
   changed one.
4. **Nothing found.** Ask: "What plan or decision should I run the premortem on? Paste it, point
   to a file, or run `/planning-stack` first."

Read the target end to end before going on. Pull out: the GOAL, the key approach decisions, the
files affected, and any risks the plan already states.

## Step 2: Imagine Forward (the inversion)

State this to yourself, and to the user as the first line of the output:

> "Assume this plan shipped 90 days ago and failed catastrophically. The team is in the war room
> writing the post-mortem. Here is what they're documenting."

This framing carries the method. Do not skip it. The 90-day delay is deliberate: it pushes you
past "shipped and obviously broken" into "shipped, ran a while, then failed in a way that was not
obvious on day one."

## Step 3: Enumerate Failure Chains

Write **3 to 7 distinct failure chains**. A failure chain is a concrete sequence of events:
trigger, then propagation, then consequence. Example shapes:

- **An outside signal changes:** "API rate limit drops from 10K/hr to 1K/hr, so the batch job
  stalls, the queue backs up, and users see timeouts."
- **Hidden coupling breaks:** "A schema migration adds a column, an old client version writes NULL
  into it, and the analytics dashboard silently shows wrong counts."
- **Scale hits a knee:** "Users cross 50K, a query that took 50 ms at 5K now takes 5 s, page-load
  p99 blows past the target, and users leave."
- **A human assumption fails:** "The doc says only the lead engineer runs this. A contractor joins,
  runs it without context, and wipes production state."
- **Failure cascades across components:** "Component A slows down, retries hammer component B, B's
  connection pool runs out, and 500 errors spread across the fleet."

Give each chain a one-sentence title that names the failure outcome, not the trigger.

## Step 4: Surface the Assumption per Chain

For each chain, name the **silent assumption** the plan rests on. The plan never states it. That
is the point. Examples:

- "Assumes the external API quota stays at 10K/hr."
- "Assumes no concurrent writes from old client versions."
- "Assumes user growth stays linear."
- "Assumes the runbook covers everything a new contractor needs."

Phrase each assumption so it can be checked: a reader should be able to ask "is this still true?"
30 days from now and get a yes or no.

## Step 5: Warning Signs per Chain

For each chain, name **2 or 3 observable signals** that the chain is firing in production. These
become candidate alerts. Examples:

- "API 429 responses exceed 1% of total calls."
- "The migration finished, but the audit log still shows old-format writes after 24 hours."
- "Page-load p99 crosses 2 s in any 5-minute window."
- "The runbook has had no edits in 90 days."

Make them specific enough that an on-call engineer at 3 a.m. could search the logs or a dashboard
for them.

## Step 6: Likelihood times Danger

Score each chain:

- **Likelihood:** H / M / L. How plausible is this chain in the next 90 days, given the plan as
  written?
- **Danger:** H / M / L. If it fires, how bad is the impact? (Data loss is H. A UX glitch is L.)
- **Impact:** combine them: HH = critical; HM or MH = high; MM, LH or HL = medium; LM, ML or
  LL = low.

Sort chains by impact, highest first. The top one or two are the ones the plan must address.

## Step 7: Revision Checklist

For each critical or high chain, write **1 to 3 concrete revisions** that would break that chain.
They are additions to the plan, not "consider X" or "think about Y". Actual edits. Examples:

- "Add a circuit breaker around the external API call, falling back to cached values."
- "Block the migration on a check that `SELECT count(*) FROM old_version_clients` returns 0."
- "Add an alert on page-load p99 over 2000 ms, and a runbook entry for inspecting the query plan."

---

## Output Template

Open with the inversion framing, then the table:

```markdown
**Premortem: {plan title}**

> Assume this plan shipped 90 days ago and failed catastrophically. Here is the post-mortem.

| #   | Failure outcome  | Likelihood | Danger | Impact            | Hidden assumption | Warning signs            | Revisions to make NOW     |
| --- | ---------------- | ---------- | ------ | ----------------- | ----------------- | ------------------------ | ------------------------- |
| 1   | [1-line outcome] | H/M/L      | H/M/L  | crit/high/med/low | [the assumption]  | [2-3 searchable signals] | [1-3 concrete plan edits] |
| 2   | ...              |            |        |                   |                   |                          |                           |

**Top revisions to apply BEFORE building**:

1. [most critical revision, from the top-impact chain]
2. [second most critical]
3. [third, only if there is a clear gap]

**What this premortem did NOT cover** (out of scope, or assumed adequately handled):

- [things you chose not to probe; this keeps you honest]
```

Save it to `.devproto/evidence/premortem.md`, read it back once, and record the `premortem` row
(see the main SKILL.md). Then apply the top revisions to the plan, or record why each was not
applied, before `/build-stack` starts.

---

## When to Use versus Other Skills

| Skill                                     | When                                                                                | Output shape                         |
| ----------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------ |
| `/devilsadvocate --premortem`             | After a plan is written, before `/build-stack` starts. Forces failure-mode listing. | Fixed table per failure chain        |
| `/devilsadvocate` (default mode)          | After research is gathered, before acting. Open-ended claim triage.                 | Claim triage in V/P/U/X buckets      |
| Skeptic pass inside `/brainstorm-stack`   | Automatic while brainstorming; no separate call                                     | 1 to 5 findings on framing and scope |
| A multi-model panel, if your team has one | A judgment call or fork where several model views help                              | Several separate model outputs       |

Run the premortem AND the default mode on critical plans. The default mode finds invented claims
and unsupported assertions. The premortem finds failure chains the plan glosses over.

## Behavioral Notes

- **Do not apologize for being negative.** Listing failure modes is the whole point. "No major
  chains surfaced" is a valid result on a simple plan, but force yourself to write at least 3
  chains before you conclude the plan is thin on failure modes.
- **Be specific.** "Could fail" is not a failure mode. "API quota runs out at hour 47 of the
  backfill and triggers cascading retries that exhaust the connection pool" is.
- **Do not restate the plan.** The user has the plan. You are surfacing what is NOT in it.
- **Stop at the table and the revisions.** Do not go meta about whether the premortem itself is
  sound. That is default-mode territory.
