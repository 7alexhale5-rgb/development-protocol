# Plugin room: plugin and marketplace manifests

One job: keep the Claude Code plugin and marketplace manifests valid and on the same version as
the release. Paths relative to the repo root.

## Inputs

- `.claude-plugin/plugin.json`: plugin `name`, `description`, `version`, `author`, `repository`,
  `homepage`, `license`, `keywords`.
- `.claude-plugin/marketplace.json`: the marketplace entry, with `source: "./"` (the whole repo,
  so the plugin loads `skills/` directly) and no `version`: the version lives only in
  `plugin.json`, so the two can never disagree.
- `CHANGELOG.md`: the newest version line.

## Process

1. Any change under `skills/` or `.claude-plugin/` bumps `version` in `plugin.json` and gets a
   `CHANGELOG.md` version line. Installs that sync automatically fetch a new copy only when the
   version changes; `scripts/check_version_bump.py` (CI's `version` job) fails a pull request
   that changes those paths without a bump. Never add `version` back to `marketplace.json`.
2. Keep the skill count in both descriptions equal to the folders in `skills/` that hold a
   `SKILL.md`.
3. These files are credit files: the author name and GitHub handle may appear here and nowhere
   else outside `README.md`, `docs/SETUP.md`, `docs/UPDATING.md` and `CHANGELOG.md`.
4. Run `python3 -m unittest discover tests` (`test_plugin_manifests_are_valid_json`,
   `test_version_lives_only_in_plugin_json`), `bash tests/sanitization.sh` and
   `python3 scripts/check_version_bump.py --base origin/main`.

## Outputs

- Edited `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.

## Human check

The maintainer installs from the branch with `/plugin marketplace add` and `/plugin install`.
Pass: the plugin installs at the new version and its skills load. Fail: fix before merge.
