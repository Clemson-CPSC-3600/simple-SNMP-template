"""
Pytest session hooks for development trace capture.

DO NOT MODIFY. This file's contents are hashed in tools/INTEGRITY_HASHES.txt
and verified by the CI integrity workflow.

If capture is misbehaving, contact your instructor rather than editing this file.
"""
from pathlib import Path

from tests._capture import capture

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SESSION_CTX = None
_BUNDLE_BY_NODEID: dict = {}


def pytest_sessionstart(session):
    """Fire once at the start of every pytest session.

    If an outer wrapper (run_tests.py) already started a capture session
    and exported its id + start time via env vars, reuse them so
    session_finish dedupe can collapse outer and inner commits.
    """
    import os
    global _SESSION_CTX
    sid = os.environ.get("CAPTURE_SESSION_ID")
    started_at_raw = os.environ.get("CAPTURE_STARTED_AT")
    try:
        started_at = float(started_at_raw) if started_at_raw else None
    except ValueError:
        started_at = None
    _SESSION_CTX = capture.session_start(
        _PROJECT_ROOT, per_test_timeout=30.0, estimated_tests=10,
        session_id=sid, started_at=started_at,
    )


def pytest_collection_modifyitems(config, items):
    """Index each item's bundle marker by nodeid for later lookup.

    Also re-scales the session hard deadline now that we know the real test
    count. If the watchdog was already spawned with an estimated deadline,
    the real count may be larger or smaller — we leave the watchdog's
    deadline alone (accepting some imprecision) since respawning it would
    race with the existing subprocess.
    """
    _BUNDLE_BY_NODEID.clear()
    for item in items:
        for mark in item.iter_markers(name="bundle"):
            if mark.args:
                _BUNDLE_BY_NODEID[item.nodeid] = mark.args[0]
                break


def pytest_sessionfinish(session, exitstatus):
    """Fire once at the end of every pytest session. Count and commit here."""
    if _SESSION_CTX is None:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        for outcome in ("passed", "failed", "error", "skipped"):
            for rep in reporter.stats.get(outcome, []):
                nodeid = getattr(rep, "nodeid", "") or ""
                bundle = _BUNDLE_BY_NODEID.get(nodeid, 1)
                _SESSION_CTX.record_test(outcome=outcome, bundle=bundle)
    capture.session_finish(_PROJECT_ROOT, _SESSION_CTX, status="completed")
