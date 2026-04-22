# Forensics Guide: Reading Capture-Layer History

This guide helps an instructor interpret the `test-run:` commit trail that the
capture layer leaves inside a student's git repository. It is intended for
instructors only and lives in `docs/`, which is excluded from student
distribution by `create-assignment.sh`.

## 1. Purpose

The capture layer (`tests/_capture/`) records a structured commit every time
pytest runs in a student's repo. The combined history of those commits is a
behavioral trace: when the student worked, how much code changed between runs,
which tests flipped, how long runs took, and whether anything hung. That trace
is a *signal* for distinguishing student-written iteration from
AI-assisted wholesale delivery.

It is not proof. A student working from class slides can look like AI-assisted
delivery. A student asking an AI between test runs will leave no in-run
signal. Use this history in combination with code review, live checks
(quizzes, synchronous debugging sessions), and oral explanations. Treat
extreme anti-patterns as a prompt for closer inspection, not as a verdict.

## 2. The commit schema

Every capture commit has a single-line subject starting with `test-run:` and
a body of `key: value` lines. Field names below are exact and come from
`tests/_capture/metadata.py`:

- `session_id` -- random per-pytest-invocation identifier used to match orphan
  recovery commits to their original run.
- `timestamp` -- ISO 8601 UTC timestamp of when the commit message was
  assembled, which is within a few ms of session end.
- `status` -- see section 3.
- `tests_total` -- count of tests pytest collected this session.
- `tests_passed` -- count of tests that passed.
- `tests_failed` -- count of tests that failed (assertion or bundle check).
- `tests_error` -- count of tests that errored (exception outside assertion).
- `tests_skipped` -- count of tests skipped (usually gated bundles).
- `duration_seconds` -- wall-clock time between session start and finish,
  reported to 2 decimals.
- `bundles_passing` -- list of bundle numbers whose every test passed.
- `bundles_failing` -- list of bundle numbers with at least one non-passing
  test.
- `diff_added_lines` -- lines added in the staged `src/` and `tests/` diff
  compared to the previous capture commit.
- `diff_removed_lines` -- lines removed in that same diff.
- `files_changed` -- comma-separated list of files touched since the previous
  capture commit; capped at the first 10 plus an `(+N more)` suffix.
- `hostname_hash` -- first 16 hex chars of sha256(hostname + project_path);
  deterministic per machine per project, not recoverable to the raw hostname.
- `python_version` -- `sys.version.split()[0]`, e.g. `3.12.3`.
- `platform` -- `sys.platform`, e.g. `win32`, `linux`, `darwin`.
- `capture_version` -- version integer for the capture layer; bump this if the
  schema changes so old parsers fail loudly rather than silently mismatch.

## 3. Status values -- what each means

- `completed` -- pytest ran to completion. This is the normal state and says
  nothing about whether tests passed or failed, only that the session ran
  cleanly end-to-end.
- `pytest_exit_<N>` -- pytest exited with non-zero code N. Common values:
  - `pytest_exit_1` -- at least one test failed. Common during normal work.
  - `pytest_exit_2` -- user interrupt (Ctrl-C) or a fatal internal error.
  - `pytest_exit_5` -- no tests were collected. Often an import error or an
    empty bundle filter.
  - Other exit codes typically indicate abnormal termination, such as
    pytest-timeout killing the session on Windows (where Unix signal-based
    timeouts cannot nudge a single test).
- `hang_watchdog_killed` -- the session exceeded the hard deadline and the
  watchdog subprocess (see `tests/_capture/watchdog.py`) terminated it. This
  is an explicit signal that the student ran into something that froze.
- `orphaned_prior_run` -- this commit records a PRIOR session that never
  finished. The capture layer detected a leftover session marker on the next
  invocation and committed a placeholder. `duration_seconds` here is "time
  since the old marker was written" and may be huge. For example, if the
  student ran tests, closed the laptop, opened it 12 minutes later, and ran
  tests again, the orphan commit for the first run shows `duration=737.12`
  even though the original session only spent a second or two actually
  running pytest.

## 4. Reading a single run

Here is a plausible body for a single capture commit:

```text
test-run: 14/21 passed -- Bundles 1,2 complete

session_id: 2a9b7f1c
timestamp: 2026-04-17T23:14:06Z
status: completed
tests_total: 21
tests_passed: 14
tests_failed: 7
tests_error: 0
tests_skipped: 0
duration_seconds: 4.81
bundles_passing: [1, 2]
bundles_failing: [3]
diff_added_lines: 22
diff_removed_lines: 4
files_changed: src/router.py, src/packet.py
hostname_hash: 7b4c1e2d0a3f
python_version: 3.12.3
platform: win32
capture_version: 1
```

Read this as:

- Bundle 1 and Bundle 2 are fully passing; Bundle 3 has failures. The student
  has earned the bundle-completion credit up through the B tier if the grade
  map treats Bundle 2 as B.
- `tests_passed=14` with `tests_total=21` confirms that 7 tests remain,
  consistent with a full Bundle 3 (7 tests) still red.
