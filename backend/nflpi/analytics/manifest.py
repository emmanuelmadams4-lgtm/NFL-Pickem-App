"""Run records: what code, lock file and data produced a model's numbers. No clock time, nothing guessed."""

import hashlib
import subprocess
from pathlib import Path

LOCK_FILE = Path("backend") / "uv.lock"
GIT_TIMEOUT_SECONDS = 20


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
                              timeout=GIT_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip()


def git_revision(repo_root: str | Path) -> tuple[str | None, bool | None]:
    """Return (HEAD, dirty); (None, None) when the folder is not the root of a readable git repository."""
    repo = Path(repo_root)
    top = _git(repo, "rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != repo.resolve():
        return None, None
    head, status = _git(repo, "rev-parse", "HEAD"), _git(repo, "status", "--porcelain")
    if not head or status is None:
        return None, None
    return head, bool(status)


def _lock_hash(repo: Path) -> tuple[str | None, str | None]:
    lock = repo / LOCK_FILE
    if not lock.is_file():
        return None, f"{LOCK_FILE.as_posix()} not found"
    return file_sha256(lock), None


def run_record(
    model: str, *, label: str, seed: int | None, seed_note: str | None, cutoff_rule: str, latest_kickoff: str | None,
    n_games: int, seasons: list[int], uses_closing_line: bool, data_files: dict[str, str | Path],
    repo_root: str | Path, games: dict[str, dict] | None = None,
) -> dict:
    repo = Path(repo_root)
    revision, dirty = git_revision(repo)
    lock_sha, lock_reason = _lock_hash(repo)
    record = {
        "model": model,
        "label": label,
        "code_revision": revision,
        "git_dirty": dirty,
        "code_revision_reason": None if revision else "not a readable git repository",
        "lock_file_sha256": lock_sha,
        "lock_file_reason": lock_reason,
        "data_sha256": {name: file_sha256(path) for name, path in sorted(data_files.items())},
        "seed": seed,
        "seed_note": seed_note,
        "cutoff": {"rule": cutoff_rule, "latest_kickoff": latest_kickoff},
        "n_games": int(n_games),
        "seasons": [int(s) for s in seasons],
        "uses_closing_line": bool(uses_closing_line),
    }
    if games is not None:  # per game: {"n_simulations": int | None, "inputs_used": [FEATURES.md names]}
        record["games"] = games
    return record
