---
name: review-stack
description: Runs an independent, read-only review of finished code through layered quality gates (static checks, pattern analysis, context and plan conformance, runtime checks, regression tests), with parallel review perspectives, a severity-ranked findings report, a ship verdict and, in audit mode, a remediation report. Use after /build-stack, or on its own when someone says "review the code", "verify", "check the implementation", "quality check", "is this ready to ship", "audit this", "review my branch" or "review-stack". Records the review row of the development-protocol checklist. Best run in a fresh session or helper agent that did not write the code.
---

# Review Stack: full review and quality gate

You are running a multi-layer review of code that is already written. You are a **read-only
reviewer**. You analyze, report and recommend. You do NOT change the project's code. The only
files you write are your own outputs under `.devproto/`. If fixes are needed, you produce a
structured findings report that the user or the building agent acts on.

**Philosophy:** the agent that wrote the code must not be the one that reviews it. You are the
independent second opinion. Be specific, quote evidence, and prioritize hard.

**Proof rule.** Prove the real artifact, keep the executed result, and tie it to the exact commit.
A check you could not run is "cannot verify", never a pass.

For UI work, read the "Design and UI proof" section of the `/development-protocol` skill's
`reference.md`. It sets the fidelity floor and how to measure the result. Scale the measurement to
the task.

## Checklist row

This skill satisfies the `review` row of the development-protocol checklist. `DEVPROTO` means
`python3 <development-protocol skill folder>/scripts/devproto.py`.

Write the report to `.devproto/evidence/review.md` and its canonical structured result to
`.devproto/evidence/review.json`. Both name the exact reviewed commit. Record the row using
the structured result; pass the human report as an instrument:

```text
DEVPROTO --project <repo> step --id <work-id> --step review --result pass \
  --evidence .devproto/evidence/review.json --instrument .devproto/evidence/review.md \
  --verify 'python3 <review-stack skill folder>/scripts/verify_review.py .devproto/evidence/review.json --commit "$(git rev-parse HEAD)"'
```

HARD_FAIL, missing gate data, failed criteria, and unresolved required findings block the
row regardless of the headline verdict. A fixed outcome needs evidence; rejection needs
a reason. Deferral is only allowed for explicitly nonrequired, noncritical/nonhigh findings
with an owner, reason and named acceptance. Re-review and update both reports after fixes.

---

## Step 0: Parse intent

From the user's input, extract:

- **SCOPE**, what to review:
  - `--all`: every uncommitted change (default).
  - `--staged`: only staged files.
  - `--branch`: the full branch diff against the base (`main` or `master`).
  - `--files path1 path2`: only these files.
  - `--plan`: check against a plan's acceptance criteria.
- **DEPTH**:
  - `--quick`: L1 only (static checks). Skip AI analysis except the skeptic.
  - default: L1, L2 and L3 (full review).
  - `--deep`: L1, L2 and L3 plus extended security, coverage analysis and architecture review.
  - `--audit`: full audit. L1 to L4 plus the remediation report. Includes everything in
    `--deep` plus runtime checks.
- **FLAGS**:
  - `--plan path/to/plan.md`: the plan to check against.
  - `--gate hard`: treat all L1 failures as blocking (default: advisory).
  - `--no-criteria`: skip the acceptance criteria check (for ad-hoc reviews).
  - `--json`: output findings as structured JSON (for other tools).
  - `--cap N`: change the finding cap (default 12).
  - `--auto`: run every stage without pausing between layers. Pause only on a BLOCKED verdict.
  - `--regression`: run L5 regression tests against golden datasets (needs promptfoo, a free,
    open-source eval tool). Auto-on with `--audit` if a `.promptfoo/` folder exists.
  - `--no-runtime`: skip L4 even in `--audit` mode (useful when no dev server is available).
  - `--target-url <url>`: the live URL to use for runtime checks.

---

## Step 0.5: Auto mode (`--auto`)