- `diff_added_lines=22 diff_removed_lines=4` across two files says the
  student made a modest edit since the last run. This is the *staged* diff
  in `src/` and `tests/`, so it reflects real work rather than untracked
  scratch files.
- `files_changed` names `src/router.py` and `src/packet.py` -- two specific
  modules were touched, not a sweeping rewrite.
- `duration_seconds=4.81` is short, which is normal for a 21-test suite of
  pure-Python unit tests.

A single commit rarely tells you much on its own. The value is in the
sequence.

## 5. Reading the sequence -- cadence and scale

Pull the full trail with:

```bash
git log --grep="^test-run:" --format="%h %cI %s"
```

For each adjacent pair of capture commits, look at four numbers:

- **Time between runs** (wall clock, from `timestamp` or the committer
  date). Humans writing code typically run tests every few minutes while
  actively working, with long gaps between sessions. A trail with 40
  runs across 6 nights, clustered by hour, looks like normal study.
  A trail with 3 runs in 12 minutes the night before the deadline
  does not.
- **Diff size per run** (`diff_added_lines + diff_removed_lines`). Humans
  doing TDD-ish iteration produce small diffs (10-30 lines) between runs.
  A single run with 200+ added lines, preceded by a run with 0 passing
  tests, is worth a second look.
- **Pass/fail delta per run** (change in `tests_passed` from the prior
  commit). Humans flip tests in small batches, often one or two at a time,
  and sometimes flip a test *back* while refactoring. AI-generated code
  tends to land a whole bundle at once.
- **Session duration** (`duration_seconds`). For a unit-test suite this
  should be seconds. A run of tens of seconds implies the student is
  exercising heavier code paths; a `hang_watchdog_killed` commit implies
  a real freeze.

## 6. Patterns suggesting AI-assisted delivery

These are the stronger indicators. No single one is conclusive.

- A huge diff (more than about 100 lines) appearing between two capture
  commits with no intermediate runs, especially when `tests_passed` jumps
  correspondingly.
- A large block of tests flipping from failing to passing in a single
  run -- for example, a jump from `tests_passed=0` to `tests_passed=21`
  in one commit.
- A final "cleanup" run with `status=completed` that touches multiple
  files at once, after which nothing changes. This looks like a polish
  pass at the end of a paste.
- A single session that produces the full implementation with no prior
  exploratory `test-run:` activity on that branch.
- Multiple runs concentrated in a narrow time window close to the
  deadline, with long empty history before.
- `files_changed` that shows a wholesale rewrite of `src/*.py` rather
  than incremental edits to a small subset.
- The first `test-run:` commit in the history lands with most bundles
  already in `bundles_passing`, rather than starting with `[]` or `[1]`
  and growing bundle-by-bundle over time.

## 7. Patterns suggesting human iteration

Counterexamples. A trail dominated by these is consistent with a student
actually doing the work.

- Many small diffs, typically 10-30 added-plus-removed lines between
  runs.
- `tests_passed` advancing one or two at a time, often in the order
  that bundles are specified.
- Runs distributed across days, sometimes weeks, with cluster lengths
  that resemble a human study session (roughly 60-120 minutes of
  activity followed by a gap).
- Occasional `status=pytest_exit_1` runs showing work-in-progress
  breakage. A trail with only `completed` statuses and monotonically
  growing pass counts is actually less human than one with some
  regressions.
- `files_changed` that shows repeated edits to the same small set of
  files (say, `src/router.py` touched in 8 consecutive runs) before
  expanding to new files.
- Evidence of debugging: a test that flips pass -> fail -> pass across
  three runs as the student refactors.

## 8. Gotchas and false positives

- **Study pairs or group debugging sessions** can produce rapid delivery
  that looks AI-assisted. Students who meet with a TA or a study group
  and then knock out a bundle in 20 minutes will leave a similar
  pattern.
- **Copying from class slides** is legitimate but produces a large
  initial diff. If the first meaningful run has `diff_added=180` and the
  files match what the slides show, that is consistent with normal use
  of course materials.
- **Scaffolding removal** is common. A commit with `diff_added=24
  diff_removed=310` early in the history usually means the student
  deleted starter code they were not going to use. Not suspicious, just
  housekeeping.
- **Windows students produce fewer mid-hang forensic records.**
  pytest-timeout kills the whole session on Windows rather than
  interrupting a single test, so a student whose code hangs once will
  see one `pytest_exit_<N>` or `hang_watchdog_killed` commit instead of
  the multiple per-test failures a Unix student would see. See
  `docs/PROCESS_TRACKING.md` for the OS-level details.
- **`hostname_hash` changes** correctly identify "worked on laptop, then
  worked on lab machine." It is not a fingerprint, just a differentiator.
  Do not treat a change as a red flag.
- **Editor autosave triggering tests on every keystroke** is rare but
  happens with some IDE plugins. Look for an unusual cluster of runs
  with very short `duration_seconds` and near-zero diffs between them.
- **Direct pytest invocations vs. run_tests.py.** Every
  `python run_tests.py` produces exactly one capture commit, and so
  does each direct `pytest` run from an IDE test runner. The two usage
  modes differ in what deadline the watchdog uses (scaled by estimated
  test count for `run_tests.py`, fixed for direct pytest), but that is
  a usage signal, not a fraud signal.

