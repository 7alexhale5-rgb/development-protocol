#!/usr/bin/env python3
"""Best-of-N helper for /build-stack --best-of.

The judgment parts (building a candidate, judging a pair) belong to agents. The parts that
must be repeatable and testable live here: the candidate ledger, the test gate, hidden-test
isolation, blind judge packets, the verdict rule and the paired bootstrap.

Python 3.9+, standard library only. State lives in <project>/.devproto/bestofn/<run>/.
Every command prints JSON on stdout. A bad input prints one line to stderr and exits 1.

    bestofn.py --project <repo> init --run R --n 3 --seed S --spec spec.md
    bestofn.py --project <repo> register --run R --candidate c1 --diff c1.diff --worktree DIR [--tokens N]
    bestofn.py --project <repo> gate --run R --candidate c1 --visible CMD --hidden CMD --cwd DIR [--timeout S]
    bestofn.py --project <repo> isolation --run R --hidden-dir DIR
    bestofn.py --project <repo> blind --run R
    bestofn.py --project <repo> verdict --run R --votes votes.json [--judge-tokens N]
    bestofn.py stats --pairs pairs.json --seed S [--boot 10000]

Commands for gate are split with shell quoting rules and run without a shell. To use a shell
feature, pass `sh -c '...'` as the command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
CAND_ID = re.compile(r"^c[0-9]+$")
TAIL = 2000

JUDGE_INSTRUCTIONS = """# Compare two implementations

Two engineers implemented the same spec. Decide which implementation is better.

1. Read the spec, then read both implementations in full.
2. Judge correctness against the spec first. Look for missed cases, wrong results and unsafe input handling.
3. If both are equally correct, prefer the simpler one. Penalise unnecessary length: do not reward length, comments or extra features the spec did not ask for.
4. You do not know who wrote either one. Do not guess.

