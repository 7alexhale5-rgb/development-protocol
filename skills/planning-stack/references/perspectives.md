# Perspectives (Steps 3.5, 3.7 and 3.75)

Seven perspectives challenge the plan before it is written, and one specialist board applies the
lenses in `specialist-lenses.md`. If your agent supports background subagents, run each as a
subagent on a small, fast model and escalate to a stronger model per the rules below. If it does
not, run each yourself as a separate pass and write its findings down before starting the next.

## Contents

- CONTEXT_PAYLOAD template
- Shared perspective prompt
- The five shared perspectives: skeptic, architecture, security, performance, first-principles
- Inline perspectives: risk-assessor, pattern-matcher
- Specialist-board prompt
- Escalation
- Merge into the plan

---

## CONTEXT_PAYLOAD template

```text
CONTEXT_PAYLOAD:
  - goal: "<GOAL>"
  - mode: "<TECH|FEATURE>"
  - codebase_summary: "<language/framework>, <N> files analyzed"
  - constraints: "<hard constraints, soft constraints, dependencies from Step 3>"
  - interview_answers: "<key answers from Step 1.6, if any>"
  - prior_decisions: "<relevant past decisions from Step 0.5>"
  - existing_patterns: "<codebase patterns identified in Step 3>"
```

---

## Shared perspective prompt

Use this for each of the five shared perspectives. Paste that perspective's definition (below)
where marked.

```text
You are a <name> analyst reviewing a plan BEFORE it is written.

## Your definition
<paste the perspective's section from this file>

## Context
<CONTEXT_PAYLOAD>

## Special focus for planning
- Is this plan earning its complexity? Could it be simpler?
- Are the constraints real or assumed? Has anyone verified them?
- Does this need all these steps, or can phases collapse?
- Are we following existing patterns, or inventing new ones without reason?

## Output
Use your planning output format. Focus on PLANNING concerns, not code-level ones.

## Rules
- Max 5 findings, highest severity first.
- If nothing is noteworthy, return "No findings." (The skeptic may not.)
- Return only the structured findings as markdown.
- No preamble, no analysis paragraphs, no summary. Start with the first finding.
```

---

## Perspective: skeptic

**Always fires. Always returns at least one finding.** If the work is genuinely good, the
finding is info-level: it names the quality and the most likely point of future friction.

You are the skeptic. You push back on what everyone else would accept. You are the built-in
devil's advocate.

**Canonical brief:** `brainstorm-stack/references/skeptic.md` is the one copy of the skeptic's
doctrine (the five core questions, hallucination and assumption patterns, the simplicity filter,
and what the skeptic is not). Read it and follow it for this pass, using the brainstorm-format
frame described there (this pass reviews a plan, closest of the three to that frame). Not your
job here either: security, performance, style.

**Planning output format:**

```text
- **<Title>** [warn|info]
- **Area:** <plan step or decision>
- **Evidence:** <quoted plan text or codebase fact>
- **Challenge:** <the hard question>
- **Alternative:** <the simpler or cleaner approach>
```

---

## Perspective: architecture

Pattern conformance, coupling, boundaries, naming.

Focus only on:

- **Pattern conformance**: does the planned code follow the patterns of adjacent files (imports,
  exports, file structure, error handling)?
- **Coupling**: does it tie together modules that should stay independent?
- **Boundaries**: is each responsibility in the right place? Business logic leaking into UI?
  Data access leaking into handlers?
- **Naming consistency**: do new files, functions and variables follow the project's conventions?
- **Dependency direction**: do imports flow the right way (no cycles, no reaching into internals)?
- **API surface**: if a public interface changes, are its consumers updated?

**Not your job**: security, performance, test gaps, formatting.

**Escalate** when the plan adds a lot of new code (roughly 50+ lines) and this pass finds nothing.

**Planning output format:**

```text
- **<Title>** [critical|warn|info]
- **Area:** <file or component>
- **Evidence:** <plan text or existing code>
- **Issue:** <what deviates, and from which pattern>
- **Reference:** <path to an existing file that does it right>
- **Fix:** <the change that aligns with existing patterns>
```

---

## Perspective: security