## 9. Example investigation walk-through

A submission lands in your grading queue. Running
`git log --grep="^test-run:" --format="%h %cI %s"` shows three
capture commits, all within a 45-minute window on the night before
the deadline.

Fabricated example. The subject plus a few key body fields:

```text
c0ffee1 2026-04-20T22:31:02Z test-run: 0/21 passed
        diff_added_lines: 0
        diff_removed_lines: 0
        duration_seconds: 3.42
        files_changed: (none)

d00dfa1 2026-04-20T23:02:47Z test-run: 21/21 passed -- ALL BUNDLES COMPLETE
        diff_added_lines: 247
        diff_removed_lines: 8
        duration_seconds: 6.10
        files_changed: src/router.py, src/packet.py, src/table.py,
                       src/link.py, tests/test_router.py

f1a5c0d 2026-04-20T23:15:55Z test-run: 21/21 passed -- ALL BUNDLES COMPLETE
        diff_added_lines: 0
        diff_removed_lines: 0
        duration_seconds: 5.84
        files_changed: (none)
```

Walking through:

- **Commit `c0ffee1`** is a baseline. Zero diff, zero passing tests,
  short duration. This looks like the student cloning the template
  and running tests to confirm the harness works. Normal.
- **Commit `d00dfa1`** lands 31 minutes later. `diff_added=247` across
  five files, and the pass count jumps from 0 to 21 -- every bundle
  complete. The 247-line diff spans four `src/` modules and a test
  file in a single step. This is the pattern flagged in section 6.
- **Commit `f1a5c0d`** lands 13 minutes after that. Zero diff, tests
  still at 21/21. This is the "re-run to confirm" pattern and is
  consistent with either human verification or an AI-pasted solution
  the student is double-checking.

What to do next: do not declare a verdict from the trail alone. Ask
the student to explain one of the `src/*.py` modules in an oral
followup, or request a live walkthrough of a small change. Compare
their code to the solution in `solution/` for structural similarity
patterns. Combine the capture trail with that second data source
before making any determination.

## 10. Limitations

Honest accounting of what this tool cannot tell you:

- **The capture layer does not see what happens between test runs.**
  A student can ask an AI, paste the result, and run tests once. The
  capture shows exactly one large diff landing with a lot of passing
  tests. That matches the pattern in section 6, but so does a
  legitimate paste from slides. You cannot distinguish the two from
  the trail alone.
- **Short hangs (under the session deadline) are not called out
  specifically.** They surface as a higher `duration_seconds` than
  usual, but there is no dedicated status for them.
- **Students can avoid capture by not running tests at all.** That
  costs them feedback on their grade, but it also erases the
  forensic signal. A submission with zero `test-run:` commits tells
  you nothing except that the student did not use the harness.
- **Shared machines produce matching `hostname_hash`.** Two students
  using the same lab computer will have identical hashes. Useful for
  noticing pair activity, but also a potential false pair-programming
  signal.
- **OS-level variance** means pytest-timeout behavior differs on
  Windows vs. Unix. A Windows student produces fewer mid-hang
  forensic records than a Unix student with the same bug.
- **The capture layer is tamper-evident** via the integrity audit
  (`tools/INTEGRITY_HASHES.txt`), but the cadence signal gets diluted
  if a student also commits frequently via normal `git add` between
  test runs. Those commits interleave with `test-run:` commits and
  the gaps between capture commits no longer reflect real iteration
  time. Filter with `--grep="^test-run:"` to see only the capture
  trail, but keep in mind the interleaved commits still affect what
  "between runs" means.

## 11. Workflow suggestions

Practical ways to use this in grading.

- **Scriptable probe.** Run
  `git log --grep="^test-run:" --format="%h %cI %s"` in a student's
  repo to get a timestamped table of their test runs. Eyeballing
  this is enough to spot extreme patterns.
- **Spot-check bodies.** For a suspicious submission, dump the
  bodies with
  `git log --grep="^test-run:" --format="%H%n%B%n---"` and grep for
  `diff_added_lines` or `tests_passed` to pull out the numbers you
  care about. Pipe to a quick script if you want a CSV.
- **Trust but verify.** When grading 50 submissions, sort by the
  extreme anti-patterns in section 6 and prioritize the two or
  three outliers for manual review. Do not accuse the other 47 of
  anything; their trails tell you nothing suspicious.
- **Optional lab-machine lookup.** If you want to flag work done
  entirely off-campus, keep a small lookup of the `hostname_hash`
  values of known lab machines. Compute the hash of a lab machine
  by running the capture code against a throwaway project path, or
  note which hashes show up repeatedly across many students (those
  are almost certainly the shared lab machines). This is optional
  and mostly useful if off-campus work is itself a course-policy
  concern.
- **Combine with the rest of your rubric.** The capture trail is
  one input. Code style review, oral followups, and direct
  comparison to the reference solution each provide independent
  signals. A conclusion drawn from any single source is weaker than
  one drawn from the intersection.
