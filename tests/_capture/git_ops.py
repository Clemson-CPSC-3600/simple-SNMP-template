"""Git subprocess wrappers used by the capture layer.

All operations are scoped to student-editable areas (src/ and tests/).
Never calls git commands that could affect branches other than HEAD.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


GIT_ENV = {
    # Never prompt for credentials — prevents hangs if auth isn't configured.
    "GIT_TERMINAL_PROMPT": "0",
    # Don't pop up askpass dialogs either.
    "GIT_ASKPASS": "echo",
}


def run_git(args: List[str], cwd: Path, timeout: float = 15.0,
            capture: bool = True) -> subprocess.CompletedProcess:
    """Run a git command with our safe env. Never raises on non-zero exit.

    Public so other capture modules can introspect git state (e.g., dedupe
    logic in capture.py checking `git log -1`).
    """
    env = {**os.environ, **GIT_ENV}
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


@dataclass
class DiffStats:
    added: int
    removed: int
    files: List[str]


def stage_student_files(repo: Path) -> None:
    """Stage the allowlisted paths. Nothing else can enter a capture commit.

    The allowlist covers: student work (src/, tests/), Codex transcripts
    (.codex-transcripts/), shipped guardrail files (AGENTS.md, .codex/,
    AI_POLICY.md). .codex/auth.json is excluded by .gitignore in student
    repos; we rely on that rather than special-casing it here so students
    can inspect .gitignore.

    Missing paths are filtered out before invoking git. `git add` exits
    non-zero on any missing pathspec and stages NOTHING when it does —
    `--ignore-errors` does not suppress that class of failure. Freshly
    generated student repos lack most of these paths until the student's
    first Codex session, so the filter is load-bearing.
    """
    allowlist = [
        "src",
        "tests",
        ".codex-transcripts",
        ".codex",
        "AGENTS.md",
        "AI_POLICY.md",
    ]
    existing = [p for p in allowlist if (repo / p).exists()]
    if not existing:
        return
    run_git(["add", "-A", "--", *existing], cwd=repo)


def commit(repo: Path, message: str, allow_empty: bool = True) -> bool:
    """Commit staged changes. Returns True on success, False on failure.

    Never raises. Uses --allow-empty by default so an unchanged tree still records
    a run. Uses -F - to pass the multi-line message via stdin, avoiding shell
    quoting pitfalls across platforms.
    """
    args = ["commit", "-F", "-"]
    if allow_empty:
        args.append("--allow-empty")
    env = {**os.environ, **GIT_ENV}
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            env=env,
            input=message,
            text=True,
            capture_output=True,
            timeout=10.0,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def push_background(repo: Path, log_path: Path) -> None:
    """Fire-and-forget push. Output goes to .test-runs.log. Never blocks caller.

    On Windows, uses DETACHED_PROCESS so that closing the parent terminal
    doesn't kill the push.
    """
    env = {**os.environ, **GIT_ENV}
    # Keep an explicit reference to the log handle so we can close the parent's
    # copy after Popen has duplicated the fd for the child. Otherwise the file
    # relies on CPython refcount cleanup and leaks deterministically on PyPy.
    log_fh = open(log_path, "ab")
    try:
        kwargs = {
            "cwd": str(repo),
            "env": env,
            "stdout": log_fh,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "nt":
            # CREATE_NO_WINDOW | DETACHED_PROCESS
            kwargs["creationflags"] = 0x08000000 | 0x00000008
        else:
            kwargs["start_new_session"] = True
        try:
            subprocess.Popen(
                ["git", "push", "origin", "HEAD"],
                **kwargs,
            )
        except OSError:
            pass  # Push is best-effort. Commit already succeeded.
    finally:
        log_fh.close()


def is_in_merge_or_rebase(repo: Path) -> bool:
    """True if the repo is mid-merge, mid-rebase, or mid-cherry-pick.

    We refuse to auto-commit in these states to avoid corrupting student work.
    """
    git_dir = repo / ".git"
    if not git_dir.is_dir():
        return False
    markers = ["MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD",
               "rebase-merge", "rebase-apply"]
    return any((git_dir / m).exists() for m in markers)


def is_git_repo(path: Path) -> bool:
    """True iff path is inside a git working tree."""
    result = run_git(["rev-parse", "--is-inside-work-tree"], cwd=path, timeout=5.0)
    return result.returncode == 0 and result.stdout.strip() == "true"


def diff_stats_staged(repo: Path) -> DiffStats:
    """Numstat of what's currently staged. Returns zeros if nothing staged."""
    result = run_git(["diff", "--cached", "--numstat"], cwd=repo, timeout=10.0)
    added = removed = 0
    files: List[str] = []
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                # Binary files report "-" for counts; treat as 0.
                try:
                    added += int(parts[0])
                    removed += int(parts[1])
                except ValueError:
                    pass
                files.append(parts[2])
    return DiffStats(added=added, removed=removed, files=files)


def current_head_sha(repo: Path) -> Optional[str]:
    """Returns HEAD sha or None if unavailable."""
    result = run_git(["rev-parse", "HEAD"], cwd=repo, timeout=5.0)
    if result.returncode == 0:
        return result.stdout.strip()
    return None