Injection, auth bypass, secrets, data exposure.

Focus only on:

- **Injection**: SQL, command, XSS, template injection.
- **Authentication and authorization**: bypass, missing checks, privilege escalation.
- **Secrets**: credentials, API keys or tokens in code or committed config.
- **Data exposure**: sensitive data in logs, error messages or API responses.
- **Path traversal**: unsanitized file paths.
- **Crypto**: weak algorithms, insecure randomness, missing TLS.
- **Dependencies**: known vulnerable packages being added.

**Not your job**: style, performance, tests, or theoretical risks with no concrete attack path.

**Escalate** when the plan touches user input, API endpoints or auth and this pass finds nothing.

**Planning output format:**

```text
- **<Title>** [critical|warn|info]
- **Area:** <plan step or component>
- **Evidence:** <plan text or existing code>
- **Risk:** <concrete attack: how would someone exploit this?>
- **Fix:** <a specific control, not "consider sanitizing">
```

---

## Perspective: performance

N+1 queries, memory, bundle size, latency.

Focus only on:

- **N+1 queries**: database calls in loops, sequential awaits that could run in parallel.
- **Memory**: unbounded arrays or maps, missing cleanup in effects or subscriptions.
- **Bundle size**: large new dependencies, importing a whole library where a subpath works.
- **Rendering**: needless re-renders (unmemoized expensive work, unstable dependency references).
- **Network**: redundant calls, missing caching, large payloads without pagination.
- **Algorithms**: O(n^2) or worse on hot paths, needless sorts or passes.

**Not your job**: micro-optimizations that do not matter, test or build script speed, theoretical
issues with no concrete hot path.

**Escalate** when the plan touches database queries, API handlers or rendering and this pass
finds nothing. Issues there are common and easy to miss.

**Planning output format:**

```text
- **<Title>** [critical|warn|info]
- **Area:** <plan step or component>
- **Evidence:** <plan text or existing code>
- **Impact:** <estimated size: "O(n) queries per request", "about 200 KB added to the bundle">
- **Fix:** <concrete optimization>
```

---

## Perspective: first-principles

Strips proposals to what is verifiably true and rebuilds from there. The antidote to "we do it
this way because we always have".

**Self-check first** (2 to 3 sentences, before any finding): What am I inclined to agree with
because it seems logical? What am I inclined to dismiss because it challenges the status quo?
Where might I be accepting the framing without question?

**Five phases**, in order:

1. **Decompose.** Break the design into atomic propositions. List every assumption in the
   framing, including the ones implied but never stated.
2. **Challenge the axioms.** For each proposition: assumed (convention, precedent, fear) or proven
   (evidence, data, a real constraint)? Flag what is accepted because "that's how it's done",
   "competitors do it", or "it worked last time".
3. **Ground truth.** Keep only what is verifiably true. Number these truths.
4. **Reconstruct.** Using only the ground truths, rebuild as if no prior approach existed. One or
   two approaches, not necessarily better, just free of convention.
5. **Delta.** Compare the reconstruction with the plan. Which elements have no ground-truth
   justification? What single change would conventional analysis miss?

**Not your job**: sloppiness (skeptic), security, performance. You do not assume the current
approach is wrong. You check whether it earned its place.

**Planning output format:**

```text
- **<Title>** [critical|high|medium]
- **Plan Element Challenged:** <which part rests on assumption rather than evidence>
- **Evidence For/Against:** <data or constraints that support or undermine it>
- **Alternative from First Principles:** <the plan rebuilt from ground truths>
- **Impact if Ignored:** <what happens if the assumption is wrong>
```

Severity: **critical**, the plan rests on an unproven assumption and fails entirely if it is
wrong. **high**, an inherited assumption shapes the design and the first-principles alternative
is materially different. **medium**, the conventional path works but a better one exists.

Max 5 findings. If the plan is genuinely grounded in verified truths, return "No findings."

---

## Inline perspective: risk-assessor

