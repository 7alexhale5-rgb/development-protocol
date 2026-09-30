# Layer 4 (runtime checks) and Layer 5 (regression tests)

Loaded by Step 4.5 and Step 4.75 of `SKILL.md`. Runs only with `--audit` (Layer 4) or
`--regression` (Layer 5).

`ART_DIR` below is a temporary folder for this run, for example
`ART_DIR="$(mktemp -d)/review-stack"`. Keep it with `--audit` so the remediation plan can point
at its files.

## Contents

1. 4.5a.0 Audit-setup preflight
2. 4.5a Detect the runtime
3. 4.5b Start the dev server
4. 4.5c Smoke tests
5. 4.5c.5 Browser UI probe
6. 4.5d API endpoint smoke tests
7. 4.5e Accessibility audit
8. 4.5f Lighthouse audit
9. 4.5g Bundle analysis
10. 4.5h Dependency vulnerability scan
11. 4.5i Project domain audits
12. 4.5k to 4.5v Area cross-checks
13. 4.5j Cleanup
14. Layer 4 severity
15. Layer 5: regression tests
16. Starter axe spec

---

## 1. Step 4.5a.0: Audit-setup preflight (one combined finding)

Before probing each tool, run the `/audit-setup` status check (its status script, if it ships
one). This turns missing tooling into ONE actionable finding, instead of every later step
emitting its own partial warning. This skill installs nothing. It only tells the user the one way
to fix the gaps.

Count the tools reported missing. If any of Lighthouse, axe, the axe spec, the bundle analyzer,
knip or the Lighthouse baseline is missing, emit a single **info** finding at the top of the L4
section:

> **Audit tooling incomplete.** {N} tools missing: {list}. Run `/audit-setup` to install what
> this project's stack needs (it detects pnpm, yarn, bun or npm). The audit still runs, with
> reduced coverage. See the notes on each step below.

If everything is present, emit nothing.

The later steps keep their own presence probes as a safety net, in case the status check itself
fails.

---

## 2. Step 4.5a: Detect the runtime

Probe in parallel:

```text
Read: package.json (scripts.dev, scripts.start, devDependencies for lighthouse,
      @axe-core/playwright, a bundle analyzer)
Find: playwright.config.{ts,js}
Find: next.config.{ts,js,mjs} or vite.config.{ts,js}
Find: ops/lighthouse/baseline/*.report.json   (a prior baseline for regression compare)
Find: .lighthouserc.{json,js,yml} or lighthouserc.{json,js,yml}
Check: a browser tool your agent can drive (a browser automation CLI, a browser MCP, Playwright)
```

Set these flags:

- `CAN_DEV_SERVER`: a `dev` or `start` script exists.
- `HAS_PLAYWRIGHT`: a Playwright config exists.
- `HAS_LIGHTHOUSE`: `npx --no-install lighthouse --version` works.
- `HAS_LH_BASELINE`: prior baseline reports exist.
- `HAS_AXE_PLAYWRIGHT`: `@axe-core/playwright` is in devDependencies.
- `HAS_BROWSER_PROBE`: your agent can open a page and read its accessibility tree.

Check whether the diff touches UI:

Use the exact selected review surface to form a NUL-delimited changed-path list:
`git diff --name-only -z HEAD` plus `git ls-files -z --others --exclude-standard`
for default uncommitted scope, `git diff --cached --name-only -z` for staged scope,
`git diff --name-only -z "$BASE_REF"...HEAD` for branch scope, or explicit files.
Set `DIFF_TOUCHES_UI=1` if any selected path is a UI component or page. Do not
substitute a committed branch diff for uncommitted review scope.

Pure API or backend changes leave `DIFF_TOUCHES_UI` unset.

---

## 3. Step 4.5b: Start the dev server

If `CAN_DEV_SERVER`:

```bash
npm run dev &
DEV_PID=$!
# Poll the port (3000 or the detected one) for up to 30 seconds
for i in $(seq 1 30); do curl -s http://localhost:3000 > /dev/null 2>&1 && break; sleep 1; done
```

If the server does not answer within 30 seconds: finding "Dev server failed to start" [critical].
Skip the rest of L4.

---

