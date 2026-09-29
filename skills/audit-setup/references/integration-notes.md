# How audit-setup plugs into /review-stack

This maps what `/audit-setup` writes to what `/review-stack --audit` looks for. It exists so a
future agent understands how the two skills work together without any direct coupling.

## Filesystem conventions

| audit-setup writes                         | /review-stack probes                                 | Effect                                                                                                                               |
| ------------------------------------------ | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `ops/lighthouse/baseline/*.report.json`    | glob for baseline reports, sets a "has baseline" flag | The runtime audit runs Lighthouse in **regression-compare mode** against the baseline. Without it, only absolute thresholds apply.    |
| `ops/lighthouse/baseline/SUMMARY.md`       | nothing (for people)                                 | People read it; no skill parses it.                                                                                                  |
| `ops/lighthouse/run-baseline.sh`           | nothing                                              | Rerun script for people and CI.                                                                                                      |
| `@axe-core/playwright` in devDependencies  | reads `package.json` devDependencies                 | The runtime audit runs the axe tests.                                                                                                |
| `<testDir>/a11y/smoke.spec.ts`             | `npx playwright test --grep @a11y`                   | The starter spec tags every test `@a11y`, so the grep finds them.                                                                    |
| `knip.json`                                | dead-code tool flag                                  | The static layer runs `npx knip`.                                                                                                    |
| `@next/bundle-analyzer` in devDependencies | bundle analyzer flag                                 | The runtime audit parses `ANALYZE=true` build output for oversized chunks.                                                           |
| `.github/workflows/ci.yml` (sentinel)      | CI status on the PR head SHA                         | Review can cite a check that runs without an agent present.                                                                          |
| `ops/audit/STATUS.md`                      | nothing                                              | Shows people, in the repo and in PR diffs, what was set up and when.                                                                 |

## Why this coupling is healthy

- **No shared module.** Neither skill imports or reads the other's code. They share only paths.
- **Each works alone.** `/review-stack --audit` runs without `/audit-setup`; it just has less
  signal. `/audit-setup` runs without `/review-stack`; the artifacts help people and CI too.
- **Versions move independently.** They agree on paths, not on APIs.

## When /review-stack should suggest /audit-setup

When a tool is missing, the fix to suggest is `/audit-setup --<tool>-only`:

- `@axe-core/playwright` missing: `/audit-setup --axe-only`
- Lighthouse CLI missing: `/audit-setup --lighthouse-only`
- Lighthouse baseline missing: `/audit-setup --lighthouse-only` (captures the baseline)
- knip missing: `/audit-setup --knip-only`
- No PR-time gate: `/audit-setup --ci`

## Idempotence contract

- Running `/audit-setup --all` twice in a row must be a no-op the second time (beyond reading
  `package.json`), and must not rewrite `ops/audit/STATUS.md`.
- `/audit-setup --lighthouse-only` with a baseline present skips; `--force` recaptures.
- `/review-stack` never writes to these paths. One-way flow: audit-setup writes, review reads.
