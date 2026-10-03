#!/usr/bin/env python3
"""pathway: which engineering pathway to run next for one piece of work.

An outcome (one work id, shared with the development-protocol checklist) owes a
set of pathways, sized by how finished it must be. A pathway closes only when an
evidence file exists and a verifier command exits 0, or when it is marked n/a
with a written reason. If a proved pathway's evidence file changes or vanishes,
it reopens and trust fails until it is proved again.

State lives in <project>/.devproto/pathway/<work-id>.json. Standard library only.
Python 3.9 or newer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# _shared.py is the development-protocol skill's, not this one's: locate it by
# relative path (skills/<this>/scripts -> skills/development-protocol/scripts)
# and fail with a clear, actionable message if that skill is not installed
# alongside this one, rather than a bare "No module named '_shared'".
_SHARED_DIR = (
    Path(__file__).resolve().parent.parent.parent / "development-protocol" / "scripts"
)
if not (_SHARED_DIR / "_shared.py").is_file():
    raise ImportError(
        "pathway.py needs the 'development-protocol' skill installed alongside it "
        f"(expected {_SHARED_DIR / '_shared.py'}); reinstall the development-protocol-skill stack."
    )
sys.path.insert(0, str(_SHARED_DIR))
from _shared import command_digest, digest, locked, now, redact  # noqa: E402
from _shared import run_verifier as _run_verifier  # noqa: E402

# Catalog order is foundation first: the router recommends the first open one.
CATALOG = [
    "govern",
    "research",
    "data",
    "security",
    "design",
    "implementation",
    "quality",
    "field",
    "observability",
    "techdebt",
    "release",
    "docs",
]
TIERS = {
    "demoable": ["govern", "implementation", "quality"],
    "live": [
        "govern",
        "implementation",
        "quality",
        "data",
        "observability",
        "release",
        "docs",
    ],
}
TIERS["production-secure"] = TIERS["live"] + ["research", "security", "techdebt"]
GOAL_PULLS = [
    (
        "design",
        re.compile(
            r"\b(ui|ux|screen|page|frontend|dashboard|visual|design|layout)\b", re.I
        ),
    ),
    (
        "research",
        re.compile(
            r"\b(research|unknown|investigate|evaluate|compare|regulation|spike)\b",
            re.I,
        ),
    ),
    (
        "data",
        re.compile(
            r"\b(data|database|schema|migration|table|query|import|export)\b", re.I
        ),
    ),
]
SAFE = {"research", "govern", "data", "security", "quality", "observability", "docs"}
CRITIC = "second-model critic: a different model family reviews the diff"
CARDS = {
    "govern": (
        "/development-protocol",
        ["/development-protocol", "/audit-setup", CRITIC],
        "Put the repo's own proof in place: checklist started, CI runs the tests on every pull request, the base branch requires that check.",
        "A pull request cannot merge unless the test check passed on its commit.",
        "the CI workflow file, the branch rule, and .devproto/<work-id>.json",
        "git host CLI (optional)",
    ),
    "research": (
        "/research-stack --focus <tags>",
        ["/research-stack --focus <tags>", "/devilsadvocate"],
        "Answer the open unknowns from primary sources before anyone builds. Confirm the focus tags"
        " the checklist suggests from the goal (for example ui-ux,a11y or devtools,security) at the"
        " research scope gate, then pass them.",
        "Every claim in research.md names a source a second reader can open.",
        ".devproto/evidence/research.md",
        "web search and docs lookup (optional)",
    ),
    "data": (
        "/planning-stack",
        ["/planning-stack", "/build-stack", "/review-stack", CRITIC],
        "Make the data shape real: schema or migration, applied to a scratch database, read back.",
        "The migration applies and rolls back on a scratch copy, and a test reads the data back.",
        "the migration file plus the round-trip test log",
        "a scratch database, never production",
    ),
    "security": (
        "/review-stack",
        ["/review-stack", "/devilsadvocate --premortem", CRITIC],
        "Check who can reach what: auth on every route, input handling, secrets kept out of the repo.",
        "A test proves an unauthorized request is refused, and a secret scan of the diff is clean.",
        ".devproto/evidence/security.md plus the access test",
        "a secret scanner (optional)",
    ),
    "design": (
        "/design-stack",
        ["/visual-spec", "/design-stack", "/review-stack"],
        "Draw the screens and every state before code: empty, loading, error, full.",
        "Screenshots of every state match the spec on a phone width and a desktop width.",
        "screenshot files plus design notes",
        "browser automation for screenshots (optional)",
    ),
    "implementation": (
        "/build-stack",
        ["/karpathy spec", "/planning-stack", "/build-stack", "/simplify", CRITIC],
        "Build the next slice against a check that was written first and failed first.",
        "The check written first now passes, and the full suite is green.",
        "the diff plus the test log",
        "the project's test runner",
    ),
    "quality": (
        "/review-stack",
        ["/karpathy verify", "/review-stack", "/simplify", CRITIC],
        "Run the full suite, then use the real thing and read back what it saved.",
        "Full suite green, and the main journey exercised end to end with the result read back.",
        "the test log plus a read-back file or screenshot",
        "the project's test runner",
    ),
    "field": (
        "/karpathy verify",
        ["/karpathy verify", "/review-stack"],
        "Use it the way a real user will, in the real environment.",
        "The main user journey completes in the real environment and the saved result reads back.",
        "screenshots or a transcript from the real environment",
        "browser automation (optional)",
    ),
    "observability": (
        "/build-stack",
        ["/planning-stack", "/build-stack", "/karpathy verify"],
        "Make failure visible: structured logs, one health check, one alert on the main path.",
        "A forced failure shows up in the log or the alert within minutes.",
        "the captured log line or alert from a forced failure",
        "the project's log viewer",
    ),
    "techdebt": (
        "/simplify",
        ["/review-stack", "/simplify", "/build-stack"],
        "Delete or simplify the riskiest shortcut this work leaned on.",
        "The diff removes more than it adds and the full suite stays green.",
        "the diff stat plus the test log",
        "the project's test runner",
    ),
    "release": (
        "/ship",
        ["/commit", "/ship"],
        "Ship the exact commit: pull request open, checks green on that commit.",
        "The pull request's checks are green on the exact commit that will merge.",
        ".devproto/evidence/ship.txt with the commit, the pull request link and the checks",
        "git host CLI (optional)",
    ),
    "docs": (
        "write the docs directly",
        ["write the README or docs page", "/review-stack"],
        "Write the page a new teammate needs to run and change this.",
        "A new reader can follow the docs to run it, and every command in them was run.",
        "the docs file plus a log of the commands it names",
        "none",
    ),
}
STORE = Path(".devproto") / "pathway"


def slug(text: str) -> str:
    return (
        re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40].rstrip("-") or "work"
    )


def _store_lock(project: Path):
    """One lock for the whole pathway store, reusing devproto's lock primitive."""
    return locked(project / STORE / ".lock")


