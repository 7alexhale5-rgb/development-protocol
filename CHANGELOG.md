# Changelog

## Unreleased

- Lighthouse capture rejects incomplete, replayed, redirected and mixed reports, and records
  durable proof for fresh-clone validation. Setup checks existing proof and helper freshness,
  preserves replaced helpers and custom exclusions, and refuses stale publication locks.
- Preview workflow output accepts only valid allowed origins. Warning tuples, including
  scalar thresholds, become errors when enforcement is requested.

## 2.0.1 (2026-09-29)

- Release proof rejects failed pipelines, stale concurrent results, unknown Git identity,
  and changed release commits. Stored commands are redacted.
- Install recovery preserves originals across interruptions and shared folders. Health checks
  detect missing runtime files; scans handle Unicode names and Windows paths.
- Audit setup preserves configuration and enforcement, repairs partial installs, binds dependency
  merges to checked commits, and validates complete preview route coverage.
- Research validation requires mandatory sections and public citation addresses, disables proxy
  bypasses, and classifies source hosts using domain boundaries.
- Design verification rejects absent or failed proof. Token conversion preserves string types,
  font families, and color meaning; unsupported transparency fails explicitly.
- Build, commit, ship, and closeout instructions bind proof to complete changes and final state.
- Retrospective metrics use correct totals, comparable windows, and local dates.

## 2.0.0 (2026-09-29)

- The whole development stack, not only the protocol: 19 skills (development-protocol, pathway,
  brainstorm-stack, research-stack, karpathy, planning-stack, visual-spec, design-stack,
  devilsadvocate, audit-setup, build-stack, review-stack, simplify, commit, ship, compound,
  closeout-stack, relentless, 1pct).
- Checklist moved to the 17-row standard, one row per skill.
- Checklist fixes from three review rounds: verifier runs without holding the lock, kills its whole
  process tree on timeout or interrupt, ignores background children; re-recording an earlier row
  reopens later rows; `--through` for pre-merge gates; `--optional`; symlinked instruments refused;
  clear reasons for each failure.
- Installer with dry run, backups and restore; uninstaller; health check.
- Docs: STANDARD, WORKFLOW, SETUP, DAILY-USE, TROUBLESHOOTING, UPDATING, PORTING.
- Private-data scan in tests and CI.

## 1.0.0 (2026-09-29)

- First shareable development-protocol skill with the evidence-checked checklist.
