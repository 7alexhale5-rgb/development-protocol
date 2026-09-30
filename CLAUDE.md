# development-protocol

> Status: active | Type: infra (public AI dev stack)

Plug-and-play AI development stack for Claude Code and Codex: 19 skills that take software
work from idea to shipped, plus a `/development-protocol` conductor that runs 17 rows in
order and will not call a row done without an evidence file and a green verifier.

## Where to go

| Task                                               | Go to        | Read                                         | Skills           |
| -------------------------------------------------- | ------------ | -------------------------------------------- | ---------------- |
| Add, edit, or sanitize one of the 19 skills        | `skills/`    | [skills/CONTEXT.md](skills/CONTEXT.md)       | `/build-stack`   |
| Update install/setup/workflow/troubleshooting docs | `docs/`      | [docs/CONTEXT.md](docs/CONTEXT.md)           | none             |
| Run or add a test (unit, sanitization, install)    | `tests/`     | [tests/CONTEXT.md](tests/CONTEXT.md)         | none             |
| Pick up a Codex handoff or in-flight state         | `.planning/` | [.planning/CONTEXT.md](.planning/CONTEXT.md) | `/handoff-codex` |

Root files stay where their tools expect them: `install.sh` / `uninstall.sh` / `health-check.sh`
(README-documented entry points), `.claude-plugin/marketplace.json` + `plugin.json` (Claude Code
plugin registration), `sync/`, `.devproto/` (state dir named by `.gitignore`).

## Naming

Skill folders `kebab-case` under `skills/`, docs `UPPERCASE.md` under `docs/` (existing
convention), tests `test_<module>.py`.
