from tests._capture import metadata


def test_hostname_hash_is_deterministic_and_16_chars():
    h1 = metadata.hostname_hash("/some/project")
    h2 = metadata.hostname_hash("/some/project")
    assert h1 == h2
    assert len(h1) == 16
    assert all(c in "0123456789abcdef" for c in h1)


def test_hostname_hash_varies_by_project_path():
    h1 = metadata.hostname_hash("/project/a")
    h2 = metadata.hostname_hash("/project/b")
    assert h1 != h2


def test_format_commit_message_includes_all_fields():
    result = metadata.TestResult(
        total=15, passed=12, failed=3, error=0, skipped=0,
        duration_seconds=23.4,
        bundles_passing=[1], bundles_failing=[2, 3],
    )
    msg = metadata.format_commit_message(
        session_id="abc12345",
        status="completed",
        result=result,
        diff_added=47, diff_removed=12,
        files_changed=["src/a.py"],
        hostname_hash="deadbeef0000",
    )
    assert msg.startswith("test-run:")
    assert "12/15 passed" in msg
    assert "session_id: abc12345" in msg
    assert "status: completed" in msg
    assert "tests_passed: 12" in msg
    assert "bundles_passing: [1]" in msg
    assert "hostname_hash: deadbeef0000" in msg


def test_format_commit_message_hang_status_has_warning_summary():
    result = metadata.TestResult(
        total=0, passed=0, failed=0, error=0, skipped=0,
        duration_seconds=180.0,
        bundles_passing=[], bundles_failing=[],
    )
    msg = metadata.format_commit_message(
        session_id="abc12345", status="hang_watchdog_killed",
        result=result, diff_added=0, diff_removed=0, files_changed=[],
        hostname_hash="deadbeef0000",
    )
    assert "SESSION HUNG" in msg
    assert "killed by watchdog" in msg
    assert "--" in msg  # ASCII separator, not em-dash
