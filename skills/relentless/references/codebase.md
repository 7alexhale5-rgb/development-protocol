# Codebase sweeps

Files, symbols and call sites in a repository: "find every place X happens", "read the
whole module", "which of these files still do Y".

## Build the universe from the repo, not the disk

- Tracked files: `git ls-files -- '*.py' '*.ts'`. Never `find .` inside a repo: it walks
  `.git`, `node_modules` and build output, and the universe fills with noise.
- Untracked work that matters too: `git ls-files --others --exclude-standard -- '*.py'`,
  added as a second enumeration.
- Outside git: `rg --files -g '*.py'`. It honours `.gitignore`. Add `--hidden` for
  dotfiles, and use `--no-ignore` only on purpose, saying so in the goal. Without ripgrep,
  `find . -name '*.py' -not -path '*/node_modules/*'` works, but name every exclusion.
- Call sites and usages: `rg -n --no-heading 'old_name\(' -g '*.py'`. The ids become
  `path:line`, which is what a reviewer needs. `rg` exits 1 for a real zero and 2 for an
  error. The ledger refuses the error and asks you to confirm the zero.
- Config and entry points belong in the universe as their own enumeration: settings files,
  CI workflows, hooks, cron and scheduler jobs, package scripts. Code that is only reached
  from config is exactly what a file-only sweep misses.

## Traps

- **Vendored and generated code.** Exclude it in the command and name the exclusion in the
  done condition, or defer it with the reason. Never drop it silently.
- **Submodules.** `git ls-files` does not recurse into them. Enumerate each with
  `git submodule foreach --quiet 'git ls-files | sed "s|^|$sm_path/|"'`.
- **Dynamic references.** String-built imports, `getattr`, reflection, template names and
  route tables do not show up in a grep. They are the reason the floor is L2 rather than
  "grep hit".
- **Truncation.** Do not pipe a universe through `head`. The enumeration runs with pipefail,
  and a cut-off list is not a universe.
- **Very large files.** Read them in parts and name the ranges in the evidence.

## What the depths mean here

- L1: a grep hit or a filename.
- L2: the whole file read. Evidence names what the file does and the lines that matter.
- L3: traced. Callers found with `rg`, imports followed, the tests and config that load it
  read. Evidence names the callers and tests.
- L4: exercised. The code or its test was run. Evidence is the command and its output.

"Find every instance of a pattern" wants L2 on every file, plus L3 on helpers the pattern
flows through (a helper that does the bad thing makes every caller an instance). A behaviour
audit wants L3. "Does it still work" wants L4.

## Done conditions

- "Every tracked `*.py` under `src/` read at L2; every hit of the pattern classified as an
  instance or a decoy, with the reason."
- When the job ends in a state, give `close` a command:
  `--done-cmd '! rg -q "str\(ts\)\[:10\]" src/'`.

## Pairs with

`/review-stack` for quality review of what the sweep finds. If your team has a call-graph
tool, use it to find L3 edges faster, and still record each visit.
