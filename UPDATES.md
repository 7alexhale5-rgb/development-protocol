# Update log

Every re-port, source baseline, and public maintenance change, newest first.

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
