---
name: audit-setup
description: Sets up the audit tool kit that /review-stack reads, in one command, installing only what is missing. It captures a Lighthouse baseline (median of 3 runs per route), adds @axe-core/playwright with a starter accessibility test, wires a bundle analyzer or size budget, configures knip for dead code, and can scaffold a PR-time CI gate and Lighthouse-on-PR checks. Use when the user says "set up QA gates", "set up audit tools", "bootstrap perf and a11y checks", "add Lighthouse to my project", "add a CI gate", "prepare this project for review-stack", or "audit setup", or mentions installing Lighthouse, axe, bundle budgets or dead-code detection on a Next.js, Vite, Astro or React project. Also use when a /review-stack audit reports missing tools.
---

# Audit Setup

Set up the inputs that `/review-stack --audit` consumes: a performance baseline, accessibility
tests, a bundle check, dead-code detection and, on request, CI gates. This is a one-shot
project initializer. Detect what exists, install what does not, then get out of the way.

It satisfies the `audit-setup` row of the development-protocol checklist (see "Record it" below).

## Doctrine

**Conventions over coupling.** `/review-stack` finds baselines and specs by looking at fixed
paths (`ops/lighthouse/baseline/*.report.json`, `@axe-core/playwright` in devDependencies,
`knip.json` at the root). This skill writes to those paths. No hand-off between the skills is
needed. The full map is in `references/integration-notes.md`.

**Idempotent by default.** Running on a fully set-up project is a no-op with a status report,
not a reinstall. Re-running after a partial install resumes cleanly.

**Default narrow.** `--all` sets up only what fits the detected stack. A Vite project does not
need `@next/bundle-analyzer`. A pure API project does not need a bundle check. Skip the mismatch.

**Never auto-edit framework configs.** `next.config.*`, `vite.config.*` and an existing
`playwright.config.*` vary too much between projects to patch safely. The kit prints the minimal
snippet and saves it to `ops/audit/`; the user pastes it. Installing packages and writing new
files is safe. Changing existing configs is not. (A `playwright.config.ts` is written only when
none exists, because without one Playwright finds 0 tests.)

## The kit

`KIT` below means `python3 <folder containing this SKILL.md>/scripts/audit_kit.py`. It needs
Python 3.9+ and Node. Every command accepts `--project-dir <path>` (default: current folder),
`--force` and `--dry-run`.

```text
KIT status                          preflight only, changes nothing
KIT run [--only TOOL]               set up every missing tool, then write ops/audit/STATUS.md
KIT lighthouse [--target-url URL] [--routes "/ /a"] [--runs N]
KIT axe [--routes "/ /a"]
KIT bundle
KIT knip
KIT quality-ci [--workdir web] [--node 22] [--default-branch main] [--uninstall]
KIT lighthouse-ci [--enforce] [--regen-assertions-only] [--uninstall] [--allow-host GLOB]
KIT routes                          print detected routes
```

Exit codes: 0 done or nothing to do, 1 a setup or check failed, 2 cannot run here.

---

## Step 0: Parse intent

From the user's words, pick one **mode**:

| Mode                | What it does                                                                          |
| ------------------- | ------------------------------------------------------------------------------------- |
| `--all` (default)   | Set up every missing local tool for the detected stack: Lighthouse, axe, bundle, knip |
| `--lighthouse-only` | Lighthouse baseline only                                                              |
| `--axe-only`        | axe + Playwright only                                                                 |
| `--bundle-only`     | Bundle analyzer or size budget only                                                   |
| `--knip-only`       | knip only                                                                             |
| `--ci`              | PR-time quality gate (`ci.yml`) plus Dependabot auto-merge. No baseline needed        |
| `--ci-only`         | Lighthouse-on-PR workflow. Needs an existing baseline                                 |
| `--status`          | Preflight report only. No changes                                                     |

And any **flags**:

- `--target-url <url>`: Lighthouse target. Default order: `LH_TARGET_URL` or `PREVIEW_URL` env
  var, then a server already on `localhost:3000`, then a local production build.
- `--routes "/ /a /b"`: explicit routes. Default: detected from the app or pages router.
- `--runs N`: Lighthouse runs per route for the median. Default 3; use 5 for performance-critical
  pages.
