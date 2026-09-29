# Setup

About ten minutes. Works on macOS and Linux. Windows works through WSL.

## 1. What you need

| Need | Why | Check |
| --- | --- | --- |
| Claude Code or Codex (or both) | runs the skills | `claude --version` / `codex --version` |
| Python 3.9 or newer | the checklist, pathway, research and sweep tools | `python3 --version` |
| git | branches, commits, fresh-main checks | `git --version` |
| GitHub CLI `gh` (optional) | `/ship` reads CI results with it | `gh auth status` |

## 2. Install

Pick one.

**Plugin (Claude Code, updates with the repo):**

```text
/plugin marketplace add 7alexhale5-rgb/development-protocol
/plugin install development-protocol@development-protocol
```

Plugin commands may show with a prefix, for example `/development-protocol:karpathy`.

**Installer (Claude Code and Codex):**

```bash
git clone https://github.com/7alexhale5-rgb/development-protocol.git
cd development-protocol
./install.sh --dry-run     # see what it would do
./install.sh               # asks before replacing anything
```

Options: `--target claude|codex|both` (default both), `--yes` to skip the question,
`--skip-backup` (not recommended). Existing skills with the same names are moved to
`~/.devproto-stack/backup-<time>/` first. `./uninstall.sh` removes the stack and puts them back.

Clone somewhere other than your skills folder. The installer refuses to run from inside it.

## 3. Check it

```bash
./health-check.sh
```

Every line should say PASS. Then restart your agent so it loads the new skills.

## 4. First run

In a real repository:

```text
/development-protocol . "Add a CSV export to the reports page. Done when a 10,000-row export opens in a spreadsheet."
```

The agent creates `.devproto/` in the repo, walks the rows, and reports after each one.

## 5. Optional services

The research skill works on free sources. These make it stronger:

- A scraping API key (for example Firecrawl) for clean page text.
- A search-answer API key (for example Perplexity) with a small prepaid balance.

Keep keys in your password manager or your shell's secret store. Never paste them into chat or
commit them.

Next: `docs/DAILY-USE.md`.