## 4. Step 4.5c: Smoke tests

If `HAS_PLAYWRIGHT`:

```bash
npx playwright test --project=smoke 2>&1
```

Parse the passed, failed and skipped counts. Each failure becomes a finding, with its screenshot
path.

If there is no Playwright but the dev server is running, use any browser tool you have:

- Open `localhost:{port}`.
- Check that the page loads, there are no console errors, and the key controls are present.
- Take a screenshot as evidence.

---

## 5. Step 4.5c.5: Browser UI probe

**Purpose:** a fast accessibility-tree check that runs on every UI-touching diff with a live
target, whether or not a Playwright spec exists for the changed flow. It is the machine version
of "open the app and look at it", which a human reviewer would otherwise do by hand.

**Runs only when all hold:**

- `DIFF_TOUCHES_UI=1`.
- `HAS_BROWSER_PROBE=1`.
- A live target resolves, in this order:
  1. the `--target-url <url>` flag,
  2. a preview deployment URL for this branch (an env var your host sets, or, optionally,
     `gh pr view --json` if your host posts previews on pull requests),
  3. the local dev server started in 4.5b.

If no target resolves, emit an **info** finding: "Browser UI probe skipped: no live target. Pass
`--target-url` or start the dev server." Then skip this step.

**Probe, per route:**

1. Open the target. If it fails to open, stop the probe for this route.
2. Take an unfiltered accessibility-tree snapshot including headings and static text. Save it to
   `$ART_DIR/snapshot-<route>.txt`. Preserve the heading and error-text evidence; do not filter it to interactive elements.
3. Take a screenshot to `$ART_DIR/probe-<route>.png`.
4. Golden-path assertion: the tree must contain at least one heading.
5. Error sweep: look for visible "error", "exception" or "stack trace" text in the tree.
6. Close the page.

**Time budget:** 15 seconds per route. If a route takes longer, stop it and emit a **warn**
finding: "Browser probe slow (over 15 s): server likely under load or hanging."

**Routes:** use the same list as 4.5f (Lighthouse): `/` plus any changed page routes from the
diff, capped at 5. Do not probe API-only routes.

**Attach to the L4 section:** the snapshot and screenshot for each route, as info-level evidence,
even on a pass. They give the next run a visual baseline.

| Condition                                          | Severity     | Finding                                                                               |
| -------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------- |
| Open fails (network error, 5xx, unreachable)       | **critical** | "Live target unreachable from the probe: runtime broken or environment misconfigured" |
| No heading in the tree                             | **critical** | "Page rendered with no heading: likely a client crash, blank shell or auth wall"      |
| Visible "error", "exception" or "stack trace" text | **warn**     | "Error-shaped text visible to users: confirm it is intended or file it as a bug"      |
| Probe over 15 s                                    | **warn**     | "Server slow to respond: performance concern, also see 4.5f"                          |
| All checks pass                                    | **info**     | "Browser probe clean: heading visible, no error text; screenshot at `<path>`"         |

**Why this is separate from 4.5c:** 4.5c runs the Playwright suite, so it catches only what a
spec already covers. This probe runs on every UI-touching diff regardless of test coverage. It is
a 5-second sanity check, not a replacement for real end-to-end tests.

**Skips (logged as info, not findings):**

- `DIFF_TOUCHES_UI` unset: "Browser probe skipped: no UI files in diff."
- No browser tool: "Browser probe skipped: no browser tool available."

---

## 6. Step 4.5d: API endpoint smoke tests

If route handlers exist in the codebase, call each one:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:{port}/api/{route}
```

- 5xx: finding [critical].
- 4xx on a route that is not meant to be protected: finding [warn].

---

## 7. Step 4.5e: Accessibility audit (runtime)

Preferred: **axe-core through Playwright**, one axe run per key route, in specs tagged `@a11y`.
A starter spec is in section 16.

If `HAS_AXE_PLAYWRIGHT`:

```bash
# Prefer a dedicated project if one exists, else tagged specs.
npx playwright test --project=a11y 2>&1 \
  || npx playwright test --grep @a11y 2>&1
