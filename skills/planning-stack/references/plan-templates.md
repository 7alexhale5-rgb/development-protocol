# Plan templates (Steps 4, 6 and 6.5)

## Contents

- Header every plan carries
- TECH mode template, and its deep additions
- FEATURE mode template, and its deep additions
- Report
- Plan summary (Step 6.5)
- Decision record (Step 6.5)

Sections marked "only if <lens> fired" render only when `scripts/lens_classify.py` fired that
lens. Leave them out otherwise; do not write empty headings.

---

## Header every plan carries

Both templates start with this block. The approval gate refuses a plan without it.

```markdown
---
date: <YYYY-MM-DD>
goal: "<GOAL>"
mode: <TECH|FEATURE>
done_tier: <Demoable|Live|Production-secure>
---

### Scope

- **In scope**: <list>
- **Out of scope**: <list>
- **Change rule**: after approval, scope changes go to AMENDMENTS.md and are approved separately.

<!-- Client builds only: countable scope -->

- **Countable scope**: <pages, templates, motion level, integrations with quantities,
  exclusions, what one revision means, how change requests work>
```

---

## TECH mode template

```markdown
## Technical Plan: <GOAL>

### Context

- **Project**: <name and one-line description>
- **Current State**: <what exists today that matters for this goal>
- **Prior Decisions**: <relevant decisions from Step 0.5, if any>

### Architecture Decision

- **Chosen Approach**: <approach with clear rationale>
- **Alternatives Considered**: <2 to 3 alternatives with their trade-offs>
- **Trade-offs**: <what we gain and what we give up>

<!-- only if reversibility fired -->

### Reversibility Ledger

| Plan Step | Class                     | Irreversibility Cost                           | Recommendation                           |
| --------- | ------------------------- | ---------------------------------------------- | ---------------------------------------- |
| <step>    | TYPE-1 / TYPE-2 / UNCLEAR | <what is destroyed if wrong; blank for TYPE-2> | <fast-track / extra diligence / clarify> |

<!-- only if economist fired -->

### ROI Snapshot

| Item                  | Estimate                                | Notes                    |
| --------------------- | --------------------------------------- | ------------------------ |
| Build cost            | <hours x loaded rate>                   | <breakdown>              |
| 3-yr TCO              | <build + infra + maintenance + support> | <dominant driver>        |
| Value vs alternatives | <expected value / cycles / users>       | <best alternative named> |

<!-- only if adversary fired -->

### Adversarial Threat Surface

- **Top attack chains** (by severity): <from the adversary lens: concrete attack paths>
- **Trust boundary shifts**: <who joins the trust zone through this plan>
- **Mitigations**: <a named control per chain>

### System Design

- **Components Affected**: <systems, services, modules>
- **Data Flow**: <the path data takes through the system>
- **API Contracts**: <new or changed endpoints and interfaces, with request and response shapes>
- **Schema Changes**: <migrations needed, if any>

### Implementation Strategy

Each phase ships one runnable thing and names the check that proves it.

- **Phase 1, Foundation**: <prerequisites, setup, scaffolding> (check: <command>)
- **Phase 2, Core**: <main implementation> (check: <command>)
- **Phase 3, Integration**: <connect the pieces, end-to-end test> (check: <command>)
- **Phase 4, Hardening**: <performance, security, error handling> (check: <command>)

### Risk Assessment

| Risk   | Severity     | Likelihood   | Mitigation   | Source               |
| ------ | ------------ | ------------ | ------------ | -------------------- |
| <risk> | High/Med/Low | High/Med/Low | <mitigation> | [perspective:<name>] |

### Performance and Security

- **Performance**: <implications, benchmarks to hit, likely bottlenecks>
- **Security**: <attack surface changes, auth implications, data exposure>
- **Scaling**: <how the design handles 10x and 100x load>

<!-- only if compliance fired -->

#### Compliance Surface

| Regulation + Article/Control | Plan Step | Required Evidence | Mitigation       |
| ---------------------------- | --------- | ----------------- | ---------------- |
| <GDPR Art X / PCI-DSS Req X> | <step>    | <auditor ask>     | <control to add> |

<!-- only if observability fired -->

### 3am Test

- **Top observability gaps** (by severity): <what is missing for diagnosis>
- **Concrete 3am scenarios**: <per gap: what fires, what on-call sees, what is missing>
- **Recommended instrumentation**: <span attributes, metric names and labels, error context>

<!-- only if sre fired (TECH only) -->

### Operability Plan

- **Rollback granularity**: <feature flag? additive schema? forward-only?>
- **Blast radius**: <users / regions / services / data if this fails>
- **Failure modes catalogued**: <only the ones this plan introduces: full disk, out of memory,
  pool exhaustion, cache stampede, region outage, cron overlap>
- **Runbook delta**: <new entries for the on-call runbook>

<!-- only if test-strategist fired -->

### Test Strategy

- **Golden Path**: <the single test or production synthetic that says "it works" when green>
- **Test layer choices**: <unit / integration / e2e / contract / property / chaos / prod probe,
  and why>
- **Intentionally NOT tested**: <what monitoring catches more cheaply, and why>

### Migration Path

- **Backwards Compatibility**: <can it be deployed incrementally?>
- **Rollback Strategy**: <how to undo it>
- **Feature Flags**: <what to gate behind flags, if anything>

### Verification

- [ ] <how to verify the architecture works as designed: command and expected output>
- [ ] <performance benchmark to run>
- [ ] <security check to run>
```