When `--auto` is set:

- Run L1, L2, L3, L4, synthesis and report without pausing between layers.
- Pause only if the verdict is BLOCKED. The user must resolve critical issues.
- Skip the intermediate "review scope" output. Go straight to the final report.
- If a layer cannot run (tool missing), log it and continue to the next layer.
- At the end, deliver the full report in one output.

When `--auto` is NOT set (default):

- Report the scope after Step 1.
- Deliver findings after each layer.
- Let the user stop or adjust between layers.

---

## Step 1: Detect context

### 1a: Find what to review

```bash
git status                          # what changed
git diff --stat                     # unstaged changes
git diff --cached --stat            # staged changes
git log --oneline main..HEAD        # branch commits (for --branch)
git rev-parse HEAD                  # the commit you are reviewing; goes in the report
```

Collect the list of changed and created files. This is the **review surface**.

### 1b: Detect project tooling

Probe for available checks in parallel:

```text
Read: package.json (scripts.build, scripts.test, scripts.lint, scripts.typecheck)
Read: package.json devDependencies for @axe-core/playwright, lighthouse
Find: tsconfig.json
Find: eslint.config.* or .eslintrc*
Find: biome.json or biome.jsonc
Find: .ruff.toml, ruff.toml or pyproject.toml
Find: **/*.test.{ts,tsx,js,jsx} or **/*.spec.{ts,tsx,js,jsx}
Find: **/pytest.ini or **/conftest.py
Find: .semgrep.yml or .semgrep/
Find: knip.json or knip.ts
Find: ops/lighthouse/baseline/*.report.json   (a prior Lighthouse baseline)
```

Set these flags: `CAN_BUILD`, `CAN_TYPECHECK`, `CAN_LINT`, `CAN_TEST`, `HAS_SECURITY_SCANNER`,
`HAS_DEAD_CODE_TOOL`, `HAS_LIGHTHOUSE_BASELINE`, `HAS_AXE_PLAYWRIGHT`.

### 1c: Find the plan (with `--plan`, or auto-detect)

Unless `--no-criteria` is set, look for a plan in the conversation, then on disk:

```text
**/.planning/**/PLAN.md
**/plans/*.md
.devproto/evidence/plan.md
```

If you find one, extract the acceptance criteria (the `- [ ]` items).

### 1d: Report the scope

> **Review scope:** {N} files ({additions} additions, {deletions} deletions) at commit {sha}
> **Tooling:** types {yes/no} | lint {yes/no} | tests {yes/no} | security {yes/no}
> **Plan:** {found at path | not found, skipping criteria check}
> **Depth:** {quick | default | deep | audit}

---

## Step 2: Spawn analysis perspectives

**For `--quick`, run only the skeptic.**

While L1 static checks run (Step 2.5), start the review perspectives in parallel. Each looks at the
code from one angle. Collect their results after L1 finishes.

If your agent supports helper agents, run each perspective as a background helper, all in one
message. If it does not, run each perspective yourself as a separate pass after L1, reading only
the payload and that perspective's rules.

### 2a: Pick perspectives by depth

| Depth     | Shared perspectives                                                                                  | Inline perspectives                                    |
| --------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| `--quick` | skeptic (always runs)                                                                                | none                                                   |
| default   | skeptic, security, code-quality, test-coverage                                                       | plan-conformance (if a plan exists)                    |
| `--deep`  | skeptic, security, architecture, code-quality, test-coverage, performance                            | plan-conformance (if a plan exists), cross-file-impact |
| `--audit` | skeptic, security, architecture, code-quality, test-coverage, performance, accessibility, lighthouse | plan-conformance, cross-file-impact                    |

The **skeptic** always runs, at every depth. It is the quality conscience that keeps the review
honest about value and sloppiness. It always returns at least one finding.