```

- axe is installed but no `@a11y` specs exist: emit **info**, "axe installed but no `@a11y` specs
  found. Add one per key route; see the starter spec in the review-stack references."
- Playwright exists but axe is not installed: emit **info** recommending
  `npm i -D @axe-core/playwright`, and skip this step. Lighthouse (4.5f) still gives an
  accessibility score, so the review is not blind.
- Neither: skip and note it.

Parse `violations[]` into findings:

- `impact: "critical"` or `"serious"`: **warn** (blocking with `--gate hard`).
- `impact: "moderate"`: **info**.
- `impact: "minor"`: dropped unless `--deep`.

Every axe finding MUST include the WCAG criterion ID and the DOM selector axe reported.

---

## 8. Step 4.5f: Lighthouse audit (runtime)

**Purpose:** black-box scores for performance, accessibility, best practices and SEO on live
routes, compared against a baseline when one exists.

**Target, in priority order:**

1. **A preview deployment URL** for this branch, if your host makes one. This is preferred. It
   matches production's edge, cache and image behavior. Running Lighthouse CI only on changed
   pages against previews is a widely used pattern (see
   https://www.bswanson.dev/blog/run-lighthouse-ci-on-changed-pages/).
2. **A local production build**, when there is no preview:
   Build first, then allocate a free `LH_PORT` distinct from the dev server port.
   Verify the port is free immediately before startup; start `PORT="$LH_PORT" npm start`
   in the background and retain its PID. Require that process to remain alive and own
   the listening port, and poll its HTTP readiness. A bind failure blocks this audit.
   Set `VERIFIED_PRODUCTION_URL` only after those checks. Never fall back to the dev port.
3. **Skip with a note** if neither is available. Emit an info finding and skip Lighthouse.

**Precondition:**

```bash
npx --no-install lighthouse --version 2>/dev/null
# Missing and not opted in: emit an info finding and skip.
# No baseline: run with absolute floors only, no regression compare.
```

**Routes:**

- If baseline reports exist in `ops/lighthouse/baseline/`, audit the same routes. That keeps the
  comparison meaningful.
- Otherwise: `/`, plus routes matching changed page files in the diff, capped at 5 routes.

**Noise control:** run each route **3 times** and use the **median** score per category. This is
Lighthouse CI's own recommendation (`numberOfRuns: 3`, see
https://github.com/GoogleChrome/lighthouse-ci/blob/main/docs/configuration.md).

```bash
TARGET_URL="${PREVIEW_URL:-${VERIFIED_PRODUCTION_URL:?production server was not verified}}"
OUT_DIR="$ART_DIR/lighthouse"
mkdir -p "$OUT_DIR"
for route in $ROUTES; do
  slug=$(echo "$route" | sed 's|/|-|g; s|^-||; s|^$|home|')
  for run in 1 2 3; do
    npx --no-install lighthouse "$TARGET_URL$route" \
      --output=json \
      --output-path="$OUT_DIR/$slug.$run.json" \
      --chrome-flags="--headless=new --no-sandbox" \
      --quiet \
      --only-categories=performance,accessibility,best-practices,seo
      # Add --preset=desktop ONLY for desktop-only sites. Mobile is Lighthouse's default.
  done
done
```

Parse the scores and take the median of the 3 runs per route per category.

**Floors (blocking with `--gate hard`, warn otherwise):**

| Category       | Hard floor  | Ideal       |
| -------------- | ----------- | ----------- |
| Performance    | 80          | 90 or more  |
| Accessibility  | 90          | 98 or more  |
| Best Practices | 90          | 96 or more  |
| SEO            | 85          | 95 or more  |
| CLS (metric)   | under 0.1   | under 0.05  |
| LCP (metric)   | under 4.0 s | under 2.5 s |

**Baseline regression (when `HAS_LH_BASELINE`):** for each route and category,
`delta = current median - baseline`.

- `delta` of -10 or worse: **critical** (significant regression).
- `delta` of -5 or worse: **warn** (noticeable, may be noise).
- `delta` of -3 or worse: **info** (watch list).
- `delta` of 0 or better: no finding.

For LCP and CLS: any route metric past its hard floor in this run is **warn**, even if the
baseline was already past it.

**Finding format:**

```text
- **Lighthouse: <route> <category> regressed <delta>** [warn]
- **File:** ops/lighthouse/baseline/<slug>.report.json (baseline) vs live
- **Evidence:** current median {score}, baseline {score}, delta {delta}
- **Metric:** {Core Web Vital if relevant: LCP, CLS, TBT, FCP}
- **Impact:** {the effect on users, for example "LCP up 1.2 s on mobile, past the 4 s floor"}
- **Fix:** {the likely cause: a new dependency, an unoptimized image, a new client component;
  hand it to the lighthouse perspective for a code-level diagnosis if unclear}
