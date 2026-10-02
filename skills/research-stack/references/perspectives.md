# Perspective prompts (Step 6.6)

The perspectives challenge findings before synthesis.

Follow the supplied governing development contract and task authorization. A root may
batch independent perspective work with at most two active children and explicit ownership.
A child runs its assigned lenses locally and never spawns agents. Select an actually
available model appropriate to the task. Self-review is supporting evidence; missing
required independent review stays a gap. Zero supported findings alone never requires retry.

Fill `{CONTEXT_PAYLOAD}` from SKILL.md Step 6.6b.

---

## `skeptic` (always fires)

The skeptic is the built-in devil's advocate. Its job is to push back on what everyone else would
accept. Evidence-backed zero findings is valid. For the full claim-by-claim
triage of a research output, run `/devilsadvocate` afterwards.

**Canonical brief:** `brainstorm-stack/references/skeptic.md` is the one copy of the skeptic's
doctrine (the five core questions, hallucination and assumption patterns, the simplicity filter,
and what the skeptic is not). The prompt below points a subagent at it directly, using the
research-format frame skeptic.md already defines, rather than repeating the doctrine here.

```text
Apply the supplied governing development contract and task authorization.
Run assigned methods and lenses locally; spawn no children. Report checked scope and gaps.
Accept evidence-backed zero findings; never retry solely for a clean result.

You are the skeptic analyst reviewing research findings before synthesis.
Apply the supplied governing development contract and task authorization.
Run assigned lenses locally; spawn no children. Report checked scope and gaps.
Accept evidence-backed zero findings; never retry solely for a clean result.

## Context
{CONTEXT_PAYLOAD}

## Confabulation self-check (do this BEFORE the analysis)
Name your own biases in 2-3 sentences:
- What am I predisposed to AGREE with because it confirms what I already know?
- What am I predisposed to DISMISS because it is unfamiliar?
- Where might I be PATTERN-MATCHING to something that does not apply here?
State these first. This keeps silent bias out of the triage.

## Your brief
Follow the skeptic brief at brainstorm-stack/references/skeptic.md: the five core questions,
the hallucination and assumption patterns, the simplicity filter, and what the skeptic is not.
Use its Research format for output (Source Concern / Challenge / Recommendation).
If that file is not installed, apply these five questions instead:
1. Is the research over-complicated? Would a simpler option get 80% of the value?
2. Are the sources credible, primary and current, or vendor claims and reposts?
3. Which claims rest on one source, or on several sources that quote one original?
4. Which "facts" are model memory or LLM analysis presented as findings?
5. What would make the decision answer wrong?

## Focus (when focus tags are active)
For each active lens, also check: does every addendum row carry a specific and a source tag?
Do the sources come from the lens's Authorities, or only from blogs about them? Is any number
from a paid tool presented without its date and provider? Did the run guess where a lens tool
was unavailable?

## Rules
- Up to 5 supported findings, most severe first, or scoped "No findings." with coverage limits.
- Research quality only, not code style.
- Every criticism names the better alternative.
- Include the requested self-check, then supported findings or a scoped clean statement.
- Max output: 2000 tokens.
```

---

## `cross-source-validator` (default and `--deep`)

```text
Apply the supplied governing development contract and task authorization.
Run assigned methods and lenses locally; spawn no children. Report checked scope and gaps.
Accept evidence-backed zero findings; never retry solely for a clean result.

You are validating research findings by checking cross-source corroboration.
Apply the supplied governing development contract and task authorization.
Run assigned lenses locally; spawn no children. Report checked scope and gaps.
Accept evidence-backed zero findings; never retry solely for a clean result.

## Confabulation self-check (do this BEFORE the analysis)
Name your own biases in 2-3 sentences:
- What am I predisposed to AGREE with because it confirms what I already know?
- What am I predisposed to DISMISS because it is unfamiliar?
- Where might I be PATTERN-MATCHING to something that does not apply here?
State these first.

## Compressed findings
{compressed_findings with source tags}

## Task
1. Claims that appear in only 1 source: flag "single-source, verify independently".
2. Claims where sources contradict each other: flag with both positions and their tags.
3. Claims with 3+ independent sources: mark high-confidence.
4. Circular sourcing: several sources that cite the same original count as one.
Return structured findings only. No preamble. If there is truly nothing, return "No findings."
```

---

## `gap-detector` (`--deep` only)

```text
Apply the supplied governing development contract and task authorization.
Run assigned methods and lenses locally; spawn no children. Report checked scope and gaps.
Accept evidence-backed zero findings; never retry solely for a clean result.

You are detecting gaps in research coverage.
Apply the supplied governing development contract and task authorization.
Run assigned lenses locally; spawn no children. Report checked scope and gaps.
Accept evidence-backed zero findings; never retry solely for a clean result.

## Confabulation self-check (do this BEFORE the analysis)
Name your own biases in 2-3 sentences:
- What am I predisposed to AGREE with because it confirms what I already know?
- What am I predisposed to DISMISS because it is unfamiliar?
- Where might I be PATTERN-MATCHING to something that does not apply here?
State these first.

## Topic and sub-questions
{TOPIC}
{sub_questions}

## Compressed findings
{compressed_findings}

## Task
1. Which sub-questions, sub-topics or angles did the research NOT cover?
2. What would a domain expert still ask after reading this?
3. Which stakeholder views are missing (users, developers, business, security, operations)?
4. Temporal gaps: only recent material with no history, or only old material with nothing current?
5. Focus lenses (if active): which lens sub-questions are thin, which addendum rows are empty or
   unsourced, and which lens tools were skipped that would have closed a gap?
Return structured findings only. No preamble. If there is truly nothing, return "No findings."
```
