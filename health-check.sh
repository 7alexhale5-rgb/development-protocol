#!/usr/bin/env bash
# Check that the development-protocol stack is installed and working.
# Usage: ./health-check.sh [--target claude|codex|both]   Exit 0 healthy, 1 problems.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="both"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      [[ $# -ge 2 ]] || { echo "--target needs a value (claude|codex|both)" >&2; exit 2; }
      target="$2"; shift 2 ;;
    -h|--help) echo "usage: $0 [--target claude|codex|both]"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
case "$target" in
  claude) roots=("$HOME/.claude/skills") ;;
  codex)  roots=("$HOME/.agents/skills") ;;
  both)   roots=("$HOME/.claude/skills" "$HOME/.agents/skills") ;;
  *) echo "--target must be claude, codex or both" >&2; exit 2 ;;
esac

pass=0; fail=0; warn=0
ok()   { echo "  PASS  $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL  $1"; fail=$((fail+1)); }
note() { echo "  WARN  $1"; warn=$((warn+1)); }

echo "Tools"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null \
  && ok "python3 3.9 or newer" || bad "python3 3.9 or newer is required"
command -v git >/dev/null && ok "git" || note "git not found (ship and closeout need it)"
command -v gh  >/dev/null && ok "gh (GitHub CLI)" || note "gh not found (optional; ship reads CI with it)"

skills=()
for d in "$here"/skills/*/; do [[ -f "$d/SKILL.md" ]] && skills+=("$(basename "$d")"); done

for root in "${roots[@]}"; do
  echo "Skills in $root"
  for s in "${skills[@]}"; do
    f="$root/$s/SKILL.md"
    if [[ ! -f "$f" ]]; then bad "$s missing"; continue; fi
    name="$(awk '/^---/{n++; next} n==1 && /^name:/{sub(/^name:[ ]*/,""); print; exit}' "$f")"
    if [[ "$name" != "$s" ]]; then bad "$s: frontmatter name is '$name'"; continue; fi
    while IFS= read -r asset; do
      relative="${asset#"$here/skills/$s/"}"
      if [[ ! -f "$root/$s/$relative" ]]; then
        bad "$s: required asset missing: $relative"
      elif ! cmp -s "$asset" "$root/$s/$relative"; then
        bad "$s: installed asset differs: $relative"
      fi
    done < <(find "$here/skills/$s" -type d -name '__pycache__' -prune -o -type f ! -name 'SKILL.md' -print)
    if cmp -s "$f" "$here/skills/$s/SKILL.md"; then ok "$s"; else note "$s differs from this repo copy (older install? re-run install.sh)"; fi
  done
  dp="$root/development-protocol/scripts/devproto.py"
  if [[ -f "$dp" ]]; then
    tmp="$(mktemp -d)"
    if python3 "$dp" --project "$tmp" start --goal "health check" --id hc >/dev/null 2>&1 \
       && python3 "$dp" --project "$tmp" status --id hc >/dev/null 2>&1; then
      ok "checklist tool runs"
    else
      bad "checklist tool failed to start a work item"
    fi
    rm -rf "$tmp"
  else
    bad "required checklist tool missing"
  fi
  pathway="$root/pathway/scripts/pathway.py"
  if [[ -f "$pathway" ]]; then
    tmp="$(mktemp -d)"
    if python3 "$pathway" --project "$tmp" doctor >/dev/null 2>&1; then
      ok "pathway tool runs"
    else
      bad "pathway tool failed its doctor check"
    fi
    rm -rf "$tmp"
  else
    bad "required pathway tool missing"
  fi
done

echo
echo "health check: $pass passed, $fail failed, $warn warnings"
[[ $fail -eq 0 ]]
