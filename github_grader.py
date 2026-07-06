#!/usr/bin/env python3
"""GitHub Classroom per-bundle grader.

Invoked by `.github/classroom/autograding.json` as `python github_grader.py N`
for N in {1, 2, 3}. Exits 0 if all tests in bundles 1..N pass (specification
grading: a bundle's credit requires every lower bundle complete), 1 otherwise.

Score source of truth: `run_tests.BundleTestRunner.compute_bundle_status` --
the same function that drives the local `python run_tests.py` display, so
the Classroom score cannot disagree with what students see locally.

Two paths to that data:
  1. Cache hit -- the workflow's `python run_tests.py` step (which runs once
     per push) wrote `.test-run-state/last_bundle_status.json`. We read it.
  2. Cache miss -- run pytest ourselves via the shared runner. Used as a
     fallback if the upstream step crashed or was removed.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from run_tests import BundleTestRunner  # noqa: E402  (after sys.path tweak)

# Outside CI we don't trust the cache: a student tinkering with their code
# between runs would otherwise see a stale verdict. CI does one run per
# checkout, so the cache is always fresh there.
TRUST_CACHE = os.environ.get("GITHUB_ACTIONS") == "true"


def load_status():
    cache_path = ROOT / BundleTestRunner.STATUS_CACHE_RELATIVE
    if TRUST_CACHE and cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            data["bundles"] = {int(k): v for k, v in data["bundles"].items()}
            return data
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            pass

    runner = BundleTestRunner()
    if TRUST_CACHE:
        # Classroom50 shows stdout/stderr from this script inside a compact
        # failure detail box. The underlying runner prints every selected
        # pytest nodeid on a cache miss, which drowns out the useful verdict.
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()):
                _exit_code, bundles_data = runner.run_tests_standard()
    else:
        _exit_code, bundles_data = runner.run_tests_standard()
    status = runner.compute_bundle_status(bundles_data)
    runner.write_status_cache(status)
    return status


def main(bundle_number: int) -> int:
    status = load_status()
    bundles = status["bundles"]
    grade = status["grade"]

    print(f"Checking Bundle {bundle_number}")
    print("-" * 40)

    info = bundles.get(bundle_number, {})
    if info:
        print(
            f"Bundle {bundle_number}: "
            f"{info.get('passed', 0)}/{info.get('total', 0)} tests passed"
        )
    else:
        print(f"Bundle {bundle_number}: Status unknown")
    print(f"Overall Grade: {grade}")
    print("-" * 40)

    # Specification grading: bundle N is only awarded when 1..N all complete.
    for required in range(1, bundle_number + 1):
        if not bundles.get(required, {}).get("complete", False):
            if required != bundle_number:
                print(
                    f"FAIL: Bundle {bundle_number} requires Bundle {required}"
                )
            else:
                print(f"FAIL: Bundle {bundle_number}")
            return 1

    print(f"PASS: Bundle {bundle_number}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python github_grader.py <bundle_number>")
        sys.exit(1)
    try:
        bundle = int(sys.argv[1])
    except ValueError:
        print("Error: Bundle number must be an integer")
        sys.exit(1)
    if bundle not in (1, 2, 3):
        print(f"Error: Bundle must be 1, 2, or 3 (got {bundle})")
        sys.exit(1)
    sys.exit(main(bundle))
