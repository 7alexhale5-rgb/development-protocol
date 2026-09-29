#!/usr/bin/env python3
"""Stop hook: /1pct red-flag detector (v3.1).

Reads the Claude Code or Codex transcript after the assistant's turn ends,
scans the last assistant message for the hedging phrases the skill bans, and logs
each violation as one JSON line to <home>/.devproto-stack/logs/1pct-violations.log
(mode 0600).

By default this hook is NON-BLOCKING (exit 0): it measures, it does not enforce.
Set ONE_PCT_STRICT=1 to enable blocking mode (exit 2 with feedback), which asks
the agent to rewrite the offending turn before it is finalized.

Install it as a Stop hook in your agent's settings, for example in Claude Code:
  {
    "hooks": {
      "Stop": [{"hooks": [{"type": "command", "command": "python3 /path/to/1pct-check.py"}]}]
    }
  }

Env vars:
  ONE_PCT_STRICT=1       block on violation (exit 2). DIAGNOSTIC ONLY. Strict mode blocks
                         the entire assistant turn from being finalized, so a single
                         false-positive flag costs the user a whole turn. Scope it to one
                         project or session (a local settings file), NOT a global shell
                         export.
  ONE_PCT_LOG_DIR=path   override the log folder
  ONE_PCT_DISABLE=1      disable entirely (exit 0, no-op)

Security hardening (v3.1):
  - transcript_path must sit inside the Claude Code or Codex home folder
    (<home>/.claude or <home>/.codex); anything else is ignored (rejects path traversal)
  - log file mode set to 0600 (owner read/write only), so a shared machine does not
    leak what was flagged
  - the logged transcript path is redacted to {parent_dir}/{filename}
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import stat
import sys
import time

# --- Red-flag patterns (extracted from SKILL.md "Red flags" section) ---
# Each tuple: (label, compiled regex). Patterns are word-boundary-anchored where
# possible. Case-insensitive. Multiline: operate on the full last assistant message.
_FLAGS: list[tuple[str, re.Pattern]] = [
    ("ready-to-implement", re.compile(r"\bReady to implement\b[.!?]*\s*\??", re.I)),
    ("ready-to-proceed",   re.compile(r"\bReady to proceed\b[.!?]*\s*\??", re.I)),
    ("would-you-like",     re.compile(r"\bWould you like me to\b", re.I)),
    ("suggested-next",     re.compile(r"\bSuggested next:\s*(\n|-\s*\w|\b[A-Za-z])", re.I)),
    ("shall-i-continue",   re.compile(r"\bShall I (continue|proceed|go ahead)\b", re.I)),
    ("fresh-session",      re.compile(r"\bin a fresh session\b", re.I)),
    ("whats-next-summary", re.compile(r"\b(?:committed|shipped|done|complete[d]?)\s+(?:at|@)\s*[A-Za-z0-9]+\.?\s*(?:what'?s next|next\??)\b", re.I)),
    ("context-as-question",re.compile(r"\bcontext\s+is\s+(?:MODERATE|DEPLETED|CRITICAL)\b[^.]*\?", re.I)),
]

# Code-fence / inline-code blocks are excluded so the skill can QUOTE its own banned
# phrases (in rationalization tables, worked examples, etc.) without self-flagging.
_CODE_FENCE = re.compile(r"```.*?```", re.S)
_INLINE_CODE = re.compile(r"`[^`\n]+`")


def _strip_code_blocks(text: str) -> str:
    """Remove fenced + inline code so the hook doesn't flag discussed patterns."""
    text = _CODE_FENCE.sub(" ", text)
    text = _INLINE_CODE.sub(" ", text)
    return text


def find_violations(text: str) -> list[str]:
    """Return list of red-flag labels that match in `text`."""
    if not text:
        return []
    stripped = _strip_code_blocks(text)
    hits: list[str] = []
    for label, pat in _FLAGS:
        if pat.search(stripped):
            hits.append(label)
    return hits


def _extract_text(content) -> str:
    """Normalize Claude/Codex message.content → plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                t = block.get("text", "")
                if isinstance(t, str):
                    parts.append(t)
        return "\n".join(parts)
    return ""


def _last_assistant_text(transcript_path: pathlib.Path) -> str:
    """Read the JSONL transcript, return text of the final assistant message."""
    try:
        lines = transcript_path.read_text(errors="replace").splitlines()
    except (OSError, UnicodeError):
        return ""
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if rec.get("type") == "assistant":
            msg = rec.get("message") or {}
            if msg.get("role") == "assistant":
                return _extract_text(msg.get("content"))
        if rec.get("type") == "response_item":
            payload = rec.get("payload") or {}
            if payload.get("role") == "assistant":
                return _extract_text(payload.get("content"))
    return ""


def _log_dir() -> pathlib.Path:
    override = os.environ.get("ONE_PCT_LOG_DIR")
    if override:
        return pathlib.Path(override)
    return pathlib.Path.home() / ".devproto-stack" / "logs"


def _redact_path(p: pathlib.Path) -> str:
    """Redact transcript path to {parent_name}/{filename}: drops the folder lineage."""
    return f"{p.parent.name}/{p.name}"


def _log_violation(transcript_path: pathlib.Path, hits: list[str]) -> None:
    d = _log_dir()
    d.mkdir(parents=True, exist_ok=True)
    log_file = d / "1pct-violations.log"
    line = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "transcript": _redact_path(transcript_path),
        "flags": hits,
    }
    with open(log_file, "a") as fh:
        fh.write(json.dumps(line) + "\n")
    # Lock log perms to owner read/write only (prevents PII leakage on shared FS).
    # Best effort: silently ignore on filesystems that don't support chmod.
    try:
        os.chmod(log_file, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _validate_transcript_path(path: pathlib.Path) -> bool:
    """Ensure transcript_path is within known agent log roots.

    Without this guard, a compromised hook stdin could pass arbitrary paths
    (a credentials folder, say) and the hook would read them.
    """
    try:
        resolved = path.resolve(strict=False)
        allowed_roots = [
            (pathlib.Path.home() / ".claude").resolve(strict=False),
            (pathlib.Path.home() / ".codex").resolve(strict=False),
        ]
        return any(resolved.is_relative_to(root) for root in allowed_roots)
    except (OSError, ValueError):
        return False


def main() -> None:
    if os.environ.get("ONE_PCT_DISABLE") == "1":
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    path_str = data.get("transcript_path") or ""
    if not path_str:
        sys.exit(0)

    transcript_path = pathlib.Path(path_str)

    # Security gate: reject paths outside known transcript roots before any read.
    if not _validate_transcript_path(transcript_path):
        sys.exit(0)

    if not transcript_path.exists():
        sys.exit(0)

    text = _last_assistant_text(transcript_path)
    hits = find_violations(text)
    if not hits:
        sys.exit(0)

    _log_violation(transcript_path, hits)

    strict = os.environ.get("ONE_PCT_STRICT") == "1"
    if strict:
        msg = (
            "[1pct] Red-flag phrases detected in response: "
            + ", ".join(hits)
            + ".\nRewrite the turn to execute the next documented plan step decisively "
            + "instead of re-asking for permission. See SKILL.md 'Red flags' section. "
            + "If a genuine stop-sign applies, name it explicitly."
        )
        print(msg, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
