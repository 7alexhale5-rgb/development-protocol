# Changelog

## 2.5.2 (2026-10-07)

- `/audit-setup` CI templates: the quality gate and the Dependabot auto-merge job now read
  `runs-on` from an optional `CI_RUNNER` variable and fall back to `ubuntu-latest` when it is unset
  or the pull request is from a fork, so teams with a self-hosted runner switch one variable, not
  every workflow. The Lighthouse job stays on `ubuntu-latest` (Chrome has no Linux arm64 build).

## 2.5.1 (2026-10-04)

- `/research-stack` validator re-ported from the public 3.3.0 follow-ups: `declared_focus` no longer
  loses lenses to blank or comment rows, YAML block lists, inline comments, CRLF files or `- #tag`
  null items, and `validate_report.py` fails any `focus:` spelling it cannot read (a wrapped flow
  list, a value on a later line) instead of skipping every focus check. The focus manifest note now
  names pathway-operating-layer as a mirror, so the shared-standards focus-tags check agrees again.

## 2.5.0 (2026-10-04)

- New skill `/icm` (20 skills now): files every project file by the ICM folder method (a root
  `CLAUDE.md` router, one `CONTEXT.md` contract per room with Inputs, Process, Outputs and Human
  check) and ships `scripts/icm_check.py`, a standard-library walk test that exits 0 when the
  layout holds, 1 when it is broken and 2 when it could not measure.
- Filing follows the room map: `/brainstorm-stack --for-plan` writes `.planning/BRAINSTORM.md`
  (never `.planning/CONTEXT.md`), `/planning-stack` names the room for every file the plan
  creates or moves, and `/build-stack` and `/design-stack` file project files by the map.
- `/development-protocol` and `docs/STANDARD.md`: three risk lanes (Small, Normal, Irreversible)
  decide which rows carry work and where a person looks; irreversible work (live-data
  migrations, money movement, external sends, production infrastructure) is checked first and
  needs a named go-ahead. New permission-mode rules for agents with a classifier-based auto mode.
  Close includes the ICM walk test.
- Research focus tags reach more callers: `/design-stack` (`ui-ux`, `a11y`, `market`), `/1pct`
  (`/research-stack --no-ask` with one tag) and the `/planning-stack` depth table.
- Plugin updates: `version` now lives only in `.claude-plugin/plugin.json` (removed from the
  marketplace entry), and CI fails a pull request that changes `skills/` or `.claude-plugin/`
  without a new version, so installs that sync automatically always receive the change.
- `/pathway` and `/research-stack` descriptions no longer contain angle-bracket placeholders.
  claude.ai's marketplace sync rejects them as XML tags and stores the text with the brackets
  removed. A package test now fails on any `<` or `>` in a skill description.

## 2.4.0 (2026-10-02)

- Review handoffs retain complete task scope and explicit gaps; no finding quotas or clean-result retries.

- Route all 15 Superpowers methods through the existing development checklist. Prove behavior
  changes with red-green checks, retain independent review for every work size, and record
  skipped required checks as blocked.
- Add bounded improvement reports with frozen comparisons, held-out cases, independent reviews
  and rollback. Actual measured adoption needs a reviewed adapter; no measured gain is claimed.


- Read-audit guidance states its retained-transcript requirement and the missing native Codex
  transcript adapter. Session ownership does not establish whole-file read proof.
- Premortem evidence uses verifier-compatible headings. Lighthouse publication locks refuse
  capture before dependency work, including forced recapture. Replaced-file backups are reported
  and their exclusions share one append path; all prior copies remain retained.
- Ad-hoc review proof still needs a request-derived acceptance criterion. Citation validation
  requires at least one live source and rejects safety-blocked fetches; unverified links remain
  distinct from dead links. The skill guidance now states those proof requirements.
- Lighthouse capture rejects incomplete, replayed, redirected and mixed reports, and records
  durable proof for fresh-clone validation. Setup checks existing proof and helper freshness,
  preserves replaced helpers and custom exclusions, and refuses stale publication locks.
- Preview workflow output accepts only valid allowed origins. Warning tuples, including
  scalar thresholds, become errors when enforcement is requested.

## 2.3.0 (2026-10-02)

- Research Stack 3.2.1: hunter/gatherer mode (`--deep` or 4+ sub-questions) splits hunting, scoring
  and writing into separate contexts, with `scripts/gather.py` scoring evidence cards against a
  rubric. The validator warns when a `--deep` report skips the perspectives, the attribution
  check or the internal round, and only the active lenses' authorities rank as official.

## 2.2.0 (2026-10-01)

- Research focus lens `comms` (voice, SMS and dialers), the 12th lens: `/research-stack --focus
  comms` splits the phone system from the programmable layer, adds
  RingCentral, Twilio, Telnyx, Aircall, Dialpad, CallRail and FCC, eCFR and CTIA rules to the
  tool registry, and requires a "Telephony and messaging plan" section.
- `data-infra` treats vercel.com, supabase.com and opentelemetry.io as authorities. `devtools`
  also triggers on api, sdk, integration and webhook. The checklist suggests `comms` for
  telephony goals.

## 2.1.0 (2026-10-01)

- Research focus lenses: `/research-stack --focus <tags>` (or `#tag`) runs up to 4 of 11 lenses (seo,
  content, market, ui-ux, a11y, perf, security, devtools, ai-agents, data-infra, legal), each with
  its own sub-questions, tool stack, authorities, audit mode and required report section. Bundles:
  `#launch`, `#ship-audit`, `#competitive`, `#build-pick`.
- `validate_report.py structure` enforces the focus addenda a report declares. New
  `focus_check.py` lints lenses against the tool registry and suggests, plans and probes tools.
- The checklist suggests focus tags from the goal when the research row turns on. Lane docs and
  the planning, spec, brainstorm, pathway and design skills pass tags through.
- `/1pct` sends external unknowns that block an approved plan to focused research, not the user.

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
