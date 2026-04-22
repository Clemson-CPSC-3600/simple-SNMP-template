# Process Tracking in This Assignment

This project automatically records a snapshot of your code every time you run the tests. These snapshots are committed to your assignment's git repository and pushed to the configured remote.

## What is captured

Files under `src/`, `tests/`, and `.codex-transcripts/` are staged into the commit, along with the shipped guardrail files (`AGENTS.md`, `.codex/config.toml`, `AI_POLICY.md`). The commit message carries this metadata:

- A timestamp and session ID
- Test pass/fail counts and duration
- How many lines were added or removed since the previous run
- Your Python version and OS type
- A one-way hash of your machine's hostname (the instructor cannot recover your hostname from the hash; it is only used to tell apart your home laptop from a lab machine in a pattern-of-use sense)

Codex transcripts (`.codex-transcripts/*.jsonl`) are also captured when present. See [AI_POLICY.md](AI_POLICY.md) for the full Codex policy.

**Nothing outside the project directory is captured. No credentials, no browsing history, no system information.**

## What is NOT captured

- Files outside the allowlist above
- Your hostname (only a hash)
- Keystrokes, timing within a session, cursor position, or anything your editor sees
- AI assistant interactions from tools **other than Codex** (Claude Code, ChatGPT web, Copilot Chat, etc.). See [AI_POLICY.md](AI_POLICY.md) for the Codex policy — Codex transcripts ARE captured under `.codex-transcripts/`.
- Your Codex OpenAI token (`.codex/auth.json` is gitignored).

## Why this exists

Your learning matters more than your final grade. A passing submission tells us you delivered working code. A development history tells us *you* wrote it — by showing how your understanding evolved, where you got stuck, which tests flipped from failing to passing as you learned. This is the process your instructor wants to see.

## You can verify exactly what is committed

Before running tests, run:

```bash
git log --oneline -20
```

After running tests, run it again. You'll see a new commit whose message begins with `test-run:`. Run `git show <commit>` to see exactly what was captured.

## Filtering test-run commits out of your log

The automatic commits are intentionally visible — that's the honesty part. But when you want to see just *your* commits (for finding a past fix, or a cleaner history view), use:

```
python tools/my_commits.py
```

Works on Windows (PowerShell, cmd, Git Bash), macOS, and Linux — no shell-specific invocation needed. It accepts any `git log` flags (e.g. `-10`, `--since=1.week`). The equivalent raw command if you prefer to type it directly:

```
git log --oneline --invert-grep --grep='^test-run:'
```

## If the push fails

The commit always happens locally, even if your machine is offline or your credentials aren't set up. The next successful push will carry all backlogged commits. Warnings are written to `.test-runs.log` in the project root.

If your student repo has no remote configured yet, or your credentials aren't set up, run:

```bash
python tools/setup_credentials.py
```

It will diagnose the most common first-time push problems (no remote, no credential helper, rejected PAT) and print step-by-step fix instructions for your platform.

## What you'll see when a test hangs

If one of your tests blocks indefinitely (most commonly a socket waiting for a connection that never arrives), two things can kill it:

- **Per-test timeout** — the default is 30 seconds per test; a test can override with `@pytest.mark.timeout(N)`. When this fires, the test is marked failed and **on Windows the entire pytest process exits** (this is a quirk of pytest-timeout's thread method, which is the only mechanism that works on Windows). On macOS/Linux with the signal method, only that one test dies and the suite continues.
- **Session watchdog** — a background subprocess that terminates the whole test session if it runs past `max(120s, 3 × n_tests × 30s)`. This is a safety net for the case where pytest itself hangs or a per-test timeout can't interrupt the blocked code path.

Both routes still produce a `test-run:` commit. A per-test timeout records `status: pytest_exit_<code>` (usually `pytest_exit_1`) or `status: completed` depending on which layer saw the exit first; a watchdog kill records `status: hang_watchdog_killed`. Either way the run is visible in your git history; you don't need to do anything special.

## Academic integrity note

Tampering with the capture layer (deleting `tests/conftest.py`, editing `tests/_capture/`, rewriting history to remove capture commits) is treated the same as any other academic integrity violation and is easy to detect. If you have a legitimate reason to disable capture on a specific machine (for example, a machine where git push authentication cannot be set up), contact your instructor rather than removing the hook.