- `--force`: set up again even if the tool looks installed.
- `--dry-run`: print what would change, touch nothing.

Map modes to the kit: `--all` is `KIT run`; `--<tool>-only` is `KIT run --only <tool>`
(`lighthouse`, `axe`, `bundle`, `knip`); `--ci` is `KIT run --only quality-ci`; `--ci-only` is
`KIT run --only ci`; `--status` is `KIT status`.

---

## Step 1: Preflight

Run `KIT status`. It reads, and never writes:

- `package.json` (name, scripts, dependencies, devDependencies)
- `next.config.*`, `vite.config.*`, `astro.config.*` to set the framework
- `playwright.config.*` for its `testDir` (a project using `e2e/` must not be reported as
  missing its accessibility spec)
- `ops/lighthouse/baseline/*.report.json` for the baseline
- `<testDir>/a11y/*.spec.*` or `<testDir>/accessibility/*.spec.*` for the axe spec
- `knip.json` or `knip.ts`
- `.github/workflows/ci.yml` and `lighthouse-ci.yml`, and whether each carries the kit's sentinel
- `node --version`, which decides the Lighthouse version

A dependency counts as installed only when its name is a **key** in dependencies or
devDependencies. A plain text search for `"knip"` also matches the script value
`"dead-code": "knip"` and reports a tool that is not there.

Report it like this, then state the plan:

```text
Audit Setup - Preflight
  framework:      next   package manager: pnpm
  node:           v22.19   (Lighthouse to install: lighthouse@^13)
  lighthouse:     missing   baseline: missing
  axe:            installed   spec: present (testDir e2e)
  bundle:         missing
  knip:           installed + config
  quality ci:     missing
  lighthouse ci:  missing
Plan: will set up lighthouse, bundle. Run again with --dry-run to preview.
```

If the mode is `--status`, stop here.

---

## Step 2: Execute

For each tool in the chosen mode that is missing (or all of them with `--force`), the kit runs
the matching setup. Each prints its own lines, returns success or a clear failure, and is safe to
re-run.

| Tool       | What it does                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| lighthouse | Installs Lighthouse as a devDependency (version by Node), finds Chrome, detects routes, picks the target URL (starts `build` then `start` if nothing is running, waits 30 seconds, stops the server after), writes `ops/lighthouse/run-baseline.sh`, copies `lh_baseline.py` beside it, then runs the script: N runs per route, the median run kept as `ops/lighthouse/baseline/<slug>.report.json`, plus `SUMMARY.md`. Fails if no report was produced. |
| axe        | Installs `@playwright/test` (if absent) and `@axe-core/playwright`, downloads Chromium (`npx playwright install chromium`, skips cached browsers), writes `playwright.config.ts` only when none exists, then writes `<testDir>/a11y/smoke.spec.ts` from `references/axe-playwright-starter.spec.ts` with the detected routes. An existing spec is kept unless `--force`.                                                                                 |
| bundle     | Next.js: installs `@next/bundle-analyzer`, adds an `analyze` script (`ANALYZE=true <pm> build`), saves the config snippet to `ops/audit/bundle-analyzer-snippet.md` and prints it. Vite: installs `rollup-plugin-visualizer`, saves and prints its snippet. Astro and other builds: installs `size-limit` and `@size-limit/preset-app`, writes `.size-limit.json` (250 KB starter budget) if absent. No framework detected: skipped with a reason.       |
| knip       | Installs knip, writes `knip.json` (the Next.js preset from `references/knip.example.json`, or a generic `src/` preset), adds a `dead-code` script.                                                                                                                                                                                                                                                                                                       |
| quality-ci | See `--ci` below.                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ci         | See `--ci-only` below.                                                                                                                                                                                                                                                                                                                                                                                                                                   |

Installs use the project's package manager, found from the lockfile (`pnpm-lock.yaml`,
`yarn.lock`, `bun.lockb` or `bun.lock`, else npm). An npm install that fails is retried once with
`--legacy-peer-deps`, because peer-dependency conflicts (ERESOLVE) are the common npm-only
breakage. npm's installer also breaks on a `node_modules` tree that pnpm built, which is why the
kit never falls back to npm on a pnpm project.