### Deep TECH additions

- A formal Architecture Decision Record section: context, decision, status, consequences.
- A trade-off matrix across 2 to 3 approaches:

  ```text
  | Criterion       | Approach A | Approach B | Approach C |
  |-----------------|------------|------------|------------|
  | Complexity      | ...        | ...        | ...        |
  | Performance     | ...        | ...        | ...        |
  | Maintainability | ...        | ...        | ...        |
  | Cost            | ...        | ...        | ...        |
  ```

- Performance implications with estimated complexity (big-O where it matters).
- A security review checklist.
- A detailed migration and rollback sequence, step by step.

---

## FEATURE mode template

```markdown
## Feature Plan: <GOAL>

### Context

- **Project**: <name and one-line description>
- **Current State**: <what exists today>
- **Prior Decisions**: <relevant decisions from Step 0.5, if any>

### Requirements

- **Goal**: <the outcome, clear and measurable>
- **Acceptance Criteria**:
  - [ ] <criterion 1: specific, testable>
  - [ ] <criterion 2: specific, testable>
  - [ ] <criterion 3: specific, testable>

### Files to Modify

| File                 | Change         | Rationale |
| -------------------- | -------------- | --------- |
| `path/to/file.ts:42` | <what changes> | <why>     |

### Files to Create

| File                  | Purpose        |
| --------------------- | -------------- |
| `path/to/new-file.ts` | <what it does> |

### Implementation Steps

1. **<Step title>**: <description with file:line references where they apply> (check: <command>)
2. **<Step title>**: <description> (check: <command>)
3. **<Step title>**: <description> (check: <command>)

### Dependencies

- **Packages**: <new packages, with versions>
- **Services**: <external services or APIs>
- **Config**: <environment variables, flags, config changes>
- **Prerequisites**: <work that must land first>

### Test Plan

- [ ] **Unit**: <what to test and the expected behaviour>
- [ ] **Integration**: <which systems interact>
- [ ] **Manual**: <the specific verification step>
- [ ] **Edge Cases**: <boundary conditions>

<!-- only if test-strategist fired -->

### Test Strategy

- **Golden Path**: <the single test or production synthetic that confirms the feature works>
- **Layer choices**: <unit / integration / e2e / contract / property, and why>
- **Intentionally NOT tested**: <what is cheaper to monitor than to test>

<!-- only if reversibility fired -->

### Reversibility Ledger

| Step   | Class                     | Cost if Wrong      | Recommendation                           |
| ------ | ------------------------- | ------------------ | ---------------------------------------- |
| <step> | TYPE-1 / TYPE-2 / UNCLEAR | <blank for TYPE-2> | <fast-track / extra diligence / clarify> |

<!-- only if economist fired -->

### ROI Snapshot

| Item                  | Estimate                          | Notes                    |
| --------------------- | --------------------------------- | ------------------------ |
| Build cost            | <hours x loaded rate>             | <breakdown>              |
| 3-yr TCO              | <build + maintenance + support>   | <dominant driver>        |
| Value vs alternatives | <expected value / users / cycles> | <best alternative named> |

<!-- only if observability fired -->

### 3am Test

- **Gaps**: <from the observability lens>
- **Add**: <specific instrumentation>

<!-- only if compliance fired -->

### Compliance Surface

| Regulation + Article | Plan Step | Required Evidence | Mitigation |
| -------------------- | --------- | ----------------- | ---------- |
| <citation>           | <step>    | <auditor ask>     | <control>  |

### Risks

| Risk   | Severity     | Mitigation   | Source               |
| ------ | ------------ | ------------ | -------------------- |
| <risk> | High/Med/Low | <mitigation> | [perspective:<name>] |

### Rollback Strategy

- <how to revert safely if the feature causes problems>
```

