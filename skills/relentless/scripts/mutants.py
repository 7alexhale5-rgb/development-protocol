#!/usr/bin/env python3
"""mutants.py: prove the relentless self-tests can fail.

A self-test that has only ever run green proves nothing. Each mutant below is one
deliberate bug: an exact piece of text in a target file and what to replace it with.
The swap happens in an in-memory copy, never on disk. The target's selftest() must
pass on the original and fail on every mutant. A mutant that survives means a
branch of the code can be deleted without any check noticing.

Exit codes: 0 every mutant killed · 1 a mutant survived or the original failed ·
2 a mutant's text is missing or does not compile, so the list has drifted from the
code and nothing was measured.

Usage:  python3 mutants.py            (all targets)
The package's unit tests run it too (tests/test_relentless.py).
"""

from __future__ import annotations

import contextlib
import io
import sys
import types
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent

# (target relative to the skill folder, label, exact original text, replacement)
MUTANTS = [
    # --- enumeration: an errored command cannot certify a universe
    (
        "scripts/sweep.py",
        "enumeration-error branch",
        "    if failed:\n",
        "    if False:\n",
    ),
    (
        # pipefail now lives in the shared runner both sweep.py and pathway.py
        # import (skills/development-protocol/scripts/_shared.py), reached
        # here by relative path since it is outside this skill's own folder.
        "../development-protocol/scripts/_shared.py",
        "pipefail dropped",
        '[bash, "-o", "pipefail", "-c", cmd],\n            cwd=str(cwd)',
        "[bash, '-c', cmd],\n            cwd=str(cwd)",
    ),
    (
        "scripts/sweep.py",
        "exit 1 with output accepted",
        "code == 1 and bool(stdout.strip() or stderr.strip())",
        "False",
    ),
    (
        "scripts/sweep.py",
        "exit 1 with stderr accepted",
        "bool(stdout.strip() or stderr.strip())",
        "bool(stdout.strip())",
    ),
    # --- counting
    ("scripts/sweep.py", "floor comparison", "if d >= floor:", "if d > floor:"),
    (
        "scripts/sweep.py",
        "phantom deferrals counted",
        'for d in data.get("deferred", []) if d["id"] in ids}',
        'for d in data.get("deferred", [])}',
    ),
    (
        "scripts/sweep.py",
        "lower visit overwrites depth",
        'if args.depth > int(it.get("depth", 0)) or args.force:',
        "if True:",
    ),
    # --- honest claims
    (
        "scripts/sweep.py",
        "evidence not required",
        "if args.depth >= EVIDENCE_FROM and not args.evidence:",
        "if False:",
    ),
    (
        "scripts/sweep.py",
        "low floor needs no reason",
        "if args.depth < EVIDENCE_FROM and not args.floor_why:",
        "if False:",
    ),
    (
        "scripts/sweep.py",
        "unknown ids deferrable",
        "        if unknown:",
        "        if False:",
    ),
    # --- close checks, each proved alone
    ("scripts/sweep.py", "close ignores open items", 'if t["open"] > 0:', "if False:"),
    (
        "scripts/sweep.py",
        "close accepts empty universe",
        'if not t["total"]:',
        "if False:",
    ),
    (
        "scripts/sweep.py",
        "deferred share unchecked",
        'if t["total"] and t["deferred"] / t["total"] > MAX_DEFERRED_SHARE:',
        "if False:",
    ),
    ("scripts/sweep.py", "drift ignored", "        if drifted:", "        if False:"),
    ("scripts/sweep.py", "done-cmd ignored", "if code != 0:", "if False:"),
    ("scripts/sweep.py", "read audit passes all", "if real in reads:", "if True:"),
    (
        "scripts/sweep.py",
        "read audit never refuses",
        "    if unverified:",
        "    if False:",
    ),
    # --- the read-only verifier a checklist row calls
    (
        "scripts/sweep.py",
        "verify accepts a forced close",
        '    if data.get("forced"):\n',
        "    if False:\n",
    ),
    (
        "scripts/sweep.py",
        "verify accepts an open sweep",
        '    if data.get("status") != "closed":\n',
        "    if False:\n",
    ),
    # --- ownership, epochs, persistence, locking
    (
        "scripts/sweep.py",
        "session filter dropped",
        'if d.get("status") == "open" and d.get("session_id") == session:',
        'if d.get("status") == "open":',
    ),
    (
        "scripts/sweep.py",
        "empty session matches",
        "    if not session:\n        return []\n",
        "",
    ),
    (
        "scripts/sweep.py",
        "no rebind",
        'if me and data.get("session_id") != me:',
        "if False:",
    ),
    (
        "scripts/sweep.py",
        "checkpoint never reopens",
        'if data.get("status") == "checkpointed":',
        "if False:",
    ),
    (
        "scripts/sweep.py",
        "epochs never reset",
        'in ("init", "resume", "rebind"):',
        'in ("init",):',
    ),
    (
        "scripts/sweep.py",
        "RESUME.md not rewritten",
        '    _atomic_write(path.parent / RESUME, resume_prompt(data, path) + "\\n")\n',
        "",
    ),
    (
        "scripts/sweep.py",
        "lock is a no-op",
        "            fcntl.flock(fd, fcntl.LOCK_EX)\n",
        "            pass\n",
    ),
    # --- the Stop hook
    (
        "hooks/relentless-stop.py",
        "ownership and status ignored",
        "ledgers = sweep.open_ledgers_for(session)",
        "ledgers = sweep.all_ledgers()",
    ),
    (
        "hooks/relentless-stop.py",
        "no-progress stop re-blocks",
        'if prior is None or t["at_floor"] > int(prior.get("at_floor", -1)):',
        'if prior is None or t["at_floor"] >= int(prior.get("at_floor", -1)):',
    ),
    (
        "hooks/relentless-stop.py",
        "always blocks",
        'if prior is None or t["at_floor"] > int(prior.get("at_floor", -1)):',
        "if True:",
    ),
    (
        "hooks/relentless-stop.py",
        "never blocks",
        'if prior is None or t["at_floor"] > int(prior.get("at_floor", -1)):',
        "if False:",
    ),
    (
        "hooks/relentless-stop.py",
        "StopFailure treated as Stop",
        'if event == "StopFailure":',
        "if False:",
    ),
    (
        "hooks/relentless-stop.py",
        "fail-open wrapper dropped",
        "    except Exception as exc:  # noqa: BLE001\n",
        "    except ZeroDivisionError as exc:  # noqa: BLE001\n",
    ),
]