Installs take 60 to 120 seconds each on a mature dependency tree. Say so before starting, so
nobody kills the run.

---

## Step 3: Verify

The kit checks each tool it claims to have set up (the canary). A setup step that returned
success without producing its file is reported as a failure, not a success:

| Tool          | Canary                                                          |
| ------------- | --------------------------------------------------------------- |
| Lighthouse    | at least one `ops/lighthouse/baseline/*.report.json`            |
| axe           | `<testDir>/a11y/*.spec.*` or `<testDir>/accessibility/*.spec.*` |
| Bundle        | the analyzer or size-limit is a devDependency                   |
| knip          | `knip.json` or `knip.ts`                                        |
| Quality CI    | `.github/workflows/ci.yml` carries the sentinel                 |
| Lighthouse CI | `.github/workflows/lighthouse-ci.yml` carries the sentinel      |

Then run the smoke checks yourself and read the output. Do not mark a tool done on the canary
alone:

| Tool             | Smoke check                                                                                                        |
| ---------------- | ------------------------------------------------------------------------------------------------------------------ |
| Lighthouse       | `ls ops/lighthouse/baseline/*.report.json` (at least 1) and read `ops/lighthouse/baseline/SUMMARY.md`              |
| axe              | `node -e "require.resolve('@axe-core/playwright')"`, then `npx playwright test --grep @a11y` against a running app |
| Bundle (Next.js) | `grep -l withBundleAnalyzer next.config.*`, or report `USER ACTION NEEDED: add the snippet in ops/audit/`          |
| knip             | `npx knip --help > /dev/null` and `test -f knip.json`, then one `npx knip` run                                     |
| Quality CI       | the first `ci` run on a PR is green on its head SHA                                                                |

If a smoke check fails, do not mark the tool complete. Print the failure and the next action for
the user.

---

## Step 4: Status file

After any run that did something (even partly), the kit writes `ops/audit/STATUS.md`: the time,
what ran, what was skipped, what failed (with the reason), the package manager, and the table of
artifacts `/review-stack --audit` will read. The file makes state visible in the repo and in PR
diffs, and tells the next person what was set up and when.

When nothing ran and nothing failed, the kit prints "nothing to do" and leaves `STATUS.md` as
it was. Rewriting it to say the same thing only adds diff noise.

---

## Step 5: Tell the user

End with a block like this, filled from the real run:

```text
Setup complete. The next /review-stack --audit will pick up:
  - Lighthouse baseline -> ops/lighthouse/baseline/ (5 routes, Lighthouse 13)
  - axe smoke tests     -> tests/a11y/smoke.spec.ts
                           run: npx playwright test --grep @a11y
  - Bundle analyzer     -> pnpm analyze
                           NOTE: paste the snippet in ops/audit/bundle-analyzer-snippet.md first
  - Dead-code check     -> npx knip

Rerun the Lighthouse baseline any time: sh ops/lighthouse/run-baseline.sh
```

Say plainly what failed or still needs a person (a config snippet to paste, a ruleset to apply).

---

## Mode details

### `--lighthouse-only`

Just the baseline. Use it to set a performance watermark fast. With a baseline present it skips;
`--force` recaptures.

### `--axe-only`

Just axe. Useful when Playwright is already there and only accessibility coverage is missing.
Installs `@playwright/test` too if it is absent.

### `--bundle-only`

Just the bundle check. Most common on a Next.js project that wants `ANALYZE=true` builds for the
first time.

### `--knip-only`

Just knip. The lowest-friction addition to any TypeScript project.

### `--ci` (PR-time quality gate)

`KIT quality-ci`. Writes three files:

- `.github/workflows/ci.yml`, one job named `ci`: install, `tsc --noEmit` when TypeScript is a
  dependency, the `test:coverage` or `test` script, the `build` script if present,
  `knip --include unlisted`, and a high-severity dependency audit.
- `.github/workflows/dependabot-auto-merge.yml`: merges patch and minor bumps that touch only the
  manifest and lockfile, after `ci` passes on the PR's head SHA. Majors and Actions bumps wait for
  a person.
