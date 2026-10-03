#!/usr/bin/env python3
"""devproto: an ordered proof checklist for one piece of software work.

Each work item gets a JSON file under <project>/.devproto/. A step passes only
when an evidence file exists and a verifier command exits 0 in the project
folder. If the evidence file (or any instrument file named with --instrument)
changes later, that step and every later passed step reopen on the next read.

Standard library only. Python 3.9 or newer.
"""

from __future__ import annotations

import argparse
import contextlib
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import (
    candidate_snapshot,
    command_digest,
    digest,
    now,
    redact,
    run_verifier,
)  # noqa: E402
from _shared import locked as _store_locked  # noqa: E402

# (row id, skill that satisfies it, what the row proves)
STEPS = [
    (
        "pathway",
        "/pathway",
        "Work item named: goal, user, owner, done condition, risk, one number.",
    ),
    (
        "brainstorm",
        "/brainstorm-stack",
        "Open questions asked and decisions surfaced before planning.",
    ),
    (
        "research",
        "/research-stack",
        "Unknowns answered from primary sources, each claim cited.",
    ),
    (
        "spec",
        "/karpathy spec",
        "Done condition written as a check that can fail, before building.",
    ),
    ("planning", "/planning-stack", "Small ordered slices, each with its own check."),
    (
        "visual-spec",
        "/visual-spec",
        "Screens, flows and data mapped and checked before UI is built.",
    ),
    ("design", "/design-stack", "UI designed against the spec, in every state."),
    (
        "premortem",
        "/devilsadvocate --premortem",
        "Ways it fails in production, each with a guard.",
    ),
    (
        "audit-setup",
        "/audit-setup",
        "Repo quality checks and CI in place before the build.",
    ),
    (
        "build",
        "/build-stack",
        "One slice at a time in a branch, focused check after each.",
    ),
    (
        "verify",
        "/karpathy verify",
        "Result checked against the spec by a second model or person.",
    ),
    (
        "review",
        "/review-stack",
        "Full suite, independent review, real artifact exercised.",
    ),
    (
        "simplify",
        "/simplify",
        "What the change does not need is removed; checks re-run.",
    ),
    ("commit", "/commit", "Clean commit with a message that says why."),
    ("ship", "/ship", "Exact merge SHA, green CI on that SHA, release checks."),
    ("compound", "/compound", "Lessons written where the next person will find them."),
    (
        "closeout",
        "/closeout-stack",
        "Fresh main re-checked, handoff written, unknowns listed.",
    ),
]
STEP_IDS = [s[0] for s in STEPS]
TERMINAL = {"passed", "not-applicable"}
RECORD_KEYS = (
    "status",
    "evidence_sha256",
    "instruments",
    "verify_command",
    "verify_command_sha256",
    "git_identity",
    "candidate_sha256",
)
RELEASE_STEPS = set(STEP_IDS[STEP_IDS.index("commit") :])
CONDITIONAL = {"brainstorm", "research", "visual-spec", "design"}
OPTIONAL_WHEN_TRIVIAL = {
    "spec",
    "planning",
    "premortem",
    "audit-setup",
    "verify",
    "simplify",
    "compound",
}
ALWAYS_REQUIRED = set(STEP_IDS) - CONDITIONAL - OPTIONAL_WHEN_TRIVIAL
STORE_DIR = ".devproto"

TRIVIAL_RE = re.compile(r"\b(typo|copy edit|one-line|trivial|tiny fix)\b", re.I)
UI_RE = re.compile(
    r"\b(ui|ux|screen|page|frontend|dashboard|visual|design|layout)\b", re.I
)
RESEARCH_RE = re.compile(
    r"\b(research|unknown|investigate|evaluate|compare|regulation|spike)\b", re.I
)

# Focus lenses for /research-stack. Source of truth: research-stack focus/tags.json (bundled as
# skills/research-stack/references/focus/tags.json). These are its `triggers`, copied in tags.json
# order; tests/test_devproto.py fails if they drift. Order breaks ties between equal matches.
FOCUS_HINTS = [
    (
        "seo",
        r"\b(seo|serp|keywords?|rankings?|backlinks?|search console|schema markup|structured data|rich results?|geo|aeo|ai overviews?|llm visibility|organic traffic)\b",
    ),
    (
        "content",
        r"\b(content|copywriting|blog|newsletter|ad creatives?|ads|creative|hooks?|social posts?|short-form|video|campaign|landing copy)\b",
    ),
    (
        "market",
        r"\b(market|competitors?|competitive|pricing|tam|vendors?|landscape|funding|positioning|alternatives)\b",
    ),
    (
        "ui-ux",
        r"\b(ui|ux|onboarding|user flows?|screens?|layout|design patterns?|figma|components?|dashboard|checkout|usability)\b",
    ),
    (
        "a11y",
        r"\b(a11y|accessibility|accessible|wcag|screen readers?|aria|colou?r contrast|keyboard navigation)\b",
    ),
    (
        "perf",
        r"\b(performance|perf|latency|core web vitals|cwv|lcp|inp|cls|bundle size|page ?speed|lighthouse|throughput)\b",
    ),
    (
        "security",
        r"\b(security|vulnerabilit(y|ies)|cves?|owasp|authn?|secrets?|xss|csrf|ssrf|injection|supply chain|sbom|pentest|threat model)\b",
    ),
    (
        "devtools",
        r"\b(librar(y|ies)|frameworks?|sdks?|apis?|integrations?|webhooks?|packages?|npm|pypi|dependenc(y|ies)|migrate to|cli tools?|which (lib|tool|framework))\b",
    ),
    (
        "ai-agents",
        r"\b(llms?|agents?|agentic|prompts?|rag|evals?|mcp|models?|fine-?tun\w*|embeddings?|claude|gpt|gemini)\b",
    ),
    (
        "data-infra",
        r"\b(databases?|postgres|schema|warehouse|etl|pipelines?|queues?|kafka|cach(e|ing)|redis|infra|kubernetes|serverless|cdn)\b",
    ),
    (
        "comms",
        r"\b(dialers?|dialing|telephony|voip|phone systems?|softphones?|webrtc|sms|text messag\w*|ivr|call (center|centre|recording|tracking|routing|logging|queues?)|contact cent(er|re)|cold call\w*|click-to-call|voicemail|ringcentral|twilio|aircall|dialpad|telnyx|10dlc|caller id|cpaas|ucaas)\b",
    ),
    (
        "legal",
        r"\b(legal|gdpr|ccpa|hipaa|compliance|regulations?|licen[cs]es?|terms of service|privacy policy|contracts?|ai act)\b",
    ),
]
FOCUS_RES = [(tag, re.compile(rx, re.I)) for tag, rx in FOCUS_HINTS]
MAX_FOCUS = 4


