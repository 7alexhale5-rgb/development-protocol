# development-protocol

A complete, plug-and-play AI development stack for Claude Code and Codex: **19 skills that take
software work from idea to shipped, and a checklist that will not call anything done without
proof.**

One command runs the whole thing:

```text
/development-protocol . "Add CSV export to the reports page. Done when a 10,000-row export opens in a spreadsheet."
```

It walks 17 rows in order: pathway, brainstorm, research, spec, planning, visual spec, design,
premortem, audit setup, build, verify, review, simplify, commit, ship, compound, closeout. Each row
hands off to a skill that owns the method. A row passes only when an evidence file exists and a
verifier command exits 0. Change the evidence later and the row reopens.

Agents (and people) say "done" too early. This stack makes "done" mean the result is readable,
repeatable, and tied to the file or commit it claims to prove.

A repo with no `origin` remote and no pull request cannot reach 17/17 by design: `ship`'s proof is
a PR check, so rows 15 (ship), 16 (compound) and 17 (closeout) stay `blocked`, correctly, until
one exists. That is not a bug if you are testing locally -- push a branch and open a pull request
to unblock them.

## Install

**Claude Code plugin:**

```text
/plugin marketplace add 7alexhale5-rgb/development-protocol
/plugin install development-protocol@development-protocol
```

**Installer (Claude Code and Codex):**

```bash
git clone https://github.com/7alexhale5-rgb/development-protocol.git
cd development-protocol
./install.sh            # backs up any skill it replaces; --dry-run to preview
./health-check.sh       # every line should say PASS
```

Restart your agent afterward. `./uninstall.sh` removes everything and restores what it replaced.
Full guide: [docs/SETUP.md](docs/SETUP.md).

Needs Python 3.9+ and git. No packages to install; every script is standard library only.

## What is inside

| Skill                   | Role                                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------------------ |
| `/development-protocol` | The conductor: runs the 17 rows, keeps the checklist, reports                                    |
| `/pathway`              | Starts each piece of work, picks the lane, tracks one work id                                    |
| `/brainstorm-stack`     | Surfaces the real goal and the decisions before planning                                         |
| `/research-stack`       | Multi-source research with cited, corroborated findings (free sources by default)                |
| `/karpathy`             | `spec`: pin the goal and the check first. `verify`: second-model critic plus real-artifact proof |
| `/planning-stack`       | A plan in 3 to 5 phases, each with a number that proves it moved                                 |
| `/visual-spec`          | Screens, flows and data mapped and machine-checked before UI is built                            |
| `/design-stack`         | UI design, refactor and critique against the spec                                                |
| `/devilsadvocate`       | Claim checking, and `--premortem`: how this fails and the guard for each                         |
| `/audit-setup`          | CI and quality checks in the repo before the build                                               |
| `/build-stack`          | Builds one slice at a time with a check after each                                               |
| `/review-stack`         | Hypercritical four-layer review with runtime checks                                              |
| `/simplify`             | Removes what the change does not need                                                            |
| `/commit`               | Clean commits that say why                                                                       |
| `/ship`                 | Proves the exact merge commit: green CI on that SHA                                              |
| `/compound`             | Turns what happened into lessons the next person finds                                           |
| `/closeout-stack`       | Commit, ship, handoff, lessons, and a resume prompt                                              |
| `/relentless`           | Coverage ledger for exhaustive sweeps, so nothing is missed                                      |
| `/1pct`                 | Stops hedging on approved work; executes the next step                                           |

## Read next

| Doc                                                     | What it covers                                                                                                              |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| [docs/STANDARD.md](docs/STANDARD.md)                    | The one-page standard: the spine, task sizes, lanes, gates                                                                  |
| [docs/WORKFLOW.md](docs/WORKFLOW.md)                    | How the work flows: plan first, phases, primary and worker sessions, resume prompts, second-model review, branches and team |
| [docs/DAILY-USE.md](docs/DAILY-USE.md)                  | A normal day with the stack                                                                                                 |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)      | Symptoms and fixes                                                                                                          |
| [docs/UPDATING.md](docs/UPDATING.md)                    | Staying current, and how updates are made and logged                                                                        |
| [docs/PORTING.md](docs/PORTING.md)                      | Rules for changing or adding a skill                                                                                        |
| [CHANGELOG.md](CHANGELOG.md) / [UPDATES.md](UPDATES.md) | What changed, by version and by item                                                                                        |

## The checklist by hand

The agent drives it, but you can too. The path below is for the **installer** path
(`./install.sh`), which puts it at `~/.claude/skills/development-protocol/scripts/devproto.py`. A
**plugin** install caches skills under `~/.claude/plugins/` instead, at a path Claude Code manages;
find it with `find ~/.claude/plugins -name devproto.py 2>/dev/null`.

```bash
devproto() { python3 ~/.claude/skills/development-protocol/scripts/devproto.py "$@"; }
devproto steps                                   # the 17 rows and their skills
devproto start --goal "Fix typo in footer" --id footer-typo
devproto status --id footer-typo
devproto check --id footer-typo                  # exit 0 only when every row is passed or n/a
devproto check --id footer-typo --through commit # pre-merge gate
```

The `devproto() { ... }` function form (not a `D=` string variable) is deliberate: zsh, macOS's
default shell, does not word-split an unquoted variable, so a `D="python3 ...";  $D steps` style
line fails with "command not found" there even though it works in bash.

`--project <folder>` and `--json` go before the subcommand. What it guards against, honestly: an
agent claiming "done" by accident. It is not tamper-proof; `status` prints every verifier so a
person can spot a weak one.

## Tests

```bash
python3 -m unittest discover tests
bash tests/sanitization.sh
```

CI runs both on Linux and macOS with Python 3.9 and 3.13, then installs into a clean home folder and
runs the health check.

## Provenance

Built by Alex Hale (PrettyFly, prettyflyforai.com) from the development practice he runs every day,
ported so it works on any machine. The dated lessons inside the skills are the reasons each rule
exists; keep them when you edit. Companion: the Gravity Stack environment blueprint at
https://github.com/7alexhale5-rgb/gravity-stack.

## License

MIT. See [LICENSE](LICENSE).
