# Output templates

Loaded by Step 5, Step 6, Step 6.5 and Step 7 of `SKILL.md`.

## Contents

1. Finding structure
2. Summary block
3. Verdicts
4. Acceptance criteria section
5. Remediation plan (`--audit` only)
6. JSON output
7. Agent isolation

---

## 1. Finding structure

Every finding in the pool uses this format:

```markdown
**{N}. {Title}** [{severity}] [{confidence}]

- **File:** {relative_path}:{line}
- **Evidence:** {quoted code or diff excerpt}
- **Issue:** {what is wrong and why it matters}
- **Recommendation:** {the concrete fix: a specific code change, not vague advice}
- **Layer:** L1-Static | L2-Pattern | L3-Context | L4-Runtime | L5-Regression
- **Source:** {tool name, or [perspective:{name}]}
- **Outcome:** {left blank for the builder: fixed | rejected, because ... | deferred to {owner}}
```

Rules:

- If you cannot quote evidence from the code, set confidence to "low".
- Every recommendation is a concrete action, never "consider reviewing".
- Include a suggested code fix when the fix is obvious and under 5 lines.

---

## 2. Summary block

```text
---
Verification Report
├─ Commit: {sha}
├─ Scope: {N} files ({additions}+ {deletions}-)
├─ Plan: {plan path | "none"}
├─ Depth: {quick | default | deep | audit}
├─ Layers:
│  ├─ L1 Static: {pass|fail} (types: {pass|fail} lint: {pass|fail} build: {pass|fail} security: {pass|fail|N/A})
│  ├─ L2 Pattern: {N} findings (coverage: {%} {up|down|same})
│  ├─ L3 Context: criteria {pass}/{total} | architecture {N} deviations
│  ├─ L4 Runtime: {pass|fail|skipped|N/A}
│  └─ L5 Regression: {pass|fail|skipped|N/A}
├─ Perspectives: {N} run | {N} returned findings | {N} retried with a stronger model
│  ├─ skeptic: {N} findings (always runs)
│  ├─ {name}: {N} findings | "clean (2x)" | "failed" | "skipped"
│  └─ ...
├─ Findings: {critical_count} critical | {warn_count} warnings | {info_count} info
├─ Gate: {PASS | SOFT FAIL | HARD FAIL}
└─ Verdict: {SHIP IT | FIX THEN SHIP | NEEDS WORK | BLOCKED | READY TO SHIP | SHIP WITH CAVEATS}
---
```

Also write a plain line `Verdict: <verdict>` near the top of the saved file. The checklist
verifier reads that line.

---

## 3. Verdicts

| Verdict               | Condition                                                                     |
| --------------------- | ----------------------------------------------------------------------------- |
| **SHIP IT**           | 0 critical, 0 warn, all criteria PASS                                         |
| **FIX THEN SHIP**     | 0 critical, 3 warn or fewer (all auto-fixable or minor), criteria mostly PASS |
| **NEEDS WORK**        | 0 critical but more than 3 warnings, OR any criterion fails                   |
| **BLOCKED**           | Any critical finding, OR a build failure, OR type errors                      |
| **READY TO SHIP**     | `--audit`: 0 critical, 0 warn, all criteria PASS, readiness checklist 100%    |
| **SHIP WITH CAVEATS** | `--audit`: 0 critical, 3 warn or fewer (non-blocking), readiness 80% or more  |

Gate: PASS when there are no critical or warn findings. SOFT FAIL when there are warnings only.
HARD FAIL on any critical, or on any L1 failure with `--gate hard`.

A CANNOT VERIFY criterion is not a PASS. It keeps SHIP IT and READY TO SHIP out of reach until it
is checked, or until the owner accepts it in writing with a reason.

---

## 4. Acceptance criteria section

```text
Plan alignment: {pass_count}/{total_count} criteria met

  1. {criterion summary}: PASS
  2. {criterion summary}: FAIL. {gap}
  3. {criterion summary}: PARTIAL. {what is missing}
  4. {criterion summary}: CANNOT VERIFY. {why}
```

---

## 5. Remediation plan (`--audit` only)

### Template

