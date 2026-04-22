"""Tests for _capture.git_ops. These run in a throwaway git repo per test."""
import subprocess
from pathlib import Path

import pytest

from tests._capture import git_ops


@pytest.fixture
def tmp_git_repo(tmp_path, monkeypatch):
    """Create a tmp git repo with src/ and tests/ directories."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / ".gitkeep").write_text("")
    (tmp_path / "tests" / ".gitkeep").write_text("")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return tmp_path


def test_stage_student_files_only_adds_src_and_tests(tmp_git_repo):
    (tmp_git_repo / "src" / "a.py").write_text("x = 1\n")
    (tmp_git_repo / "tests" / "b.py").write_text("y = 2\n")
    (tmp_git_repo / "secret.env").write_text("KEY=nope\n")
    git_ops.stage_student_files(tmp_git_repo)
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_git_repo, capture_output=True, text=True, check=True,
    )
    staged = set(result.stdout.strip().splitlines())
    assert "src/a.py" in staged
    assert "tests/b.py" in staged
    assert "secret.env" not in staged


def test_stage_student_files_includes_codex_artifacts(tmp_git_repo):
    import subprocess
    (tmp_git_repo / ".codex-transcripts").mkdir()
    (tmp_git_repo / ".codex").mkdir()
    (tmp_git_repo / ".codex-transcripts" / "rollout-a.jsonl").write_text("{}\n")
    (tmp_git_repo / ".codex" / "config.toml").write_text('model = "gpt-5.4"\n')
    (tmp_git_repo / "AGENTS.md").write_text("# tutor rules\n")
    (tmp_git_repo / "AI_POLICY.md").write_text("# policy\n")
    (tmp_git_repo / "src" / "work.py").write_text("x = 1\n")

    git_ops.stage_student_files(tmp_git_repo)

    staged = set(subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines())

    assert "src/work.py" in staged
    assert ".codex-transcripts/rollout-a.jsonl" in staged
    assert ".codex/config.toml" in staged
    assert "AGENTS.md" in staged
    assert "AI_POLICY.md" in staged


def test_stage_student_files_succeeds_when_optional_paths_missing(tmp_git_repo):
    """Template repos and fresh student repos lack .codex-transcripts/,
    .codex/, AGENTS.md, AI_POLICY.md until the first Codex session or the
    create-assignment run. stage_student_files must still succeed.

    Regression protection: the naive `git add -A -- src tests .codex-transcripts
    .codex AGENTS.md AI_POLICY.md` implementation exits 128 on missing
    pathspecs and stages NOTHING — the pre-filter is load-bearing.
    """
    import subprocess
    (tmp_git_repo / "src" / "work.py").write_text("x = 1\n")
    # Intentionally do NOT create the optional paths.

    git_ops.stage_student_files(tmp_git_repo)

    staged = set(subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines())

    assert "src/work.py" in staged, (
        "Regression: stage_student_files must keep working when optional "
        "Codex paths are absent. git add exits 128 on missing pathspecs "
        "and stages nothing; the implementation must pre-filter."
    )


def test_stage_student_files_honors_gitignore_for_codex_auth(tmp_git_repo):
    """auth.json must NEVER enter a capture commit (would leak OpenAI tokens).

    Task 5 adds .codex/auth.json to the real repo .gitignore; this test
    seeds its own synthetic gitignore so the test is self-contained and
    passes regardless of Task 5's state.
    """
    import subprocess
    (tmp_git_repo / ".codex").mkdir()
    (tmp_git_repo / ".codex" / "auth.json").write_text('{"token": "sk-secret"}')
    (tmp_git_repo / ".codex" / "config.toml").write_text('model = "gpt-5.4"\n')
    (tmp_git_repo / ".gitignore").write_text(".codex/auth.json\n")

    git_ops.stage_student_files(tmp_git_repo)

    staged = set(subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines())

    assert ".codex/auth.json" not in staged
    assert ".codex/config.toml" in staged


def test_commit_with_message_creates_commit(tmp_git_repo):
    (tmp_git_repo / "src" / "x.py").write_text("x = 1\n")
    git_ops.stage_student_files(tmp_git_repo)
    ok = git_ops.commit(tmp_git_repo, "test-run: sample\n\nsession_id: abc12345\n")
    assert ok is True
    result = subprocess.run(
        ["git", "log", "--oneline", "-1"],
        cwd=tmp_git_repo, capture_output=True, text=True, check=True,
    )
    assert "test-run: sample" in result.stdout


def test_commit_with_no_changes_still_commits_when_allow_empty(tmp_git_repo):
    ok = git_ops.commit(tmp_git_repo, "test-run: empty\n", allow_empty=True)
    assert ok is True


def test_is_in_merge_or_rebase_detects_merge(tmp_git_repo):
    assert git_ops.is_in_merge_or_rebase(tmp_git_repo) is False
    (tmp_git_repo / ".git" / "MERGE_HEAD").write_text("deadbeef\n")
    assert git_ops.is_in_merge_or_rebase(tmp_git_repo) is True


def test_diff_stats_since_head_reports_added_removed(tmp_git_repo):
    (tmp_git_repo / "src" / "a.py").write_text("line1\nline2\nline3\n")
    git_ops.stage_student_files(tmp_git_repo)
    stats = git_ops.diff_stats_staged(tmp_git_repo)
    assert stats.added >= 3
    assert stats.removed == 0
    assert "src/a.py" in stats.files
