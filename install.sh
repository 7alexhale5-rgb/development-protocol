#!/usr/bin/env bash
# Install the development-protocol stack: 19 skills for Claude Code and/or Codex.
# Safe to re-run. Any existing skill with the same name is backed up first.
set -Eeuo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
stamp="$(date +%Y%m%d-%H%M%S)"
state_dir="$HOME/.devproto-stack"
manifest="$state_dir/installed.txt"
stamp_written=0

err_trap() {
  local rc=$?
  echo >&2
  echo "install.sh failed (exit $rc)." >&2
  if [[ -d "$state_dir/backup-$stamp" ]]; then
    echo "Skills backed up so far are under: $state_dir/backup-$stamp" >&2
    echo "Restore what was backed up with: ./uninstall.sh --yes" >&2
    echo "or by hand with its restore.tsv, e.g.:" >&2
    echo "  while IFS=\$'\t' read -r o s; do mv \"\$s\" \"\$o\"; done < \"$state_dir/backup-$stamp/restore.tsv\"" >&2
  fi
}
trap err_trap ERR

target="both"; dry_run=0; assume_yes=0; skip_backup=0

usage() {
  cat <<EOF
Install the development-protocol stack.

Usage: ./install.sh [--target claude|codex|both] [--dry-run] [--yes] [--skip-backup]

  --target       where to install (default: both)
                   claude -> ~/.claude/skills/
                   codex  -> ~/.agents/skills/
  --dry-run      print what would happen, change nothing
  --yes, -y      do not ask before replacing skills that already exist
  --skip-backup  replace existing skills without backing them up (not recommended)

Undo with ./uninstall.sh. Check with ./health-check.sh.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      [[ $# -ge 2 ]] || { echo "--target needs a value (claude|codex|both)" >&2; exit 2; }
      target="$2"; shift 2 ;;
    claude|codex|both) target="$1"; shift ;;   # old positional form still works
    --dry-run) dry_run=1; shift ;;
    --yes|-y) assume_yes=1; shift ;;
    --skip-backup) skip_backup=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$target" in
  claude) roots=("$HOME/.claude/skills") ;;
  codex)  roots=("$HOME/.agents/skills") ;;
  both)   roots=("$HOME/.claude/skills" "$HOME/.agents/skills") ;;
  *) echo "--target must be claude, codex or both" >&2; exit 2 ;;
esac

run() { if [[ $dry_run -eq 1 ]]; then echo "[dry-run] $*"; else "$@"; fi; }

# A dest already recorded in the manifest is our own previous install, not a
# user's pre-existing skill, so it gets replaced without a fresh backup
# (unless its content has drifted from what we installed; see tree_hash below).
is_ours() { [[ -f "$manifest" ]] && grep -qxF "$1" "$manifest"; }

hashes="$state_dir/hashes.txt"

# Deterministic hash of a skill's on-disk tree (path + content of every file,
# __pycache__ excluded), used to tell "repo updated" from "user edited" so a
# re-install or uninstall never silently destroys a local edit. python3 (not
# sha256sum/shasum, which are not both guaranteed present) is already required.
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

set_hash() {
  local tmp="$hashes.tmp.$$"
  [[ -f "$hashes" ]] && grep -vF "$(printf '%s\t' "$1")" "$hashes" > "$tmp" || : > "$tmp"
  printf '%s\t%s\n' "$1" "$2" >> "$tmp"
  mv "$tmp" "$hashes"
}

