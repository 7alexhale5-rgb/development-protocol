#!/usr/bin/env python3
"""sweep.py: the coverage ledger behind /relentless.

WHY THIS EXISTS. "Do I have enough?" is a feeling, and a feeling cannot be
checked, argued with, or handed to another agent. This turns it into arithmetic:
a named universe of N items, a depth floor every item must reach, and a count of
how many have not reached it. "Enough" stops being a judgment call and becomes
`312 - 47`.

It also makes stopping a deliberate act rather than a fade. Every change
re-renders RESUME.md, so an agent that is killed mid-sweep (usage limit, crash,
closed laptop) still leaves the next agent an exact place to start.

THE DEPTH LADDER (an item's `depth` field):
  0 listed     in the universe, nothing read
  1 skimmed    grep hit or excerpt seen. A lead, not evidence.
  2 read       whole artifact read start to finish
  3 traced     edges followed: imports, callers, callees, tests, config, history
  4 exercised  run, reproduced, or otherwise tested against the live thing

Anything below the sweep's floor counts as OPEN. Interestingness is not depth.

HONEST NUMBERS. A depth claim of L2 or more needs --evidence. `close` refuses
while items are open, when the universe is empty, when more than a quarter of it
is deferred, when a re-run of a recorded enumeration finds items the ledger never
saw, when --done-cmd fails, or when a file the ledger calls read was never opened
in the transcript of the session that visited it. `--force` closes anyway and
records which checks it overrode.

OWNERSHIP. A ledger belongs to the session that last changed it. The session id
comes from SWEEP_SESSION_ID if set, else CLAUDE_CODE_SESSION_ID, else CODEX_THREAD_ID.
Claude Code subagents share their parent's id. With none, ledgers are unbound and
no Stop hook acts on them. The optional Stop hook (../hooks/relentless-stop.py)
acts only on open ledgers the stopping session owns.

STORE. <project>/.sweeps/<slug>/ledger.json, where <project> is the git root of
--project (default: the current folder), or that folder itself outside git.
SWEEP_HOME overrides the whole store. Closed and abandoned sweeps move to
.sweeps/_closed/. ledger.json is the whole state; RESUME.md is re-rendered from it
on every save, so the two can never drift apart.

A checklist verifier can read a closed ledger without changing it:
`sweep.py verify <ledger.json>` requires a close without --force and retained read proof.
It re-audits visiting-session transcripts under the configured transcript root.
Pruned transcripts prevent a fresh pass even when the ledger is unchanged. Claude reads
require successful full results. SWEEP_CODEX_READ_PROOF=1 opts into exact-output Codex
proof; CODEX_THREAD_ID alone binds ownership and never establishes a read.

Exit codes:  0 ok  ·  1 refused (open items, bad args)  ·  2 could not measure

Self-test:  python3 sweep.py --selftest
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import fcntl
import functools
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

from read_proof import prove_reads

# _shared.py is the development-protocol skill's, not this one's: locate it by
# relative path (skills/<this>/scripts -> skills/development-protocol/scripts)
# and fail with a clear, actionable message if that skill is not installed
# alongside this one, rather than a bare "No module named '_shared'".
_SHARED_DIR = (
    Path(__file__).resolve().parent.parent.parent / "development-protocol" / "scripts"
)
if not (_SHARED_DIR / "_shared.py").is_file():
    raise ImportError(
        "sweep.py needs the 'development-protocol' skill installed alongside it "
        f"(expected {_SHARED_DIR / '_shared.py'}); reinstall the development-protocol-skill stack."
    )
sys.path.insert(0, str(_SHARED_DIR))
from _shared import run_bash  # noqa: E402

DEPTHS = {
    0: "listed",
    1: "skimmed",
    2: "read",
    3: "traced",
    4: "exercised",
}
EVIDENCE_FROM = 2  # a depth claim at or above this needs --evidence
MAX_DEFERRED_SHARE = 0.25
LEDGER = "ledger.json"
RESUME = "RESUME.md"
STORE_DIR = ".sweeps"
LOCK = ".lock"
CLOSED_DIR = "_closed"
UNFINISHED = ("open", "checkpointed")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
READ_VERBS = re.compile(r"\b(cat|sed|head|tail|nl|awk|less|more|bat|view)\b")
SWEEP_PY = Path(__file__).resolve()


# --------------------------------------------------------------------------
# time: ISO 8601 with the local offset, never naive
# --------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def age_minutes(s: str) -> float | None:
    try:
        d = datetime.datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
    if d.tzinfo is None:
        d = d.astimezone()
    return (datetime.datetime.now().astimezone() - d).total_seconds() / 60.0


# --------------------------------------------------------------------------
# where ledgers live, and who owns them
# --------------------------------------------------------------------------
_base: str | None = None  # --project, or the Stop hook payload's cwd


def set_base(path: str | None) -> None:
    """Point the store at the project holding `path` (None: the current folder)."""
    global _base
    _base = path


@functools.lru_cache(maxsize=None)
def _root_of(start: str) -> str:
    return project_root(Path(start))


def store_root() -> Path:
    home = os.environ.get("SWEEP_HOME")
    if home:
        return Path(home)
    return Path(_root_of(os.path.abspath(_base or os.getcwd()))) / STORE_DIR


def ledger_path(slug: str) -> Path:
    return store_root() / slug / LEDGER


def all_ledgers(include_closed: bool = False) -> list[Path]:
    root = store_root()
    found: list[Path] = []
    if not root.is_dir():
        return found
    for child in sorted(root.iterdir()):
        if child.name == CLOSED_DIR:
            if include_closed:
                found += sorted(child.glob(f"*/{LEDGER}"))
            continue
        if (child / LEDGER).is_file():
            found.append(child / LEDGER)
    return found


def current_session() -> str | None:
    for key in ("SWEEP_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def project_root(start: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return str(start.resolve())


def open_ledgers_for(session: str | None) -> list[Path]:
    """Open ledgers owned by `session`. An empty session id matches nothing."""
    if not session:
        return []
    hits = []
    for p in all_ledgers():
        try:
            d = load(p)
        except Exception:
            continue
        if d.get("status") == "open" and d.get("session_id") == session:
            hits.append(p)
    return hits


# --------------------------------------------------------------------------
# read / write, under a lock
# --------------------------------------------------------------------------
def die(msg: str, code: int = 1) -> None:
    print(f"sweep: {msg}", file=sys.stderr)
    sys.exit(code)


def load(path: Path) -> dict:
    return json.loads(path.read_text())


@contextlib.contextmanager
def ledger_lock(path: Path, timeout: float | None = None):
    """Exclusive lock on <dir>/.lock, not on ledger.json: os.replace swaps the
    ledger's inode, so a lock on the file itself would guard a file that is gone.
    timeout=None waits; otherwise retries until the deadline, then TimeoutError."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path.parent / LOCK), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if timeout is None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        else:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"ledger lock busy: {path}") from None
                    time.sleep(0.05)
        yield
    finally:
        os.close(fd)  # closing the descriptor releases the lock


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def save(path: Path, data: dict) -> None:
    """Atomic. RESUME.md is re-rendered from the same data on every save, so a
    sweep that dies mid-flight still leaves an exact place to resume from."""
    data["updated"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    _atomic_write(path.parent / RESUME, resume_prompt(data, path) + "\n")


def log(data: dict, event: str, detail: str = "", **extra) -> None:
    entry = {"ts": now_iso(), "event": event, "detail": detail}
    entry.update(extra)
    data.setdefault("log", []).append(entry)


def claim(data: dict) -> None:
    """Run on every piece of work. The last session to change a ledger owns it,
    and a checkpointed ledger that gets new work is open again. Both start a
    new epoch, which is what the Stop hook counts blocks within."""
    me = current_session()
    if me and data.get("session_id") != me:
        log(data, "rebind", f"{data.get('session_id')} -> {me}", session=me)
        data["session_id"] = me
    if data.get("status") == "checkpointed":
        data["status"] = "open"
        log(data, "resume", "new work after a checkpoint", session=me)


def mutate(path: Path, fn, work: bool = True, timeout: float | None = None):
    """Lock, load fresh, apply fn(data), save. Returns (data, fn's result)."""
    with ledger_lock(path, timeout=timeout):
        data = load(path)
        if data.get("status") not in UNFINISHED:
            die(
                f"sweep '{data.get('slug')}' is {data.get('status')}; start a new one.",
                1,
            )
        if work:
            claim(data)
        result = fn(data)
        save(path, data)
    return data, result


def resolve(args) -> Path:
    """--slug if given; else the one unfinished ledger this session owns."""
    slug = getattr(args, "slug", None)
    if slug:
        p = ledger_path(slug)
        if not p.is_file():
            die(f"no unfinished sweep named '{slug}' in {store_root()}", 1)
        return p
    me = current_session()
    mine, unfinished = [], []
    for p in all_ledgers():
        try:
            d = load(p)
        except Exception:
            continue
        if d.get("status") in UNFINISHED:
            unfinished.append(p)
            if me and d.get("session_id") == me:
                mine.append(p)
    if len(mine) == 1:
        return mine[0]
    if not unfinished:
        die(
            "no sweep ledger found. Start one with:  sweep.py init --slug <name> "
            '--goal "<goal>" --done "<falsifiable done condition>"',
            1,
        )
    names = ", ".join(p.parent.name for p in (mine or unfinished))
    die(f"name the sweep with --slug ({names}).", 1)
    return Path()  # unreachable; keeps type checkers calm


# --------------------------------------------------------------------------
# counting: the arithmetic that replaces the feeling
# --------------------------------------------------------------------------
def tally(data: dict) -> dict:
    floor = int(data.get("depth_floor", 2))
    items = data.get("universe", [])
    ids = {it["id"] for it in items}
    deferred = {d["id"] for d in data.get("deferred", []) if d["id"] in ids}
    at = 0
    open_ids: list[str] = []
    bydepth: dict[int, int] = {}
    for it in items:
        d = int(it.get("depth", 0))
        bydepth[d] = bydepth.get(d, 0) + 1
        if it["id"] in deferred:
            continue
        if d >= floor:
            at += 1
        else:
            open_ids.append(it["id"])
    return {
        "slug": data.get("slug"),
        "status": data.get("status"),
        "goal": data.get("goal"),
        "done_condition": data.get("done_condition"),
        "depth_floor": floor,
        "depth_floor_name": DEPTHS.get(floor, str(floor)),
        "total": len(items),
        "at_floor": at,
        "open": len(open_ids),
        "deferred": len(deferred),
        "findings": len(data.get("findings", [])),
        "by_depth": {DEPTHS.get(k, str(k)): v for k, v in sorted(bydepth.items())},
        "open_ids": open_ids,
        "session_id": data.get("session_id"),
        "updated": data.get("updated"),
        "age_minutes": age_minutes(data.get("updated", "")),
        "complete": len(items) > 0 and not open_ids,
    }


def headline(t: dict) -> str:
    """The denominator is the whole universe: deferring never inflates coverage."""
    return (
        f"sweep '{t['slug']}': {t['at_floor']}/{t['total']} at L{t['depth_floor']} "
        f"({t['depth_floor_name']}), {t['open']} open, {t['deferred']} deferred, "
        f"{t['findings']} findings [{t['status']}]"
    )


def epoch_start(data: dict) -> int:
    """Index in the log where the current open epoch began (init, resume, rebind)."""
    entries = data.get("log", [])
    for i in range(len(entries) - 1, -1, -1):
        if entries[i].get("event") in ("init", "resume", "rebind"):
            return i
    return 0


def last_block(data: dict) -> dict | None:
    """The Stop hook's most recent block in the current epoch, if any."""
    entries = data.get("log", [])
    for e in reversed(entries[epoch_start(data) :]):
        if e.get("event") == "stop-block":
            return e
    return None


# --------------------------------------------------------------------------
# enumeration: an errored command cannot certify a universe
# --------------------------------------------------------------------------
def enumerate_ids(cmd: str) -> tuple[list[str] | None, dict, str | None]:
    """Run an enumeration. Returns (ids, record, error). On error ids is None."""
    record = {"cmd": cmd, "ts": now_iso()}
    # pipefail: without it a pipeline reports only its last stage, so
    # `rg --files missing/ | sort` exits 0 and hides rg's error. run_bash never
    # raises: a missing bash or a timeout comes back as a plain non-zero exit.
    code, stdout, stderr = run_bash(cmd, timeout=300)
    if code == 124:
        return None, record, f"enumeration timed out after 300s: {cmd}"
    if code == 126 or code == 127:
        return None, record, f"could not run the enumeration ({stderr.strip()}): {cmd}"
    record.update(exit=code, stderr_bytes=len(stderr.encode()))
    # rg/grep exit 1 on "no matches": a real zero, but only when they printed
    # nothing at all. find and ls also exit 1, on errors, with partial output or
    # an error message; that is a broken enumeration, not an empty one.
    failed = code not in (0, 1) or (
        code == 1 and bool(stdout.strip() or stderr.strip())
    )
    if failed:
        return (
            None,
            record,
            f"enumeration failed (exit {code}): {stderr.strip()[:300]}\n"
            f"  command: {cmd}\nAn enumeration that errored cannot certify a universe.",
        )
    ids = [ln.strip() for ln in stdout.splitlines()]
    ids = [i for i in ids if i and not i.startswith("#")]
    record["count"] = len(ids)
    return ids, record, None


def _collect_ids(args) -> tuple[list[str], list[dict]]:
    ids: list[str] = []
    sources: list[dict] = []
    if args.ids:
        ids += args.ids
        sources.append({"source": "args", "count": len(args.ids), "ts": now_iso()})
    if args.from_file:
        p = Path(args.from_file)
        if not p.is_file():
            die(f"--from-file not found: {p}", 2)
        got = [ln.strip() for ln in p.read_text().splitlines()]
        ids += got
        sources.append({"file": str(p.resolve()), "count": len(got), "ts": now_iso()})
    if args.from_cmd:
        got, record, error = enumerate_ids(args.from_cmd)
        if error:
            die(error, 2)
        ids += got or []
        sources.append(record)
    if args.stdin:
        got = [ln.strip() for ln in sys.stdin.read().splitlines()]
        ids += got
        sources.append({"source": "stdin", "count": len(got), "ts": now_iso()})
    return [i for i in ids if i and not i.startswith("#")], sources


# --------------------------------------------------------------------------
# the read audit: a visit claim is checked against what was actually opened
# --------------------------------------------------------------------------
def transcripts_root() -> Path:
    return Path(
        os.environ.get("SWEEP_TRANSCRIPTS") or Path.home() / ".claude" / "projects"
    )


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def session_reads(session: str) -> tuple[bool, set[str], list[tuple[str, str]]]:
    """Successful full-file reads only; combine numbered partial results by path.

    Requests without matching results, failed results, and incomplete coverage
    do not count. Bash evidence retains successful output for the caller to check.
    """
    root = transcripts_root()
    files = list(root.glob(f"*/{session}.jsonl")) + list(
        root.glob(f"*/{session}/subagents/*.jsonl")
    )
    reads, line_coverage, cmds = set(), {}, []
    for file in files:
        requests = {}
        try:
            for line in file.read_text(errors="replace").splitlines():
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                content = (record.get("message") or {}).get("content") or []
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use" and block.get("id"):
                        requests[block["id"]] = block
                        continue
                    if block.get("type") != "tool_result" or block.get("is_error"):
                        continue
                    request = requests.get(block.get("tool_use_id"))
                    if not request:
                        continue
                    inp = request.get("input") or {}
                    output = _result_text(block.get("content"))
                    if request.get("name") == "Bash" and inp.get("command"):
                        cmds.append((inp["command"], output))
                    if request.get("name") != "Read" or not inp.get("file_path"):
                        continue
                    path = os.path.realpath(inp["file_path"])
                    try:
                        body = Path(path).read_text()
                    except (OSError, UnicodeError):
                        continue
                    count = len(body.splitlines())
                    numbered = {int(m.group(1)) for m in re.finditer(
                        r"^\s*(\d+)(?:→|\t)", output, re.M)}
                    if numbered:
                        line_coverage.setdefault(path, set()).update(numbered)
                        if set(range(1, count + 1)) <= line_coverage[path]:
                            reads.add(path)
                    elif output == body and (count or not inp.get("offset")):
                        reads.add(path)
        except OSError:
            continue
    return bool(files), reads, cmds


def _named_in(cmd: str, path_text: str) -> bool:
    return (
        re.search(r"(^|[\s'\"=/])" + re.escape(path_text) + r"($|[\s'\";|)])", cmd)
        is not None
    )


def codex_session_file(session: str) -> Path | None:
    """Find one canonical UUID transcript; never interpolate unchecked ids."""
    try:
        if str(uuid.UUID(session)) != session:
            return None
    except (TypeError, ValueError):
        return None
    root = Path(
        os.environ.get("SWEEP_CODEX_TRANSCRIPTS") or Path.home() / ".codex" / "sessions"
    )
    matches = list(root.rglob(f"*{session}.jsonl"))
    if len(matches) != 1:
        return None
    try:
        with matches[0].open(encoding="utf-8") as stream:
            first = json.loads(stream.readline())
    except (OSError, UnicodeError, ValueError):
        return None
    if (
        not isinstance(first, dict)
        or first.get("type") != "session_meta"
        or not isinstance(first.get("payload"), dict)
        or first["payload"].get("id") != session
    ):
        return None
    return matches[0]


def codex_session_proofs(session: str, targets: set[Path]) -> tuple[bool, set[Path]]:
    """Scan one session through the exact current-output proof algorithm."""
    transcript = codex_session_file(session)
    if transcript is None:
        return False, set()
    result = prove_reads(
        transcript, {path.resolve() for path in targets}, session_id=session
    )
    return True, result["proved_paths"]


def audit_reads(data: dict) -> tuple[list[str], int]:
    """Items at L2+ that are files and were never opened in the transcript of the
    session that visited them. Returns (unverified ids, unauditable count).
    Unauditable = not a file, no visiting session recorded, or no
    transcript on disk. Those are counted and shown, never passed silently."""
    project = Path(data.get("project") or ".")
    deferred = {d["id"] for d in data.get("deferred", [])}
    cache: dict[str, tuple[bool, set[str], list[tuple[str, str]]]] = {}
    codex_cache: dict[str, tuple[bool, set[Path]]] = {}
    codex_opt_in = os.environ.get("SWEEP_CODEX_READ_PROOF") == "1"
    codex_origin: dict[str, bool] = {}
    unverified: list[str] = []
    unauditable = 0
    for it in data.get("universe", []):
        if int(it.get("depth", 0)) < EVIDENCE_FROM or it["id"] in deferred:
            continue
        p = Path(it["id"]) if os.path.isabs(it["id"]) else project / it["id"]
        session = it.get("session")
        if codex_opt_in and session and session not in codex_origin:
            codex_origin[session] = (
                session == os.environ.get("CODEX_THREAD_ID")
                or codex_session_file(session) is not None
            )
        is_codex = codex_origin.get(session, False)
        if not p.is_file():
            unauditable += 1
            if is_codex:
                unverified.append(it["id"])
            continue
        if not session:
            unauditable += 1
            unverified.append(it["id"])
            continue
        if is_codex:
            if session not in codex_cache:
                targets = {
                    (
                        Path(x["id"]) if os.path.isabs(x["id"]) else project / x["id"]
                    ).resolve()
                    for x in data.get("universe", [])
                    if x.get("session") == session
                    and int(x.get("depth", 0)) >= EVIDENCE_FROM
                    and x["id"] not in deferred
                }
                codex_cache[session] = codex_session_proofs(session, targets)
            found, proved = codex_cache[session]
            if not found:
                unauditable += 1
            if p.resolve() not in proved:
                unverified.append(it["id"])
            continue
        if session not in cache:
            cache[session] = session_reads(session)
        found, reads, cmds = cache[session]
        if not found:
            unauditable += 1
            unverified.append(it["id"])
            continue
        real = os.path.realpath(str(p))
        if real in reads:
            continue
        try:
            body = p.read_text()
        except (OSError, UnicodeError):
            body = ""
        if body and any(
            READ_VERBS.search(command)
            and any(_named_in(command, x) for x in (real, str(p), it["id"]))
            and body in output
            for command, output in cmds
        ):
            continue
        unverified.append(it["id"])
    return unverified, unauditable


# --------------------------------------------------------------------------
# closing checks
# --------------------------------------------------------------------------
def close_checks(data: dict) -> tuple[list[tuple[str, str, list[str]]], bool, int]:
    """Every reason not to close. Returns (problems, could_not_measure, unauditable)."""
    t = tally(data)
    problems: list[tuple[str, str, list[str]]] = []
    unmeasured = False
    if not t["total"]:
        problems.append(("empty", "the universe is empty; nothing was enumerated", []))
    if t["open"] > 0:
        problems.append(
            (
                "open",
                f"{t['open']} item(s) below depth floor L{t['depth_floor']}",
                t["open_ids"],
            )
        )
    if t["total"] and t["deferred"] / t["total"] > MAX_DEFERRED_SHARE:
        problems.append(
            (
                "deferred",
                f"{t['deferred']} of {t['total']} items are deferred; more than "
                f"{int(MAX_DEFERRED_SHARE * 100)}% deferred is a sweep that was not done",
                [],
            )
        )
    known = {it["id"] for it in data.get("universe", [])}
    for rec in data.get("enumerations", []):
        if not rec.get("cmd"):
            continue
        got, _, error = enumerate_ids(rec["cmd"])
        if error:
            unmeasured = True
            problems.append(("drift", "could not re-run an enumeration", [error]))
            continue
        drifted = [i for i in got or [] if i not in known]
        if drifted:
            problems.append(
                (
                    "drift",
                    f"re-running `{rec['cmd']}` found {len(drifted)} item(s) the "
                    "ledger never saw; add and visit them, or defer them with a reason",
                    drifted,
                )
            )
    if data.get("done_cmd"):
        code, out, err = run_bash(data["done_cmd"], timeout=300)
        if code != 0:
            tail = (out + err).strip().splitlines()[-5:]
            problems.append(
                (
                    "done-cmd",
                    f"--done-cmd exited {code}: {data['done_cmd']}",
                    tail,
                )
            )
    unverified, unauditable = audit_reads(data)
    if unverified:
        problems.append(
            (
                "read-audit",
                f"{len(unverified)} file(s) marked read (L2+) were never opened in the "
                "visiting session's transcript",
                unverified,
            )
        )
    return problems, unmeasured, unauditable


def move_to_closed(path: Path) -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = store_root() / CLOSED_DIR / f"{path.parent.name}-{stamp}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path.parent), str(dest))
    return dest / LEDGER


def mark_checkpoint(data: dict, why: str, by: str) -> None:
    """Flip an unfinished ledger to checkpointed, with the reason and who did it."""
    t = tally(data)
    data["status"] = "checkpointed"
    data["checkpoint"] = {"why": why, "by": by, "ts": now_iso(), "open": t["open"]}
    log(data, "checkpoint", why, by=by, open=t["open"])


def checkpoint(
    path: Path, why: str, by: str = "agent", timeout: float | None = None
) -> dict:
    """Pause a sweep on purpose. Shared by the CLI and the hooks."""
    data, _ = mutate(
        path, lambda d: mark_checkpoint(d, why, by), work=False, timeout=timeout
    )
    return data


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def resume_prompt(data: dict, path: Path) -> str:
    t = tally(data)
    s = f"python3 {SWEEP_PY}"
    slug = t["slug"]
    recent = data.get("findings", [])[-8:]
    flines = (
        "\n".join(
            f"- {f['text']}"
            + (f"  (evidence: {f['evidence']})" if f.get("evidence") else "")
            for f in recent
        )
        or "- none recorded yet"
    )
    dlines = (
        "\n".join(f"- {d['id']}: {d['why']}" for d in data.get("deferred", []))
        or "- none"
    )
    elines = (
        "\n".join(
            f"- `{e['cmd']}` ({e.get('count', '?')} items)"
            for e in data.get("enumerations", [])
            if e.get("cmd")
        )
        or "- no recorded command (items were added by hand or from a file)"
    )
    nxt = "\n".join(f"- {i}" for i in t["open_ids"][:15]) or "- none"
    more = (
        f"\n...and {t['open'] - 15} more (`{s} next --slug {slug} -n 50`)"
        if t["open"] > 15
        else ""
    )
    cp = data.get("checkpoint") if data.get("status") == "checkpointed" else None
    paused = f" (paused by {cp['by']}: {cp['why']})" if cp else ""
    done_cmd = (
        f"\nDONE CHECK (close runs it): `{data['done_cmd']}`"
        if data.get("done_cmd")
        else ""
    )
    return f"""Resume the sweep '{slug}'. Read this whole prompt before acting.

STATUS: {t["status"]}{paused}
GOAL: {t["goal"]}
DONE WHEN: {t["done_condition"]}{done_cmd}
DEPTH FLOOR: L{t["depth_floor"]} ({t["depth_floor_name"]}). An item below it is NOT visited. Claims of L2+ need --evidence.
COVERAGE: {t["at_floor"]}/{t["total"]} at floor, {t["open"]} open, {t["deferred"]} deferred.
LEDGER: {path}

THE UNIVERSE WAS BUILT FROM (close re-runs these and refuses if they find new items):
{elines}

FINDINGS SO FAR (do not re-derive these):
{flines}

DEFERRED, with reasons (revive only if the reason no longer holds):
{dlines}

NEXT OPEN ITEMS:
{nxt}{more}

HOW TO WORK (your first change re-opens the sweep and makes it yours):
1. {s} status --slug {slug}
2. {s} next --slug {slug} -n 20
3. Take each item to L{t["depth_floor"]}, then record it:
   {s} visit --slug {slug} <id> --depth {t["depth_floor"]} --evidence "<what you read, followed or ran>"
4. {s} finding --slug {slug} "<finding>" --evidence "<proof>" --item <id>
5. Leaving an item on purpose: {s} defer --slug {slug} <id> --why "<reason>"  (never skip silently)
6. Finished: {s} close --slug {slug}  (it audits what you say you read)
7. Must stop: {s} checkpoint --slug {slug} --why "<reason>"

Do not report this sweep as done while open > 0. Coverage is a fraction, not a feeling."""


def render_markdown(data: dict) -> str:
    t = tally(data)
    lines = [
        f"# Sweep: {t['slug']}",
        "",
        f"- **Goal**: {t['goal']}",
        f"- **Done when**: {t['done_condition']}",
        f"- **Depth floor**: L{t['depth_floor']} ({t['depth_floor_name']})",
        f"- **Coverage**: {t['at_floor']}/{t['total']} at floor, {t['open']} open, "
        f"{t['deferred']} deferred",
        f"- **Status**: {t['status']}  ·  updated {t['updated']}",
        "",
    ]
    if data.get("findings"):
        lines += ["## Findings", ""]
        lines += [
            f"{n}. {f['text']}"
            + (f"  \n   _evidence_: {f['evidence']}" if f.get("evidence") else "")
            for n, f in enumerate(data["findings"], 1)
        ]
        lines.append("")
    if data.get("deferred"):
        lines += ["## Deferred", ""]
        lines += [f"- `{d['id']}`: {d['why']}" for d in data["deferred"]]
        lines.append("")
    if t["open_ids"]:
        lines += ["## Open", ""] + [f"- `{i}`" for i in t["open_ids"][:200]] + [""]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_init(args) -> int:
    if not SLUG_RE.match(args.slug):
        die("slug must be lowercase letters, digits and hyphens (max 64).", 1)
    if not (0 <= args.depth <= 4):
        die("depth floor must be 0-4.", 1)
    if args.depth < EVIDENCE_FROM and not args.floor_why:
        die(
            f"a floor below L{EVIDENCE_FROM} counts skimmed items as covered. "
            "Give --floor-why if that is really the job.",
            1,
        )
    path = ledger_path(args.slug)
    data = {
        "slug": args.slug,
        "goal": args.goal,
        "done_condition": args.done,
        "done_cmd": args.done_cmd,
        "depth_floor": args.depth,
        "floor_why": args.floor_why,
        "project": project_root(Path(args.project or os.getcwd())),
        "session_id": current_session(),
        "status": "open",
        "created": now_iso(),
        "universe": [],
        "enumerations": [],
        "findings": [],
        "deferred": [],
        "log": [],
    }
    log(data, "init", args.goal, session=data["session_id"])
    with ledger_lock(path):
        if path.exists():
            die(
                f"a sweep named '{args.slug}' already exists at {path}. Resume it, or "
                "pick another slug (prefix it with the project, e.g. billing-auth-audit).",
                1,
            )
        save(path, data)
    print(f"sweep '{args.slug}' opened at {path}")
    print(f"  done when: {args.done}")
    print(f"  depth floor: L{args.depth} ({DEPTHS[args.depth]})")
    print("\nNext: enumerate the universe BEFORE investigating anything.")
    print(
        f"  python3 {SWEEP_PY} add --slug {args.slug} --from-cmd 'git ls-files \"*.py\"'"
    )
    return 0


def cmd_add(args) -> int:
    path = resolve(args)
    ids, sources = _collect_ids(args)

    def apply(data: dict) -> int:
        have = {it["id"] for it in data["universe"]}
        new = []
        for i in ids:
            if i not in have:
                have.add(i)
                new.append(
                    {
                        "id": i,
                        "depth": 0,
                        "note": None,
                        "evidence": None,
                        "ts": None,
                        "session": None,
                    }
                )
        if not new and not args.allow_empty:
            die(
                "enumeration produced 0 new items. An empty universe is a measurement "
                "failure until proven otherwise; check the command, then re-run with "
                "--allow-empty if the zero is real.",
                2,
            )
        data["universe"].extend(new)
        data.setdefault("enumerations", []).extend(sources)
        log(data, "add", f"+{len(new)} items")
        return len(new)

    data, n = mutate(path, apply)
    t = tally(data)
    print(f"+{n} items ({t['total']} in universe)")
    print(headline(t))
    return 0


def cmd_visit(args) -> int:
    if not (0 <= args.depth <= 4):
        die("depth must be 0-4.", 1)
    if args.depth >= EVIDENCE_FROM and not args.evidence:
        die(
            f"a depth claim of L{EVIDENCE_FROM} or more needs --evidence (what you read, "
            "followed or ran). A depth claim with no evidence is the same unfalsifiable "
            "feeling this ledger exists to replace.",
            1,
        )
    path = resolve(args)
    me = current_session()

    def apply(data: dict) -> tuple[list[str], list[str], list[str]]:
        index = {it["id"]: it for it in data["universe"]}
        raised, kept, missing = [], [], []
        for ident in args.ids:
            it = index.get(ident)
            if it is None:
                missing.append(ident)
                continue
            if args.depth > int(it.get("depth", 0)) or args.force:
                it.update(
                    depth=args.depth,
                    evidence=args.evidence,
                    note=args.note,
                    ts=now_iso(),
                    session=me,
                )
                raised.append(ident)
            else:
                kept.append(ident)
        if missing and args.add_missing:
            for m in missing:
                data["universe"].append(
                    {
                        "id": m,
                        "depth": args.depth,
                        "note": args.note,
                        "evidence": args.evidence,
                        "ts": now_iso(),
                        "session": me,
                    }
                )
            data.setdefault("enumerations", []).append(
                {
                    "source": "visit --add-missing",
                    "count": len(missing),
                    "ts": now_iso(),
                }
            )
            raised += missing
            missing = []
        log(data, "visit", f"{len(raised)} -> L{args.depth}")
        return raised, kept, missing

    data, (raised, kept, missing) = mutate(path, apply)
    msg = f"{len(raised)} item(s) raised to L{args.depth} ({DEPTHS[args.depth]})"
    if kept:
        msg += f"; {len(kept)} already at or above it, unchanged"
    print(msg)
    print(headline(tally(data)))
    if missing:
        print(
            f"sweep: {len(missing)} id(s) not in the universe: "
            f"{', '.join(missing[:5])}{' ...' if len(missing) > 5 else ''}\n"
            "       nothing recorded for them; pass --add-missing to enumerate them now.",
            file=sys.stderr,
        )
        return 1
    return 0


def cmd_finding(args) -> int:
    path = resolve(args)

    def apply(data: dict) -> int:
        data["findings"].append(
            {
                "text": args.text,
                "evidence": args.evidence,
                "item": args.item,
                "ts": now_iso(),
                "session": current_session(),
            }
        )
        log(data, "finding", args.text[:80])
        return len(data["findings"])

    _, n = mutate(path, apply)
    print(f"finding #{n} recorded")
    return 0


def cmd_defer(args) -> int:
    """Deferring is honest. Silently skipping is not."""
    if not args.why.strip():
        die(
            "--why is required. A deferral without a reason is a skip wearing a deferral's clothes.",
            1,
        )
    path = resolve(args)

    def apply(data: dict) -> int:
        known = {it["id"] for it in data["universe"]}
        unknown = [i for i in args.ids if i not in known]
        if unknown:
            die(
                f"{len(unknown)} id(s) are not in the universe ({', '.join(unknown[:5])}). "
                "Deferring an id the ledger never listed would inflate coverage; add it "
                "first or fix the id.",
                1,
            )
        have = {d["id"] for d in data["deferred"]}
        n = 0
        for ident in args.ids:
            if ident not in have:
                data["deferred"].append(
                    {
                        "id": ident,
                        "why": args.why,
                        "ts": now_iso(),
                        "session": current_session(),
                    }
                )
                n += 1
        log(data, "defer", f"{n}: {args.why}")
        return n

    data, n = mutate(path, apply)
    print(f"{n} item(s) deferred: {args.why}")
    print(headline(tally(data)))
    return 0


def cmd_revive(args) -> int:
    """Explicitly remove obsolete deferrals while retaining their full history."""
    if not args.why.strip():
        die("revive needs a written --why", 1)
    path = resolve(args)

    def apply(data):
        requested = set(args.ids)
        previous = [row for row in data["deferred"] if row["id"] in requested]
        if requested != {row["id"] for row in previous}:
            die("revive only accepts currently deferred item ids", 1)
        data["deferred"] = [row for row in data["deferred"] if row["id"] not in requested]
        log(data, "revive", args.why, ids=sorted(requested), prior_deferrals=previous,
            session=current_session())
        return len(previous)

    data, count = mutate(path, apply)
    print(f"{count} item(s) revived: {args.why}")
    print(headline(tally(data)))
    return 0


def cmd_status(args) -> int:
    paths = (
        [ledger_path(args.slug)] if args.slug else all_ledgers(include_closed=args.all)
    )
    payload = []
    for p in paths:
        if not p.is_file():
            continue
        try:
            data = load(p)
        except Exception as exc:
            payload.append({"path": str(p), "error": str(exc)})
            continue
        if not args.all and not args.slug and data.get("status") not in UNFINISHED:
            continue
        t = tally(data)
        t["path"] = str(p)
        t["checkpoint"] = (
            data.get("checkpoint") if data.get("status") == "checkpointed" else None
        )
        payload.append(t)
    if args.json:
        print(json.dumps({"sweeps": payload}, indent=2))
        return 0
    if not payload:
        print(
            "no sweep ledger found"
            + ("" if args.all else " (unfinished; --all shows closed)")
        )
        return 0
    for t in payload:
        if "error" in t:
            print(f"UNREADABLE {t['path']}: {t['error']}")
            continue
        print(headline(t))
        print(f"  goal: {t['goal']}")
        print(f"  done when: {t['done_condition']}")
        print(f"  depth spread: {t['by_depth']}")
        if t.get("checkpoint"):
            print(f"  paused by {t['checkpoint']['by']}: {t['checkpoint']['why']}")
        if args.next and t["open_ids"]:
            print(f"  next {min(args.next, len(t['open_ids']))} open:")
            for i in t["open_ids"][: args.next]:
                print(f"    {i}")
        elif t["open"]:
            print(
                f"  {t['open']} open: `sweep.py next --slug {t['slug']} -n 20` to pull work"
            )
    return 0


def cmd_next(args) -> int:
    """Pull the next slice of open work without loading the whole ledger."""
    t = tally(load(resolve(args)))
    for i in t["open_ids"][: args.n]:
        print(i)
    return 0


def cmd_checkpoint(args) -> int:
    if not args.why.strip():
        die("--why is required: say why the sweep stops here.", 1)
    path = resolve(args)
    data = checkpoint(path, args.why, by="agent")
    print(headline(tally(data)))
    print(f"\ncheckpoint written: {path.parent / RESUME}")
    print("\n--- paste this to resume in a fresh session ---\n")
    print((path.parent / RESUME).read_text())
    return 0


def cmd_close(args) -> int:
    path = resolve(args)
    with ledger_lock(path):
        data = load(path)
        if data.get("status") not in UNFINISHED:
            die(f"sweep '{data.get('slug')}' is already {data.get('status')}.", 1)
        problems, unmeasured, unauditable = close_checks(data)
        t = tally(data)
        if unauditable:
            print(
                f"note: {unauditable} item(s) at L2+ could not be audited (not a file, "
                "no recorded session, or no transcript on disk).",
                file=sys.stderr,
            )
        if problems and not args.force:
            print(headline(t), file=sys.stderr)
            for _name, msg, items in problems:
                print(f"\nsweep: REFUSED to close: {msg}", file=sys.stderr)
                for i in items[:10]:
                    print(f"  {i}", file=sys.stderr)
                if len(items) > 10:
                    print(f"  ...and {len(items) - 10} more", file=sys.stderr)
            print(
                "\nDo one of: keep working; `defer <id> --why` for each item you are "
                'consciously leaving; or `checkpoint --why "..."` to hand off. `--force` '
                "closes anyway and records the checks it overrode.",
                file=sys.stderr,
            )
            return 2 if unmeasured else 1
        data["status"] = "closed"
        data["closed"] = now_iso()
        data["forced"] = [name for name, _m, _i in problems] if args.force else []
        data["unauditable"] = unauditable
        log(
            data,
            "close",
            f"forced past: {', '.join(data['forced'])}"
            if data["forced"]
            else "all checks passed",
        )
        save(path, data)
    dest = move_to_closed(path)
    print(headline(tally(data)))
    if data["forced"]:
        print(f"closed (FORCED past: {', '.join(data['forced'])})")
    else:
        print("closed: universe covered, drift and read checks passed")
    print(f"archived at {dest}")
    return 0


def cmd_render(args) -> int:
    out = render_markdown(load(resolve(args)))
    if args.out:
        Path(args.out).write_text(out)
        print(f"written: {args.out}")
    else:
        print(out)
    return 0


def cmd_abandon(args) -> int:
    if not args.why.strip():
        die("--why is required: say why this sweep is being dropped.", 1)
    path = resolve(args)

    def apply(data: dict) -> None:
        data["status"] = "abandoned"
        log(data, "abandon", args.why)

    data, _ = mutate(path, apply, work=False)
    dest = move_to_closed(path)
    print(f"sweep '{data['slug']}' abandoned ({args.why}); archived at {dest}.")
    print("It no longer blocks turn end, and it claims no coverage.")
    return 0


def verify_ledger(path: Path) -> tuple[int, str]:
    """Read-only: (0, line) only for a ledger closed with every check passed."""
    if path.is_dir():
        path = path / LEDGER
    try:
        data = load(path)
    except (OSError, ValueError) as exc:
        return 2, f"cannot read {path}: {exc}"
    line = headline(tally(data))
    if data.get("status") != "closed":
        return 1, f"{line}\nnot closed ({data.get('status')})"
    if data.get("forced"):
        return 1, f"{line}\nclosed with --force past: {', '.join(data['forced'])}"
    missing_reads, _ = audit_reads(data)
    if missing_reads:
        return 1, f"{line}\n{len(missing_reads)} file read(s) unauditable or unverified"
    return 0, f"{line}\nclosed with every check passed"


def cmd_verify(args) -> int:
    """For a checklist verifier. It reads the ledger and never writes it."""
    code, text = verify_ledger(Path(args.ledger))
    print(text, file=sys.stdout if code == 0 else sys.stderr)
    return code


# --------------------------------------------------------------------------
# self-test
# --------------------------------------------------------------------------
def selftest() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="sweep-selftest-"))
    saved = {
        k: os.environ.get(k)
        for k in (
            "SWEEP_HOME",
            "SWEEP_TRANSCRIPTS",
            "SWEEP_SESSION_ID",
            "CLAUDE_CODE_SESSION_ID",
            "CODEX_THREAD_ID",
            "SWEEP_CODEX_READ_PROOF",
            "SWEEP_CODEX_TRANSCRIPTS",
        )
    }
    os.environ["SWEEP_HOME"] = str(tmp / "home")
    os.environ["SWEEP_TRANSCRIPTS"] = str(tmp / "transcripts")
    os.environ.pop("SWEEP_SESSION_ID", None)
    os.environ.pop("CODEX_THREAD_ID", None)
    os.environ.pop("SWEEP_CODEX_READ_PROOF", None)
    os.environ.pop("SWEEP_CODEX_TRANSCRIPTS", None)
    proj = tmp / "proj"
    proj.mkdir()
    fails: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(("  ok   " if cond else "  FAIL ") + name)
        if not cond:
            fails.append(name)

    def run(*argv: str, session: str | None = "sess-a") -> int:
        if session is None:
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        else:
            os.environ["CLAUDE_CODE_SESSION_ID"] = session
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()):
                try:
                    return main(list(argv))
                except SystemExit as exc:
                    return int(exc.code or 0)

    def ledger(slug: str) -> dict:
        return load(ledger_path(slug))

    def transcript(session: str, reads: list[Path] = (), bash: list[str] = ()) -> None:
        f = tmp / "transcripts" / "proj-slug" / f"{session}.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a") as fh:
            for p in reads:
                tool_id = f"read-{p}"
                block = {
                    "id": tool_id,
                    "type": "tool_use",
                    "name": "Read",
                    "input": {"file_path": str(p)},
                }
                fh.write(json.dumps({"message": {"content": [block]}}) + "\n")
                result = {"type": "tool_result", "tool_use_id": tool_id, "content": p.read_text()}
                fh.write(json.dumps({"message": {"content": [result]}}) + "\n")
            for c in bash:
                tool_id = f"bash-{c}"
                block = {"type": "tool_use", "id": tool_id, "name": "Bash", "input": {"command": c}}
                fh.write(json.dumps({"message": {"content": [block]}}) + "\n")
                code, output, error = run_bash(c)
                result = {"type": "tool_result", "tool_use_id": tool_id,
                          "is_error": code != 0, "content": output + error}
                fh.write(json.dumps({"message": {"content": [result]}}) + "\n")

    try:

        def init(slug: str, *extra: str, depth: str = "2") -> int:
            return run(
                "init",
                "--slug",
                slug,
                "--goal",
                "g",
                "--done",
                "d",
                "--depth",
                depth,
                "--project",
                str(proj),
                *extra,
            )

        def make(*names: str) -> list:
            made = []
            for name in names:
                (proj / name).write_text("x = 1\n")
                made.append(proj / name)
            return made

        def closed(slug: str) -> list:
            return [
                load(p) for p in (store_root() / CLOSED_DIR).glob(f"{slug}-*/{LEDGER}")
            ]

        fa, fb, _fc, fd, fe = make("a.py", "b.py", "c.py", "d.py", "e.py")

        # --- opening and counting --------------------------------------------
        check(
            "init opens a ledger",
            init("t", depth="3") == 0 and ledger_path("t").is_file(),
        )
        check("init binds the session", ledger("t")["session_id"] == "sess-a")
        check("a reused slug is refused", init("t") == 1)
        check(
            "a floor below L2 needs a reason",
            init("low", depth="1") == 1
            and init("low", "--floor-why", "triage", depth="1") == 0,
        )
        run("abandon", "--slug", "low", "--why", "test fixture")

        rc = run("add", "--slug", "t", "a.py", "b.py", "c.py", "d.py", "e.py")
        led = ledger("t")
        check(
            "5 items enumerated, all open",
            rc == 0 and len(led["universe"]) == 5 and tally(led)["open"] == 5,
        )
        check(
            "RESUME.md is written on every save",
            "a.py" in (ledger_path("t").parent / RESUME).read_text(),
        )
        run("add", "--slug", "t", "a.py", "--allow-empty")
        check("a duplicate id is not re-added", len(ledger("t")["universe"]) == 5)

        check(
            "L2+ without --evidence is refused",
            run("visit", "--slug", "t", "a.py", "--depth", "3") == 1,
        )
        run(
            "visit",
            "--slug",
            "t",
            "a.py",
            "--depth",
            "3",
            "--evidence",
            "traced callers",
        )
        t = tally(ledger("t"))
        check("a visit at the floor counts", t["at_floor"] == 1 and t["open"] == 4)
        run("visit", "--slug", "t", "b.py", "--depth", "1")
        t = tally(ledger("t"))
        check("below the floor stays open", t["at_floor"] == 1 and t["open"] == 4)
        run("visit", "--slug", "t", "a.py", "--depth", "1")
        check(
            "a lower visit does not lower depth",
            ledger("t")["universe"][0]["depth"] == 3,
        )
        check(
            "visiting an unknown id is refused",
            run("visit", "--slug", "t", "zzz.py", "--depth", "1") == 1,
        )
        check(
            "deferring an unknown id is refused",
            run("defer", "--slug", "t", "nope.py", "--why", "x") == 1,
        )
        run("defer", "--slug", "t", "c.py", "--why", "vendored, out of scope")
        t = tally(ledger("t"))
        check(
            "a deferral leaves the open count, not the denominator",
            t["open"] == 3 and t["deferred"] == 1 and t["total"] == 5,
        )
        # From here each close attempt has exactly one reason to refuse, so each
        # check proves its own branch rather than riding on another one.
        transcript("sess-a", reads=[fa])
        check("close refuses with open items", run("close", "--slug", "t") == 1)

        # --- the read audit ----------------------------------------------------
        for name in ("b.py", "d.py", "e.py"):
            run("visit", "--slug", "t", name, "--depth", "3", "--evidence", "read it")
        transcript("sess-a", reads=[fa, fd], bash=[f"sed -n '1,200p' {fb}"])
        check(
            "close refuses a visit with no read in the transcript",
            run("close", "--slug", "t") == 1,
        )
        transcript("sess-a", bash=[f"cat {fe} | head"])
        check("close passes when covered and audited", run("close", "--slug", "t") == 0)
        check(
            "a closed sweep moves to _closed/",
            not ledger_path("t").exists() and len(closed("t")) == 1,
        )
        closed_t = next((store_root() / CLOSED_DIR).glob(f"t-*/{LEDGER}"))
        check(
            "verify passes a sweep closed with every check passed",
            run("verify", str(closed_t)) == 0,
        )

        # --- the deferred share ------------------------------------------------
        init("t5")
        run("add", "--slug", "t5", "a.py", "b.py", "c.py", "d.py")
        run("defer", "--slug", "t5", "c.py", "d.py", "--why", "out of scope")
        for name in ("a.py", "b.py"):
            run("visit", "--slug", "t5", name, "--depth", "2", "--evidence", "read")
        check("more than 25% deferred blocks close", run("close", "--slug", "t5") == 1)
        check(
            "--force closes and records the check it overrode",
            run("close", "--slug", "t5", "--force") == 0
            and [c.get("forced") for c in closed("t5")] == [["deferred"]],
        )
        closed_t5 = next((store_root() / CLOSED_DIR).glob(f"t5-*/{LEDGER}"))
        check("verify refuses a forced close", run("verify", str(closed_t5)) == 1)

        # --- ownership, checkpoint, resume, epochs -------------------------------
        init("t2")
        run("add", "--slug", "t2", "x", "y")
        check(
            "an open ledger belongs to its session",
            open_ledgers_for("sess-a") == [ledger_path("t2")],
        )
        mutate(
            ledger_path("t2"),
            lambda data: data["deferred"].append({"id": "ghost", "why": "hand edit"}),
            work=False,
        )
        check(
            "a deferral for an id outside the universe is not counted",
            tally(ledger("t2"))["deferred"] == 0,
        )
        # An unbound ledger (no session id, e.g. opened on Codex) must never be
        # claimed by a session whose own id is empty.
        run("init", "--slug", "t7", "--goal", "g", "--done", "d", session=None)
        run("add", "--slug", "t7", "u1", session=None)
        check(
            "an empty session id matches nothing, not even an unbound ledger",
            ledger("t7")["session_id"] is None
            and open_ledgers_for("") == []
            and open_ledgers_for(None) == [],
        )
        check(
            "checkpoint needs a reason",
            run("checkpoint", "--slug", "t2", "--why", " ") == 1,
        )
        run("checkpoint", "--slug", "t2", "--why", "budget")
        led = ledger("t2")
        resume_text = (ledger_path("t2").parent / RESUME).read_text()
        check(
            "checkpoint records its reason",
            led["status"] == "checkpointed" and "budget" in resume_text,
        )
        check("the resume prompt names the floor", "L2" in resume_text)
        check("a checkpointed ledger is not open", open_ledgers_for("sess-a") == [])
        run("visit", "--slug", "t2", "x", "--depth", "1")
        led = ledger("t2")
        check(
            "new work reopens a checkpointed sweep",
            led["status"] == "open" and led["log"][-2]["event"] == "resume",
        )
        mutate(
            ledger_path("t2"),
            lambda data: log(data, "stop-block", "", at_floor=0),
            work=False,
        )
        check(
            "a block is visible within its epoch", last_block(ledger("t2")) is not None
        )
        run("visit", "--slug", "t2", "y", "--depth", "1", session="sess-b")
        led = ledger("t2")
        check("new work from another session rebinds it", led["session_id"] == "sess-b")
        check(
            "a rebind starts a new epoch that forgets earlier blocks",
            led["log"][epoch_start(led)]["event"] == "rebind"
            and last_block(led) is None,
        )
        check(
            "ownership moved with the rebind",
            open_ledgers_for("sess-a") == []
            and open_ledgers_for("sess-b") == [ledger_path("t2")],
        )

        # --- the lock --------------------------------------------------------------
        done = threading.Event()

        def visit_y() -> None:
            run(
                "visit",
                "--slug",
                "t2",
                "y",
                "--depth",
                "2",
                "--evidence",
                "e",
                session="sess-b",
            )
            done.set()

        with ledger_lock(ledger_path("t2")):
            worker = threading.Thread(target=visit_y)
            worker.start()
            time.sleep(0.3)
            waited = not done.is_set()
        worker.join(10)
        landed = (
            next(it for it in ledger("t2")["universe"] if it["id"] == "y")["depth"] == 2
        )
        check("a writer waits for the lock, then lands", waited and landed)

        # --- drift, then the done check --------------------------------------------
        listing = tmp / "list.txt"
        listing.write_text("m1\nm2\n")
        flag = tmp / "done.flag"
        flag.write_text("")
        init("t3", "--done-cmd", f"test -f {flag}")
        run("add", "--slug", "t3", "--from-cmd", f"cat {listing}")
        for m in ("m1", "m2"):
            run("visit", "--slug", "t3", m, "--depth", "2", "--evidence", "read")
        listing.write_text("m1\nm2\nm3\n")
        check(
            "close refuses when the universe drifted", run("close", "--slug", "t3") == 1
        )
        run("add", "--slug", "t3", "m3")
        run("visit", "--slug", "t3", "m3", "--depth", "2", "--evidence", "read")
        flag.unlink()
        check("close refuses while --done-cmd fails", run("close", "--slug", "t3") == 1)
        flag.write_text("")
        check(
            "close passes once drift is covered and the done check holds",
            run("close", "--slug", "t3") == 0,
        )

        gone = tmp / "gone.txt"
        gone.write_text("q1\n")
        init("t6")
        run(
            "add",
            "--slug",
            "t6",
            "--from-cmd",
            f"test -f {gone} && cat {gone} || exit 3",
        )
        run("visit", "--slug", "t6", "q1", "--depth", "2", "--evidence", "read")
        gone.unlink()
        check(
            "close exits 2 when an enumeration can no longer run",
            run("close", "--slug", "t6") == 2,
        )

        init("t4")
        check("close refuses an empty universe", run("close", "--slug", "t4") == 1)
        check(
            "verify refuses an open sweep", run("verify", str(ledger_path("t4"))) == 1
        )

        # --- an enumeration that errored must not certify a universe ----------------
        # Each failing command PRINTS an id before failing, so the empty-universe
        # guard cannot catch it; only the exit-code branch under test can.
        def add_from(cmd: str, allow_empty: bool = False) -> int:
            argv = ["add", "--slug", "t4", "--from-cmd", cmd]
            return run(*(argv + (["--allow-empty"] if allow_empty else [])))

        def universe_ids() -> set:
            return {it["id"] for it in ledger("t4")["universe"]}

        rc = add_from("printf 'z\\n'; exit 7")
        check(
            "errored enumeration exits 2 and writes nothing",
            rc == 2 and "z" not in universe_ids(),
        )
        rc = add_from("false | printf 'w\\n'")
        check(
            "failed pipeline stage exits 2 and writes nothing",
            rc == 2 and "w" not in universe_ids(),
        )
        check(
            "exit 1 with an error message is a failure",
            add_from("echo oops >&2; exit 1", allow_empty=True) == 2,
        )
        check("silent exit 1 is a real zero", add_from("exit 1", allow_empty=True) == 0)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="sweep.py", description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    # every command takes --project so the store can be found from anywhere
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--project",
        help="project whose .sweeps/ store to use (default: git root of the current folder)",
    )

    def add(name: str, **kw) -> argparse.ArgumentParser:
        return sub.add_parser(name, parents=[common], **kw)

    p = add("init", help="open a sweep: goal, done condition, depth floor")
    p.add_argument("--slug", required=True)
    p.add_argument("--goal", required=True)
    p.add_argument("--done", required=True, help="falsifiable done condition")
    p.add_argument("--done-cmd", help="shell check that close runs; must exit 0")
    p.add_argument(
        "--depth", type=int, default=2, help="depth floor 0-4 (default 2=read)"
    )
    p.add_argument("--floor-why", help="required for a floor below L2")
    p.set_defaults(fn=cmd_init)

    p = add("add", help="enumerate the universe")
    p.add_argument("ids", nargs="*")
    p.add_argument("--slug")
    p.add_argument("--from-cmd", help="shell command whose stdout lines are ids")
    p.add_argument("--from-file")
    p.add_argument("--stdin", action="store_true")
    p.add_argument(
        "--allow-empty",
        action="store_true",
        help="accept a zero-item enumeration as real",
    )
    p.set_defaults(fn=cmd_add)

    p = add("visit", help="record items reaching a depth")
    p.add_argument("ids", nargs="+")
    p.add_argument("--slug")
    p.add_argument("--depth", type=int, required=True)
    p.add_argument("--evidence", help="required at L2+: what you read, followed or ran")
    p.add_argument("--note")
    p.add_argument("--force", action="store_true", help="allow lowering a depth")
    p.add_argument("--add-missing", action="store_true")
    p.set_defaults(fn=cmd_visit)

    p = add("finding", help="record a finding with its evidence")
    p.add_argument("text")
    p.add_argument("--slug")
    p.add_argument("--evidence")
    p.add_argument("--item")
    p.set_defaults(fn=cmd_finding)

    p = add("defer", help="consciously leave items, with a reason")
    p.add_argument("ids", nargs="+")
    p.add_argument("--slug")
    p.add_argument("--why", required=True)
    p.set_defaults(fn=cmd_defer)

    p = add("revive", help="remove an obsolete deferral and preserve its history")
    p.add_argument("ids", nargs="+")
    p.add_argument("--slug")
    p.add_argument("--why", required=True)
    p.set_defaults(fn=cmd_revive)

    p = add("status", help="coverage arithmetic")
    p.add_argument("--slug")
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--all", action="store_true", help="include closed and abandoned sweeps"
    )
    p.add_argument("--next", type=int, default=0, help="also list N open items")
    p.set_defaults(fn=cmd_status)

    p = add("next", help="print the next N open ids, one per line")
    p.add_argument("-n", type=int, default=20)
    p.add_argument("--slug")
    p.set_defaults(fn=cmd_next)

    p = add("checkpoint", help="pause on purpose; the resume prompt is always current")
    p.add_argument("--slug")
    p.add_argument("--why", required=True)
    p.set_defaults(fn=cmd_checkpoint)

    p = add("close", help="close; refuses while items are open or unaudited")
    p.add_argument("--slug")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_close)

    p = add("render", help="render the ledger as markdown")
    p.add_argument("--slug")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_render)

    p = add("abandon", help="drop a sweep without claiming coverage")
    p.add_argument("--slug")
    p.add_argument("--why", required=True)
    p.set_defaults(fn=cmd_abandon)

    p = add("verify", help="read-only: exit 0 only for a ledger closed without --force")
    p.add_argument("ledger", help="a ledger.json, or the folder holding one")
    p.set_defaults(fn=cmd_verify)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not getattr(args, "cmd", None):
        ap.print_help()
        return 1
    project = getattr(args, "project", None)
    if project is not None and not Path(project).expanduser().is_dir():
        die(f"--project {project!r} is not a folder")
    set_base(project)
    return args.fn(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
