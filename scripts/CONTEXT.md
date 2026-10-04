# Maintainer scripts room: release checks

One job: hold the maintainer-only checks that guard a release. Nothing here is installed:
`install.sh` copies only `skills/<name>/` folders. Paths relative to the repo root.

## Inputs

- `.claude-plugin/plugin.json`: the one place the plugin `version` lives.
- The pull request's base branch (CI passes `origin/<base>`). Missing base ref: the check
  exits 2 and the CI step fails; it never passes silently.
- `CHANGELOG.md`: the newest version line a bump must match.

## Process

1. `python3 scripts/check_version_bump.py --base origin/main` compares the branch with its base.
   A change under `skills/` or `.claude-plugin/` whose version matches the base's current version
   or the version where the branch started exits 1.
2. Scripts are Python 3.9+ standard library only, each with a unit test under `tests/`
   (`tests/test_check_version_bump.py`).
3. A new check added here goes into `.github/workflows/ci.yml` in the same change.

## Outputs

- `scripts/check_version_bump.py`: exit 0 no shipped change or the version changed, 1 a
  shipped change without a bump, 2 could not measure.

## Human check

The maintainer reads the `version` job on the pull request. Pass: green, and the new version
matches the `CHANGELOG.md` entry. Fail: bump `.claude-plugin/plugin.json` before merge.
