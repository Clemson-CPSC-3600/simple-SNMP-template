"""End-to-end test of the capture orchestration against a tmp git repo.

This test does NOT invoke pytest recursively — it exercises the capture
functions directly with a mock session object. Recursive pytest invocation
is covered by test_capture_conftest.py.
"""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests._capture import capture, metadata


@pytest.fixture
def tmp_git_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / ".gitkeep").write_text("")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.fixture
def tmp_git_repo_with_capture(tmp_git_repo):
    """tmp_git_repo plus project-template-config.json enabling capture."""
    (tmp_git_repo / "project-template-config.json").write_text(
        '{"capture_enabled": true}'
    )
    return tmp_git_repo


def test_session_start_then_finish_produces_one_commit(tmp_git_repo_with_capture):
    tmp_git_repo = tmp_git_repo_with_capture  # alias for brevity below
    ctx = capture.session_start(tmp_git_repo)
    assert ctx is not None
    (tmp_git_repo / "src" / "work.py").write_text("x = 1\n")
    ctx.record_test(outcome="passed", bundle=1, points=10)
    ctx.record_test(outcome="failed", bundle=2, points=15)
    capture.session_finish(tmp_git_repo, ctx, status="completed")

    result = subprocess.run(
        ["git", "log", "--pretty=%B", "-1"],
        cwd=tmp_git_repo, capture_output=True, text=True, check=True,
    )
    body = result.stdout
    assert "test-run:" in body
    assert "tests_total: 2" in body
    assert "tests_passed: 1" in body
    assert "tests_failed: 1" in body
    assert "bundles_passing: [1]" in body
    assert "bundles_failing: [2]" in body
    assert "status: completed" in body


def test_session_skipped_when_capture_disabled(tmp_git_repo):
    # No config file at all — capture should be off.
    ctx = capture.session_start(tmp_git_repo)
    assert ctx is None

    # Config present but capture_enabled false.
    (tmp_git_repo / "project-template-config.json").write_text(
        '{"capture_enabled": false}'
    )
    assert capture.session_start(tmp_git_repo) is None

    # Malformed config — treat as disabled (fail-safe).
    (tmp_git_repo / "project-template-config.json").write_text("not json")
    assert capture.session_start(tmp_git_repo) is None


def test_session_skipped_if_in_merge_state(tmp_git_repo):
    # Enable capture so we exercise the merge check, not the config gate.
    (tmp_git_repo / "project-template-config.json").write_text(
        '{"capture_enabled": true}'
    )
    (tmp_git_repo / ".git" / "MERGE_HEAD").write_text("deadbeef\n")
    ctx = capture.session_start(tmp_git_repo)
    assert ctx is None  # capture skipped


def test_session_finish_ingests_codex_rollouts(
    tmp_git_repo_with_capture, tmp_path, monkeypatch
):
    """session_finish should copy matching Codex rollouts into .codex-transcripts/.

    Uses the REAL Codex rollout schema (type: session_meta, payload.cwd) and
    places the fixture under sessions/YYYY/MM/DD/ to exercise the recursive
    scan.
    """
    tmp_git_repo = tmp_git_repo_with_capture

    # Point CODEX_HOME at an isolated tmp dir and seed a realistic rollout.
    codex_home = tmp_path / "codex_home"
    rollout_dir = codex_home / "sessions" / "2026" / "04" / "22"
    rollout_dir.mkdir(parents=True)
    rollout_path = rollout_dir / "rollout-xyz.jsonl"
    session_meta = {
        "timestamp": "2026-04-22T12:00:00Z",
        "type": "session_meta",
        "payload": {
            "id": "xyz",
            "cwd": str(tmp_git_repo),
            "originator": "codex_exec",
            "cli_version": "0.119.0-alpha.28",
            "source": "exec",
        },
    }
    rollout_path.write_text(json.dumps(session_meta) + "\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    ctx = capture.session_start(tmp_git_repo)
    assert ctx is not None
    # Note: we do NOT need to forward-date the rollout mtime. The ingest
    # matches by cwd alone (plus idempotency) — the realistic workflow has
    # the student using Codex BEFORE running pytest, so the rollout mtime
    # is necessarily < session_started_at. Capturing it is the whole point.
    ctx.record_test(outcome="passed", bundle=1, points=10)
    capture.session_finish(tmp_git_repo, ctx, status="completed")

    copied = tmp_git_repo / ".codex-transcripts" / "rollout-xyz.jsonl"
    assert copied.exists(), (
        f"Expected rollout to be copied to {copied}, but it was not. "
        f"Contents of .codex-transcripts/: "
        f"{list((tmp_git_repo / '.codex-transcripts').glob('*')) if (tmp_git_repo / '.codex-transcripts').exists() else 'missing'}"
    )


def test_session_start_commits_orphan_from_prior_run(tmp_git_repo_with_capture):
    tmp_git_repo = tmp_git_repo_with_capture
    # Simulate a prior orphaned session
    from tests._capture import state
    import json, time
    sid = state.start_session(tmp_git_repo, hard_deadline_seconds=1)
    marker = tmp_git_repo / ".test-run-state" / f"{sid}.json"
    data = json.loads(marker.read_text())
    data["started_at"] = time.time() - 120
    marker.write_text(json.dumps(data))

    capture.session_start(tmp_git_repo)

    log = subprocess.run(
        ["git", "log", "--pretty=%s", "-3"],
        cwd=tmp_git_repo, capture_output=True, text=True, check=True,
    ).stdout
    assert "orphaned session" in log
