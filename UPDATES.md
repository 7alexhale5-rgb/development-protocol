# Update log

Every re-port, source baseline, and public maintenance change, newest first.

## 2026-10-04T13:52:09-05:00

- skill:brainstorm-stack: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:planning-stack: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:research-stack: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:icm: source fingerprint recorded for drift monitoring; this is not a re-port

## 2026-10-04T13:50:51-05:00

Release 2.5.0. Each drifted item was compared with the committed source version its lock hash
matches, then re-ported from the committed changes since. A source with uncommitted edits that
this port did not make is ported from its committed version only, and its lock is not updated.

- skill:icm (new): ported from the private ICM folder standard and its checker. Files:
  `skills/icm/SKILL.md`, `skills/icm/scripts/icm_check.py` (standard library, exit 0 holds,
  1 broken, 2 could not measure), `tests/test_icm.py` (43 tests, including the seeded broken
  fixture `tests/fixtures/icm-broken/`) and a test that this repo passes its own walk test.
  Dropped: private corpus and rollout-ledger paths, the home-folder project finder and owner
  family names that only private hooks used, private hook names (now "enforcement, if your team
  wants it"), private examples in the forms table, and personal approval wording ("the owner's
  approval"). Kept: every rule, the 13 conventions, the six forms, the walk test, the dated
  2026-09-30 project-boundary lessons and the paper's own limits. Lock recorded.
- skill:brainstorm-stack: full re-port. The focus-tag line was already in the port. Added the
  committed ICM rule that `--for-plan` writes `.planning/BRAINSTORM.md`, never
  `.planning/CONTEXT.md` (it was in the recorded source but missing here). Lock recorded.
- skill:planning-stack: full re-port. Depth table passes focus tags; the interview names the
  room for every file the plan creates or moves. The source's visual-pack path change does not
  apply: `/visual-spec` owns the pack here. Lock recorded.
- skill:research-stack: no content change needed. Drift cause: the source folder is its own git
  repository, ignored by the parent repository, so its two commits since the lock never showed
  in the parent's history. One replaced the private copy with public research-stack
  3.3.0 plus a private `local/` add-on; the other changed only that add-on. The lock also still
  held the pre-v3 fingerprint from before the 2.2.0 and 2.3.0 re-ports. The public files equal
  upstream 3.3.0 byte for byte, and the only SKILL.md change since the 3.2.1 port is the optional
  `config/` and `local/` overlay lines, left out on purpose (this port has neither). The
  maintainer's drift check now skips private-only add-ons inside a mapped folder (`local/`,
  `config/config.md`, per-machine agent memory), so an add-on edit no longer counts as drift.
  Lock recorded.
- Focus tags: `references/focus/tags.json` still differs from upstream only in its metadata
  note, the allowed public divergence (upstream names a private implementation). Triggers,
  addenda, bundles and `FOCUS_HINTS` match.
- skill:1pct: partial. Added the `/research-stack` composition row; the external-unknowns rule
  and its examples were already ported. Lock not updated: the source has uncommitted edits.
- skill:design-stack: partial. The `/research-stack` row passes focus tags (`ui-ux`, `a11y`,
  `market`), and a project-filing note points to `/icm`. Lock not updated: the source has
  uncommitted edits.
- skill:karpathy: partial. The committed focus-tag change was already in the port; nothing new.
  Lock not updated: the source has uncommitted edits.
- skill:build-stack: partial. No committed change since the lock; added the project-filing note
  that was in the recorded source. Lock not updated: the source has uncommitted edits.
- skill:compound: partial. No committed change since the lock; nothing to port. Lock not
  updated: the source has uncommitted edits.
- skill:development-protocol: partial. `reference.md` gains the three risk lanes, generalized
  permission-mode rules and the ICM walk test at close; `SKILL.md` applies the lane at `start`
  and adds the auto-mode config check. Lock not updated: the source has uncommitted edits.
- doc:STANDARD: partial. The irreversible class (checked first), the risk-lane table, the
  file-by-the-map gate, and the cloud-thread note for desktop Projects. Lock not updated: one
  source file has uncommitted edits.
