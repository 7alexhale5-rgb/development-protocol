"""Conservative proof of a Codex full-file read from a JSONL transcript.

This intentionally recognizes one narrow, auditable functions.exec shape. It
does not execute transcript text or infer success from a requested command.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path


_STRING = r'"(?:\\.|[^"\\])*"'
_CALL = re.compile(
    rf"\s*const r=await tools\.exec_command\(\{{cmd:({_STRING})\}}\);text\(r\)\s*;?\s*",
    re.DOTALL,
)


def _command_path(source: str) -> Path | None:
    if not isinstance(source, str):
        return None
    match = _CALL.fullmatch(source)
    if not match:
        return None
    try:
        command = json.loads(match.group(1))
        tokens = shlex.split(command)
    except (ValueError, TypeError):
        return None
    if len(tokens) != 2 or tokens[0] != "cat":
        return None
    path = Path(tokens[1])
    if not path.is_absolute() or command != "cat " + shlex.quote(str(path)):
        return None
    return path


def prove_reads(
    transcript: Path, targets: set[Path], session_id: str | None = None
) -> dict:
    """Verify many paths in one scan; return paths and counts, never content."""
    expected = {}
    for target in targets:
        target = Path(target)
        if not target.is_absolute() or not target.is_file():
            continue
        try:
            expected[target] = target.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    calls = {}
    outputs = {}
    metadata_seen = False
    try:
        with Path(transcript).open(encoding="utf-8") as stream:
            for raw in stream:
                item = json.loads(raw)
                if not isinstance(item, dict):
                    return {
                        "proved_paths": set(),
                        "reason": "invalid_record_shape",
                        "eligible_calls": {},
                    }
                if item.get("type") == "session_meta" and session_id is not None:
                    metadata = item.get("payload")
                    if (
                        not isinstance(metadata, dict)
                        or metadata.get("id") != session_id
                    ):
                        return {
                            "proved_paths": set(),
                            "reason": "session_metadata_mismatch",
                            "eligible_calls": {},
                        }
                    metadata_seen = True
                if item.get("type") != "response_item":
                    continue
                payload = item.get("payload", {})
                if not isinstance(payload, dict):
                    return {
                        "proved_paths": set(),
                        "reason": "invalid_payload_shape",
                        "eligible_calls": {},
                    }
                call_id = payload.get("call_id")
                if not isinstance(call_id, str):
                    continue
                if (
                    payload.get("type") == "custom_tool_call"
                    and payload.get("name") == "exec"
                ):
                    if call_id in calls:
                        return {
                            "proved_paths": set(),
                            "reason": "duplicate_call_id",
                            "eligible_calls": {},
                        }
                    calls[call_id] = payload
                elif payload.get("type") == "custom_tool_call_output":
                    if call_id in outputs:
                        return {
                            "proved_paths": set(),
                            "reason": "duplicate_output_id",
                            "eligible_calls": {},
                        }
                    outputs[call_id] = payload
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {
            "proved_paths": set(),
            "reason": "transcript_unreadable_or_invalid",
            "eligible_calls": {},
        }
    if session_id is not None and not metadata_seen:
        return {
            "proved_paths": set(),
            "reason": "session_metadata_missing",
            "eligible_calls": {},
        }

    eligible = {target: 0 for target in expected}
    proved = set()
    for call_id, call in calls.items():
        path = _command_path(call.get("input", ""))
        if path not in expected:
            continue
        eligible[path] += 1
        if call.get("status") != "completed":
            continue
        blocks = outputs.get(call_id, {}).get("output")
        if not isinstance(blocks, list) or len(blocks) != 2:
            continue
        if any(
            not isinstance(block, dict) or block.get("type") != "input_text"
            for block in blocks
        ):
            continue
        status, result_text = (block.get("text") for block in blocks)
        if not isinstance(status, str) or not status.startswith("Script completed\n"):
            continue
        try:
            result = json.loads(result_text)
        except (TypeError, json.JSONDecodeError):
            continue
        if (
            not isinstance(result, dict)
            or type(result.get("exit_code")) is not int
            or result["exit_code"] != 0
        ):
            continue
        if result.get("output") != expected[path]:
            continue
        proved.add(path)
    return {"proved_paths": proved, "reason": "parsed", "eligible_calls": eligible}


def prove_read(transcript: Path, target: Path) -> dict:
    """Return proof metadata only, never transcript content or target bytes."""
    target = Path(target)
    if not target.is_absolute() or not target.is_file():
        return {"proved": False, "reason": "target_missing_or_relative"}
    try:
        content = target.read_bytes()
        size = len(content)
        content.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return {"proved": False, "reason": "target_unreadable_or_non_utf8"}
    result = prove_reads(transcript, {target})
    proved = target in result["proved_paths"]
    return {
        "proved": proved,
        "reason": "exact_current_bytes"
        if proved
        else result["reason"]
        if result["reason"] != "parsed"
        else "no_successful_exact_full_read",
        "bytes": size if proved else None,
        "eligible_calls": result["eligible_calls"].get(target, 0),
    }
