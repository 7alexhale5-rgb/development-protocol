"""Shared primitives for the development-protocol stack's checklist tools.

Canonical home for the pieces devproto.py, pathway.py and sweep.py would
otherwise each hand-roll: the verifier runner (temp-file output, no stdin,
whole-process-group kill), the per-store file lock, a file digest, a
timestamp, a bash-with-pipefail runner, and an output redactor.

Python 3.9+, standard library only. Importers outside this folder locate this
file by relative path (see each caller's own docstring) and should raise a
clear error if it is missing, rather than fail on an unrelated ImportError.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import shutil
import signal
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

try:
    import fcntl  # POSIX
except ImportError:  # Windows: no lock, so run one agent per project at a time
    fcntl = None


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _file_sha256(path: Path) -> bytes:
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.digest()


def digest(path: Path) -> str:
    return _file_sha256(path).hex() if path.is_file() else ""


@contextlib.contextmanager
def locked(path: Path):
    """One lock for the whole store, held only for reads and writes, never for a verifier."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if fcntl is None:
        yield
        return
    with (path.parent / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True
            )
    except (ProcessLookupError, PermissionError):
        pass


def run_verifier(cmd: str, project: Path, timeout: int) -> tuple[int, str]:
    """Run cmd in the project folder with no stdin.

    Output goes to a temp file, not a pipe, so a background child that keeps the
    output open cannot hang the run. When the command ends, times out, or is
    interrupted, its whole process group is killed so nothing keeps running.
    """
    bash = shutil.which("bash")
    if bash is None:
        return 127, "bash not found on PATH"
    with tempfile.TemporaryFile() as out:
        proc = subprocess.Popen(
            [bash, "-o", "pipefail", "-c", cmd],
            cwd=str(project),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=os.name == "posix",
        )
        try:
            code = proc.wait(timeout=timeout)
            note = ""
        except subprocess.TimeoutExpired:
            code, note = 124, f"\nverifier timed out after {timeout}s"
        except BaseException:
            _kill_tree(proc)
            proc.wait()
            raise
        _kill_tree(proc)
        proc.wait()
        out.seek(0)
        return code, out.read().decode(errors="replace") + note


def run_bash(
    cmd: str, cwd: Path | None = None, timeout: int = 300
) -> tuple[int, str, str]:
    """Run cmd under bash with pipefail. Returns (exit_code, stdout, stderr).

    pipefail matters: without it a pipeline reports only its last stage, so
    `rg --files missing/ | sort` exits 0 and hides rg's error. Never raises for
    a missing bash or a timed-out command; both come back as a non-zero exit
    with the reason in stderr, so a caller's own error handling stays simple.
    """
    bash = shutil.which("bash")
    if bash is None:
        return 127, "", "bash not found on PATH"
    try:
        out = subprocess.run(
            [bash, "-o", "pipefail", "-c", cmd],
            cwd=str(cwd) if cwd is not None else None,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s: {cmd}"
    except OSError as exc:
        return 126, "", f"could not run bash: {exc}"
    return out.returncode, out.stdout, out.stderr


# ---------------------------------------------------------------------------
# secret redaction: applied to verifier output before it is written to a
# work item's JSON file, which is git-trackable by default.
# ---------------------------------------------------------------------------
REDACT_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk_(live|test)_[A-Za-z0-9]{16,}"),  # Stripe live/test secret key
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[bpar]-[A-Za-z0-9-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),  # Google API key
    re.compile(
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]{10,})?"
    ),  # JWT
    re.compile(
        r"[a-zA-Z][a-zA-Z0-9+.-]*://[^/\s:@]+:[^@\s]+@"
    ),  # credentialed URL / connection string
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{10,}"),
    re.compile(r"(?im)\b(api[_-]?key|access[_-]?token|secret|password)\b\s*[:=]\s*\S+"),
    # Broader catch-all for env-var-style dumps this doesn't already cover,
    # e.g. SUPABASE_SERVICE_ROLE_KEY=, AUTH_TOKEN=, DB_PASSWORD=.
    re.compile(r"(?i)\b[A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)\b\s*[:=]\s*\S+"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
    ),
]


def command_digest(cmd: str) -> str:
    """Identify an original command without storing its plaintext credentials."""
    return hashlib.sha256(cmd.encode("utf-8")).hexdigest()


def redact(text: str) -> str:
    """Replace anything that looks like a credential with a placeholder."""
    for pattern in REDACT_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def sections_have_content(text: str, sections: list[str]) -> bool:
    """Reject missing/empty Markdown sections, not judge their factual quality."""
    text = re.sub(r"<!--[\s\S]*?-->", "", text)
    bodies = {section: [] for section in sections}
    active = None
    level = 0
    fence = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            fence = None if fence == marker else (marker if fence is None else fence)
            continue
        if fence:
            continue
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            depth, title = len(heading[1]), heading[2]
            if title in bodies:
                active, level = title, depth
            elif depth <= level:
                active = None
            continue
        if active:
            value = re.sub(r"^(?:[-*+]\s*|\d+[.)]\s*)", "", stripped).strip()
            substantive = re.sub(r"^\*\*[^*]*:\*\*\s*", "", value)
            substantive = re.sub(r"^[^:\[\]]{1,40}:\s*", "", substantive)
            substantive = re.sub(r"\[[^\]]*\]", "", substantive)
            if (
                value
                and substantive.strip().upper() not in ("TODO", "TBD")
                and not re.fullmatch(r"\[.*\]", value)
                and re.search(r"\w", substantive)
            ):
                bodies[active].append(value)
    return all(bodies.values())