```

**Cleanup:** remove `OUT_DIR` unless `--audit`. With `--audit`, keep it for the remediation plan.

**Notes:**

- Lighthouse 13.x needs Node 22.19 or newer. On older Node, install Lighthouse 12.6.1 locally, or
  skip.
- Do not install Lighthouse globally from inside this skill. Require `npx --no-install`, so the
  project opts in on purpose.
- Only `--audit --write-baseline` may write new baseline files.
- A median of 3 runs catches most single-run noise. Use 5 runs (`LH_RUNS=5`) for
  performance-critical audits.

---

## 9. Step 4.5g: Bundle analysis

```bash
npm run build 2>&1
```

Parse chunk sizes from the output:

- Any chunk over 500 KB: [critical].
- Any chunk over 250 KB: [warn].

With a bundle analyzer configured (for example `ANALYZE=true npm run build` for Next.js), use its
output instead.

---

## 10. Step 4.5h: Dependency vulnerability scan

```bash
npm audit --json 2>&1
# Python: pip-audit --format json
```

Parse the counts: critical, high, moderate, low.

- Each critical: [critical].
- Each high: [warn].

---

## 11. Step 4.5i: Project domain audits

**Purpose:** some projects have quality bars of their own (extraction accuracy, ML eval pass
rates, data-pipeline integrity, row-level security checks). They drop a hook script at
`ops/audit/<name>/run.sh`. This step finds those hooks, runs them in parallel, and turns their
verdicts into findings. It is convention over coupling: review-stack does not need to know what
each audit does, only its stable output contract.

**Find hooks:**

```bash
PROJECT_AUDITS=$(find ops/audit -mindepth 2 -maxdepth 2 -name run.sh -type f 2>/dev/null | sort)
```

None found: emit info "Project domain audits skipped: no ops/audit/*/run.sh hooks" and continue.

**Output contract every hook MUST print on success:**

```text
AUDIT_VERDICT=<GREEN|YELLOW|RED>
AUDIT_REPORT=<absolute path to a markdown file>
AUDIT_JSON=<absolute path to a json file>
AUDIT_RESULT=<one-line JSON: {name, verdict, bars:[{bar,value,target,verdict,note}], artifacts:{csv?,json,md}}>
```

Exit code: 0 if passable (GREEN or YELLOW), non-zero if RED.

**Run them in parallel:**

```bash
pids=(); names=()
for hook in "${PROJECT_AUDITS[@]}"; do
  name=$(basename "$(dirname "$hook")")
  bash "$hook" > "$ART_DIR/audit-$name.stdout" 2> "$ART_DIR/audit-$name.stderr" &
  pids+=("$!"); names+=("$name")
done
for index in "${!pids[@]}"; do
  code=0
  wait "${pids[$index]}" || code=$?
  printf '%s\n' "$code" > "$ART_DIR/audit-${names[$index]}.exit"