- Intentional divergence: the source's Small lane omits review and closeout. Here they stay,
  because the checklist always requires pathway, build, review, commit, ship and closeout.
  `audit-setup` and `review-stack` did not take the source's project-filing note: their ports
  write fixed paths that `/review-stack` and the checklist look for.
- Version 2.5.0. `version` lives only in `.claude-plugin/plugin.json`;
  `scripts/check_version_bump.py` and CI's `version` job fail a pull request that changes
  `skills/` or `.claude-plugin/` without a bump. New `scripts/` room with its contract.

## 2026-10-02T16:42:05-05:00

- Ship and closeout now block outward release when required review or verification is missing.
  Intake captures the work baseline before planning commits; review binds the complete candidate.
- Version 2.4.0: integrate all 15 Superpowers methods within the existing protocol.
  Behavior changes require red-green evidence, every class needs independent review, and
  skipped required checks end with a blocked record. Bounded improvement reports distinguish
  truthful learning from measured adoption; this package requires a reviewed measurement adapter.
- Align canonical skeptic briefs and brainstorm, planning, research and review consumers with
  evidence-backed clean results. Retain full baseline-to-head scope and coverage gaps.
- Intentional note-only public divergence in `skills/research-stack/references/focus/tags.json`:
  the metadata note uses a generic workflow-consumer description. Triggers, lenses and
  `FOCUS_HINTS` are unchanged. This removes a private implementation pointer from current
  public files; the earlier published history retains it and is not rewritten.
- Source fingerprints are not reset merely to hide drift. Installation and review receipts
  must bind this candidate before its release. No vendor package or measured gain is claimed.


## 2026-10-02T13:26:41-05:00

- skill:research-stack: re-ported from upstream research-stack 3.2.1 (`3af6987`). New: hunter/gatherer
  mode (SKILL.md Step 3H and the `--hunt` / `--no-hunt` flags), `scripts/gather.py` (rubric
  scorer, keep/drop/requote/escalate router, agreement and eval commands, optional Jev scorer in
  shadow mode), `references/hunter-gatherer.md` and `references/jev-question-design.md`, with the
  gather tests and fixtures under `tests/`. Fixes carried over: `validate_report.py` warns when a
  `--deep` report does not record perspectives, attribution or the internal round, ranks only the
  active lenses' authorities as official, and reads `focus: none` as no focus; `focus_check.py`
  walks fallback chains and plans from a given lens folder; the `claude-subagent` and `jev`
  registry entries; the dashboard Gatherer line; the perf and seo lens wording. `tags.json` is
  now byte-equal to upstream. `FOCUS_HINTS` in `devproto.py` already matched the upstream
  triggers, which did not change.
- Left out on purpose: `references/power-tier.md` (local extras: Gemini CLI, Groq, NotebookLM,
  last30days, vault notes), as in the earlier port. The upstream research dossier and its run
  data (`docs/research/`) are not bundled; vendor prices, vendor speed claims and the reseller's
  company name are stripped from the Jev text. Jev stays optional, paid and in shadow mode.
- Source lock: `sync/sources.lock.json` is left unchanged. The recorded hashes come from the
  maintainer's drift check, which cannot run from this repo, so the next drift check should
  re-record `skill:research-stack` after confirming this port.
- Version 2.3.0.

## 2026-10-02T11:59:38-05:00

- skill:relentless: source fingerprint recorded for drift monitoring; this is not a re-port

## 2026-10-02T11:50:35-05:00

- skill:relentless: source fingerprint recorded for drift monitoring; this is not a re-port

## 2026-10-02T11:32:52-05:00

- skill:relentless: source fingerprint recorded for drift monitoring; this is not a re-port

## 2026-10-02T10:53:05-05:00

- skill:relentless: source fingerprint recorded for drift monitoring; this is not a re-port

## 2026-10-01T18:46:20-05:00