def selftest() -> int:
    """Smoke-check this module's own primitives. Used by relentless/scripts/mutants.py,
    which has no other hook into this file: it execs a mutated copy and calls this.
    """
    import tempfile as _tempfile

    fails = []

    # pipefail must be on: a failing first stage in a pipe must fail the pipe,
    # even though the pipeline's last stage exits 0.
    code, _, _ = run_bash("false | true")
    if code == 0:
        fails.append("run_bash does not enforce pipefail")

    # a bogus command must come back as a clean non-zero exit, never a raise.
    code, _, _ = run_bash("__no_such_command_xyz__")
    if code == 0:
        fails.append("run_bash did not report a failed command cleanly")

    if "sk-ant-" + "a" * 20 in redact("token " + "sk-ant-" + "a" * 20):
        fails.append("redact() left an Anthropic-shaped key in place")
    if "AKIA" + "B" * 16 in redact("key=" + "AKIA" + "B" * 16):
        fails.append("redact() left an AWS-shaped key in place")

    with _tempfile.TemporaryDirectory() as d:
        f = Path(d) / "x.txt"
        f.write_text("hi")
        if not digest(f):
            fails.append("digest() returned empty for a real file")
        if digest(Path(d) / "missing.txt") != "":
            fails.append("digest() did not return empty for a missing file")
        with locked(Path(d) / "store" / "item.json"):
            pass  # must not raise

    if not now():
        fails.append("now() returned empty")

    for name in fails:
        print(f"FAIL {name}")
    return 1 if fails else 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Check primitives or nonempty Markdown evidence sections."
    )
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--section", action="append", default=[])
    args = parser.parse_args()
    if args.evidence is None:
        if args.section:
            parser.error("--section requires --evidence")
        raise SystemExit(selftest())
    if not args.section:
        parser.error("--evidence requires at least one --section")
    try:
        passed = sections_have_content(
            args.evidence.read_text(encoding="utf-8"), args.section
        )
    except (OSError, UnicodeError) as exc:
        print(f"FAIL cannot read evidence: {exc}")
        raise SystemExit(1)
    print(
        "PASS required sections contain text"
        if passed
        else "FAIL required sections are missing or empty"
    )
    raise SystemExit(0 if passed else 1)


def candidate_snapshot(project):
    """Hash the complete nonignored candidate without modifying the user's Git index."""
    project = project.resolve()
    def git(*args):
        result = subprocess.run(['git', '-C', str(project), *args], capture_output=True)
        if result.returncode:
            raise ValueError('candidate Git state cannot be read')
        return result.stdout
    if Path(os.fsdecode(git('rev-parse', '--show-toplevel')).strip()).resolve() != project:
        raise ValueError('--project must name the repository root')
    head_entries = {}
    for entry in git('ls-tree', '-rz', 'HEAD').split(b'\0'):
        if entry:
            metadata, name = entry.split(b'\t', 1)
            head_entries[name] = metadata.split(b' ')[0]
    names = set(head_entries)
    names.update(git('ls-files', '-z', '-co', '--exclude-standard').split(b'\0'))
    digest = hashlib.sha256()
    index_modes = {}
    for entry in git('ls-files', '-sz').split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        if name == b'.devproto' or name.startswith(b'.devproto/'):
            continue
        index_modes[name] = metadata.split(b' ')[0]
        digest.update(b'index\0' + entry + b'\0')
    for name in sorted(names - {b''}):
        if name == b'.devproto' or name.startswith(b'.devproto/'):
            continue
        path = project / os.fsdecode(name)
        if index_modes.get(name) == b'160000':
            raise ValueError('candidate includes an unsupported indexed submodule')
        digest.update(name + b'\0')
        if path.is_symlink():
            kind, content = b'symlink', os.fsencode(os.readlink(path))
        elif not path.exists():
            kind, content = b'deleted', b''
        elif path.is_file():
            kind = b'executable' if path.stat().st_mode & 0o111 else b'file'
            digest.update(kind + b'\0' + _file_sha256(path))
            continue
        elif path.is_dir() and head_entries.get(name) != b'160000' and index_modes.get(name) != b'160000':
            if (path / '.git').exists():
                raise ValueError('candidate includes an unsupported nested repository')
            kind, content = b'deleted', b''
        else:
            raise ValueError('candidate includes an unsupported directory or submodule')
        digest.update(kind + b'\0' + hashlib.sha256(content).digest())
    return digest.hexdigest()