done
```

**Parse and classify:** a missing or nonzero exit receipt is a failure regardless of GREEN
stdout. First check each exit receipt, then read each stdout file, take the `AUDIT_RESULT=` line, and parse its JSON.
Emit one summary finding per audit plus one finding per failed bar.

| Outcome                                 | Severity     | Finding                                                                         |
| --------------------------------------- | ------------ | ------------------------------------------------------------------------------- |
| `verdict=RED`                           | **critical** | "<name> audit RED: <N> bar(s) failing: <failing bar names>". Link AUDIT_REPORT. |
| `verdict=YELLOW`                        | **warn**     | "<name> audit YELLOW: 1 bar failing: <bar>". Link AUDIT_REPORT.                 |
| `verdict=GREEN`                         | **info**     | "<name> audit GREEN". Link AUDIT_REPORT only with `--audit`.                    |
| Hook crashed, or no `AUDIT_RESULT` line | **critical** | "<name> audit hook gave no stable AUDIT_RESULT line: see its stderr file"       |
| Hook stopped on a missing dependency    | **warn**     | "<name> audit hook blocked: <last stderr lines>". A remediation candidate.      |

**Per failed bar** (each `bars[].verdict == FAIL`):

```text
- **<name>.<bar> FAIL: <value> vs target <target>** [warn|critical]
- **Source:** AUDIT_RESULT.bars[<bar>]
- **Note:** <bar.note>
- **Artifact:** AUDIT_REPORT
- **Severity:** critical if the audit is RED, warn if YELLOW
```

**Why this sits in L4, not L1:** domain audits run against the project's real data and tools.
They can call other programs, read stored artifacts and compute statistics over past runs. L1 is
deterministic and static only.

**The project's side of the deal:** each hook is read-only on shared data, gives the same result
on the same input, and prints the contract above. The hook owns its dependencies. Review-stack
does not install them.

---

## 12. Steps 4.5k to 4.5v: Area cross-checks

Twelve areas of engineering risk. For each area that applies to this change, do one of two
things:

- If your team has a guard script for the area, run it with JSON output and fold each finding
  into the pool at the severity it reports.
- Otherwise, check the items below by hand, reading the named files. Emit each failed item as a
  finding with the given ID and severity.

A finding ID's prefix names its area (`ff-`, `gov-`, `mig-`, `sec-`, `rel-`, `impl-`, `q-`,
`obs-`, `debt-`, `ds-`, `doc-`, `res-`). Step 7.5 uses that prefix to tag the finding's area.

These are static checks of wiring and records. Live proof (a real rollout, a real restore)
stays with the runtime steps above.

### 4.5k Foundation-first prerequisites

Runs when a foundation lock file exists (for example `.planning/*/foundation.yaml`), which
declares the skeleton a new product must have before features (auth, tenancy, data model,
deploy rails).

- `ff-no-lock` [critical]: the build looks new or multi-tenant, but there is no foundation lock.
  The pathway was skipped.
- `ff-ledger-unreadable` [critical]: the lock or its ledger cannot be parsed.
- `ff-prereq-*` [warn]: a declared skeleton prerequisite is not met.
- `ff-scope-drift` [warn]: the build went beyond the lock's scope without an amendment.
- `ff-profile-underdeclared` [warn]: the lock declares a lighter risk profile than the code shows
  (for example "internal tool" while handling payments).
- `ff-amendment-churn` [info]: many amendments in a short time. The plan may be unstable.

### 4.5u Governance ledger

The shared record every area reports to: which commit shipped when, what failed, how fast it was
fixed (the DORA delivery metrics: deploy frequency, lead time, change failure rate, time to
restore).

- `gov-ledger-unreadable` [critical]: the ledger exists but cannot be parsed.
- `gov-ledger-incomplete`, `gov-ledger-sha-not-in-git` [warn]: entries are missing fields, or
  name commits that do not exist.
- `gov-cfr-high`, `gov-mttr-high` [warn]: change failure rate or time to restore is past the
  team's target.
- `gov-incidents-unlinked` [warn]: incidents are not linked to the change that caused them.
- `gov-ai-survival-low` [warn]: much AI-written code is rewritten or reverted soon after merge.
- `gov-no-ledger`, `gov-no-deploy-ledger`, `gov-ai-attribution-gap`, `gov-no-drift-detection`,
  `gov-maturity-below-l3` [info]: the record is missing or thin.

### 4.5l Data and migrations

Runs when the diff touches migration files (`**/migrations/**.sql`, `supabase/migrations`,
`db/migrate` and similar).

- Critical: `mig-drop-*` (drops a table or column), `mig-truncate`, `mig-delete-no-where`,
  `mig-delete-where-true`.
- Warn: `mig-alter-type` (column type change), `mig-rename`, `mig-notnull-no-default` (adds
  NOT NULL with no default on a live table), `mig-dropindex-no-concurrent`, `mig-rewrite-lock`
  (a change that rewrites or locks a large table), `mig-coupled-expand-contract` (adding and
  removing in one step instead of expand, migrate, contract), `mig-no-down` (no rollback),
  `mig-no-data-quality-check`.
- Info: `mig-backfill-unbatched`, `mig-backfill-offset` (paging by OFFSET, slow on big tables),
  `mig-batch-too-large`, `mig-backfill-not-idempotent` (unsafe to re-run),
  `mig-constraint-no-notvalid` (adds a constraint without `NOT VALID` first).

A write-time hook can block the criticals as they are written. This step is the check at rest.

### 4.5m Security posture

- Critical: `sec-rls-disabled` (row-level security off on a table holding user data),
  `sec-secret-committed`, `sec-auth-bypass-literal` (a hardcoded bypass, such as a fixed admin
  user name or a test flag left on).
- Warn: missing authorization or authentication checks, IDOR (reading another user's record by
  changing an ID), injection, XSS, unsafe deserialization, weak crypto, missing TLS.
- Info or warn by risk profile: supply-chain gaps (unpinned dependencies, no lockfile), no threat
  model, missing security middleware.

### 4.5n Release and deploy

Check release safety wiring. If you can ask the host which commit is in production, compare it
with the ledger (give it at most 10 seconds; skip offline).

- `rel-no-deploy-rails`: no defined deploy path.
- Feature flags: risky changes are behind a flag, with a kill switch, off by default.
- Canary or staged rollout, with an abort condition.
- Post-deploy verification: a check that runs after each deploy.
- Error tracking wired, and releases tagged with their commit.
- Rollback plan, and forward-only migrations when rollback is not possible.
- The deploy is recorded in the governance ledger.

### 4.5o Implementation spec

- `impl-no-spec`: no spec or plan for a non-trivial change.
- `impl-spec-no-acceptance`: the spec has no acceptance criteria.
- `impl-spec-drift`: the code does something the spec does not describe.
- `impl-change-radius`: the change touches far more files or modules than the spec implies.
- `impl-wide-radius-acknowledged` [info]: a wide change the spec explicitly accepts.

Also confirm the build ran its checks before stopping, stopped after repeated failures instead of
looping, and kept the plan it was given.

### 4.5p Quality and tests

- `q-no-coverage-gate`, `q-coverage-gate-empty`, `q-coverage-gate-low`: no enforced coverage
  floor in CI, or a floor that is empty or set too low.
- `q-no-mutation-testing` [info]: nothing checks that tests fail when the code is broken.
- Regression and golden-set gaps: no fixed set of expected outputs for critical behavior.
- Flaky tests: no quarantine process, or known flaky tests still gating merges.
- Test pyramid shape: almost all end-to-end with few unit tests, or the reverse with no
  integration tests.

### 4.5q Observability and reliability

- Instrumentation is initialized at startup, with a service name, following OpenTelemetry naming
  conventions if the project uses them.
- Service level objectives (SLOs, the reliability targets) exist and have the right shape.
- An error budget policy says what happens when the budget is spent, with multi-window,
  multi-burn-rate alerts.
- Alerts fire on user-facing symptoms, not internal causes, and each links a runbook.
- Incident write-ups exist and are blameless.

### 4.5r Maintenance and tech debt

- Dependency updates are automated (for example Dependabot or Renovate).
- Lockfiles are committed and installs are reproducible.
- Dependency staleness (how far behind current releases, sometimes counted as "libyears").
- A vulnerability scan runs regularly.
- Dead-code and debt tooling exists.
- License and SBOM (software bill of materials) checks exist where required.
- Debt markers (`TODO`, `FIXME`, `HACK`) are counted, not growing unowned.
- Hotspots: files that change often and are complex, from git history.

### 4.5s Design system

- Raw values in components where tokens exist (hex colors, pixel sizes).
- Tokens follow the W3C design tokens format (DTCG) if the project uses tokens.
- Primitive tokens used directly in components where semantic tokens exist.
- Component API stability tooling.
- An accessibility gate in CI.
- Visual regression tests, including every supported theme.
- Story coverage for components (for example Storybook), and generated docs kept tidy.

Run alongside a UI critique (`/design-stack --critique`) and any design-token lint the project
has.

### 4.5t Documentation and knowledge

- A README exists and docs live next to the code.
- Docs match the code (no documented flags or endpoints that no longer exist).
- Architecture decision records (ADRs) exist for major choices, follow a standard template, and
  are not stale or written long after the fact.
- Runbooks are usable by someone who did not write them.
- API contracts (for example OpenAPI files) are valid and versioned.
- Docs cover the four needs: tutorials, how-to guides, reference and explanation.
- Links resolve, and contract tests exist where an API is public.

### 4.5v Research and context

Checks the planning dossier behind the change, if the work needed research.

- A capability map, a source list, and a register of claims with their sources.
- Coverage across source types (code, docs, primary sources, the running system).
- Contradictions between sources are resolved or noted.
- Unknowns are listed and classified, not hidden.
- A short card for each engineering area above, saying whether it applies.
- A validation note stating what was checked and how.

Live source retrieval is `/research-stack`'s job. This step only checks that the dossier exists
and is complete.

---

## 13. Step 4.5j: Cleanup

```bash
kill $DEV_PID 2>/dev/null
rm -rf "$OUT_DIR" 2>/dev/null   # Lighthouse runs (keep with --audit)
```

---

## 14. Layer 4 severity

| Severity     | Criteria                                                                                                                                                                                        |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **critical** | Dev server crash, Playwright test failure, 5xx on an API route, critical dependency vulnerability, Lighthouse performance under 80 or accessibility under 90, LCP over 4 s, axe impact critical |
| **warn**     | Console errors, axe impact serious, a bundle chunk over 250 KB, high dependency vulnerability, a Lighthouse category down 5 or more from baseline, CLS over 0.1                                 |
| **info**     | axe impact moderate, bundle warnings, moderate dependency vulnerability, a Lighthouse category down 3 or more from baseline                                                                     |

---

## 15. Layer 5: regression tests

**Skip if** `--regression` is not set AND (`--audit` is not set OR no `.promptfoo/` folder
exists).

promptfoo is a free, open-source tool that runs a fixed set of test prompts and checks the
outputs. It fits projects with AI features whose behavior can drift.

### 5a: Find golden datasets

```text
Find: .promptfoo/golden/*.yaml
```

None found: skip L5 with the note "No golden datasets. See `npx promptfoo init` to set one up."

### 5b: Run the eval

```bash
npx promptfoo eval --config .promptfoo/promptfooconfig.yaml \
  --output "$ART_DIR/regression-results.json" \
  --no-cache 2>&1
```

Timeout: 120 seconds. If promptfoo cannot run, skip L5 with a note.

### 5c: Parse results

Read the results file. For each test case:

- **PASS:** the output matches the expected behavior within the threshold.
- **FAIL:** regression. The output drifted from the golden baseline.

Tag every finding `[L5-Regression]`.

### 5d: Report

```text
Regression: {pass}/{total} tests passed
```

For each FAIL, include the test case name, the expected behavior (from the golden file), a summary
of the actual output, and the difference between them.

### Layer 5 severity

| Severity     | Criteria                                            |
| ------------ | --------------------------------------------------- |
| **critical** | More than 50% of tests failing: a major regression  |
| **warn**     | 1 to 50% failing: a partial regression              |
| **info**     | All tests pass, but output quality scores went down |

---

## 16. Starter axe spec

One canonical starter spec: `audit-setup/references/axe-playwright-starter.spec.ts`. `/audit-setup`
already writes it into a project as `<testDir>/a11y/smoke.spec.ts` with the detected routes filled
in; if `/audit-setup` has not run, copy that file in by hand instead of retyping it here. Then
either tag specs with `@a11y` and run `npx playwright test --grep @a11y`, or define a Playwright
project named `a11y` and run `npx playwright test --project=a11y`.

Prerequisite: `npm i -D @axe-core/playwright`. Docs:
https://www.npmjs.com/package/@axe-core/playwright

The review gate reads `violations[]`: `critical` and `serious` block at `--gate hard`, `moderate`
is a warning, and `minor` is info (reported only with `--deep`). Keep the route list tight, 4 to
7 key routes. axe takes 1 to 2 seconds per route on a warm page.