### Deep FEATURE additions

- More granular steps, with code snippets for complex logic.
- Alternative implementation approaches with short trade-off notes.
- An extended test plan with edge cases and failure scenarios.
- User experience considerations (for UI work, the Visual Spec Pack from `/visual-spec` is the
  plan's visual body).
- Monitoring and observability additions: logs, metrics, alerts.

---

## Report

Append to the delivered plan (Step 6):

```text
---
Planning Stack Report
├─ Mode: TECH | FEATURE
├─ Depth: deep
├─ Confidence: High | Medium | Low  (load-bearing claims: <n> verified, <n> reported,
│                                    <n> inferred, <n> unverifiable)
├─ Sources: codebase (<n>), repo memory (<n>), plans (<n>), research (<n> | skipped),
│           best practices (<n> | skipped)
├─ Perspectives (<N> fired): skeptic=<n>, architecture=<n>, security=<n>, performance=<n>,
│                            first-principles=<n>, risk-assessor=<n>, pattern-matcher=<n>
├─ Specialist lenses: <N> always on + <N> keyword-gated = <total> fired
│  ├─ Always on: adversary, observability, reversibility, economist, test-strategist
│  ├─ Triggered: <gated lenses, or "none">  (dropped by cap: <list or "none">)
│  └─ Cross-cutting findings: <n>
├─ Verification: <n> passes, all checks passed | <failed checks>
├─ Independent review: <reviewer kind>, <n> rounds, <n> fixed / <n> dismissed / <n> deferred
│                      | not reviewed: <why>
├─ Prior decisions applied: <list> | none
└─ Plan file: <path>

Ask me anything about this plan. I have full context on the codebase and requirements.
```

---

## Plan summary

Written at Step 6.5 to `.devproto/plans/<YYYY-MM-DD>-<goal-slug>.summary.md` (next to the plan):

```markdown
---
date: <YYYY-MM-DD>
type: plan-summary
project: <project name>
mode: <MODE>
confidence: <High|Medium|Low>
plan: <path to the full plan>
---

# Plan: <GOAL>

## Approach

<1 to 2 sentences on the chosen approach>

## Key files

<top 5 files affected>

## Risks

<top 2 to 3 risks>

## Decisions

<key architectural or implementation decisions>
```

## Decision record

When a significant architectural decision was made (especially in TECH mode), also write
`.devproto/decisions/<YYYY-MM-DD>-<decision-slug>.md`, or use the project's ADR folder if it has
one:

```markdown
---
date: <YYYY-MM-DD>
type: decision
project: <project name>
status: accepted
---

# Decision: <one-line summary>

## Context

<GOAL and the constraints that forced a choice>

## Decision

<what was chosen>

## Rationale

<why this approach>

## Alternatives rejected

<list, each with the reason>
```
