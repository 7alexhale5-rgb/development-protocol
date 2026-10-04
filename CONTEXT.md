# development-protocol: workspace context

## Purpose and boundary

This system-map organizes the work named in [the project map](CLAUDE.md).
It connects the existing rooms below; source and tooling paths stay where they are.

- [Bundled skills and their ports](skills/CONTEXT.md)
- [The standard, workflow and daily-use docs](docs/CONTEXT.md)
- [Test suite, sanitization and private scans](tests/CONTEXT.md)
- [Drift lock against upstream sources](sync/CONTEXT.md)
- [Plugin and marketplace manifests](.claude-plugin/CONTEXT.md)
- [Continuous integration](.github/CONTEXT.md)
- [Maintainer release checks](scripts/CONTEXT.md)

## Start or resume work

Read the project map, then the contract for the task. Check its Inputs before writing.
Use its Process, output path and Human check; stop if a required input is absent.
Resume the existing named task or record rather than starting a duplicate.

## Stable rules and changing work

The map and room contracts define routing and review rules. Working artifacts stay
in each room's Outputs locations. Preserve existing source, records and tooling paths.
New filing does not authorize moves, publication or changes to approved decisions.

## Status and first check

Read the newest entries in [UPDATES.md](UPDATES.md) and [CHANGELOG.md](CHANGELOG.md), then compare
their claims with current files and tests. A file existing is not approval or proof of current
operation.

From this checkout, run `git status`, `python3 -m unittest discover tests`,
`bash tests/sanitization.sh` and `python3 skills/icm/scripts/icm_check.py .`. Use this worktree's path when checking a branch.
Record the command and result in the task receipt; keep failed work open.