- skill:research-stack: re-ported the upstream comms lens (voice, SMS and dialers; CPaaS versus
  UCaaS). New `references/focus/comms.md` and a 12th tag in `references/focus/tags.json` (between
  `data-infra` and `legal`, addendum "Telephony and messaging plan"), plus 7 registry tools:
  RingCentral, Twilio, Telnyx, Aircall, Dialpad, CallRail and FCC, eCFR and CTIA rules (83 tools).
  `data-infra` authorities gain vercel.com, supabase.com and opentelemetry.io; `devtools`
  triggers also match api, sdk, integration and webhook. The lens's pathway line points to
  `/pathway`, as in the other lenses. Nothing dropped: the new entries hold no private material.
- skill:development-protocol: `FOCUS_HINTS` in `devproto.py` mirrors the new and changed triggers.
- tests: `test_focus.py` gains the upstream dialer-topic regression test.
- Version 2.2.0.

## 2026-10-01T18:39:01-05:00

- skill:relentless: source fingerprint recorded for drift monitoring; this is not a re-port

Portable re-port of the tested Codex read-proof parser and opt-in sweep integration.
The Claude successful-result lane stays unchanged. Tests cover complete output, failures,
truncation, conflicting sessions and changed targets. Read proof never grants runtime
coverage. Both outside reviews and new exact-head cloud checks remain required.

## 2026-10-01T13:05:28-05:00

- Repo layout: agent routing by the ICM folder method. A root `CLAUDE.md` router (with an
  `AGENTS.md` symlink for Codex), a `CONTEXT.md` system map, and one `CONTEXT.md` contract each
  for `skills/`, `docs/`, `tests/`, `sync/`, `.claude-plugin/` and `.github/`. No files moved,
  nothing installed changes: `install.sh` copies only `skills/<name>/` folders that hold a
  `SKILL.md`. Not a user-visible change, so no version bump.

## 2026-10-01T12:50:53-05:00

- skill:research-stack: research-stack re-ported from v3 (focus lenses). Eleven lenses and the tag
  manifest now ship under `references/focus/`, with the tool registry, `focus_check.py` and a
  validator that enforces focus addenda. Dropped: the power tier (local extras), config file
  reading, and notes-vault paths. Person-specific connectors became generic "if your team has
  one" entries.
- skill:1pct: re-ported the "External unknowns go to research, not to the user" rule.
- skill:development-protocol: `devproto.py` suggests `/research-stack --focus <tags>` from the
  goal when the research row turns on. Lane docs and callers pass focus tags through.
- Source lock: not updated. The recorded hashes come from the maintainer's drift check, whose
  method could not be reproduced here (no plain SHA-256 of the source SKILL.md or any of its
  committed versions matches). The next drift check should re-record `skill:research-stack` and
  `skill:1pct` after confirming this port.

## 2026-10-01T01:27:20-05:00

Independent review follow-up: the premortem template matches its verifier; Lighthouse
publication locks refuse capture early and retained backup paths are reported. Ad-hoc review
and citation guidance now state their proof requirements. Read-audit guidance also states
its retained-transcript requirement and missing native Codex transcript adapter. These are
portable maintenance changes, not an upstream re-port; source fingerprints remain unchanged.

## 2026-09-30T21:21:38-05:00

- skill:audit-setup: source fingerprint recorded for drift monitoring; this is not a re-port


## 2026-09-29T21:01:33-05:00

Public maintenance release 2.0.1 fixes confirmed release-review findings. These are changes to
the portable package, not a re-port from private sources. The source fingerprint lock remains
unchanged so future drift checks do not hide upstream differences.

- Runtime proof: development-protocol and pathway.
- Safety and recovery: installer, uninstaller, health check, and scanner.
- Validation: audit-setup, research-stack, design-stack, and workflow instructions.
- Reporting: compound metric definitions and local-day grouping.


## 2026-09-29T20:07:41-05:00

- doc:STANDARD: source fingerprint recorded for drift monitoring; this is not a re-port
- doc:WORKFLOW: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:1pct: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:audit-setup: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:brainstorm-stack: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:build-stack: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:closeout-stack: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:commit: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:compound: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:design-stack: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:development-protocol: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:devilsadvocate: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:karpathy: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:pathway: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:planning-stack: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:relentless: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:research-stack: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:review-stack: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:ship: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:simplify: source fingerprint recorded for drift monitoring; this is not a re-port
- skill:visual-spec: source fingerprint recorded for drift monitoring; this is not a re-port