def run_selftest(path: Path, source: str) -> tuple[int, list[str], str]:
    """Execute `source` as a fresh module named after `path` and run its selftest()."""
    code = compile(source, str(path), "exec")
    mod = types.ModuleType(f"mutant_{path.stem.replace('-', '_')}")
    mod.__file__ = str(path)
    out = io.StringIO()
    crash = ""
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            exec(code, mod.__dict__)
            rc = int(mod.selftest() or 0)
        except SystemExit as exc:  # a mutant can make a die() escape the test
            rc, crash = 1, f"SystemExit({exc.code})"
        except Exception as exc:  # noqa: BLE001 - any crash is a failed selftest
            rc, crash = 1, f"{type(exc).__name__}: {exc}"
    fails = [
        ln.strip()[5:].strip()
        for ln in out.getvalue().splitlines()
        if ln.strip().startswith("FAIL ")
    ]
    return rc, fails, crash


def main() -> int:
    originals: dict[str, str] = {}
    drift = []
    for rel, label, old, _new in MUTANTS:
        text = originals.setdefault(rel, (SKILL / rel).read_text())
        if text.count(old) != 1:
            drift.append(f"{rel} · {label}: expected 1 match, found {text.count(old)}")
    if drift:
        print("mutants: list has drifted from the code; nothing measured:")
        for d in drift:
            print(f"  {d}")
        return 2

    status = 0
    for rel, text in originals.items():
        rc, fails, crash = run_selftest(SKILL / rel, text)
        ok = rc == 0 and not fails and not crash
        print(f"{'ok  ' if ok else 'FAIL'}  original {rel} passes its selftest")
        if not ok:
            print(f"        rc={rc} fails={fails} {crash}")
            status = 1

    print()
    print(f"{'result':8} {'target':20} {'mutant':28} checks that failed")
    for rel, label, old, new in MUTANTS:
        mutated = originals[rel].replace(old, new)
        try:
            compile(mutated, rel, "exec")
        except SyntaxError as exc:
            print(f"mutants: '{label}' does not compile ({exc}); fix the list.")
            return 2
        rc, fails, crash = run_selftest(SKILL / rel, mutated)
        killed = rc != 0
        detail = "; ".join(fails) or crash or "(none)"
        print(f"{'killed' if killed else 'SURVIVED':8} {rel:20} {label:28} {detail}")
        if not killed:
            status = 1
    print()
    print("every mutant killed" if status == 0 else "mutation check FAILED")
    return status


if __name__ == "__main__":
    sys.exit(main())