The **code-quality** perspective enforces DRY (no duplication), KISS (no unjustified complexity),
YAGNI (no speculative generality), SOLID (no tangled responsibilities), no unnecessary elements,
and surgical diffs. Its findings name the principle broken, not just "this is messy."

Every perspective's focus list, exclusions, threshold and output format are in
`references/perspectives.md`.

### 2b: Prepare the context payload

Build a summary for the perspectives. This is what they get instead of the whole conversation:

```text
CONTEXT_PAYLOAD:
  - project_summary: "{language/framework}, {N} files changed, {additions}+ {deletions}-"
  - diff: "{full git diff from Step 1a}"
  - changed_files: "{changed file paths with full content}"
  - plan_summary: "{acceptance criteria, if found}"            (plan-conformance only)
  - adjacent_files: "{2 or 3 files next to the changes}"       (architecture only)
```

### 2c: Start them together

Start every selected perspective at once, using the templates in `references/perspectives.md`.
Registry perspectives use the shared template. Security adds the OWASP block. Plan-conformance and
cross-file-impact use their own inline templates. Use a fast, cheap model for the first pass if
your agent lets you choose.

### 2d: Go straight on to L1

Do NOT wait for the perspectives. Continue to Step 2.5 while they run.

---

## Step 2.5: LAYER 1, deterministic static checks

Run every available check in parallel. These are fast, repeatable and high-signal.

- **Types** (`CAN_TYPECHECK`): `npx tsc --noEmit`, `mypy .` or `pyright .`. Turn errors into
  findings.
- **Lint** (`CAN_LINT`): `npm run lint`, `npx eslint . --format json`,
  `ruff check . --output-format json` or `npx biome check .`. Separate auto-fixable issues from
  logic issues.
- **Build** (`CAN_BUILD`): `npm run build` or `pnpm build`.
- **Security** (`HAS_SECURITY_SCANNER`, `--deep` and up): `npx semgrep scan --config auto`,
  `npm audit --json` or `pip-audit`.
- **Dead code** (`HAS_DEAD_CODE_TOOL`, `--deep` and up): `npx knip --reporter compact` or
  `npx ts-prune`.

### L1 severity

| Severity     | Criteria                                                                     | Gate level |
| ------------ | ---------------------------------------------------------------------------- | ---------- |
| **critical** | Type errors, build failures, security vulnerabilities (high or critical)     | Hard gate  |
| **warn**     | Lint errors (not auto-fixable), security vulnerabilities (medium), dead code | Soft gate  |
| **info**     | Lint warnings (auto-fixable), style issues, minor dead code                  | Advisory   |

---

## Step 2.75: Collect perspective results

After L1 finishes, collect every perspective's output. If one is still running, wait. They
should finish in 30 to 60 seconds.

### Escalation check

```text
FOR each perspective result:
  IF result is empty or an error:
    Log: "{name}: failed, skipping"
  ELIF result is "No findings." AND the perspective always runs (skeptic):
    This should not happen. Retry with a stronger model.
  ELIF result is "No findings." AND the diff is 50 lines or more AND the perspective's area is touched:
    Retry with a stronger model, adding: "The first review found nothing. Look harder."
  ELIF the retry also returns "No findings.":
    Accept as clean. Note: "{name}: clean (checked 2x)"
  ELSE:
    Parse the findings into the shared finding pool.
    Tag each with its source: [perspective:{name}]
```

### Merge into the finding pool

Perspective findings join the same pool as L1 findings, tagged `[perspective:{name}]` so the
synthesis step can credit them. Each perspective maps to a layer:

| Perspective       | Layer      |
| ----------------- | ---------- |
| skeptic           | L3-Context |
| security          | L3-Context |
| architecture      | L3-Context |
| code-quality      | L2-Pattern |
| test-coverage     | L2-Pattern |
| performance       | L2-Pattern |
| accessibility     | L3-Context |
| lighthouse        | L2-Pattern |
| plan-conformance  | L3-Context |
| cross-file-impact | L3-Context |

---