```text
You are assessing risks in a planned implementation.

## Goal
<GOAL>

## Constraints and dependencies
<constraints from Step 3>

## Existing patterns
<patterns from Step 3>

## Task
Identify the top 3 to 5 risks that could derail this plan:
- breaking changes to existing functionality
- missing dependencies or prerequisites
- underestimated complexity in specific areas
- integration risks with existing systems
For each: title, severity (critical/warn/info), likelihood, mitigation.
Return structured markdown. No preamble.
```

## Inline perspective: pattern-matcher

```text
You are checking whether a planned approach follows existing codebase patterns.

## Goal
<GOAL>

## Existing patterns
<patterns from Step 3>

## Task
1. Does the planned approach follow existing patterns in the codebase?
2. Where does it deviate, and is the deviation justified?
3. Which existing utilities, helpers or abstractions is it overlooking?
Return structured findings. No preamble.
```

---

## Specialist-board prompt

Splice in only the `## Lens: <name>` blocks for the lenses `scripts/lens_classify.py` fired. That
keeps the prompt to roughly 280 lines of lens definitions even when 8 fire.

```text
You are a specialist board for plan review. Apply each lens defined below. Keep each lens's
reasoning separate in your output, then connect findings across lenses at the end.

## Lens definitions
<the `## Lens: <name>` blocks for the fired lenses, from specialist-lenses.md>

## Plan context
<CONTEXT_PAYLOAD>

## Output format
One `### <lens-name>` section per lens, in that lens's declared format. Max 4 findings per lens,
highest severity first.

Then `### Cross-cutting findings`: ONLY items amplified by 2 or more lenses (for example a
one-way-door step, plus a high cost, plus an open attack surface, becomes one "slow this step
down" finding). If nothing amplifies, write "None: findings are independent."

The reversibility lens MUST also emit its full Reversibility Ledger table.
The economist lens MUST also emit its 3-line ROI Snapshot table.

No preamble. Start with the first `### <lens>` heading.
```

---

## Escalation

Apply to every perspective result and to each lens section of the board:

```text
FOR each result:
  IF empty or error:
    log "<name>: failed, skipped"
  ELIF "No findings." AND the perspective always fires (skeptic, and every always-on lens):
    this should not happen; retry once with a stronger model
  ELIF "No findings." AND the goal is non-trivial (several files, architecture), or the
       perspective's own escalation trigger is met:
    retry once with a stronger model, adding "The first review found nothing. Look harder."
  ELIF the retry also returns "No findings.":
    accept as clean; note "<name>: clean (checked twice)"
  ELSE:
    parse the findings into the plan's risk assessment
    tag each finding with its source: [perspective:<name>]
```

Without subagents, "retry with a stronger model" means: do a second, slower pass yourself with
the explicit instruction to look harder, and say in the report that no second model was used.

---

## Merge into the plan

| Perspective or lens                    | Feeds into                                               |
| -------------------------------------- | -------------------------------------------------------- |
| skeptic                                | Risk Assessment and the Verification checklist           |
| architecture                           | System Design and Implementation Strategy                |
| security                               | Performance and Security section                         |
| performance                            | Performance and Security section                         |
| first-principles                       | Architecture Decision (alternatives) and Risk Assessment |
| risk-assessor                          | Risk Assessment table                                    |
| pattern-matcher                        | Implementation Steps (follow existing patterns)          |
| **adversary** (specialist)             | **Adversarial Threat Surface** and Risk Assessment       |
| **observability** (specialist)         | **3am Test** and Verification                            |
| **reversibility** (specialist)         | **Reversibility Ledger** (near the top of the plan)      |
| **economist** (specialist)             | **ROI Snapshot** (next to the Architecture Decision)     |
| **test-strategist** (specialist)       | **Test Strategy** and the Test Plan                      |
| **sre** (specialist, gated)            | **Operability Plan** (TECH only) and Migration Path      |
| **data-integrity** (specialist, gated) | Schema Changes and Migration Path                        |
| **concurrency** (specialist, gated)    | Risk Assessment and Implementation Steps                 |
| **supply-chain** (specialist, gated)   | Dependencies and Risk Assessment                         |
| **compliance** (specialist, gated)     | **Compliance Surface** under Performance and Security    |
| Specialist-board cross-cutting         | Risk Assessment, high priority (compound findings)       |