```text
═══════════════════════════════════════════════════
REMEDIATION PLAN: {project}, {date}, commit {sha}
═══════════════════════════════════════════════════

EXECUTIVE SUMMARY
  Verdict: {verdict}
  Total findings: {N} ({critical} critical, {warn} warnings, {info} info)
  Estimated remediation: {total effort}
  Auto-fixable: {auto_count}/{total_count} ({percentage}%)

───────────────────────────────────────────────────
PRIORITY GROUP 1: BLOCKERS (fix before ship)
───────────────────────────────────────────────────

Fix 1.1: {title}
  Source: L{layer} / {perspective or tool}
  File: {path}:{line}
  Effort: {about X min} | {auto-fixable | manual}
  Action: {exact command or code change}

───────────────────────────────────────────────────
PRIORITY GROUP 2: HIGH (fix before go-live)
───────────────────────────────────────────────────

Fix 2.1: ...

───────────────────────────────────────────────────
PRIORITY GROUP 3: MEDIUM (fix this sprint)
───────────────────────────────────────────────────

Fix 3.1: ...

───────────────────────────────────────────────────
PRIORITY GROUP 4: LOW (track for later)
───────────────────────────────────────────────────

Fix 4.1: ...

═══════════════════════════════════════════════════
AUTO-FIX MANIFEST
═══════════════════════════════════════════════════

Run these commands in order to fix every auto-fixable issue:

  1. {command}: fixes {Fix 1.1, Fix 3.2}
  2. {command}: fixes {Fix 2.3}
  3. {specific code patch}: fixes {Fix 1.2}

After the auto-fixes, re-check with:
  /review-stack --quick

═══════════════════════════════════════════════════
GOING-PUBLIC READINESS CHECKLIST
═══════════════════════════════════════════════════

  [ ] Types pass (tsc --noEmit or equivalent)
  [ ] Lint clean
  [ ] Build succeeds
  [ ] All end-to-end smoke tests pass
  [ ] No critical security vulnerabilities
  [ ] WCAG 2.1 AA (axe: 0 critical or serious on key routes)
  [ ] No critical dependency audit findings
  [ ] Bundle size under threshold
  [ ] API endpoints return the expected status codes
  [ ] No console errors in the browser
  [ ] Lighthouse Performance 80 or more on every audited route (hard floor)
  [ ] Lighthouse Accessibility 90 or more on every audited route (hard floor)
  [ ] No Lighthouse category down 10 or more from baseline
  [ ] CLS under 0.1 on every audited route
  [ ] LCP under 4.0 s on every audited route
  [ ] Release controls: no launch-gate control in review without issue, owner, date, approver

  READINESS: {X}/{Y} checks passed: {READY | NOT READY}
```

Tick a box only when a check in this run proved it. A box you could not check stays empty and is
listed as "not verified".

### Effort estimates

| Category                                 | Estimate     |
| ---------------------------------------- | ------------ |
| Auto-fixable lint                        | about 1 min  |
| Type error (missing import)              | about 2 min  |
| Type error (wrong type)                  | about 5 min  |
| Missing test                             | about 15 min |
| Security vulnerability (code)            | about 20 min |
| Accessibility violation (missing ARIA)   | about 5 min  |
| Accessibility violation (needs refactor) | about 30 min |
| Architecture deviation                   | about 30 min |
| End-to-end test failure                  | about 30 min |

### Priority mapping

| Finding severity                | Finding source | Priority group |
| ------------------------------- | -------------- | -------------- |
| critical (any layer)            | any            | BLOCKERS       |
| warn, security or accessibility | L3 or L4       | HIGH           |
| warn, code-quality or test      | L2 or L3       | MEDIUM         |
| info (any)                      | any            | LOW            |

---

## 6. JSON output

```json
{
  "verdict": "FIX_THEN_SHIP",
  "gate": "SOFT_FAIL",
  "commit": "a1b2c3d",
  "scope": { "files": 6, "additions": 142, "deletions": 23 },
  "layers": {
    "l1": {
      "types": "pass",
      "lint": "fail",
      "build": "pass",
      "security": "n/a"
    },
    "l2": { "coverage": 78.3, "coverage_delta": -2.1, "findings": 3 },
    "l3": { "criteria_pass": 4, "criteria_total": 5, "deviations": 1 }
  },
  "findings": [
    {
      "id": 1,
      "title": "Missing null check on user input",
      "severity": "warn",
      "confidence": "high",
      "file": "src/api/handler.ts",
      "line": 42,
      "evidence": "const data = req.body.payload // no validation",
      "recommendation": "Validate the payload with a schema before reading it",
      "layer": "L3-Context",
      "source": "perspective:security"
    }
  ],
  "criteria": [
    {
      "text": "API returns 200 with valid data",
      "verdict": "PASS",
      "evidence": "src/api/handler.ts:58"
    }
  ]
}
```

The same object is what Step 7.5 writes to `.devproto/review/latest-findings.json`.

---

## 7. Agent isolation

### As a helper agent (from `/build-stack` Step 6.5)

```text
Helper agent:
  instructions: |
    Run /review-stack --branch --plan {plan_path}
    Review all changes on this branch against the plan.
    Return the full verification output.
  model: a stronger model than the builder, or a different model family
  description: "Post-implementation review"
```

### As a fresh session

```text
# Start a new session in the repository, then:
/review-stack --branch --plan .planning/phases/03-auth/PLAN.md
```

### As part of `/build-stack`

`/build-stack` runs this as its review step (Step 6.5) and passes the plan path and scope.