def focus_tags(goal: str) -> list[str]:
    """Up to MAX_FOCUS lens tags whose triggers match the goal: most distinct matches first."""
    hits = []
    for order, (tag, rx) in enumerate(FOCUS_RES):
        words = {m.group(0).lower() for m in rx.finditer(goal)}
        if words:
            hits.append((-len(words), order, tag))
    return [tag for _, _, tag in sorted(hits)[:MAX_FOCUS]]


def research_hint(goal: str) -> str:
    """The /research-stack call to suggest for this goal, or "" when no lens matches."""
    tags = focus_tags(goal)
    return f"/research-stack --focus {','.join(tags)}" if tags else ""


def slug(text: str) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return words[:40].rstrip("-") or "work"


def store_path(project: Path, work_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", work_id):
        raise ValueError(
            "work id may use letters, digits, dot, dash and underscore only"
        )
    return project / STORE_DIR / f"{work_id}.json"


def ensure_store(store: Path) -> None:
    store.mkdir(parents=True, exist_ok=True)
    ignore = store / ".gitignore"
    if not ignore.exists():
        ignore.write_text(".lock\n*.tmp\n")


@contextlib.contextmanager
def locked(path: Path):
    """One lock for the whole store, held only for reads and writes, never for a verifier."""
    ensure_store(path.parent)
    with _store_locked(path):
        yield


def load(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"no work item at {path}; run start first")
    record = json.loads(path.read_text())
    if [s.get("step_id") for s in record.get("steps", [])] != STEP_IDS:
        raise ValueError("checklist file does not match this version of devproto")
    return record


def save(path: Path, record: dict) -> None:
    tmp = path.with_suffix(".json.tmp")  # plain open() keeps the user's umask
    try:
        with tmp.open("w") as stream:
            json.dump(record, stream, indent=2)
            stream.write("\n")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def resolve(project: Path, name: str) -> Path:
    p = Path(name).expanduser()
    return p if p.is_absolute() else (project / p)


def portable(project: Path, p: Path) -> str:
    """Store paths inside the project relative, so the file works on any clone."""
    try:
        return p.resolve().relative_to(project.resolve()).as_posix()
    except ValueError:
        return str(p)


def required_steps(goal: str, force=(), optional=()) -> tuple[set[str], list[str]]:
    """Return the required rows and a note for each goal word or flag that changed them."""
    notes = []
    conditional = set(CONDITIONAL)
    trivial = TRIVIAL_RE.search(goal)
    if trivial:
        conditional |= OPTIONAL_WHEN_TRIVIAL
        notes.append(
            f'"{trivial.group(0)}" made {", ".join(sorted(OPTIONAL_WHEN_TRIVIAL))} optional'
        )
    else:
        conditional.discard("brainstorm")
    ui = UI_RE.search(goal)
    if ui:
        conditional -= {"visual-spec", "design"}
        notes.append(f'"{ui.group(0)}" made visual-spec and design required')
    research = RESEARCH_RE.search(goal)
    if research:
        conditional.discard("research")
        notes.append(f'"{research.group(0)}" made research required')
    required = (set(STEP_IDS) - conditional) | set(force)
    required -= set(optional)
    notes += [f"{s} required by --require" for s in sorted(force)]
    notes += [f"{s} made optional by --optional" for s in sorted(optional)]
    hint = research_hint(goal) if "research" in required else ""
    if hint:
        notes.append(f"research focus suggested from the goal: {hint}")
    if notes:
        notes.append("change a row at start with --require <step> or --optional <step>")
    return required, notes


def check_rows(force=(), optional=()) -> None:
    unknown = (set(force) | set(optional)) - set(STEP_IDS)
    if unknown:
        raise ValueError(f"unknown step(s): {', '.join(sorted(unknown))}")
    locked_on = set(optional) & ALWAYS_REQUIRED
    if locked_on:
        raise ValueError(
            "these steps are always required: " + ", ".join(sorted(locked_on))
        )


def new_row(i: int, sid: str, skill: str, purpose: str, required: bool) -> dict:
    return {
        "step_id": sid,
        "sequence": i + 1,
        "skill": skill,
        "purpose": purpose,
        "required": required,
        "status": "pending",
        "evidence_path": "",
        "evidence_sha256": "",
        "evidence_stat": None,
        "instruments": {},
        "verify_command": "",
        "verify_command_sha256": "",
        "git_identity": None,
        "verifier_exit": None,
        "output_tail": "",
        "verified_at": "",
        "reason": "",
    }


def start(project: Path, goal: str, work_id: str = "", force=(), optional=()) -> dict:
    goal = goal.strip()
    if not goal:
        raise ValueError("goal is required")
    check_rows(force, optional)
    work_id = work_id or f"{datetime.now():%Y%m%d}-{slug(goal)}"
    path = store_path(project, work_id)
    required, notes = required_steps(goal, force, optional)
    with locked(path):
        if path.exists():
            record = load(path)
            if refresh(project, record):
                save(path, record)
            if record["goal"] != goal:
                raise ValueError("that work id already exists with a different goal")
            stored = {s["step_id"] for s in record["steps"] if s["required"]}
            if (force or optional) and stored != required:
                if any(s["status"] != "pending" for s in record["steps"]):
                    raise ValueError(
                        "work id already has recorded steps; --require/--optional can only "
                        "change rows before the first step is recorded"
                    )
                for s in record["steps"]:
                    s["required"] = s["step_id"] in required
                record["rule_notes"] = notes + [
                    n
                    for n in record.get("rule_notes", [])
                    if n.startswith("Git intake baseline")
                ]
                save(path, record)
            return summary(project, record)
        try:
            identity = git_identity(project)
        except ValueError as exc:
            if str(exc) == "Git identity lookup failed":
                raise
            identity = None
            notes.append(
                f"Git intake baseline unavailable: {exc}; required Git proof remains blocked"
            )
        if identity is not None:
            baseline = project / STORE_DIR / "evidence" / f"{work_id}-build-base.txt"
            baseline.parent.mkdir(parents=True, exist_ok=True)
            expected = f"base {identity['head']}\nwork-id {work_id}\n"
            try:
                with baseline.open("x") as out:
                    out.write(expected)
            except FileExistsError:
                if baseline.read_text() != expected:
                    raise ValueError(
                        "existing intake baseline conflicts; preserve it and recover provenance"
                    )
        record = {
            "work_id": work_id,
            "goal": goal,
            "rule_notes": notes,
            "created_at": now(),
            "steps": [
                new_row(i, sid, skill, purpose, sid in required)
                for i, (sid, skill, purpose) in enumerate(STEPS)
            ],
        }
        save(path, record)
        return summary(project, record)


def _fp(path: Path) -> list | None:
    """Cheap fingerprint (mtime_ns, size) so refresh() can skip a re-hash."""
    if not path.is_file():
        return None
    st = path.stat()
    return [st.st_mtime_ns, st.st_size]


STAT_SHORTCUT_MIN_SIZE = 1_000_000  # 1 MB


def _stable(path: Path, sha: str, stat) -> tuple[bool, list | None]:
    """Whether `path` still matches `sha`.

    Below STAT_SHORTCUT_MIN_SIZE, always hashes rather than trusting the
    (mtime, size) fingerprint alone: a coarse-mtime filesystem (HFS+, exFAT,
    some Docker/NFS bind mounts) rounds mtime to whole seconds, so a rewrite
    that lands in the same second and keeps the same size would otherwise be
    missed. Evidence and instrument files are typically small, so this is the
    common path, not a rare one. At or above the threshold the fingerprint
    shortcut is kept for performance; a same-second, same-size rewrite of a
    file that large on a coarse-mtime filesystem is a documented residual
    gap, not one this closes.
    """
    cur = _fp(path)
    if (
        cur is not None
        and stat is not None
        and list(stat) == cur
        and cur[1] >= STAT_SHORTCUT_MIN_SIZE
    ):
        return True, cur
    return digest(path) == sha, cur


def git_identity(project: Path) -> dict | None:
    """None means a confirmed ordinary folder, never a failed Git lookup."""
    has_git = any(
        (parent / ".git").exists()
        for parent in (project.resolve(), *project.resolve().parents)
    )
    if shutil.which("git") is None:
        if has_git:
            raise ValueError("Git identity unavailable: git is missing")
        return None

    def read(*args):
        try:
            return subprocess.run(
                ["git", "-C", str(project), *args],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("Git identity lookup failed") from exc

    inside = read("rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0:
        if not has_git and "not a git repository" in inside.stderr.lower():
            return None
        raise ValueError("Git identity lookup failed")
    if inside.stdout.strip() != "true":
        raise ValueError("Release proof requires a Git working tree")
    head = read("rev-parse", "--verify", "HEAD")
    branch = read("symbolic-ref", "--quiet", "HEAD")
    if head.returncode != 0 or branch.returncode not in (0, 1):
        raise ValueError("Git release identity cannot be established")
    return {"head": head.stdout.strip(), "branch": branch.stdout.strip() or None}


def completion_digest(record: dict) -> str:
    """Bind immutable proof fields, excluding cheap file-stat caches."""
    rows = []
    for row in record["steps"]:
        fields = {
            k: row.get(k)
            for k in (
                "step_id",
                "required",
                "status",
                "reason",
                "evidence_path",
                "evidence_sha256",
                "verify_command_sha256",
                "verifier_exit",
                "verified_at",
                "git_identity",
                "candidate_sha256",
            )
        }
        fields["instruments"] = {
            name: meta.get("sha256") if isinstance(meta, dict) else meta
            for name, meta in row.get("instruments", {}).items()
        }
        rows.append(fields)
    return hashlib.sha256(
        json.dumps([record["work_id"], rows], sort_keys=True).encode()
    ).hexdigest()


def archive_directory(project: Path, record: dict) -> Path:
    store_path(
        project, record["work_id"]
    )  # validate the work ID before path construction
    return (
        project.resolve()
        / STORE_DIR
        / "evidence"
        / "completed"
        / record["work_id"]
        / completion_digest(record)
    )


def historical_artifact(project: Path, record: dict, source: str, sha: str) -> Path:
    completion = record.get("completion", {})
    if not completion.get("archive_dir"):
        return resolve(project, source)
    archive = archive_directory(project, record)
    if completion["archive_dir"] != portable(project, archive) or not re.fullmatch(
        r"[0-9a-f]{64}", sha
    ):
        raise ValueError("historical archive provenance is invalid")
    path = archive / sha
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("historical archive cannot be redirected through symlinks")
    return path


def ancestry_valid(project: Path, record: dict, base: str, head: str) -> bool:
    completion = record.get("completion", {})
    if completion.get("ancestry_sha256"):
        path = historical_artifact(project, record, "", completion["ancestry_sha256"])
        if not path.is_file() or digest(path) != completion["ancestry_sha256"]:
            return False
        receipt = json.loads(path.read_text())
        return (
            receipt.get("kind") == "git-ancestry-receipt-v1"
            and receipt.get("base") == base
            and receipt.get("head") == head
            and receipt.get("receipt_sha256") == completion_digest(record)
            and receipt.get("argv")
            == ["git", "merge-base", "--is-ancestor", base, head]
            and receipt.get("exit_code") == 0
            and bool(receipt.get("verified_at"))
        )
    result = subprocess.run(
        ["git", "-C", str(project), "merge-base", "--is-ancestor", base, head],
        capture_output=True,
        timeout=10,
    )
    return result.returncode == 0


def retained_completion(project: Path, record: dict) -> bool:
    """Historical completion needs retained executed proofs, not terminal labels."""
    try:
        rows = record["steps"]
        if [r["step_id"] for r in rows] != STEP_IDS or rows[-1]["status"] != "passed":
            return False
        for row in rows:
            if row["status"] == "not-applicable":
                if row["required"] or not row.get("reason", "").strip():
                    return False
                continue
            if (
                row["status"] != "passed"
                or row.get("verifier_exit") != 0
                or not row.get("verified_at")
                or not row.get("verify_command_sha256")
                or not row.get("evidence_sha256")
            ):
                return False
            ev = historical_artifact(
                project, record, row["evidence_path"], row["evidence_sha256"]
            )
            if (
                ev.is_symlink()
                or not ev.is_file()
                or digest(ev) != row["evidence_sha256"]
            ):
                return False
            for name, meta in row.get("instruments", {}).items():
                sha = meta.get("sha256") if isinstance(meta, dict) else meta
                path = historical_artifact(project, record, name, sha)
                if path.is_symlink() or not path.is_file() or digest(path) != sha:
                    return False
        review = next(r for r in rows if r["step_id"] == "review")
        baseline = (
            project / STORE_DIR / "evidence" / (record["work_id"] + "-build-base.txt")
        )
        # Old Git records bound release rows but not review rows. A missing review
        # identity is a provenance gap, never evidence that this was non-Git work.
        git_obligations = (
            review.get("git_identity") is not None
            or any(r.get("git_identity") for r in rows if r["step_id"] in RELEASE_STEPS)
            or bool(record.get("completion", {}).get("baseline_sha256"))
            or baseline.exists()
            or any(
                portable(project, baseline) in r.get("instruments", {})
                or str(baseline) in r.get("instruments", {})
                for r in rows
            )
        )
        if git_obligations:
            if not review.get("git_identity"):
                return False
            if not review.get("candidate_sha256"):
                return False
            if record.get("completion", {}).get("archive_dir"):
                baseline = historical_artifact(
                    project,
                    record,
                    portable(project, baseline),
                    record["completion"]["baseline_sha256"],
                )
            if baseline.is_symlink() or not baseline.is_file():
                return False
            lines = baseline.read_text().splitlines()
            if (
                len(lines) != 2
                or lines[1] != "work-id " + record["work_id"]
                or not re.fullmatch(r"base [0-9a-f]{40}(?:[0-9a-f]{24})?", lines[0])
            ):
                return False
            base = lines[0].split(" ", 1)[1]
            if not ancestry_valid(
                project, record, base, review["git_identity"]["head"]
            ):
                return False
            if record.get("completion", {}).get(
                "baseline_sha256", digest(baseline)
            ) != digest(baseline):
                return False
            if any(
                not r.get("git_identity")
                for r in rows
                if r["step_id"] in RELEASE_STEPS and r["status"] == "passed"
            ):
                return False
        completion = record.get("completion")
        return not completion or (
            completion.get("state") == "completed"
            and completion.get("receipt_sha256") == completion_digest(record)
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        subprocess.TimeoutExpired,
    ):
        return False


def publish_archive(destination: Path, sha: str, source=None, payload=None) -> None:
    """Publish verified bytes atomically; unsealed partial files may recover."""
    if destination.is_symlink() or (destination.exists() and not destination.is_file()):
        raise ValueError(
            "completion archive cannot replace a redirected or non-file artifact"
        )
    if destination.is_file() and digest(destination) == sha:
        return
    if source is not None:
        if source.is_symlink() or not source.is_file() or digest(source) != sha:
            raise ValueError("completion source bytes changed before publication")
    elif payload is None or hashlib.sha256(payload).hexdigest() != sha:
        raise ValueError("completion payload does not match its content hash")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".copy-", dir=destination.parent, delete=False
        ) as outgoing:
            temporary = Path(outgoing.name)
            if source is not None:
                with source.open("rb") as incoming:
                    shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
            else:
                outgoing.write(payload)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if digest(temporary) != sha or (source is not None and digest(source) != sha):
            raise ValueError("completion bytes changed during publication")
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def seal_completion(project: Path, record: dict) -> None:
    completion = {
        "state": "completed",
        "completed_at": record["steps"][-1]["verified_at"],
        "receipt_sha256": completion_digest(record),
    }
    baseline = (
        project / STORE_DIR / "evidence" / (record["work_id"] + "-build-base.txt")
    )
    if record.get("completion", {}).get("archive_dir") and record["completion"].get(
        "baseline_sha256"
    ):
        baseline = historical_artifact(
            project,
            record,
            portable(project, baseline),
            record["completion"]["baseline_sha256"],
        )
    if baseline.is_file():
        completion["baseline_sha256"] = digest(baseline)
    archive = archive_directory(project, record)
    if any(parent.is_symlink() for parent in (archive, *archive.parents)):
        raise ValueError("historical archive cannot be redirected through symlinks")
    archive.mkdir(parents=True, exist_ok=True)
    sources = {}
    for row in record["steps"]:
        if row["status"] != "passed":
            continue
        sources[row["evidence_sha256"]] = historical_artifact(
            project, record, row["evidence_path"], row["evidence_sha256"]
        )
        for name, meta in row.get("instruments", {}).items():
            sha = meta.get("sha256") if isinstance(meta, dict) else meta
            sources[sha] = historical_artifact(project, record, name, sha)
    if baseline.is_file():
        sources[completion["baseline_sha256"]] = baseline
    for sha, source in sources.items():
        if (
            not re.fullmatch(r"[0-9a-f]{64}", sha)
            or source.is_symlink()
            or not source.is_file()
        ):
            raise ValueError("completion proof cannot be archived")
        publish_archive(archive / sha, sha, source=source)
    review = next(row for row in record["steps"] if row["step_id"] == "review")
    if review.get("git_identity") is not None:
        base = baseline.read_text().splitlines()[0].split(" ", 1)[1]
        head = review["git_identity"]["head"]
        if not ancestry_valid(project, record, base, head):
            raise ValueError("completion Git ancestry cannot be verified")
        payload = json.dumps(
            {
                "kind": "git-ancestry-receipt-v1",
                "base": base,
                "head": head,
                "receipt_sha256": completion_digest(record),
                "argv": ["git", "merge-base", "--is-ancestor", base, head],
                "exit_code": 0,
                "verified_at": now(),
            },
            sort_keys=True,
        ).encode()
        sha = hashlib.sha256(payload).hexdigest()
        publish_archive(archive / sha, sha, payload=payload)
        completion["ancestry_sha256"] = sha
    completion["archive_dir"] = portable(project, archive)
    record["completion"] = completion


def refresh(project: Path, record: dict) -> bool:
    """Reopen a passed step, and every later passed step, when its inputs changed."""
    changed_any, reopen = False, False
    # Legacy records migrate only with complete, retained verifier provenance.
    if not record.get("completion") and retained_completion(project, record):
        seal_completion(project, record)
        changed_any = True
    if record.get("completion"):
        review = next(row for row in record["steps"] if row["step_id"] == "review")
        needs_provenance = not record["completion"].get("archive_dir") or (
            review.get("git_identity") is not None
            and not record["completion"].get("ancestry_sha256")
        )
        if needs_provenance and retained_completion(project, record):
            seal_completion(project, record)
            return True
        # Sealed rows are immutable; validity is reported separately from live work.
        return changed_any
    historical = bool(record.get("completion"))
    identity = (
        git_identity(project)
        if any(
            s["status"] == "passed"
            and (s["step_id"] in RELEASE_STEPS or s["step_id"] == "review")
            for s in record["steps"]
        )
        and not historical
        else None
    )
    for step in record["steps"]:
        # Scrub old receipts on read, too; status must not expose old credentials.
        command = step.get("verify_command", "")
        if command and not step.get("verify_command_sha256"):
            step["verify_command_sha256"] = command_digest(command)
            changed_any = True
        for key in ("verify_command", "output_tail"):
            original = step.get(key, "")
            if redact(original) != original:
                step[key] = redact(original)
                changed_any = True
        if step["status"] != "passed":
            continue
        ev_ok, ev_stat = _stable(
            resolve(project, step["evidence_path"]),
            step["evidence_sha256"],
            step.get("evidence_stat"),
        )
        step["evidence_stat"] = ev_stat
        identity_changed = (
            not historical
            and (step["step_id"] in RELEASE_STEPS or step["step_id"] == "review")
            and step.get("git_identity") != identity
        )
        candidate_changed = False
        if (
            not historical
            and step["step_id"] == "review"
            and git_identity(project) is not None
        ):
            try:
                candidate_changed = step.get("candidate_sha256") != candidate_snapshot(
                    project
                )
            except (OSError, ValueError):
                candidate_changed = True
        changed = not ev_ok or identity_changed or candidate_changed
        for name, meta in step["instruments"].items():
            sha = meta["sha256"] if isinstance(meta, dict) else meta
            stat = meta.get("stat") if isinstance(meta, dict) else None
            ok, cur = _stable(resolve(project, name), sha, stat)
            step["instruments"][name] = {"sha256": sha, "stat": cur}
            changed = changed or not ok
        if changed or reopen:
            step["revision"] = step.get("revision", 0) + 1
            step["status"] = "pending"
            step["reason"] = (
                "Reviewed candidate changed or cannot be inspected. Repeat review and later steps."
                if candidate_changed
                else "Git HEAD or branch changed after it passed. Repeat this step."
                if identity_changed
                else "Evidence or instrument changed after it passed. Repeat this step."
            )
            reopen = changed_any = True
    return changed_any


def summary(project: Path, record: dict) -> dict:
    # Rendering never relies on a mutating refresh to scrub legacy secrets.
    record = json.loads(json.dumps(record))
    for row in record["steps"]:
        for key in ("verify_command", "output_tail"):
            row[key] = redact(row.get(key, ""))
    open_steps = [s["step_id"] for s in record["steps"] if s["status"] not in TERMINAL]
    out = {
        "ok": True,
        "work_id": record["work_id"],
        "goal": record["goal"],
        "file": portable(project, store_path(project, record["work_id"])),
        "ready": not open_steps and not bool(record.get("completion")),
        "next_step": open_steps[0] if open_steps else None,
        "open": open_steps,
        "rule_notes": record.get("rule_notes", []),
        "steps": record["steps"],
        "completed": bool(record.get("completion")),
        "completion": record.get("completion"),
        "historical_receipts_valid": retained_completion(project, record)
        if record.get("completion")
        else False,
        "current_candidate_ready": not open_steps
        and not bool(record.get("completion")),
    }
    research = next(s for s in record["steps"] if s["step_id"] == "research")
    hint = research_hint(record["goal"])
    if hint and research["required"] and research["status"] not in TERMINAL:
        out["research_focus"] = hint
    return out


def status(project: Path, work_id: str, through: str = "") -> dict:
    path = store_path(project, work_id)
    if not path.is_file():
        raise ValueError(f"no work item at {path}; run start first")
    with locked(path):
        record = load(path)
        if refresh(project, record):
            save(path, record)
    out = summary(project, record)
    if through:
        last = STEP_IDS.index(through)
        open_rows = [s for s in out["open"] if STEP_IDS.index(s) <= last]
        out.update(
            through=through,
            ready=not open_rows and not out["completed"],
            open=open_rows,
            next_step=open_rows[0] if open_rows else None,
        )
    return out


def _open_before(record: dict, target: dict) -> list[str]:
    return [
        s["step_id"]
        for s in record["steps"][: target["sequence"] - 1]
        if s["status"] not in TERMINAL
    ]


def _target(record: dict, step_id: str) -> dict:
    target = next((s for s in record["steps"] if s["step_id"] == step_id), None)
    if target is None:
        raise ValueError(f"unknown step {step_id!r}; steps are: {', '.join(STEP_IDS)}")
    return target


def _commit(
    project: Path, path: Path, record: dict, target: dict, before: dict
) -> None:
    if {k: target.get(k) for k in RECORD_KEYS} != before:
        for later in record["steps"][target["sequence"] :]:
            if later["status"] == "passed":
                later["revision"] = later.get("revision", 0) + 1
                later["status"] = "pending"
                later["reason"] = "An earlier step was re-recorded. Repeat this step."
    target["revision"] = target.get("revision", 0) + 1
    record["updated_at"] = now()
    save(path, record)


def set_optional(project: Path, work_id: str, step_id: str, reason: str) -> dict:
    """Make a currently-required, not-yet-recorded row optional mid-run.

    Fixes the dead end where a goal's words (or the default) made a row
    required, and only partway through the checklist does it become clear
    the row does not apply (e.g. a design row for a verified nonvisual command-line change) -- with no way to flip it without abandoning the work id
    and re-proving every earlier row under a new one.

    Least-surprise rule: only a row that is (a) not one of the ALWAYS_REQUIRED
    rows -- those never bend regardless of goal wording, --require/--optional
    at start, or this -- and (b) still pending, so a row already passed,
    n/a'd or blocked is never silently reinterpreted after the fact.
    """
    if step_id not in STEP_IDS:
        raise ValueError(f"unknown step {step_id!r}; steps are: {', '.join(STEP_IDS)}")
    if step_id in ALWAYS_REQUIRED:
        raise ValueError(f"{step_id} is always required and cannot be made optional")
    if not reason.strip():
        raise ValueError("set-optional needs a written --reason")
    path = store_path(project, work_id)
    if not path.is_file():
        raise ValueError(f"no work item at {path}; run start first")
    with locked(path):
        record = load(path)
        if refresh(project, record):
            save(path, record)
        if record.get("completion"):
            raise ValueError(
                "completed work is historical; use reopen or start new work"
            )
        target = _target(record, step_id)
        if target["status"] != "pending":
            raise ValueError(
                f"{step_id} already has a recorded result ({target['status']}); "
                "set-optional only changes a row that has not been recorded yet"
            )
        if not target["required"]:
            raise ValueError(f"{step_id} is already optional")
        target["revision"] = target.get("revision", 0) + 1
        target["required"] = False
        record.setdefault("rule_notes", []).append(
            f"{step_id} made optional by set-optional: {reason.strip()}"
        )
        record["updated_at"] = now()
        save(path, record)
        return summary(project, record)


def step(
    project: Path,
    work_id: str,
    step_id: str,
    result: str,
    evidence: str = "",
    verify_cmd: str = "",
    reason: str = "",
    instruments=(),
    timeout: int = 600,
) -> dict:
    path = store_path(project, work_id)
    if not path.is_file():
        raise ValueError(f"no work item at {path}; run start first")
    if result not in {"pass", "na", "blocked"}:
        raise ValueError("result must be pass, na, or blocked")

    # Phase 1, under the lock: validate everything that does not need the verifier.
    with locked(path):
        record = load(path)
        if refresh(project, record):
            save(path, record)
        if record.get("completion"):
            raise ValueError(
                "completed work is historical; use reopen or start new work"
            )
        target = _target(record, step_id)
        before = {k: target.get(k) for k in RECORD_KEYS}
        before_revision = target.get("revision", 0)
        if result in {"na", "blocked"}:
            if result == "na" and target["required"]:
                raise ValueError("n/a needs a conditional step; this row is required")
            if not reason.strip():
                raise ValueError(f"{result} needs a written --reason")
            if result == "blocked":
                earlier = _open_before(record, target)
                if earlier:
                    raise ValueError(
                        "earlier steps are still open: "
                        + ", ".join(earlier)
                        + ". Pass them or mark conditional ones n/a first."
                    )
            target.update(
                status="not-applicable" if result == "na" else "blocked",
                reason=reason.strip(),
                verified_at=now(),
            )
            _commit(project, path, record, target, before)
            return summary(project, record)
        earlier = _open_before(record, target)
        if earlier:
            raise ValueError(
                "earlier steps are still open: "
                + ", ".join(earlier)
                + ". Pass them or mark conditional ones n/a first."
            )
        ev = resolve(project, evidence) if evidence else None
        if ev is None or ev.is_symlink() or not ev.is_file() or not verify_cmd.strip():
            raise ValueError(
                "pass needs --evidence (an existing regular file) and --verify"
            )
        deps = {}
        for name in instruments:
            q = resolve(project, name)
            if q.is_symlink() or not q.is_file():
                raise ValueError(
                    f"instrument {name!r} must be an existing regular file"
                )
            deps[portable(project, q)] = digest(q)
        sha = digest(ev)
        identity = (
            git_identity(project)
            if step_id in RELEASE_STEPS or step_id == "review"
            else None
        )
        candidate = (
            candidate_snapshot(project)
            if step_id == "review" and git_identity(project) is not None
            else None
        )

    # Phase 2, unlocked: the verifier may take minutes; others can still read status.
    code, output = run_verifier(verify_cmd, project, timeout)

    # Phase 3, under the lock: re-check nothing moved while the verifier ran.
    with locked(path):
        record = load(path)
        refresh(project, record)
        if record.get("completion"):
            raise ValueError(
                "work became completed while this verifier ran; historical rows are immutable"
            )
        target = _target(record, step_id)
        if (
            target.get("revision", 0) != before_revision
            or {k: target.get(k) for k in RECORD_KEYS} != before
        ):
            raise ValueError(
                "this step was changed by someone else while the verifier ran; retry"
            )
        earlier = _open_before(record, target)
        stable = sha == digest(ev) and all(
            digest(resolve(project, q)) == h for q, h in deps.items()
        )
        identity_stable = (
            step_id not in RELEASE_STEPS and step_id != "review"
        ) or identity == git_identity(project)
        try:
            candidate_stable = candidate is None or candidate == candidate_snapshot(
                project
            )
        except (OSError, ValueError):
            candidate_stable = False
        passed = (
            code == 0
            and stable
            and identity_stable
            and candidate_stable
            and not earlier
        )
        if not identity_stable:
            why = "Git HEAD or branch changed while the verifier ran. Retry on the current commit."
        elif earlier:
            why = "An earlier step reopened while the verifier ran: " + ", ".join(
                earlier
            )
        elif not candidate_stable:
            why = "Reviewed candidate changed while the verifier ran. Repeat review."
        elif not stable:
            why = (
                "The verifier changed the evidence or an instrument file. "
                "Write the evidence first, then verify it with a command that only reads it."
            )
        elif code == 124:
            why = f"Verifier timed out after {timeout}s."
        else:
            why = f"Verifier exited {code}."
        target.update(
            status="passed" if passed else "blocked",
            evidence_path=portable(project, ev),
            evidence_sha256=sha,
            evidence_stat=_fp(ev) if passed else target.get("evidence_stat"),
            instruments={
                name: {
                    "sha256": h,
                    "stat": _fp(resolve(project, name)) if passed else None,
                }
                for name, h in deps.items()
            },
            verify_command=redact(verify_cmd),
            verify_command_sha256=command_digest(verify_cmd),
            git_identity=identity,
            candidate_sha256=candidate,
            verifier_exit=code,
            output_tail=redact(output)[-2000:],
            verified_at=now(),
            reason="" if passed else why,
        )
        _commit(project, path, record, target, before)
        if passed and step_id == "closeout" and retained_completion(project, record):
            seal_completion(project, record)
            save(path, record)
        out = summary(project, record)
        if not passed:
            out.update(ok=False, error=why)
        return out


def reopen(project: Path, work_id: str, reason: str) -> dict:
    """Explicitly restart proof work, retaining history and the original baseline."""
    if not reason.strip():
        raise ValueError("reopen needs a written reason")
    path = store_path(project, work_id)
    with locked(path):
        record = load(path)
        if not record.get("completion"):
            raise ValueError("work is not completed")
        if (
            record["completion"].get("baseline_sha256")
            or git_identity(project) is not None
        ):
            baseline = project / STORE_DIR / "evidence" / (work_id + "-build-base.txt")
            if baseline.is_symlink() or not baseline.is_file():
                raise ValueError("original baseline is missing; retain the scope gap")
            if (
                record["completion"].get("baseline_sha256")
                and digest(baseline) != record["completion"]["baseline_sha256"]
            ):
                raise ValueError("original baseline changed; retain the scope gap")
        record.setdefault("completion_history", []).append(
            {
                "completion": record.pop("completion"),
                "steps": json.loads(json.dumps(record["steps"])),
                "reopened_at": now(),
                "reason": reason.strip(),
            }
        )
        for row in record["steps"]:
            row.update(
                status="pending",
                reason="Explicitly reopened: " + reason.strip(),
                revision=row.get("revision", 0) + 1,
            )
        save(path, record)
    return summary(project, record)


def list_items(project: Path) -> dict:
    items = []
    for f in sorted((project / STORE_DIR).glob("*.json")):
        try:
            s = status(project, f.stem)
            items.append(
                {
                    k: s[k]
                    for k in (
                        "work_id",
                        "goal",
                        "ready",
                        "next_step",
                        "completed",
                        "historical_receipts_valid",
                        "current_candidate_ready",
                    )
                }
            )
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            items.append({"work_id": f.stem, "error": str(exc)})
    return {"ok": True, "items": items}


def doctor(project: Path) -> dict:
    here = Path(__file__).resolve().parent.parent
    skills_root = here.parent
    bundled = sorted(
        {s[1].split()[0].lstrip("/") for s in STEPS} | {"development-protocol"}
    )
    checks = {
        "python_3_9_or_newer": sys.version_info >= (3, 9),
        "skill_file_next_to_script": (here / "SKILL.md").is_file(),
        "reference_file_next_to_script": (here / "reference.md").is_file(),
        "git_on_path": shutil.which("git") is not None,
        "project_folder_exists": project.is_dir(),
        "project_writable": os.access(project, os.W_OK),
    }
    # Advisory: the stack skills live beside this one when installed together.
    warnings = {
        f"skill_installed:{name}": (skills_root / name / "SKILL.md").is_file()
        for name in bundled
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


def print_human(result: dict) -> None:
    if "checks" in result:
        for name, passed in result["checks"].items():
            print(f"{'PASS' if passed else 'FAIL'}  {name}")
        for name, passed in result.get("warnings", {}).items():
            print(f"{'PASS' if passed else 'WARN'}  {name}")
        print(
            "devproto doctor: " + ("ok" if result["ok"] else "fix the FAIL lines above")
        )
        return
    if "items" in result:
        for item in result["items"]:
            if item.get("completed"):
                state = (
                    "historical proof verified"
                    if item.get("historical_receipts_valid")
                    else "historical proof gap"
                )
            else:
                state = (
                    "ready" if item.get("ready") else f"next: {item.get('next_step')}"
                )
            state = item.get("error") or state
            print(f"{item['work_id']}  {state}")
        return
    print(f"{result['work_id']}  {result['goal']}")
    if result.get("completed"):
        print(
            "  historical completion: "
            + (
                "retained proof valid"
                if result.get("historical_receipts_valid")
                else "proof gap"
            )
            + "; not a current release gate"
        )
    for note in result.get("rule_notes", []):
        print(f"  note: {note}")
    for s in result["steps"]:
        mark = {"passed": "x", "not-applicable": "-", "blocked": "!"}.get(
            s["status"], " "
        )
        need = "required" if s["required"] else "if needed"
        line = f"  [{mark}] {s['sequence']:>2}. {s['step_id']:<11} {need:<9} {s['skill']:<28}"
        if s["reason"]:
            line += f"  ({s['reason']})"
        elif s["status"] == "passed":
            line += f"  verified by: {s['verify_command']}"
        elif s["step_id"] == "research" and result.get("research_focus"):
            line += f"  suggested: {result['research_focus']}"
        print(line.rstrip())
    if result.get("error"):
        print(f"ERROR: {result['error']}")
    scope = f" through {result['through']}" if result.get("through") else ""
    if result.get("completed"):
        print(
            "HISTORICAL PROOF VERIFIED."
            if result.get("historical_receipts_valid")
            else "HISTORICAL PROOF GAP."
        )
    elif result["ready"]:
        print(f"READY{scope}.")
    elif result["next_step"] == "research" and result.get("research_focus"):
        print(f"Next step: research  (run {result['research_focus']})")
    else:
        print(f"Next step: {result['next_step']}")


def main(argv=None) -> int:
    # SUPPRESS, not a literal default: a subparser always re-parses into its own
    # namespace and copies every key it sees back over the top-level one, so a
    # subparser copy of this action with a real default would stomp a value the
    # top-level parser already set from before the subcommand. getattr() below
    # supplies the real default once, after parsing, from whichever copy fired.
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
        prog="devproto",
        description=__doc__.splitlines()[0],
        epilog="--project and --json may go before or after the subcommand.",
        parents=[common],
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser(
        "start", parents=[common], help="create a checklist for one piece of work"
    )
    p.add_argument("--goal", required=True)
    p.add_argument("--id", default="", help="work id (default: date plus goal slug)")
    p.add_argument(
        "--require",
        action="append",
        default=[],
        choices=STEP_IDS,
        help="force a conditional step on",
    )
    p.add_argument(
        "--optional",
        action="append",
        default=[],
        choices=STEP_IDS,
        help="turn off a conditional step the goal words wrongly required",
    )

    for name in ("status", "check"):
        p = sub.add_parser(
            name,
            parents=[common],
            help="show the checklist"
            if name == "status"
            else "exit 0 only when every row is passed or n/a",
        )
        p.add_argument("--id", required=True)
        if name == "check":
            p.add_argument(
                "--historical",
                action="store_true",
                help="verify retained completed-work receipts; never a current release gate",
            )
        p.add_argument(
            "--through",
            choices=STEP_IDS,
            default="",
            help="only consider rows up to this step (for a pre-merge gate)",
        )

    p = sub.add_parser("step", parents=[common], help="record a result for one step")
    p.add_argument("--id", required=True)
    p.add_argument("--step", required=True, choices=STEP_IDS)
    p.add_argument("--result", required=True, choices=["pass", "na", "blocked"])
    p.add_argument("--evidence", default="", help="file that shows the step's output")
    p.add_argument(
        "--verify", default="", help="command that must exit 0 in the project folder"
    )
    p.add_argument(
        "--instrument",
        action="append",
        default=[],
        help="test or grader file; editing it later reopens this step",
    )
    p.add_argument("--reason", default="")
    p.add_argument("--timeout", type=int, default=600)

    p = sub.add_parser(
        "set-optional",
        parents=[common],
        help="make a pending, currently-required row optional mid-run",
    )
    p.add_argument("--id", required=True)
    p.add_argument("--step", required=True, choices=STEP_IDS)
    p.add_argument("--reason", required=True)

    sub.add_parser(
        "steps", parents=[common], help="print the 17 rows and the skill for each"
    )
    sub.add_parser("list", parents=[common], help="list work items in this project")
    p = sub.add_parser(
        "reopen",
        parents=[common],
        help="restart completed work without changing its original baseline",
    )
    p.add_argument("--id", required=True)
    p.add_argument("--reason", required=True)
    sub.add_parser(
        "doctor", parents=[common], help="check the install and the project folder"
    )

    args = ap.parse_args(argv)
    as_json = getattr(args, "json", False)
    project = Path(getattr(args, "project", ".")).expanduser().resolve()
    if getattr(args, "historical", False) and args.through:
        ap.error("--historical cannot be combined with --through")
    try:
        if args.cmd == "start":
            result = start(project, args.goal, args.id, args.require, args.optional)
        elif args.cmd in ("status", "check"):
            if getattr(args, "historical", False):
                path = store_path(project, args.id)
                with locked(path):
                    result = summary(project, load(path))
            else:
                result = status(project, args.id, args.through)
        elif args.cmd == "step":
            result = step(
                project,
                args.id,
                args.step,
                args.result,
                args.evidence,
                args.verify,
                args.reason,
                args.instrument,
                args.timeout,
            )
        elif args.cmd == "set-optional":
            result = set_optional(project, args.id, args.step, args.reason)
        elif args.cmd == "steps":
            result = {
                "ok": True,
                "steps": [dict(step_id=s, skill=k, purpose=p) for s, k, p in STEPS],
            }
        elif args.cmd == "list":
            result = list_items(project)
        elif args.cmd == "reopen":
            result = reopen(project, args.id, args.reason)
        else:
            result = doctor(project)
    except KeyboardInterrupt:
        print("interrupted; nothing recorded", file=sys.stderr)
        return 130
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        msg = {"ok": False, "error": str(exc)}
        print(
            json.dumps(msg, indent=2) if as_json else f"ERROR: {exc}", file=sys.stderr
        )
        return 2

    if as_json:
        print(json.dumps(result, indent=2))
    elif args.cmd == "steps":
        for i, s in enumerate(result["steps"], 1):
            print(f"{i:>2}. {s['step_id']:<11} {s['skill']:<28} {s['purpose']}")
    else:
        print_human(result)
    if args.cmd == "check":
        if args.historical:
            return (
                0
                if result.get("completed") and result.get("historical_receipts_valid")
                else 1
            )
        return 0 if result["ready"] and not result.get("completed") else 1
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