Answer on the first line with exactly one word: X, Y or tie. Then give at most five lines of reasons.
"""


# ---------- paths and ledger ----------


def _run_dir(project: Path, run: str) -> Path:
    if not RUN_ID.match(run or ""):
        raise ValueError(f"bad run id {run!r}: use letters, digits, dot, dash, underscore")
    return Path(project) / ".devproto" / "bestofn" / run


def _load(project: Path, run: str) -> dict:
    path = _run_dir(project, run) / "ledger.json"
    if not path.exists():
        raise ValueError(f"no such run {run!r}: run init first")
    return json.loads(path.read_text())


def _save(project: Path, run: str, ledger: dict) -> None:
    d = _run_dir(project, run)
    tmp = d / "ledger.json.tmp"
    tmp.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, d / "ledger.json")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _idnum(cid: str) -> int:
    """Candidate ids sort as numbers, so c10 comes after c2."""
    return int(cid[1:])


def _cand(ledger: dict, cid: str) -> dict:
    if not CAND_ID.match(cid or "") or cid not in ledger["candidates"]:
        raise ValueError(f"unknown candidate {cid!r}")
    return ledger["candidates"][cid]


def diff_size(diff_text: str) -> int:
    """Changed lines in a unified diff: added plus removed, file headers excluded."""
    lines = diff_text.splitlines()
    count = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            i += 2
            continue
        if line.startswith("+") or line.startswith("-"):
            count += 1
        i += 1
    return count


# ---------- init, register, gate ----------


def init_run(project, run, n, seed, spec_text):
    if n < 2:
        raise ValueError("best-of-N needs at least 2 candidates")
    d = _run_dir(project, run)
    if (d / "ledger.json").exists():
        raise ValueError(f"run {run!r} already exists")
    d.mkdir(parents=True, exist_ok=True)
    (d / "spec.md").write_text(spec_text)
    ledger = {
        "run": run,
        "n": n,
        "seed": str(seed),
        "spec_sha256": _sha(spec_text),
        "candidates": {f"c{i}": {"status": "pending"} for i in range(1, n + 1)},
    }
    _save(project, run, ledger)
    return ledger


def register(project, run, cid, diff_text, worktree, tokens=None):
    ledger = _load(project, run)
    cand = _cand(ledger, cid)
    d = _run_dir(project, run)
    (d / "diffs").mkdir(exist_ok=True)
    (d / "diffs" / f"{cid}.diff").write_text(diff_text)
    cand.update(
        worktree=str(Path(worktree).resolve()),
        diff_sha256=_sha(diff_text),
        diff_lines=diff_size(diff_text),
        tokens=tokens,
    )
    _save(project, run, ledger)
    return ledger


def _run(command: str, cwd: str, timeout: int, env: dict) -> dict:
    argv = shlex.split(command)
    if not argv:
        raise ValueError("empty test command")
    start = time.time()
    # Output goes to a temp file, not a pipe: a child that started its own session could hold a
    # pipe open and make us wait for it after the timeout.
    with tempfile.TemporaryFile() as out:
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT,
                                    start_new_session=True)
        except OSError as exc:
            return {"exit_code": 127, "timed_out": False, "tail": f"could not start: {exc}"[-TAIL:],
                    "wall_seconds": 0.0}
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        try:
            os.killpg(proc.pid, 9)  # also reaps leftovers of a run that finished
        except OSError:
            pass
        if timed_out:
            proc.wait()
        out.seek(0)
        text = out.read()[-TAIL:].decode("utf-8", "replace")
    return {"exit_code": 124 if timed_out else proc.returncode, "timed_out": timed_out, "tail": text,
            "wall_seconds": round(time.time() - start, 3)}


def gate(project, run, cid, visible_cmd, hidden_cmd, cwd, timeout=600):
    """Run the visible and hidden commands. Both must exit 0 for the candidate to survive.

    Only the exit code, timeout flag and time are kept for the hidden command. Its output is
    dropped so the ledger can never teach a builder what the hidden tests assert.
    """
    ledger = _load(project, run)
    cand = _cand(ledger, cid)
    cwd = str(Path(cwd).resolve())
    env = dict(os.environ, BESTOFN_CANDIDATE_DIR=cwd)
    vis = _run(visible_cmd, cwd, timeout, env)
    hid = _run(hidden_cmd, cwd, timeout, env)
    hid.pop("tail", None)
    passed = vis["exit_code"] == 0 and hid["exit_code"] == 0 and not vis["timed_out"] and not hid["timed_out"]
    cand.update(visible=vis, hidden=hid, status="survivor" if passed else "out")
    _save(project, run, ledger)
    return {"candidate": cid, "status": cand["status"], "visible": vis, "hidden": hid}


def check_isolation(project, run, hidden_dir):
    """Problems if the hidden tests sit inside, or around, any candidate worktree."""
    ledger = _load(project, run)
    hidden = Path(hidden_dir).resolve()
    problems = []
    for cid, cand in sorted(ledger["candidates"].items(), key=lambda kv: _idnum(kv[0])):
        wt = cand.get("worktree")
        if not wt:
            continue
        wt = Path(wt).resolve()
        if hidden == wt or wt in hidden.parents:
            problems.append(f"hidden dir is inside {cid}'s worktree")
        elif hidden in wt.parents:
            problems.append(f"{cid}'s worktree is inside the hidden dir")
    return problems


# ---------- blind packets and verdict ----------


def _survivors(ledger: dict) -> list:
    return sorted((c for c, v in ledger["candidates"].items() if v.get("status") == "survivor"), key=_idnum)


def blind(project, run):
    ledger = _load(project, run)
    d = _run_dir(project, run)
    survivors = _survivors(ledger)
    packets_dir, private = d / "packets", d / "private"
    packets_dir.mkdir(exist_ok=True)
    private.mkdir(exist_ok=True)
    for old in packets_dir.glob("*.md"):
        old.unlink()
    (private / "survivors.json").write_text(json.dumps(survivors) + "\n")
    if len(survivors) < 2:
        (private / "key.json").write_text("{}\n")
        return []
    spec = (d / "spec.md").read_text()
    key = {}
    for ai, a in enumerate(survivors):
        for b in survivors[ai + 1:]:
            for order, (x, y) in (("ab", (a, b)), ("ba", (b, a))):
                pid = "j" + _sha(f"{ledger['seed']}|{a}|{b}|{order}")[:6]
                if pid in key:
                    raise ValueError("packet id collision: change the seed")
                key[pid] = {"x": x, "y": y}
                body = JUDGE_INSTRUCTIONS + "\n## Spec\n\n" + spec.rstrip() + "\n"
                for label, who in (("X", x), ("Y", y)):
                    text = (d / "diffs" / f"{who}.diff").read_text()
                    wt = ledger["candidates"][who].get("worktree")
                    if wt and len(wt) > 1 and os.path.isabs(wt):
                        text = text.replace(wt, "<path>")
                    longest = max([len(m) for m in re.findall(r"`+", text)] or [0])
                    fence = "`" * max(3, longest + 1)  # a diff cannot close its own block
                    body += f"\n## Candidate {label}\n\n{fence}diff\n{text.rstrip()}\n{fence}\n"
                (packets_dir / f"{pid}.md").write_text(body)
    (private / "key.json").write_text(json.dumps(key, indent=2, sort_keys=True) + "\n")
    return sorted(key)


def verdict(project, run, votes, judge_tokens=None):
    ledger = _load(project, run)
    d = _run_dir(project, run)
    survivors = _survivors(ledger)
    result = {"run": run, "survivors": survivors, "pairs": [], "judge_tokens": judge_tokens}
    if not isinstance(votes, dict):
        raise ValueError("votes must be a JSON object mapping packet id to X, Y or tie")
    if not survivors:
        result.update(winner=None, winner_decided_by="no_survivor")
    elif len(survivors) == 1:
        result.update(winner=survivors[0], winner_decided_by="only_survivor")
    else:
        key = json.loads((d / "private" / "key.json").read_text())
        recorded = json.loads((d / "private" / "survivors.json").read_text())
        if recorded != survivors:
            raise ValueError(f"survivors changed since blind ({recorded} then, {survivors} now): run blind again")
        if set(votes) != set(key):
            missing, extra = sorted(set(key) - set(votes)), sorted(set(votes) - set(key))
            raise ValueError(f"votes do not match packets (missing {missing}, unknown {extra})")
        for pid, v in votes.items():
            if v not in ("X", "Y", "tie"):
                raise ValueError(f"vote for {pid} must be X, Y or tie, not {v!r}")
        size = {c: ledger["candidates"][c]["diff_lines"] for c in survivors}
        wins = {c: 0 for c in survivors}
        for ai, a in enumerate(survivors):
            for b in survivors[ai + 1:]:
                picks = []
                for pid, k in sorted(key.items()):
                    if {k["x"], k["y"]} == {a, b}:
                        v = votes[pid]
                        picks.append(k["x"] if v == "X" else k["y"] if v == "Y" else None)
                if picks[0] is not None and picks[0] == picks[1]:
                    win, how = picks[0], "both_orders_agree"
                elif size[a] != size[b]:
                    win, how = (a if size[a] < size[b] else b), "smaller_diff"
                else:
                    win, how = a, "lower_id"  # survivors are sorted, so a has the lower id
                wins[win] += 1
                result["pairs"].append({"pair": [a, b], "winner": win, "decided_by": how})
        top = max(wins.values())
        leaders = [c for c in survivors if wins[c] == top]
        if len(leaders) == 1:
            result.update(winner=leaders[0], winner_decided_by="most_pairwise_wins")
        else:
            leaders.sort(key=lambda c: (size[c], _idnum(c)))
            by = "cycle_smaller_diff" if size[leaders[0]] != size[leaders[1]] else "cycle_lower_id"
            result.update(winner=leaders[0], winner_decided_by=by)
        result["wins"] = wins
    (d / "verdict.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


# ---------- stats ----------


def bootstrap_ci(diffs, seed, n_boot=10000, alpha=0.05):
    """Seeded percentile bootstrap of the mean of paired differences."""
    values = [float(v) for v in diffs]
    if not values:
        raise ValueError("no paired observations")
    if n_boot < 100:
        raise ValueError("use at least 100 bootstrap resamples")
    rng = random.Random(str(seed))
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot) - 1]
    return sum(values) / n, lo, hi


# ---------- command line ----------


def _emit(obj) -> int:
    print(json.dumps(obj, indent=2, sort_keys=True))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, *flags):
        p = sub.add_parser(name)
        for flag, kwargs in flags:
            p.add_argument(flag, **kwargs)
        return p

    run = ("--run", {"required": True})
    add("init", run, ("--n", {"type": int, "default": 3}), ("--seed", {"required": True}), ("--spec", {"required": True}))
    add("register", run, ("--candidate", {"required": True}), ("--diff", {"required": True}),
        ("--worktree", {"required": True}), ("--tokens", {"type": int}))
    add("gate", run, ("--candidate", {"required": True}), ("--visible", {"required": True}),
        ("--hidden", {"required": True}), ("--cwd", {"required": True}), ("--timeout", {"type": int, "default": 600}))
    add("isolation", run, ("--hidden-dir", {"required": True}))
    add("blind", run)
    add("verdict", run, ("--votes", {"required": True}), ("--judge-tokens", {"type": int}))
    add("stats", ("--pairs", {"required": True}), ("--seed", {"required": True}), ("--boot", {"type": int, "default": 10000}))
    a = ap.parse_args(argv)
    project = Path(a.project)
    try:
        if a.cmd == "init":
            led = init_run(project, a.run, a.n, a.seed, Path(a.spec).read_text())
            return _emit({"run": a.run, "candidates": sorted(led["candidates"]), "spec_sha256": led["spec_sha256"]})
        if a.cmd == "register":
            led = register(project, a.run, a.candidate, Path(a.diff).read_text(), a.worktree, a.tokens)
            c = led["candidates"][a.candidate]
            return _emit({"candidate": a.candidate, "diff_sha256": c["diff_sha256"], "diff_lines": c["diff_lines"]})
        if a.cmd == "gate":
            res = gate(project, a.run, a.candidate, a.visible, a.hidden, a.cwd, a.timeout)
            return _emit({"candidate": a.candidate, "status": res["status"], "visible_exit": res["visible"]["exit_code"],
                          "hidden_exit": res["hidden"]["exit_code"]})
        if a.cmd == "isolation":
            problems = check_isolation(project, a.run, a.hidden_dir)
            _emit({"ok": not problems, "problems": problems})
            return 1 if problems else 0
        if a.cmd == "blind":
            return _emit({"packets": blind(project, a.run)})
        if a.cmd == "verdict":
            res = verdict(project, a.run, json.loads(Path(a.votes).read_text()), a.judge_tokens)
            _emit(res)
            if res["winner"] is None:
                print("bestofn: no survivor, so no winner. Stop and tell the person; do not lower the gate.", file=sys.stderr)
                return 1
            return 0
        if a.cmd == "stats":
            pairs = json.loads(Path(a.pairs).read_text())
            diffs = [p["best_of"] - p["single"] for p in pairs]
            mean, lo, hi = bootstrap_ci(diffs, a.seed, a.boot)
            return _emit({"n": len(diffs), "mean_diff": mean, "ci_low": lo, "ci_high": hi,
                          "excludes_zero": lo > 0 or hi < 0})
    except (ValueError, OSError, KeyError, TypeError, AttributeError, IndexError, json.JSONDecodeError) as exc:
        print(f"bestofn: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