def item_path(project: Path, work_id: str) -> Path:
    if work_id in (".", "..") or not re.fullmatch(r"[A-Za-z0-9._-]+", work_id):
        raise ValueError(
            "work id may use letters, digits, dot, dash and underscore only"
        )
    return project / STORE / f"{work_id}.json"


def load(project: Path, work_id: str) -> dict:
    p = item_path(project, work_id)
    if not p.is_file():
        raise ValueError(f"no outcome {work_id!r}; run start first")
    return json.loads(p.read_text())


def save(project: Path, item: dict) -> None:
    p = item_path(project, item["work_id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(item, indent=2) + "\n")
    os.replace(tmp, p)


def items(project: Path) -> list:
    d = project / STORE
    return (
        [json.loads(f.read_text()) for f in sorted(d.glob("*.json"))]
        if d.is_dir()
        else []
    )


def blank() -> dict:
    return {
        "status": "open",
        "evidence": "",
        "sha256": "",
        "verify": "",
        "verify_sha256": "",
        "revision": 0,
        "exit": None,
        "verified_at": "",
        "reason": "",
        "stale": False,
    }


def completion_digest(item: dict) -> str:
    payload = [item["work_id"], item["goal"], item["pathways"]]
    if "checklist_generation" in item:
        payload.append(item["checklist_generation"])
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def archive_directory(project: Path, item: dict) -> Path:
    item_path(project, item["work_id"])
    root = project.resolve()
    path = root / STORE / "completed" / item["work_id"] / completion_digest(item)
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError("closed outcome archive cannot follow symlinks")
        current = current.parent
    return path


def retained_completion(project: Path, item: dict, artifact_provider=None) -> bool:
    try:
        completion = item["completion"]
        if artifact_provider is None:
            archive = archive_directory(project, item)
        else:
            # A checklist may retain its own copies after the original itinerary
            # archive is gone. Preserve receipt identity without consulting that
            # mutable source directory; the provider must supply retained bytes.
            item_path(project, item["work_id"])
            archive = (
                project.resolve()
                / STORE
                / "completed"
                / item["work_id"]
                / completion_digest(item)
            )
        if (
            completion["receipt_sha256"] != completion_digest(item)
            or completion["archive_dir"]
            != archive.relative_to(project.resolve()).as_posix()
        ):
            return False
        for row in item["pathways"].values():
            if row["status"] == "na" and row.get("reason", "").strip():
                continue
            sha = row.get("sha256", "")
            if (
                row["status"] != "proved"
                or row.get("exit") != 0
                or not row.get("verified_at")
                or not row.get("verify_sha256")
                or not re.fullmatch(r"[0-9a-f]{64}", sha)
            ):
                return False
            artifact = archive / sha
            if artifact_provider is not None:
                artifact = artifact_provider(artifact, sha)
            if (
                artifact.is_symlink()
                or not artifact.is_file()
                or digest(artifact) != sha
            ):
                return False
        return bool(item["pathways"])
    except (OSError, ValueError, KeyError, TypeError):
        return False


def seal_completion(project: Path, item: dict) -> None:
    archive = archive_directory(project, item)
    archive.mkdir(parents=True, exist_ok=True)
    for row in item["pathways"].values():
        if row["status"] == "na" and row.get("reason", "").strip():
            continue
        sha = row.get("sha256", "")
        if (
            row["status"] != "proved"
            or row.get("exit") != 0
            or not row.get("verified_at")
            or not row.get("verify_sha256")
            or not re.fullmatch(r"[0-9a-f]{64}", sha)
        ):
            raise ValueError("closed outcome needs executed proof provenance")
        source = Path(row["evidence"])
        source = source if source.is_absolute() else project / source
        if source.is_symlink() or not source.is_file() or digest(source) != sha:
            raise ValueError("closed outcome evidence changed before archival")
        destination = archive / sha
        if destination.is_symlink():
            raise ValueError("closed outcome archive cannot follow symlinks")
        if destination.is_file() and digest(destination) == sha:
            continue
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=archive, delete=False) as out:
                temporary = Path(out.name)
                with source.open("rb") as incoming:
                    shutil.copyfileobj(incoming, out)
            if digest(temporary) != sha:
                raise ValueError("closed outcome evidence changed during archival")
            os.replace(temporary, destination)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    item["completion"] = {
        "receipt_sha256": completion_digest(item),
        "archive_dir": archive.relative_to(project.resolve()).as_posix(),
    }


def start(project: Path, goal: str, tier: str = "live", work_id: str = "") -> dict:
    goal = goal.strip()
    if not goal:
        raise ValueError("goal is required")
    if tier not in TIERS:
        raise ValueError(f"tier must be one of: {', '.join(TIERS)}")
    # Match checklist closeout's lock order: checklist store, then pathway store.
    with locked(project / ".devproto" / ".lock"), _store_lock(project):
        if work_id:
            _check_checklist_goal_locked(project, work_id, goal)
        for it in items(project):  # Validate the association before refreshing proof.
            if (
                it["goal"] == goal
                and not it.get("closed")
                and (not work_id or it["work_id"] == work_id)
            ):
                _check_checklist_goal_locked(project, it["work_id"], goal)
                out = _report_locked(project, it["work_id"])
                _enroll_checklist_locked(project, it["work_id"])
                out["note"] = (
                    "an open outcome with this goal already exists; reusing it"
                )
                return out
        work_id = work_id or f"{datetime.now():%Y%m%d}-{slug(goal)}"
        _check_checklist_goal_locked(project, work_id, goal)
        if item_path(project, work_id).exists():
            raise ValueError("that work id already exists with a different goal")
        seeded = set(TIERS[tier]) | {p for p, rx in GOAL_PULLS if rx.search(goal)}
        item = {
            "work_id": work_id,
            "goal": goal,
            "tier": tier,
            "created_at": now(),
            "closed": False,
            "pathways": {p: blank() for p in CATALOG if p in seeded},
            "log": [],
        }
        save(project, item)
        _enroll_checklist_locked(project, work_id)
        return _report_locked(project, work_id)


def _check_checklist_goal_locked(project: Path, work_id: str, goal: str) -> None:
    import devproto

    path = devproto.store_path(project, work_id)
    if path.exists() and devproto.load(path).get("goal") != goal:
        raise ValueError("Checklist and itinerary goals must match before enrollment.")


def _enroll_checklist_locked(project: Path, work_id: str) -> None:
    """An actual enrollment adds an obligation; it never edits sealed history."""
    import devproto

    path = devproto.store_path(project, work_id)
    if not path.exists():
        return
    item = load(project, work_id)
    _check_checklist_goal_locked(project, work_id, item.get("goal"))
    record = devproto.load(path)
    if record.get("completion"):
        return
    generation = record.get("execution_generation")
    if type(generation) is not int or generation < 1:
        raise ValueError(
            "Checklist execution generation is unknown; preserve the provenance gap."
        )
    record["itinerary_enrollment"] = {"version": 1, "mode": "required"}
    devproto.save(path, record)
    # Only freshly reset rows may enter a new cycle. Never relabel old proof.
    if not item.get("closed") and all(
        row["status"] == "open" and not row.get("verified_at") and not row.get("sha256")
        for row in item["pathways"].values()
    ):
        item["checklist_generation"] = generation
        save(project, item)


def cover(
    project: Path, work_id: str, pathway: str, add: bool, na: bool, reason: str = ""
) -> dict:
    if pathway not in CATALOG:
        raise ValueError(f"unknown pathway {pathway!r}; catalog: {', '.join(CATALOG)}")
    if add == na:
        raise ValueError("choose exactly one of --add or --na")
    with _store_lock(project):
        item = load(project, work_id)
        if item.get("closed"):
            raise ValueError("closed outcome is historical; use reopen before changing coverage")
        ways = item["pathways"]
        if add:
            if pathway not in ways:
                ways[pathway] = blank()
                item["pathways"] = {p: ways[p] for p in CATALOG if p in ways}
        else:
            if not reason.strip():
                raise ValueError("--na needs a written --reason")
            ways.setdefault(pathway, blank()).update(
                status="na",
                reason=reason.strip(),
                stale=False,
                verified_at=now(),
                revision=ways.get(pathway, {}).get("revision", 0) + 1,
            )
            item["pathways"] = {p: ways[p] for p in CATALOG if p in ways}
        item["log"].append(
            {
                "at": now(),
                "pathway": pathway,
                "action": "add" if add else "na",
                "reason": reason.strip(),
            }
        )
        _reopen_if_incomplete(item)
        save(project, item)
        return _report_locked(project, work_id)


def log(
    project: Path,
    work_id: str,
    pathway: str,
    evidence: str,
    verify: str,
    timeout: int = 600,
) -> dict:
    # Phase 1, under the lock: validate everything that does not need the verifier.
    with _store_lock(project):
        item = load(project, work_id)
        if item.get("closed"):
            raise ValueError(
                "closed outcome is historical; use reopen before recording proof"
            )
        if pathway not in item["pathways"]:
            raise ValueError(
                f"{pathway} is not on this outcome's itinerary; add it with cover --add"
            )
        ev = Path(evidence).expanduser()
        ev = ev if ev.is_absolute() else project / ev
        if ev.is_symlink() or not ev.is_file() or not verify.strip():
            raise ValueError(
                "log needs --evidence (an existing regular file) and --verify"
            )
        sha = digest(ev)
        prior = json.dumps(item["pathways"][pathway], sort_keys=True)
        prior_generation = item.get("checklist_generation")

    # Phase 2, unlocked: the verifier may take minutes; others can still read status.
    # Reuses devproto's verifier runner: temp-file output (no pipe a background
    # child can hang), no stdin, and the whole process group is killed after.
    code, output = _run_verifier(verify, project, timeout)

    # Phase 3, under the lock: write the result.
    with _store_lock(project):
        item = load(project, work_id)
        if item.get("closed"):
            raise ValueError(
                "closed outcome is historical; use reopen before recording proof"
            )
        if pathway not in item["pathways"]:
            raise ValueError(
                f"{pathway} is not on this outcome's itinerary; add it with cover --add"
            )
        if json.dumps(item["pathways"][pathway], sort_keys=True) != prior:
            raise ValueError("pathway changed while the verifier ran; verify it again")
        if item.get("checklist_generation") != prior_generation:
            raise ValueError(
                "checklist generation changed while the verifier ran; verify it again"
            )
        stable = digest(ev) == sha
        passed = code == 0 and stable
        try:
            shown = ev.resolve().relative_to(project.resolve()).as_posix()
        except ValueError:
            shown = str(ev)
        reason = (
            ""
            if passed
            else (
                "The verifier changed the evidence file. Write evidence first, then verify it with a read-only command."
                if not stable
                else f"Verifier exited {code}."
            )
        )
        item["pathways"][pathway].update(
            status="proved" if passed else "blocked",
            evidence=shown,
            sha256=sha,
            verify=redact(verify),
            verify_sha256=command_digest(verify),
            revision=item["pathways"][pathway].get("revision", 0) + 1,
            exit=code,
            verified_at=now(),
            reason=reason,
            stale=False,
            output_tail=redact(output)[-2000:],
        )
        item["log"].append(
            {
                "at": now(),
                "pathway": pathway,
                "action": "log",
                "result": "proved" if passed else "blocked",
                "evidence": shown,
            }
        )
        save(project, item)
        out = _report_locked(project, work_id)
    if not passed:
        out.update(ok=False, error=reason)
    return out


def _reopen_if_incomplete(item: dict) -> bool:
    if item.get("closed") and any(
        p["status"] not in ("proved", "na") for p in item["pathways"].values()
    ):
        item["closed"] = False
        item.pop("closed_at", None)
        return True
    return False


def _live_items_locked(project: Path) -> list:
    live = []
    for item in items(project):
        if refresh(project, item):
            save(project, item)
        if not item.get("closed"):
            live.append(item)
    return live


def refresh(project: Path, item: dict) -> bool:
    """Reopen a proved pathway whose evidence changed or vanished. Marks it stale."""
    if item.get("closed"):
        return False  # Historical validation must never rewrite sealed rows.
    changed = False
    for name, p in item["pathways"].items():
        raw = p.get("verify", "")
        if raw and not p.get("verify_sha256"):
            p["verify_sha256"] = command_digest(raw)
            changed = True
        for key in ("verify", "output_tail"):
            if key in p and redact(p[key]) != p[key]:
                p[key] = redact(p[key])
                changed = True
        if p["status"] == "proved":
            ev = Path(p["evidence"])
            ev = ev if ev.is_absolute() else project / ev
            if digest(ev) != p["sha256"]:
                p.update(
                    status="open",
                    revision=p.get("revision", 0) + 1,
                    stale=True,
                    reason="Evidence changed or vanished after it was proved. Prove it again.",
                )
                changed = True
    return _reopen_if_incomplete(item) or changed


def checklist_confidence(project: Path, work_id: str) -> tuple:
    f = project / ".devproto" / f"{work_id}.json"
    if not f.is_file():
        return "low", "no development-protocol checklist shares this work id"
    try:
        steps = json.loads(f.read_text()).get("steps", [])
    except (OSError, ValueError):
        return "low", "the checklist file could not be read"
    blocked = [s.get("step_id") for s in steps if s.get("status") == "blocked"]
    if blocked:
        return "low", f"checklist rows blocked: {', '.join(blocked)}"
    return "high", "checklist present with no blocked rows"


def report(project: Path, work_id: str) -> dict:
    with _store_lock(project):
        return _report_locked(project, work_id)


def scope(project: Path, work_id: str) -> dict:
    """Stable intake evidence: proof progress never changes this payload."""
    with _store_lock(project):
        item = load(project, work_id)
        return {
            "ok": True,
            "work_id": work_id,
            "goal": item["goal"],
            "tier": item["tier"],
            "pathways": [
                {
                    "name": name,
                    "required": item["pathways"][name]["status"] != "na",
                    "reason": item["pathways"][name]["reason"]
                    if item["pathways"][name]["status"] == "na"
                    else "",
                }
                for name in CATALOG
                if name in item["pathways"]
            ],
        }


def _report_locked(project: Path, work_id: str) -> dict:
    item = load(project, work_id)
    if refresh(project, item):
        save(project, item)
    ways = item["pathways"]
    proved = [p for p, v in ways.items() if v["status"] == "proved"]
    na = [p for p, v in ways.items() if v["status"] == "na"]
    open_ = [p for p, v in ways.items() if v["status"] in ("open", "blocked")]
    stale = [p for p, v in ways.items() if v.get("stale")]
    # Preserve the canonical catalog while deferring outward release until all
    # candidate-changing work, including documentation, is proved.
    open_ = [p for p in open_ if p != "release"] + (["release"] if "release" in open_ else [])
    stale = [p for p in stale if p != "release"] + (["release"] if "release" in stale else [])
    owed = len(ways) - len(na)
    rate = round(len(proved) / owed, 2) if owed else 0.0
    historical_valid = retained_completion(project, item) if item.get("closed") else None
    trust = "fail" if stale or historical_valid is False else "pass"
    confidence, why_conf = checklist_confidence(project, work_id)
    eligible_stale = [p for p in stale if p != "release" or not any(q != "release" for q in open_)]
    if eligible_stale:
        pick, why = (
            eligible_stale[0],
            f"trust failed: the proof for {eligible_stale[0]} no longer matches its evidence",
        )
    elif open_:
        pick, why = (
            open_[0],
            f"first open pathway in foundation-first order ({len(open_)} open)",
        )
    else:
        pick, why = None, "every pathway is proved or n/a; the outcome can close"
    safe_ok = rate >= 0.5 and trust == "pass" and confidence == "high"
    tier = "execute-safe" if safe_ok else "recommend"
    rationale = f"proof rate {rate:.2f} (needs 0.50), trust {trust}, confidence {confidence} ({why_conf})"
    card = None
    if pick:
        skill, stack, move, good, artifact, tools = CARDS[pick]
        card = {
            "skill": skill,
            "execution_stack": stack,
            "one_percent_move": move,
            "verifier_good": good,
            "real_artifact": artifact,
            "execution_tools": tools,
            "auto_eligible": pick in SAFE,
        }
    result = {
        "ok": historical_valid is not False,
        "work_id": item["work_id"],
        "goal": item["goal"],
        "tier": item["tier"],
        "closed": item.get("closed", False),
        "coverage": {
            "owed": owed,
            "proved": proved,
            "na": na,
            "open": open_,
            "line": f"{len(proved)} of {owed} pathways proved"
            + (f"; remaining: {', '.join(open_)}" if open_ else ""),
        },
        "recommended_pathway": pick,
        "why": why,
        "card": card,
        "trust": trust,
        "stale": stale,
        "confidence": confidence,
        "proof_rate": rate,
        "suggested_autonomy_tier": tier,
        "autonomy_rationale": rationale,
        "pathways": ways,
        "completion": item.get("completion"),
        "historical_receipts_valid": historical_valid,
    }
    if historical_valid is False:
        result["error"] = "Historical proof is missing, changed, or lacks provenance."
    # Render legacy verifier text safely without modifying sealed records.
    for row in result["pathways"].values():
        for key in ("verify", "output_tail"):
            if key in row:
                row[key] = redact(row[key])
    return result


def select(project: Path, work_id: str) -> str:
    if work_id:
        return work_id
    with _store_lock(project):
        live = [it["work_id"] for it in _live_items_locked(project)]
    if len(live) == 1:
        return live[0]
    if not live:
        raise ValueError("no open outcome in this project; run start with a goal")
    raise ValueError("several open outcomes; pass --id one of: " + ", ".join(live))


def close(project: Path, work_id: str) -> dict:
    with _store_lock(project):
        out = _report_locked(project, work_id)
        if out["closed"]:
            return out  # Never reseal invalid past proof from overwritten live paths.
        blockers = out["coverage"]["open"]
        if blockers:
            out.update(
                ok=False,
                closed=False,
                error="still owed proof or an n/a reason: " + ", ".join(blockers),
            )
            return out
        item = load(project, work_id)
        seal_completion(project, item)
        item.update(closed=True, closed_at=now())
        item["log"].append({"at": now(), "action": "close"})
        save(project, item)
        return _report_locked(project, work_id)


def reopen(project: Path, work_id: str, reason: str) -> dict:
    if not reason.strip():
        raise ValueError("reopen needs a written reason")
    with locked(project / ".devproto" / ".lock"), _store_lock(project):
        item = load(project, work_id)
        if not item.get("closed"):
            raise ValueError("outcome is not closed")
        item.setdefault("completion_history", []).append(
            {
                **(
                    {"checklist_generation": item["checklist_generation"]}
                    if "checklist_generation" in item
                    else {}
                ),
                "closed_at": item.get("closed_at"),
                "goal": item["goal"],
                "completion": item.pop("completion", None),
                "pathways": item["pathways"],
                "reason": reason.strip(),
                "at": now(),
            }
        )
        prior = item["pathways"]
        item["pathways"] = {
            name: dict(blank(), revision=row.get("revision", 0) + 1)
            for name, row in prior.items()
        }
        item["closed"] = False
        item.pop("closed_at", None)
        item["log"].append({"at": now(), "action": "reopen", "reason": reason.strip()})
        save(project, item)
        _enroll_checklist_locked(project, work_id)
        return _report_locked(project, work_id)


def pilot(projects: list, goal: str, report_file: str) -> dict:
    rows = []
    for raw in projects:
        proj = Path(raw).expanduser().resolve()
        if not proj.is_dir():
            rows.append({"project": str(proj), "error": "not a folder"})
            continue
        with _store_lock(proj):
            live = _live_items_locked(proj)
        if len(live) > 1:
            rows.append(
                {
                    "project": str(proj),
                    "error": "several open outcomes; run next --id on one",
                }
            )
            continue
        wid = live[0]["work_id"] if live else start(proj, goal)["work_id"]
        r = report(proj, wid)
        rows.append(
            {
                "project": str(proj),
                "work_id": wid,
                "pathway": r["recommended_pathway"],
                "lead": f"agent running {r['card']['skill']}" if r["card"] else "none",
                "critic": "a different model family, or a fresh-context reviewer",
                "proof_gate": r["card"]["verifier_good"] if r["card"] else "none",
                "review_gate": "a person approves before /ship or close",
                "proof_rate": r["proof_rate"],
                "trust": r["trust"],
            }
        )
    ok_rows = [x for x in rows if "error" not in x]
    baseline = (
        round(sum(x["proof_rate"] for x in ok_rows) / len(ok_rows), 2)
        if ok_rows
        else 0.0
    )
    risk = sorted(ok_rows, key=lambda x: (x["trust"] == "pass", x["proof_rate"]))
    lines = [
        f"# Pathway pilot: {goal}",
        "",
        f"Created {now()}. Baseline proof rate {baseline:.2f}.",
        "",
        "| project | work id | pathway | lead | critic | proof gate | review gate |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for x in rows:
        if "error" in x:
            lines.append(f"| {x['project']} | error: {x['error']} | | | | | |")
        else:
            lines.append(
                f"| {x['project']} | {x['work_id']} | {x['pathway']} | {x['lead']} | "
                f"{x['critic']} | {x['proof_gate']} | {x['review_gate']} |"
            )
    out = Path(report_file).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    return {
        "ok": bool(ok_rows),
        "goal": goal,
        "baseline_proof_rate": baseline,
        "report": str(out),
        "assignments": rows,
        "first_target": risk[0]["project"] if risk else None,
    }


def doctor(project: Path) -> dict:
    here = Path(__file__).resolve().parent.parent  # .../skills/pathway
    skills_root = here.parent
    checks = {
        "python_3_9_or_newer": sys.version_info >= (3, 9),
        "skill_file_next_to_script": (here / "SKILL.md").is_file(),
        "project_folder_exists": project.is_dir(),
        "project_writable": os.access(project, os.W_OK),
    }
    # Advisory: the checklist row (`pathway`) that this router reports through
    # comes from the development-protocol skill; a lone pathway install has no
    # other way to notice that skill is missing.
    warnings = {
        "skill_installed:development-protocol": (
            skills_root / "development-protocol" / "SKILL.md"
        ).is_file(),
    }
    warnings["project_is_git_repo"] = (
        shutil.which("git") is not None
        and subprocess.run(
            ["git", "-C", str(project), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
        ).returncode
        == 0
    )
    return {"ok": all(checks.values()), "checks": checks, "warnings": warnings}


def print_human(r: dict) -> None:
    if "checks" in r:
        for name, passed in r["checks"].items():
            print(f"{'PASS' if passed else 'FAIL'}  {name}")
        for name, passed in r.get("warnings", {}).items():
            print(f"{'PASS' if passed else 'WARN'}  {name}")
        print("pathway doctor: " + ("ok" if r["ok"] else "fix the FAIL lines above"))
        return
    if "assignments" in r:
        print(
            f"pilot report: {r['report']}  baseline proof rate {r['baseline_proof_rate']:.2f}"
        )
        for a in r["assignments"]:
            print(f"  {a['project']}: {a.get('error') or a['pathway']}")
        print(f"first target: {r['first_target']}")
        return
    print(f"{r['work_id']}  {r['goal']}  (tier {r['tier']})")
    print(f"  coverage: {r['coverage']['line']}")
    for name, p in r["pathways"].items():
        mark = {"proved": "x", "na": "-", "blocked": "!"}.get(p["status"], " ")
        extra = (
            f"  ({p['reason']})"
            if p["reason"]
            else (f"  verified by: {p['verify']}" if p["verify"] else "")
        )
        print(f"  [{mark}] {name:<14}{extra}")
    print(
        f"  trust {r['trust']}, confidence {r['confidence']}, autonomy {r['suggested_autonomy_tier']}"
    )
    if r.get("note"):
        print(f"  note: {r['note']}")
    if r.get("error"):
        print(f"ERROR: {r['error']}")
    if r["closed"]:
        print("CLOSED.")
    elif r["recommended_pathway"]:
        print(f"Next: {r['recommended_pathway']}  ({r['why']})")
        print(f"  skill: {r['card']['skill']}  move: {r['card']['one_percent_move']}")
    else:
        print("Next: close")


def main(argv=None) -> int:
    # SUPPRESS, not a literal default: see devproto.py's main() for why a
    # subparser copy of this action needs SUPPRESS rather than a real default,
    # and why getattr() below supplies the real default after parsing instead.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--project",
        default=argparse.SUPPRESS,
        help="project folder (default: current folder)",
    )
    common.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="print JSON"
    )
    ap = argparse.ArgumentParser(
        prog="pathway",
        description=__doc__.splitlines()[0],
        epilog="--project and --json may go before or after the subcommand.",
        parents=[common],
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser(
        "start", parents=[common], help="open an outcome and seed its itinerary"
    )
    p.add_argument("--goal", required=True)
    p.add_argument("--tier", default="live", choices=list(TIERS))
    p.add_argument("--id", default="")
    p = sub.add_parser(
        "next",
        parents=[common],
        help="coverage, trust and the next pathway (read-mostly)",
    )
    p.add_argument("--id", default="")
    p = sub.add_parser(
        "scope", parents=[common], help="stable intake and itinerary evidence as JSON"
    )
    p.add_argument("--id", required=True)
    p = sub.add_parser(
        "cover",
        parents=[common],
        help="add a pathway, or mark one n/a with a reason",
    )
    p.add_argument("--id", required=True)
    p.add_argument("--pathway", required=True)
    p.add_argument("--add", action="store_true")
    p.add_argument("--na", action="store_true")
    p.add_argument("--reason", default="")
    p = sub.add_parser(
        "log",
        parents=[common],
        help="prove a pathway: evidence file plus a verifier that exits 0",
    )
    p.add_argument("--id", required=True)
    p.add_argument("--pathway", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--verify", required=True)
    p.add_argument("--timeout", type=int, default=600)
    p = sub.add_parser(
        "close",
        parents=[common],
        help="close the outcome when every pathway is proved or n/a",
    )
    p.add_argument("--id", required=True)
    p = sub.add_parser("reopen", parents=[common], help="explicitly reopen a closed outcome")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", required=True)
    p = sub.add_parser(
        "pilot",
        parents=[common],
        help="measured multi-project rehearsal; writes a report file",
    )
    p.add_argument("--projects", required=True, help="comma-separated project folders")
    p.add_argument("--goal", required=True)
    p.add_argument(
        "--report",
        default="",
        help="report file (default under .devproto/pathway/pilots/)",
    )
    sub.add_parser(
        "doctor", parents=[common], help="check the install and the project folder"
    )
    a = ap.parse_args(argv)
    as_json = getattr(a, "json", False)
    project = Path(getattr(a, "project", ".")).expanduser().resolve()
    try:
        if a.cmd == "start":
            r = start(project, a.goal, a.tier, a.id)
        elif a.cmd == "next":
            r = report(project, select(project, a.id))
        elif a.cmd == "scope":
            r = scope(project, a.id)
        elif a.cmd == "cover":
            r = cover(project, a.id, a.pathway, a.add, a.na, a.reason)
        elif a.cmd == "log":
            r = log(project, a.id, a.pathway, a.evidence, a.verify, a.timeout)
        elif a.cmd == "close":
            r = close(project, a.id)
        elif a.cmd == "reopen":
            r = reopen(project, a.id, a.reason)
        elif a.cmd == "doctor":
            r = doctor(project)
        else:
            default = (
                project
                / STORE
                / "pilots"
                / f"{datetime.now():%Y%m%d}-{slug(a.goal)}.md"
            )
            r = pilot(
                [s for s in a.projects.split(",") if s.strip()],
                a.goal,
                a.report or str(default),
            )
    except ValueError as exc:
        r = {"ok": False, "error": str(exc)}
        print(json.dumps(r, indent=2) if as_json else f"ERROR: {exc}")
        return 2
    if as_json or a.cmd == "scope":
        print(json.dumps(r, indent=2))
    else:
        print_human(r)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
