# Keeping the stack current

## For everyone

```bash
cd development-protocol && git pull && ./install.sh --yes && ./health-check.sh
```

Plugin users: `/plugin marketplace update development-protocol`. Read `CHANGELOG.md` for what
changed and `UPDATES.md` for the item-by-item log.

## For maintainers

The skills here are ports of a private working setup. When a source skill changes:

1. A drift check on the maintainer's machine compares each source with `sync/sources.lock.json`
   (hashes only; no private content lives in this repo). That file does not exist until the first
   drift check records it; there is nothing to compare against before then.
2. Each drifted item is re-ported by an agent under `docs/PORTING.md`.
3. `python3 -m unittest discover tests` and `bash tests/sanitization.sh` must pass.
4. The lock is updated, `UPDATES.md` gets a dated entry per item, and `CHANGELOG.md` gets a version
   line for anything a user would notice.
5. Commit on a branch, open a pull request, merge when CI is green.

The drift check runs weekly. A private file is never copied into this repo; a changed source only
triggers a re-port.