## Step 3: LAYER 2, pattern analysis

**Note:** if perspectives ran, the code-quality, test-coverage and performance findings are
already in the pool. Still run the L2 checks below, but skip areas the perspectives already
covered, to avoid duplicates.

### 3a: Test coverage analysis

If `CAN_TEST`:

```bash
npm run test -- --coverage 2>&1
# or: pytest --cov --cov-report=json
```

Extract:

- **Overall coverage %.**
- **Coverage change** against the baseline: up or down?
- **Uncovered lines in changed files.** These are the gaps that matter.

Coverage findings:

- Coverage went down: **warn**.
- New code with 0% coverage: **warn**.
- A changed file under 50% coverage: **info**.

### 3b: Complexity analysis

Read the changed files. For each, check:

- **Nesting:** functions with deeply nested conditionals.
- **File length:** any file over 300 lines that could be split.
- **Function length:** any function over 50 lines.
- **Duplication:** repeated blocks across the changed files.

Flag issues only in CHANGED code, not in code that was already there.

### 3c: Code smell detection

Check the diff for common AI-generated code smells:

- Over-abstraction (premature patterns, needless factories or wrappers).
- Under-abstraction (copy-paste with small variations).
- Inconsistent error handling (some paths handle errors, others do not).
- Magic values with no named constant.
- Missing edge cases (null, empty, boundary values).
- Unsafe type assertions or casts.
- `console.log` or `print` left in production code.

---

## Step 4: LAYER 3, context review

**Note:** if perspectives ran, the security, architecture, skeptic, plan-conformance and
cross-file-impact findings are already in the pool. Focus on the gaps, especially the
acceptance criteria check (4a) if plan-conformance did not run.

### 4a: Plan acceptance criteria

If a plan was found and `--no-criteria` is not set, assess each criterion:

```text
### Criterion: {text}
**Verdict:** PASS | FAIL | PARTIAL | CANNOT VERIFY
**Evidence:** {file:line}
**Gap (if not PASS):** {what is missing}
```

| Verdict       | Meaning                                                      |
| ------------- | ------------------------------------------------------------ |
| PASS          | The code clearly satisfies it. Evidence is a real file:line. |
| FAIL          | Not implemented, or broken.                                  |
| PARTIAL       | Partly met. List the specific gaps.                          |
| CANNOT VERIFY | Needs a runtime test or human judgment.                      |

### 4b: Architecture conformance (default and `--deep`)

Compare the changed code with the codebase's patterns:

- Does new code follow the patterns in nearby files?
- Are imports consistent with the rest of the project?
- Does the file and function layout match the existing structure?
- Are naming conventions consistent?

**Rule:** flag only new deviations, not old issues. Name the pattern you expected by citing an
existing file that does it right.

### 4c: Cross-file impact (`--deep` only)

For each changed file:

- Who imports or references it? Search for the file name and its exports.
- Could the change break any of those consumers?
- Did an API contract change without matching consumer updates?

### 4d: Security review (`--deep` only)

For changed code that touches:

- User input: check for injection (SQL, XSS, command injection).
- Authentication or authorization: check for bypass paths.
- API endpoints: check for missing auth middleware.
- File operations: check for path traversal.
- Environment variables: check for hardcoded secrets.
- Crypto: check for weak algorithms.

---

## Step 4.4: Release control record (`--audit`, client or regulated releases)

Some releases carry a list of release controls (a QA sign-off sheet, a compliance checklist, a
client acceptance list). If the project has one, the machine layers answer only part of it. In
one real control set, the automated layers answered 11 of 35 controls. The other 24 needed a
named person and a date.

If the project keeps such a list (for example `docs/release-controls.md` or an `AUDIT-<release>.md`
file), refresh it for this release:

- For each control the review layers answered, fill in the result and point to the evidence.
- For each control that needs a person, fill in the owner and a date, or leave it in review.
- Count and paste into the findings: pass, in review, not applicable, and launch-critical
  blockers.

