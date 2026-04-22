#!/usr/bin/env python3
"""Show your commits without the automatic test-run entries.

The capture layer records a commit on every test run (see PROCESS_TRACKING.md).
Those entries are intentionally visible in the raw `git log`, but when you're
looking for *your* commits (to find a past fix, review your own progress, etc.)
the automatic entries add noise. This wrapper filters them out.

Usage:
    python tools/my_commits.py              # all your commits, most recent first
    python tools/my_commits.py -10          # last 10
    python tools/my_commits.py --since=1.week
    python tools/my_commits.py --author=you@example.com

Any argument you pass is forwarded to `git log`. The filter is:
    git log --oneline --invert-grep --grep='^test-run:' <your args>

If you prefer typing the raw command, the one-liner above works in any shell
with no Python needed.
"""
import subprocess
import sys


def main() -> int:
    cmd = [
        "git", "log", "--oneline",
        "--invert-grep", "--grep=^test-run:",
        *sys.argv[1:],
    ]
    try:
        result = subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print("git is not on PATH. Install Git and retry.", file=sys.stderr)
        return 127
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
