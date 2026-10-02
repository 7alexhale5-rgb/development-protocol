# Sync room: the drift lock

One job: record which upstream source each port was made from, by hash only, so a changed source
triggers a re-port. Paths relative to the repo root.

## Inputs

- `sync/sources.lock.json`: one key per tracked item (`skill:<name>` for each bundled skill,
  `doc:STANDARD`, `doc:WORKFLOW`), each with a `sha256` and a `recorded` date. No private content
  lives here.
- `docs/UPDATING.md`: the maintainer loop.
- The newest `UPDATES.md` entry: it says when the lock was last updated, or why it was not.
- Missing input: the drift check runs on the maintainer's machine against private sources. It
  cannot be reproduced from this repo, so the lock is not rewritten from here.

## Process

1. The maintainer's weekly drift check compares each source with this lock.
2. Each drifted item is re-ported under `docs/PORTING.md` (see
   [skills/CONTEXT.md](../skills/CONTEXT.md)).
3. `python3 -m unittest discover tests` and `bash tests/sanitization.sh` pass.
4. The drift check re-records the hash and date for each re-ported item. A port made without it
   leaves the lock unchanged and says so in `UPDATES.md`, so drift is not hidden.
5. `UPDATES.md` gets a dated entry per item, `CHANGELOG.md` a version line for anything a user
   would notice.

## Outputs

- Edited `sync/sources.lock.json` (hashes and dates only), keys sorted.

## Human check

The maintainer confirms each changed hash came from the drift check, not a hand edit. Pass: every
re-ported item has a new hash or an `UPDATES.md` note explaining why not. Fail: revert the lock
change.