A launch-gate control that is still in review with no issue, owner, date and approver is a
**blocker**, not a note. If no list exists and the release needs one, say so as a finding and mark
the gate "manual".

---

## Step 4.5: LAYER 4, runtime verification (`--audit` only)

**Gate:** runs only when `--audit` is set AND `--no-runtime` is not.

Sub-checks, in order. The full procedure for each is in `references/runtime-checks.md`.

1. **4.5a.0 Audit-setup preflight.** Run the `/audit-setup` status check. If any tool is missing,
   emit ONE info finding that lists them and says how to install them.
2. **4.5a Detect the runtime.** Set `CAN_DEV_SERVER`, `HAS_PLAYWRIGHT`, `HAS_LIGHTHOUSE`,
   `HAS_AXE_PLAYWRIGHT`, `HAS_BROWSER_PROBE` and `DIFF_TOUCHES_UI`.
3. **4.5b Start the dev server.** Poll for up to 30 seconds. On failure: critical finding, skip
   the rest of L4.
4. **4.5c Smoke tests.** Run the Playwright smoke project. Fall back to a browser page-load check.
5. **4.5c.5 Browser UI probe.** Runs when the diff touches UI and a live target exists. Take an
   accessibility-tree snapshot and a screenshot per route. Budget: 15 seconds per route.
6. **4.5d API endpoint smoke tests.** Call each detected route. 5xx is critical. 4xx on an
   unprotected route is warn.
7. **4.5e Accessibility audit.** axe-core through Playwright (specs tagged `@a11y`). Every
   finding names the WCAG criterion and the DOM selector.
8. **4.5f Lighthouse audit.** Median of 3 runs per route. Prefer a preview deployment URL over a
   local production build. NEVER run it against the dev server. Floors are in the reference file.