- `.github/dependabot.yml`, only if absent (weekly npm and Actions updates).

It detects the package folder (`.`, `web/` or `app/`), the package manager from the lockfile, and
the Node version from `engines`. Then it prints the one `gh api` call that makes `ci` a required
check, to run after the first green run.

The rules behind it, each from a real failure:

- **The gate must run with no agent present.** Proof that only exists while an agent watches
  expires when the session ends. A CI job on every PR and every push to the default branch
  does not.
- **Refuses a package with no test script.** A gate with no tests is theater. Add a test runner
  first.
- **`pull_request` is unfiltered.** A required check with path filters that never reports on a PR
  blocks the merge forever as "pending".
- **No `|| true` and no `continue-on-error`.** A step that cannot fail is not a gate.
- **Next.js projects run `npx next typegen` before `tsc`.** Next 16 generates page and layout prop
  types into `.next/types` at build time. Measured 2026-09-05: a clean runner hit 8 TS2304 errors
  that never showed locally, where `.next/types` was left over from the last build.
- **Dependabot merge waits by reading check runs for the head SHA**, never
  `gh pr checks --watch`, which can reprint a previous commit's results (measured 2026-08-15).
- **Actions are pinned by commit SHA.** If `zizmor` (a workflow security linter) is installed, the
  kit runs it on the new workflows.
- **`knip --include unlisted` is narrow on purpose.** It catches the class of dead import that
  breaks builds when a transitive dependency moves. A gate nobody can pass is a gate everyone
  ignores.

Files carry the sentinel `audit-setup:quality-ci v1`. An existing workflow without the sentinel
is hand-written: the kit refuses to overwrite it (exit 1) unless `--force`. `--ci --uninstall`
removes only files that carry the sentinel.

### `--ci-only` (Lighthouse on every PR)

`KIT lighthouse-ci`. Needs a baseline (run `--lighthouse-only` first). Installs `@lhci/cli` and
writes:

- `.github/workflows/lighthouse-ci.yml`: fires on successful preview deploys
  (`deployment_status`, environment `Preview` as Vercel names it; edit the `if:` for other hosts)
  and on manual dispatch. It checks the URL against an allowlist, fails fast when the preview is
  behind a login, rebuilds the route list from each baseline report's `requestedUrl`, runs LHCI,
  and upserts one PR comment with deltas against the baseline.
- `.lighthouserc.json`: assertions derived from the baseline. Performance, best practices and SEO
  may dip 3 points below baseline, never below floors of 80, 95 and 95. Accessibility must be 100. The preset follows the baseline (mobile or desktop), or every assertion fails on the first
  run.
- `.github/ci/lh-bless.sh` and `.github/ci/README.md`: the baseline refresh flow and the docs.
- `lhci` and `lh:bless` package scripts.

The URL allowlist defaults to `https://*.vercel.app*` plus a guess from the repo name. Pass
`--allow-host GLOB` (repeatable) for other hosts.

**Assertions start warn-only.** Regressions show in the PR comment but do not fail the build
until you flip `"warn"` to `"error"` in `.lighthouserc.json`, or run `--ci-only --enforce`.

**Why the login check exists.** When a preview sits behind a login, Lighthouse follows the
redirect and audits the login page. Its path matches no assertion pattern, so every assertion is
skipped and the run reports success, including error-level ones. The workflow fails on HTTP 401
or 403 instead.

`--ci-only --uninstall` deletes only the owned files that still carry their own sentinel (the
workflow, `.lighthouserc.json` and `.github/ci/README.md` share one; `lh-bless.sh` carries a
distinct one) and strips the scripts. A file that was hand-edited (its sentinel missing) is kept
and named on stdout, not deleted. Forked PRs get no comment: `deployment_status` events do not
fire for forks.

### `--status`

Preflight only. Safe anywhere.

---

## What this skill does not do

- **It is not a review.** It sets up inputs; `/review-stack --audit` uses them.
- **It does not edit `next.config.*`, `vite.config.*` or an existing `playwright.config.*`.** It
  prints and saves a minimal snippet for the user to apply.
- **CI is opt-in.** `--all` never writes workflows. `--ci` and `--ci-only` each own named files
  and never touch other workflows.
