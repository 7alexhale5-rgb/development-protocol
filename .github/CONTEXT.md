# CI room: the pull request gate

One job: run the same checks on every pull request and push to `main` with no agent present.
Paths relative to the repo root.

## Inputs

- `.github/workflows/ci.yml`: a `test` job on `ubuntu-latest` and `macos-latest` with Python
  3.9 and 3.13, and a `version` job on pull requests only.
- The checks it runs: `python3 -m unittest discover tests -v`, `bash tests/sanitization.sh`, then
  `./install.sh --yes --target both`, `./health-check.sh --target both` and `./uninstall.sh --yes`
  in a clean temporary `HOME`. The `version` job checks out full history and runs
  `python3 scripts/check_version_bump.py --base "origin/$BASE_REF"` (see
  [scripts/CONTEXT.md](../scripts/CONTEXT.md)).

## Process

1. Pin every action by full 40-character commit SHA with the version in a comment, and keep
   `permissions: contents: read`. `tests/test_package.py` fails otherwise.
2. A new check added to the repo goes in this workflow in the same change.
3. Keep Python 3.9 in the matrix: it is the oldest version the stack supports.

## Outputs

- Edited `.github/workflows/ci.yml`.

## Human check

The maintainer reads the CI run on the pull request head commit. Pass: every matrix job is green.
Fail: blocks merging.
