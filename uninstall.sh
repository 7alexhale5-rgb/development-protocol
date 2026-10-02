#!/usr/bin/env bash
# Remove the development-protocol stack and restore any skills it replaced.
# Usage: ./uninstall.sh [--dry-run] [--yes]
set -euo pipefail

stamp="$(date +%Y%m%d-%H%M%S)"
state_dir="$HOME/.devproto-stack"
manifest="$state_dir/installed.txt"
hashes="$state_dir/hashes.txt"
dry_run=0; assume_yes=0

# Same tree hash install.sh records at install time: path + content of every
# file under dest, __pycache__ excluded. Used to tell whether the whole
# installed skill (not just its SKILL.md) was edited after install.
tree_hash() {
  python3 -c '
import hashlib, os, sys
root = sys.argv[1]
h = hashlib.sha256()
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
    for name in sorted(filenames):
        path = os.path.join(dirpath, name)
        h.update(os.path.relpath(path, root).encode())
        with open(path, "rb") as f:
            h.update(f.read())
print(h.hexdigest())
' "$1"
}

get_hash() {
  [[ -f "$hashes" ]] && grep -F "$(printf '%s\t' "$1")" "$hashes" | tail -1 | cut -f2-
}
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) dry_run=1; shift ;;
    --yes|-y) assume_yes=1; shift ;;
    -h|--help) echo "usage: $0 [--dry-run] [--yes]"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
run() { if [[ $dry_run -eq 1 ]]; then echo "[dry-run] $*"; else "$@"; fi; }

[[ -f "$manifest" ]] || { echo "Nothing to remove: no install record at $manifest"; exit 0; }

echo "Will remove:"; sed 's/^/  /' "$manifest"
if [[ $assume_yes -eq 0 && $dry_run -eq 0 ]]; then
  # R3-8: a closed stdin makes `read` hit EOF immediately; without this it
  # falls through to whatever comes next instead of stopping cleanly.
  read -r -p "Continue? [y/N] " answer || { echo "no input to read; re-run with --yes" >&2; exit 2; }
  [[ "$answer" =~ ^[Yy]$ ]] || { echo "Nothing changed."; exit 0; }
fi

changed_dir=""
while IFS= read -r dest; do
  [[ -n "$dest" && -e "$dest" ]] || continue
  name="$(basename "$dest")"
  stored_hash="$(get_hash "$dest" || true)"
  # No stored hash (never a clean install, e.g. a crashed copy) is nothing to
  # compare against: just remove it. A stored hash that no longer matches the
  # whole tree on disk (not just SKILL.md) means it was edited after install.
  if [[ -n "$stored_hash" ]] && [[ "$stored_hash" != "$(tree_hash "$dest")" ]]; then
    [[ -n "$changed_dir" ]] || changed_dir="$state_dir/uninstall-changed-$stamp"
    saved="$changed_dir/$(basename "$(dirname "$(dirname "$dest")")")/$name"
    run mkdir -p "$(dirname "$saved")"
    run mv "$dest" "$saved"
    # R3-5: dry-run must never claim the move already happened.
    if [[ $dry_run -eq 1 ]]; then
      echo "[dry-run] would keep changed copy: $name differs from the installed version, would save to $saved"
    else
      echo "kept changed copy: $name differs from the installed version, saved to $saved"
    fi
  else
    run rm -rf "$dest"
    if [[ $dry_run -eq 1 ]]; then
      echo "[dry-run] would remove: $dest"
    else
      echo "removed: $dest"
    fi
  fi
done < "$manifest"

# Removal is complete. Persist that before restoring anything: a retry must
# never mistake a restored original for an unhashed partial installation.
# Keep the empty manifest until restoration finishes, so retries still restore.
[[ $dry_run -eq 1 ]] || : > "$manifest"

# Restore backups, oldest first, so the first thing that was replaced comes back.
if [[ -f "$state_dir/backups.txt" ]]; then
  while IFS= read -r bstamp; do
    restore="$state_dir/backup-$bstamp/restore.tsv"
    [[ -f "$restore" ]] || continue
    while IFS=$'\t' read -r original saved; do
      if [[ -e "$saved" && ! -e "$original" ]]; then
        run mv "$saved" "$original"
        if [[ $dry_run -eq 1 ]]; then
          echo "[dry-run] would restore: $original"
        else
          echo "restored: $original"
        fi
      fi
    done < "$restore"
  done < "$state_dir/backups.txt"
fi

# R3-3: edited stack copies (edited.tsv) are reported so the operator knows
# where local edits went, but are never restored onto the live path -- that
# is reserved for genuine pre-existing user skills in restore.tsv above.
if [[ -f "$state_dir/edited.tsv" ]]; then
  while IFS=$'\t' read -r original saved; do
    [[ -n "$original" ]] || continue
    echo "kept edited copy: $original is not being restored; it is saved at $saved"
  done < "$state_dir/edited.tsv"
fi

if [[ $dry_run -eq 1 ]]; then
  echo "[dry-run] would be done here; nothing was changed."
else
  rm -f "$manifest" "$state_dir/backups.txt" "$hashes"
  echo "Done. Backups that could not be restored stay under $state_dir/."
fi