- **It does not upgrade versions.** Installs are idempotent. To upgrade, the user runs the
  package manager's update command.
- **It does not make `ci` required by itself.** Changing branch rules is a repository setting;
  the kit prints the exact call and the user (or someone with admin rights) runs it.

---

## Graceful degradation

| Situation                     | Behavior                                                                                                                      |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| No `package.json`             | Stop: "Not a Node project. Run from a package root." For the checklist row itself, see "Non-Node repos" above.                |
| Unknown framework             | Set up Lighthouse, axe and knip. Skip the bundle check: "needs Next.js, Vite or a known build."                               |
| Node older than 18            | Stop the Lighthouse and axe steps: "Upgrade Node first."                                                                      |
| Node 18 to 22.18              | Install Lighthouse 12.6.1, the last release for older Node. Say so.                                                           |
| Node 22.19 or newer           | Install Lighthouse 13.                                                                                                        |
| No routes detected            | Use `/` and say so. The user can pass `--routes`.                                                                             |
| Install fails mid-way         | Report which install failed, leave partial state, exit 1. Re-running resumes.                                                 |
| Lighthouse target unreachable | Fail the Lighthouse step only; other tools still run. Say: set `--target-url` or `PREVIEW_URL`, or make build and start work. |
| No Chrome or Chromium         | Fail the Lighthouse step: set `CHROME_PATH` or run `npx playwright install chromium`.                                         |
| Playwright not installed      | The axe step installs `@playwright/test` and Chromium.                                                                        |
| `gh` CLI not installed        | `--ci` still writes the files; the user applies the required-check ruleset in the repository settings page instead.           |
| `zizmor` not installed        | Skip the workflow lint and say so.                                                                                            |

---

## Why this shape

**Why a setup skill separate from `/review-stack`?** Review is a gate; this is a one-shot
installer. Kept apart, review stays fast (no installs in its hot path) and setup stays focused
(no review logic). They meet only at file paths.

**Why never auto-edit configs?** A `next.config.ts` can be 5 lines or 500, ESM or CommonJS, with
middleware chains or custom webpack. A wrong patch breaks the build. Printing the snippet costs
the user 30 seconds; a wrong patch costs an incident.

**Why the median of 3 Lighthouse runs?** Single runs swing by about 3 points on a cold start. The
LHCI default (3 runs, median) removes most of that swing without the time cost of 5 runs
(research done 2026-04-18).

**Why prefer a preview URL?** A local production server on a cold machine gives slower LCP than
production. A preview deploy matches production's edge and cache behavior, so its numbers track
what users feel. Capture the baseline on the same surface CI will audit: GitHub-hosted runners
score 30 to 50 performance points below a fast laptop or a CDN.

**Why copy `lh_baseline.py` into the project?** So the rerun script and the bless flow work on
any clone and any CI runner, without knowing where this skill is installed.

---

## Record it in the checklist

This skill satisfies the `audit-setup` row. Evidence is the status file the kit wrote; the
verifier only reads it and fails on any recorded failure:

```text
python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
  --id <work-id> --step audit-setup --result pass --evidence ops/audit/STATUS.md \
  --verify "grep -q '^## Ran this invocation' ops/audit/STATUS.md && ! grep -q '^- FAILED' ops/audit/STATUS.md"
```

If every tool was already in place (the kit said "nothing to do"), save the preflight instead
and verify it has no missing tool:

```text
KIT status > .devproto/evidence/audit-setup.txt
... --evidence .devproto/evidence/audit-setup.txt \
  --verify "! grep -E '^  (lighthouse|axe|bundle|knip):' .devproto/evidence/audit-setup.txt | grep -q missing"
```

If a tool genuinely does not apply (an API-only project needs no bundle check), say which and why
in the evidence. If a required tool failed, record the row as `blocked` with the reason. Do not
pass it.

### Non-Node repos (no `package.json`)

The kit's tools are Node-only by design (Lighthouse, axe, the bundle check and knip all need a JS
build), so none of them can run on a Python, Go, Rust or other non-Node repo. `audit-setup` is
still required by default there (it is only conditional when the goal itself reads as trivial),
so there must be a way to close the row without the kit:

