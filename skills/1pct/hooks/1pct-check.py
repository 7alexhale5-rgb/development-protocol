#!/usr/bin/env python3
"""Stop hook: /1pct red-flag detector (v3.1).

Reads the Claude Code or Codex transcript after the assistant's turn ends,
scans the last assistant message for the hedging phrases the skill bans, and logs
each violation as one JSON line to <home>/.devproto-stack/logs/1pct-violations.log
(mode 0600).

By default this hook is NON-BLOCKING (exit 0): it measures, it does not enforce.
Set ONE_PCT_STRICT=1 to enable blocking mode (exit 2 with feedback), which asks
the agent to rewrite the offending turn before it is finalized.
Use strict mode only for already-authorized execution; new scope or required human
approval is not stalling. Ambiguous approval language is diagnostic-only, even in
strict mode. A second active Stop-hook pass is allowed through.

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
    ("want-me-to",         re.compile(r"\b(?:do you )?want me to\b", re.I)),
    ("should-i",           re.compile(r"\bshould I (?:go ahead|proceed|continue|start|run|merge|deploy|apply|do|open|fix|build)\b", re.I)),
    ("let-me-know",        re.compile(r"\blet me know (?:if|when|whether) you(?:'d| would)? (?:like|want)\b", re.I)),
    ("say-the-word",       re.compile(r"\b(?:say the word|just say (?:go|yes|the word))\b", re.I)),
    ("i-can-if-you-like",  re.compile(r"\bif you(?:'d| would)? like,? I (?:can|could|will)\b", re.I)),
    ("waiting-on-go",      re.compile(r"\b(?:once|when) you (?:approve|confirm|say go)\b|\bwaiting (?:on|for) your (?:go|ok|okay|approval|confirmation)\b", re.I)),
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


# Exempt explicit personal actions, never authentication/pricing topic words.
_HUMAN_ACTION = re.compile(
    r"(?:please )?(?:(?:you (?:must |need to )?)?"
    r"(?:enter|provide) your (?:password|passcode|2fa code|two-factor code|captcha)"
    r"|you (?:must )?send (?:this|the|your) (?:draft|message|email|reply)"
    r"|you (?:must )?(?:choose|set|confirm) (?:the|your) (?:price|scope|recipients?)"
    r"|(?:you (?:must |need to )?)?(?:sign|log) in to your account)[.!]?",
    re.I,
)
_BULLET = re.compile(r"\s*(?:[-*\u2022]|\d+[.)])\s+(.+)")


def _heading_level(line: str) -> int:
    match = re.match(r"^(#{1,6})[ \t]+\S", line.strip())
    return len(match.group(1)) if match else 0


def _is_next_heading(line: str) -> bool:
    """Normalize one line without overlapping optional whitespace repeats."""
    line = line.strip()
    if _heading_level(line):
        line = line.lstrip("#").strip()
    line = line.removesuffix(":").strip()
    if line.startswith("**") and line.endswith("**"):
        line = line[2:-2].strip().removesuffix(":").strip()
    return bool(re.fullmatch(r"next steps?|what'?s next", line, re.I))


def _human_only_action(item: str) -> bool:
    # Complete, bounded contextual forms; never grant an exemption by avoiding keywords.
    item=re.sub(r"\*\*([^*]+)\*\*",r"\1",item).strip()
    match=_HUMAN_ACTION.match(item)
    if match is None:return False
    tail=item[match.end():].strip().rstrip('.!?').strip()
    if not tail:return True
    action=match.group(0).casefold()
    if 'send ' in action:
        recipient=r"(?:[A-Z][\w'’-]*(?: [A-Z][\w'’-]*){0,3}|[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|(?:the|your|our) (?:team|client)|them|her|him)"
        return bool(re.fullmatch(r"(?i:to) "+recipient+r"(?:(?:, | and | & )"+recipient+r")*",tail))
    if 'confirm ' in action or 'choose ' in action or 'set ' in action:
        return bool(re.fullmatch(r"of (?:the |your |this |that )?(?:production change|project|plan|work|release|budget)",tail,re.I))
    return bool(re.fullmatch(r"(?:in|into|on|using|for) (?:the |your |same |this |that )?(?:browser|Chrome(?: profile)?|Safari|Firefox|desktop app|app|sign[- ]in (?:page|form)|login (?:page|form)|account|website|profile)",tail,re.I))


def _section_label(line: str) -> str:
    return line.strip().lstrip('#').replace('**', '').strip().rstrip(':').strip()


def _next_steps_all_human_only(text: str) -> bool:
    """Inspect every complete section, including nested subsections and loose lists."""
    lines = text.splitlines()
    levels=[]
    enclosing=1
    for line in lines:
        enclosing=_heading_level(line) or enclosing
        levels.append(enclosing)
    headings = [i for i, line in enumerate(lines) if _is_next_heading(line)]
    if not headings:
        return False
    for index in headings:
        level = levels[index]
        items = []
        continuation = False
        for position in range(index + 1, len(lines)):
            line = lines[position]
            if not line.strip():
                continuation = False
                continue
            following_level = _heading_level(line)
            if following_level:
                if following_level <= level:
                    break
                continuation = False
                if _is_next_heading(line):continue
                label=_section_label(line)
                if label.casefold() in {'remaining work','work','human actions','account access'}:continue
                items.append(label)
                continue
            if _is_next_heading(line):
                continuation = False
                continue
            if re.fullmatch(r"\*\*[^*]+\*\*:?", line.strip()):
                continuation = False
                label=_section_label(line)
                if label.casefold() in {"remaining work","work","human actions","account access"}:continue
                items.append(label)
                continue
            bullet = _BULLET.fullmatch(line)
            if bullet:
                items.append(bullet.group(1).strip())
                continuation = not (line.endswith("  ") or line.endswith("\\"))
            elif items and continuation:
                items[-1] += " " + line.strip()
            else:
                items.append(line.strip())
                continuation = not (line.endswith("  ") or line.endswith("\\"))
        if not items or not all(_human_only_action(item) for item in items):
            return False
    return True


def find_violations(text: str) -> list[str]:
    """Return list of red-flag labels that match in `text`."""
    if not text:
        return []
    stripped = _strip_code_blocks(text)
    hits: list[str] = []
    for label, pat in _FLAGS:
        if pat.search(stripped):
            hits.append(label)
    if any(_is_next_heading(line) for line in stripped.splitlines()) and not _next_steps_all_human_only(stripped):
        hits.append("next-steps-heading")
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

    if data.get("stop_hook_active"):
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
    # Approval language alone cannot establish authorization to execute.
    required_scope_wait = bool(re.fullmatch(
        r"Stop sign: this production change is outside the approved scope\. Waiting for your approval\.",
        text.strip(), re.I))
    blocking_hits = [hit for hit in hits if not (hit == "waiting-on-go" and required_scope_wait)]
    if strict and blocking_hits:
        msg = (
            "[1pct] Red-flag phrases detected in response: "
            + ", ".join(blocking_hits)
            + ".\nRewrite the turn to execute the next documented plan step decisively "
            + "instead of re-asking for permission. See SKILL.md 'Red flags' section. "
            + "If a genuine stop-sign applies, name it explicitly."
        )
        print(msg, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
