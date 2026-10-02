# Plugin room: plugin and marketplace manifests

One job: keep the Claude Code plugin and marketplace manifests valid and on the same version as
the release. Paths relative to the repo root.

## Inputs

- `.claude-plugin/plugin.json`: plugin `name`, `description`, `version`, `author`, `repository`,
  `homepage`, `license`, `keywords`.
- `.claude-plugin/marketplace.json`: the marketplace entry, with its own `plugins[0].version` and
  `source: "./"` (the whole repo, so the plugin loads `skills/` directly).
- `CHANGELOG.md`: the newest version line.

## Process

1. A change a user would notice gets a `CHANGELOG.md` version line. Bump `version` in both
   `plugin.json` and `marketplace.json` to that same version.
2. Keep the skill count in both descriptions equal to the folders in `skills/` that hold a
   `SKILL.md`.
3. These files are credit files: the author name and GitHub handle may appear here and nowhere
   else outside `README.md`, `docs/SETUP.md`, `docs/UPDATING.md` and `CHANGELOG.md`.
4. Run `python3 -m unittest discover tests` (`test_plugin_manifests_are_valid_json`) and
   `bash tests/sanitization.sh`.

## Outputs

- Edited `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.

## Human check

The maintainer installs from the branch with `/plugin marketplace add` and `/plugin install`.
Pass: the plugin installs at the new version and its skills load. Fail: fix before merge.