# ---- preflight --------------------------------------------------------------
command -v python3 >/dev/null || { echo "python3 is required (3.9 or newer)" >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
  || { echo "python3 is too old; 3.9 or newer is required" >&2; exit 1; }
command -v git >/dev/null || echo "note: git not found; ship and closeout steps need it"

skills=()
for d in "$here"/skills/*/; do
  [[ -f "$d/SKILL.md" ]] && skills+=("$(basename "$d")")
done
[[ ${#skills[@]} -gt 0 ]] || { echo "no skills found under $here/skills" >&2; exit 1; }

# R3-4: a symlinked skills root (or skills/ itself symlinked in from $here)
# would make $root/$s and $here/skills/$s the same file on disk -- installing
# would then read from and write to the same tree at once. realpath, not the
# string-prefix check above, is what actually catches that.
same_path() {
  python3 -c '
import os, sys
a, b = sys.argv[1], sys.argv[2]
sys.exit(0 if os.path.exists(a) and os.path.exists(b) and os.path.realpath(a) == os.path.realpath(b) else 1)
' "$1" "$2"
}

for root in "${roots[@]}"; do
  for s in "${skills[@]}"; do
    case "$here/" in "$root/$s"/*)
      echo "refusing: this repo is inside $root/$s. Clone it somewhere else first." >&2
      exit 1 ;;
    esac
    if same_path "$root/$s" "$here/skills/$s"; then
      echo "refusing: $root/$s and $here/skills/$s are the same path on disk (a symlinked skills root?). Clone this repo somewhere else first." >&2
      exit 1
    fi
  done
done

# ---- confirm replacements -----------------------------------------------------
existing=()
for root in "${roots[@]}"; do
  for s in "${skills[@]}"; do
    [[ -e "$root/$s" ]] && existing+=("$root/$s")
  done
done
# R3-2: the existing-skills list is shown even with --yes, so a silent
# --yes run still tells the operator what it is about to touch.
if [[ ${#existing[@]} -gt 0 && $dry_run -eq 0 ]]; then
  echo "These skills already exist and will be replaced:"
  printf '  %s\n' "${existing[@]}"
  [[ $skip_backup -eq 1 ]] || echo "Any that are not already this stack's own copy will be backed up to $state_dir/backup-$stamp/ first."
  if [[ $assume_yes -eq 0 ]]; then
    read -r -p "Continue? [y/N] " answer || { echo "no input to read; re-run with --yes" >&2; exit 2; }
    [[ "$answer" =~ ^[Yy]$ ]] || { echo "Nothing changed."; exit 0; }
  fi
fi

# ---- install ------------------------------------------------------------------
run mkdir -p "$state_dir"
for root in "${roots[@]}"; do
  run mkdir -p "$root"
  for s in "${skills[@]}"; do
    dest="$root/$s"
    dest_was_ours=0
    is_ours "$dest" && dest_was_ours=1
    edited=0
    if [[ -e "$dest" && $dest_was_ours -eq 1 ]]; then
      stored_hash="$(get_hash "$dest" || true)"
      # No stored hash means we never finished a clean install of this dest
      # before (e.g. a crashed copy) -- there is nothing to compare, so it is
      # safe to overwrite. A stored hash that no longer matches means the
      # installed copy was edited since: back it up like a real user skill.
      [[ -n "$stored_hash" && "$stored_hash" != "$(tree_hash "$dest")" ]] && edited=1
    fi
    if [[ -e "$dest" ]] && [[ $edited -eq 1 ]] && [[ $skip_backup -eq 0 ]]; then
      # R3-3: an edited stack copy is ours, but no longer what we installed.
      # It must never be restored by uninstall's restore.tsv step (that step
      # is for genuine pre-existing user skills) -- so it gets its own
      # edited-<stamp> dir and edited.tsv, never backup-<stamp>/restore.tsv.
      edir="$state_dir/edited-$stamp/$(basename "$(dirname "$root")")"
      run mkdir -p "$edir"
      run mv "$dest" "$edir/$s"
      [[ $dry_run -eq 1 ]] || echo "$dest	$edir/$s" >> "$state_dir/edited.tsv"
      if [[ $dry_run -eq 1 ]]; then
        echo "[dry-run] would back up edited copy: $dest -> $edir/$s"
      else
        echo "backed up edited copy: $dest -> $edir/$s"
      fi
    elif [[ -e "$dest" ]] && [[ $dest_was_ours -eq 0 ]] && [[ $skip_backup -eq 0 ]]; then
      bdir="$state_dir/backup-$stamp/$(basename "$(dirname "$root")")"
      run mkdir -p "$bdir"
      if [[ $dry_run -eq 0 && $stamp_written -eq 0 ]]; then
        echo "$stamp" >> "$state_dir/backups.txt"
        stamp_written=1
      fi
      run mv "$dest" "$bdir/$s"
      [[ $dry_run -eq 1 ]] || echo "$dest	$bdir/$s" >> "$state_dir/backup-$stamp/restore.tsv"
      # R3-2: print for every backup, not only edited ones, so a silent
      # --yes run still says what it replaced.
      if [[ $dry_run -eq 1 ]]; then
        echo "[dry-run] would back up: $dest -> $bdir/$s"
      else
        echo "backed up: $dest -> $bdir/$s"
      fi
    else
      run rm -rf "$dest"
    fi
    # Recorded before the copy: from this moment $dest is ours, so a crash
    # partway through cp leaves a partial directory that the next run
    # recognizes as its own (safe to replace) rather than a user's skill.
    if [[ $dry_run -eq 0 ]]; then
      touch "$manifest"
      grep -qxF "$dest" "$manifest" || echo "$dest" >> "$manifest"
    fi
    run cp -R "$here/skills/$s" "$dest"
    run find "$dest" -name '__pycache__' -type d -prune -exec rm -rf {} +
    [[ $dry_run -eq 0 ]] && set_hash "$dest" "$(tree_hash "$dest")"
    # R3-5: dry-run must never claim to have done something it didn't.
    if [[ $dry_run -eq 1 ]]; then
      echo "[dry-run] would install: $dest"
    else
      echo "installed: $dest"
    fi
  done
done

if [[ $dry_run -eq 0 ]]; then
  echo
  bash "$here/health-check.sh" --target "$target" || true
  echo
  echo "Done. Restart your agent, then try:"
  echo "  /development-protocol . \"<one sentence goal>\""
  echo "Read docs/DAILY-USE.md for a normal day with the stack."
else
  echo
  echo "[dry-run] would finish here; nothing was changed."
fi
