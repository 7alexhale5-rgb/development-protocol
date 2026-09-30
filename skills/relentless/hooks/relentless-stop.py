#!/usr/bin/env python3
"""Stop / StopFailure hook: /relentless keeps a sweep from ending on a feeling.

WHY
---
An agent on an exhaustive sweep tends to stop when it FEELS it has enough. The
coverage ledger (../scripts/sweep.py) turns that feeling into a count. This hook
makes the count bind at the one moment it matters: the end of a turn.

WHAT IT DOES
------------
It looks in the .sweeps/ store of the project the session runs in (the hook
payload's cwd; SWEEP_HOME overrides).
Stop. For each OPEN ledger the stopping session owns (the last session to change it):
  * no block logged in the current open epoch, or the at-floor count rose since
    the last one -> exit 2 with the coverage line and the ways out (keep going,
    close, or checkpoint with a reason). The block is written to the ledger's log.
  * the agent stops again with no progress since the last block -> checkpoint the
    ledger for it (RESUME.md is always current) and tell the user; exit 0.
StopFailure (usage limit, API error). Checkpoint every open ledger the session
owns, with the failure as the reason. Never blocks.

DECLARED EXCEPTIONS (decided 2026-09-22)
----------------------------------------
  * It does not stand down on stop_hook_active, as most Stop hooks should. It
    re-blocks only while the at-floor count strictly rises, and that count is
    bounded by the universe, so it cannot re-fire forever. A stall checkpoints
    and says so. Nothing is ever silenced: the only record it reads is the
    ledger's own log.
  * Fails open. Bad stdin, an unreadable ledger, a busy lock or any exception
    -> exit 0, logged. It must never trap a session.
  * No disable switch. The release valves are the ledger commands.

Log: <project>/.sweeps/stop-hook.log (JSON lines, mode 0600), written only when
that store already exists; RELENTLESS_LOG overrides.
Self-test:  python3 relentless-stop.py --selftest
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import sweep  # noqa: E402

LOCK_WAIT = 2.0  # seconds; well inside the hook's 10 s timeout
STALL_WHY = "stop hook: the agent stopped again with no progress since the last block"


def log_path() -> Path | None:
    """RELENTLESS_LOG, else a log inside an existing store. None: do not log,
    so a stop in a project with no sweeps never creates a .sweeps/ folder."""
    override = os.environ.get("RELENTLESS_LOG")
    if override:
        return Path(override)
    store = sweep.store_root()
    return store / "stop-hook.log" if store.is_dir() else None


def note(**entry) -> None:
    entry = {"ts": sweep.now_iso(), **entry}
    try:
        path = log_path()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        fresh = not path.exists()
        with path.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")
        if fresh:
            os.chmod(path, 0o600)
    except OSError:
        pass


def decide(path: Path, session: str, failure: str = None) -> tuple[str, dict]:
    """Block while the at-floor count keeps rising; checkpoint on a stall."""

    def apply(data: dict) -> tuple[str, dict]:
        t = sweep.tally(data)
        if failure is not None:
            sweep.mark_checkpoint(data, failure, by="stop-failure")
            return "checkpoint", sweep.tally(data)
        prior = sweep.last_block(data)
        if prior is None or t["at_floor"] > int(prior.get("at_floor", -1)):
            sweep.log(
                data,
                "stop-block",
                f"{t['open']} open",
                at_floor=t["at_floor"],
                open=t["open"],
            )
            return "block", t
        sweep.mark_checkpoint(data, STALL_WHY, by="stop-hook")
        return "stall", sweep.tally(data)

    with sweep.ledger_lock(path, timeout=LOCK_WAIT):
        data = sweep.load(path)
        if not session or data.get("session_id") != session or data.get("status") != "open":
            return "skip", sweep.tally(data)
        result = apply(data)
        sweep.save(path, data)
        return result


def block_message(t: dict, path: Path) -> str:
    s = f"python3 {sweep.SWEEP_PY}"
    slug = t["slug"]
    why = (
        f"{t['open']} item(s) are still below L{t['depth_floor']}"
        if t["open"]
        else "every item is at the floor, but the sweep was never closed"
    )
    return (
        "relentless (the /relentless skill's Stop hook): this session owns an open "
        f"sweep ledger at {path}\n"
        f"{sweep.headline(t)}\n"
        f"The sweep is not done: {why}. Ending the turn now would end it on a "
        "feeling. Pick one:\n"
        f"  keep going:  {s} next --slug {slug} -n 20   (visit each with --evidence)\n"
        f"  finished:    {s} close --slug {slug}   (it audits the reads)\n"
        "  must stop (budget, blocked, or the user paused or changed topic):\n"
        f'               {s} checkpoint --slug {slug} --why "<reason>"\n'
        "To ask the user something, use a question tool that waits inside the turn "
        "if your agent has one (Claude Code: AskUserQuestion). Stopping again with "
        "no new progress checkpoints the sweep for you and tells the user."
    )


def stall_notice(t: dict, path: Path) -> str:
    return (
        f"relentless: sweep '{t['slug']}' paused with {t['open']} of {t['total']} "
        f"items open (no progress since the last nudge). Resume prompt: "
        f"{path.parent / sweep.RESUME}"
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        note(event="bad-stdin")
        return 0
    event = payload.get("hook_event_name") or "Stop"
    session = payload.get("session_id") or ""
    cwd = payload.get("cwd")
    sweep.set_base(cwd if isinstance(cwd, str) and cwd else None)
    ledgers = sweep.open_ledgers_for(session)
    if not ledgers:
        return 0
    blocks: list[str] = []
    notices: list[str] = []
    for path in ledgers:
        slug = path.parent.name
        try:
            failure = None
            if event == "StopFailure":
                reason = payload.get("error") or payload.get("reason") or "unknown"
                failure = f"session stopped by a failure: {reason}"
            kind, t = decide(path, session, failure)
            if kind == "skip":
                continue
        except TimeoutError:
            note(event=event, session=session, slug=slug, kind="lock-busy")
            continue
        except Exception as exc:  # noqa: BLE001 - fail open, but say why in the log
            note(event=event, session=session, slug=slug, kind="error", error=repr(exc))
            continue
        note(
            event=event,
            session=session,
            slug=slug,
            kind=kind,
            at_floor=t["at_floor"],
            open=t["open"],
        )
        if kind == "block":
            blocks.append(block_message(t, path))
        else:
            notices.append(stall_notice(t, path))
    if blocks:
        print("\n\n".join(blocks + notices), file=sys.stderr)
        return 2
    if notices:
        print(json.dumps({"systemMessage": "\n".join(notices)}))
    return 0


def entry() -> int:
    """The fail-open wrapper. A broken hook must never trap a session."""
    try:
        return main()
    except Exception as exc:  # noqa: BLE001
        note(event="crash", error=repr(exc))
        return 0


# --------------------------------------------------------------------------
# self-test (in-process, so mutants.py can kill mutations of this file)
# --------------------------------------------------------------------------
def selftest() -> int:
    global LOCK_WAIT
    tmp = Path(tempfile.mkdtemp(prefix="relentless-stop-selftest-"))
    keys = (
        "SWEEP_HOME",
        "SWEEP_TRANSCRIPTS",
        "RELENTLESS_LOG",
        "SWEEP_SESSION_ID",
        "CLAUDE_CODE_SESSION_ID",
    )
    saved = {k: os.environ.get(k) for k in keys}
    saved_wait = LOCK_WAIT
    saved_open = sweep.open_ledgers_for
    os.environ["SWEEP_HOME"] = str(tmp / "home")
    os.environ["SWEEP_TRANSCRIPTS"] = str(tmp / "transcripts")
    os.environ["RELENTLESS_LOG"] = str(tmp / "stop.log")
    os.environ.pop("SWEEP_SESSION_ID", None)
    LOCK_WAIT = 0.2
    fails: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(("  ok   " if cond else "  FAIL ") + name)
        if not cond:
            fails.append(name)

    def cli(*argv: str, session: str = "s1") -> int:
        os.environ["CLAUDE_CODE_SESSION_ID"] = session
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()):
                try:
                    return sweep.main(list(argv))
                except SystemExit as exc:
                    return int(exc.code or 0)

    def fire(payload) -> tuple[int, str, str]:
        text = payload if isinstance(payload, str) else json.dumps(payload)
        out, err = io.StringIO(), io.StringIO()
        real_stdin = sys.stdin
        sys.stdin = io.StringIO(text)
        try:
            with contextlib.redirect_stdout(out):
                with contextlib.redirect_stderr(err):
                    rc = entry()
        finally:
            sys.stdin = real_stdin
        return rc, out.getvalue(), err.getvalue()

    def stop(session: str = "s1") -> tuple[int, str, str]:
        return fire({"session_id": session, "hook_event_name": "Stop"})

    def ledger(slug: str) -> dict:
        return sweep.load(sweep.ledger_path(slug))

    try:
        check("no ledger: silent pass", stop() == (0, "", ""))

        cli("init", "--slug", "h1", "--goal", "g", "--done", "d", "--project", str(tmp))
        cli("add", "--slug", "h1", "i1", "i2", "i3")
        rc, _out, err = stop()
        check("first stop with open items blocks", rc == 2 and "not done" in err)
        check(
            "the block is logged in the ledger",
            sweep.last_block(ledger("h1")) is not None,
        )
        check("another session's sweep never blocks", stop("s2") == (0, "", ""))
        check("an empty session id never blocks", stop("") == (0, "", ""))

        cli("visit", "--slug", "h1", "i1", "--depth", "2", "--evidence", "read")
        rc, _out, err = stop()
        check("progress since the last block blocks again", rc == 2)

        rc, out, _err = stop()
        led = ledger("h1")
        check(
            "a stall checkpoints instead of blocking",
            rc == 0
            and led["status"] == "checkpointed"
            and led["checkpoint"]["by"] == "stop-hook",
        )
        check(
            "the stall tells the user where to resume",
            "systemMessage" in json.loads(out or "{}")
            and "RESUME.md" in json.loads(out)["systemMessage"],
        )
        check(
            "the resume prompt is on disk",
            (sweep.ledger_path("h1").parent / sweep.RESUME).is_file(),
        )
        check("a checkpointed sweep does not block", stop() == (0, "", ""))

        cli("visit", "--slug", "h1", "i2", "--depth", "2", "--evidence", "read")
        rc, _out, _err = stop()
        check("resumed work starts a new epoch, so the first stop blocks", rc == 2)

        rc, _out, _err = fire(
            {
                "session_id": "s1",
                "hook_event_name": "StopFailure",
                "error": "rate_limit",
            }
        )
        led = ledger("h1")
        check(
            "StopFailure checkpoints and never blocks",
            rc == 0
            and led["status"] == "checkpointed"
            and "rate_limit" in led["checkpoint"]["why"],
        )

        cli("init", "--slug", "h2", "--goal", "g", "--done", "d", "--project", str(tmp))
        cli("add", "--slug", "h2", "j1")
        cli("abandon", "--slug", "h2", "--why", "fixture")
        check("an abandoned sweep does not block", stop() == (0, "", ""))

        cli("init", "--slug", "h3", "--goal", "g", "--done", "d", "--project", str(tmp))
        cli("add", "--slug", "h3", "k1")
        with sweep.ledger_lock(sweep.ledger_path("h3")):
            rc, _out, _err = stop()
        check("a busy lock fails open", rc == 0)
        busy = [json.loads(ln) for ln in (tmp / "stop.log").read_text().splitlines()]
        check(
            "the busy lock is logged", any(e.get("kind") == "lock-busy" for e in busy)
        )

        check("bad stdin fails open", fire("not json")[0] == 0)

        def boom(_session):
            raise RuntimeError("simulated")

        sweep.open_ledgers_for = boom
        try:
            crashed = fire({"session_id": "s1", "hook_event_name": "Stop"})[0]
        finally:
            sweep.open_ledgers_for = saved_open
        check("an exception inside the hook fails open", crashed == 0)
    finally:
        sweep.open_ledgers_for = saved_open
        LOCK_WAIT = saved_wait
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'PASS' if not fails else 'FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(selftest())
    sys.exit(entry())