9. **4.5g Bundle analysis.** A chunk over 500 KB is critical. Over 250 KB is warn.
10. **4.5h Dependency vulnerability scan.** `npm audit --json` (or the language's equivalent).
    Critical and high become findings.
11. **4.5i Project domain audits.** Run any `ops/audit/*/run.sh` hooks. Parse their
    `AUDIT_RESULT=` output line.
12. **4.5k to 4.5v Area cross-checks.** Twelve checklists (foundation, governance ledger, data
    and migrations, security posture, release and deploy, implementation spec, quality and test,
    observability, maintenance, design system, documentation, research dossier). Run each that
    applies. If your team has a guard script for an area, run it and fold in its findings;
    otherwise check the listed items by hand. All are in the reference file.
13. **4.5j Cleanup.** Stop the dev server. Remove temporary files (keep them with `--audit`).

---

## Step 4.75: LAYER 5, regression testing (`--regression`, or `--audit` with `.promptfoo/`)

**Skip if** `--regression` is not set AND (`--audit` is not set OR no `.promptfoo/` folder exists).

- Find `.promptfoo/golden/*.yaml`. If none, skip with a note.
- Run `npx promptfoo eval --config .promptfoo/promptfooconfig.yaml --output <temp>/regression-results.json --no-cache`.
  Timeout: 120 seconds.
- Parse PASS or FAIL per test case. Tag every finding `[L5-Regression]`.
- Severity: more than 50% failing is critical, 1 to 50% is warn, all passing with a lower score
  is info.

Full procedure: `references/runtime-checks.md` (section "Layer 5").

---

## Step 5: Synthesize findings

### 5a: Remove duplicates

Remove the same finding reported by more than one layer (for example a type error caught by both
`tsc` and a perspective).

### 5b: Prioritize

Sort by severity: critical, then warn, then info. Within a severity, sort by confidence: high,
medium, low.

### 5c: Cap the list

Apply the finding cap (default 12, change with `--cap N`). If there are more findings than the cap:

- ALWAYS include every critical finding. The cap never hides a critical.
- Fill the remaining slots with the highest-confidence warn and info findings.
- Add: "{N} more findings omitted. Run with `--cap 0` to see all."

### 5d: Structure each finding

Use the finding format in `references/output-templates.md` (section "Finding structure"). Key rules:
quote the evidence or set confidence to "low"; every recommendation is a concrete action; include
the code fix when it is obvious and under 5 lines.

---

## Step 6: Deliver the report

All output templates are in `references/output-templates.md`.

### Summary block

Render the tree-style header: scope, commit, plan, depth, layer results, perspective counts,
finding counts, gate and verdict.

### Verdict

Pick the verdict with the table in `references/output-templates.md` (section "Verdicts"). Summary:
SHIP IT (nothing open), FIX THEN SHIP (minor, few), NEEDS WORK (many warnings or failed
criteria), BLOCKED (any critical). In audit mode also READY TO SHIP and SHIP WITH CAVEATS.

### Findings

List every finding in the Step 5d structure. Leave an "Outcome" line on each for the builder to
fill: fixed, rejected with reason, or deferred with owner.

### Acceptance criteria (if a plan exists)

List each criterion with its PASS, FAIL, PARTIAL or CANNOT VERIFY verdict and the gap.

### Suggested next steps

- **SHIP IT:** "Clean implementation. Next: `/simplify` for a cleanup pass, then `/commit`, then
  `/ship` to push and open a pull request."
- **FIX THEN SHIP:** "Minor issues. Auto-fixable items: run `{lint fix command}`. Then re-check
  with `/review-stack --quick`."
- **NEEDS WORK:** "{N} issues need manual attention. Top priority: {top 3}. Fix these and re-run
  `/review-stack`."
- **BLOCKED:** "Cannot ship. {critical_count} blocking issue(s): {list}. These must be fixed
  first."

### Save the report

Write the whole report to `.devproto/evidence/review.md` and record the checklist row as described
in "Checklist row" above.

### Visual page (optional, never blocks)

If your team has a tool that renders a findings report as a web page, run it on the report. The
Markdown report stays the source of truth. Skip on failure.

---

## Step 6.5: Remediation report (`--audit` only)

**Gate:** generated only when `--audit` is set.

After the verification report, produce a prioritized remediation plan: 4 priority groups
(BLOCKERS, HIGH, MEDIUM, LOW), an AUTO-FIX MANIFEST of commands to run in order, and a
GOING-PUBLIC READINESS CHECKLIST.

Full template, effort estimates and priority mapping: `references/output-templates.md` (section
"Remediation plan").

---

## Step 7: JSON output (`--json`)

If `--json` is set, output the findings as structured JSON instead of Markdown. The schema and an
example are in `references/output-templates.md` (section "JSON output").

---

## Step 7.5: Persist the findings (always)

At the end of **every** run, including clean runs, write the structured finding pool (the Step 7 JSON
shape: verdict plus findings) to `.devproto/review/latest-findings.json`.

This file is current state. Overwrite it each run. Never append. It lets the next session, and
any tool your team uses to rank the next piece of work, see this project's real open findings
without anyone copying them by hand. Tag each
finding with the area its ID prefix points to (for example `mig-` is data and migrations, `sec-`
is security, `rel-` is release). A clean run writes `findings: []` and its current commit,
gate and verdict, clearing stale issues.

---

## Agent isolation

This skill runs apart from the building context. Three ways:

- As a helper agent: give it the instruction "Run /review-stack --branch --plan <path> and return
  the full verification report." Use a stronger model, or a different model family, than the one
  that wrote the code.
- As a fresh session: start a new session in the repository and run
  `/review-stack --branch --plan .planning/<phase>/PLAN.md`.
- As part of `/build-stack` Step 6.5, which passes the plan path and scope for you.

Invocation examples: `references/output-templates.md` (section "Agent isolation").

---

## Graceful degradation

| Component              | If missing                               | Fallback                                                                                                                                                  |
| ---------------------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TypeScript             | No `tsconfig.json`                       | Skip the type check. Note it in the report                                                                                                                |
| Linter                 | No config                                | Skip lint. Note it in the report                                                                                                                          |
| Test suite             | No tests                                 | Skip coverage. Flag it as a finding ("no test coverage")                                                                                                  |
| Security scanner       | No semgrep                               | AI security review only (L3)                                                                                                                              |
| Dead code tool         | No knip                                  | Skip. Note it in the report                                                                                                                               |
| Plan                   | No plan found                            | Skip the criteria check. Review code quality only                                                                                                         |
| Git                    | Not a repository                         | Review the named files without diff context                                                                                                               |
| Dev server             | No `dev` script                          | Skip local L4. Try a preview URL if one is set. Otherwise note "no runtime target, L4 skipped"                                                            |
| Playwright             | Not installed                            | Use any browser tool for a page-load smoke check. Skip structured end-to-end tests                                                                        |
| `@axe-core/playwright` | Not installed                            | The Lighthouse accessibility score (4.5f) and the accessibility perspective cover the gap. Emit info: "run `/audit-setup` to add axe"                     |
| Lighthouse CLI         | `npx --no-install lighthouse` fails      | Skip 4.5f. Emit info: "run `/audit-setup` to add Lighthouse". Still run axe, bundle and npm audit                                                         |
| Lighthouse baseline    | No reports in `ops/lighthouse/baseline/` | Absolute floors only, no regression compare. Emit info: "run `/audit-setup` to capture a baseline". Write a baseline ONLY with `--audit --write-baseline` |
| Preview URL            | None for this branch                     | Fall back to a local production build. If that fails too, skip 4.5f                                                                                       |
| Bundle analyzer        | Not configured                           | Read chunk sizes from the build output only                                                                                                               |
| npm audit              | npm not available                        | Skip. Note it in the report                                                                                                                               |
| Foundation lock        | No `.planning/*/foundation.yaml`         | Skip 4.5k. Exception: if the build looks new or multi-tenant, emit the `ff-no-lock` finding                                                               |
| Helper agents          | Not supported                            | Run each perspective yourself as a separate pass, one lens at a time                                                                                      |
| Checklist tool         | `/development-protocol` not installed    | Still write `.devproto/evidence/review.md` and report in chat                                                                                             |

**Minimum viable run:** read the changed files and analyze them. Everything else is enhancement.

---

## Depth tiers

| Tier           | L1 static       | L2 pattern         | L3 context              | L4 runtime                                                                           | L5 regression           | Perspectives                                        | Remediation       | Est. time    |
| -------------- | --------------- | ------------------ | ----------------------- | ------------------------------------------------------------------------------------ | ----------------------- | --------------------------------------------------- | ----------------- | ------------ |
| `--quick`      | All available   | Skip               | Skip                    | Skip                                                                                 | Skip                    | skeptic only                                        | No                | 15 to 30 s   |
| default        | All available   | Complexity, smells | Criteria, conformance   | Skip                                                                                 | Skip                    | skeptic, security, code-quality, test-coverage      | No                | 2 to 5 min   |
| `--deep`       | All + dead code | Full + duplication | All + cross-file impact | Skip                                                                                 | Skip                    | All 6 shared + plan-conformance + cross-file-impact | No                | 5 to 15 min  |
| `--audit`      | All + dead code | Full + duplication | All + cross-file impact | Full (smoke, axe, Lighthouse with baseline compare, bundle, npm audit, cross-checks) | Auto (if `.promptfoo/`) | All 8 shared + plan-conformance + cross-file-impact | Yes (full report) | 10 to 25 min |
| `--regression` | Skip            | Skip               | Skip                    | Skip                                                                                 | Full                    | None                                                | No                | 1 to 3 min   |

For `--deep` and `--audit`, use the highest reasoning effort your agent offers. For the other
tiers, the default high effort is enough.