- **Pass it on the repo's own CI and test config**, when that config already gates quality the
  way the kit's tools gate a Node project (lint and tests running in CI on every PR). Evidence
  names the CI workflow and test config found; the verifier re-checks both still exist:

  ```text
  printf 'CI: %s\nTests: %s\n' .github/workflows/ci.yml pyproject.toml > .devproto/evidence/audit-setup.txt
  python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
    --id <work-id> --step audit-setup --result pass --evidence .devproto/evidence/audit-setup.txt \
    --verify "test -f .github/workflows/ci.yml && test -f pyproject.toml"
  ```

- **Make the row optional mid-run**, if there is no CI/test gate yet to point to, or the goal made
  it required and it plainly does not apply this time:

  ```text
  python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> set-optional \
    --id <work-id> --step audit-setup --reason "pure Python repo, no package.json"
  python3 <development-protocol skill folder>/scripts/devproto.py --project <repo> step \
    --id <work-id> --step audit-setup --result na --reason "pure Python repo, no package.json"
  ```

  Unlike `start`'s `--require`/`--optional`, `set-optional` works after earlier rows have already
  passed -- it does not require abandoning the work id and re-proving rows 1 onward under a new
  one just to mark one later row not applicable.

## Acceptance scenarios

Use these to check the skill behaves as written:

1. **Greenfield Next.js marketing site with home, about, pricing, contact.** `--all` writes 4
   baseline reports plus `SUMMARY.md` and `run-baseline.sh`, `tests/a11y/smoke.spec.ts` with the
   4 routes, `knip.json` with Next.js entry points, installs `@next/bundle-analyzer` with an
   `analyze` script, prints the `next.config` snippet, and writes `ops/audit/STATUS.md`.
2. **Partial setup.** With axe installed and a month-old baseline, `--all` runs only bundle and
   knip, does not recapture the baseline, and `STATUS.md` lists Lighthouse and axe as skipped.
3. **Status only.** `--status` prints framework, Node and each tool's state, installs nothing and
   creates no `STATUS.md`.

## Files

| Path                                        | Purpose                                                           |
| ------------------------------------------- | ----------------------------------------------------------------- |
| `scripts/audit_kit.py`                      | Preflight, per-tool setup, CI scaffolds, canary and status file   |
| `scripts/lh_baseline.py`                    | Median summary, LHCI assertions, enforce. Copied into the project |
| `references/integration-notes.md`           | How these outputs line up with what `/review-stack` looks for     |
| `references/axe-playwright-starter.spec.ts` | The axe starter test (routes filled in by the kit)                |
| `references/playwright.config.example.ts`   | Written only when a project has no Playwright config              |
| `references/knip.example.json`              | knip preset for Next.js app router projects                       |
| `references/bundle-analyzer.md`             | Next.js and Vite snippets the user pastes                         |
| `references/run-baseline.sh.tmpl`           | The Lighthouse capture and rerun script (POSIX sh)                |
| `references/quality-ci.yml.tmpl`            | The PR-time gate workflow                                         |
| `references/dependabot-auto-merge.yml.tmpl` | Patch and minor auto-merge after `ci` passes                      |
| `references/lighthouse-ci.yml.tmpl`         | Lighthouse-on-PR workflow                                         |
| `references/lh-bless.sh.tmpl`               | Baseline refresh script                                           |
| `references/ci-readme.md.tmpl`              | Docs written to `.github/ci/README.md`                            |

## Related skills

| Skill                   | Relationship                                                                                    |
| ----------------------- | ----------------------------------------------------------------------------------------------- |
| `/review-stack --audit` | Downstream consumer. Finds these outputs by path.                                               |
| `/planning-stack`       | When a plan says "set up quality gates" or "add perf or a11y coverage", suggest this skill.     |
| `/simplify`             | If the new dependencies overlap tools the project already has, run it to remove the duplicates. |
| `/development-protocol` | Tracks this as the `audit-setup` row.                                                           |

Before installing, check the project does not already have its own audit scripts under another
name (`scripts/lighthouse.sh`, a custom axe runner). Reuse them instead of adding a second copy.
