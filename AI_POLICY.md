# AI Assistance Policy for This Assignment

This course provides access to Codex (OpenAI's coding assistant) through
Clemson's site license. You are encouraged to use it as a tutor. You are
**not** encouraged to use it as a ghostwriter.

## What is captured

Every transcript of every Codex session you start inside this repository is
saved to `.codex-transcripts/` and committed to your assignment's git
repository alongside your code, on the next `python run_tests.py`. Your
instructor can read these transcripts.

**This is captured:**
- The prompt you typed to Codex.
- The reasoning and reply Codex produced.
- Any shell commands Codex ran on your behalf.
- Any file edits Codex proposed or made.

**This is NOT captured:**
- Your OpenAI API token (`.codex/auth.json` is gitignored).
- Codex sessions you run in directories outside this assignment.
- Codex sessions you run in other tools (ChatGPT web, Copilot Chat, etc.).
  If you want to use those for this course, you must paste the transcripts
  into a file under `.codex-transcripts/` yourself so your work is
  auditable.

## What Codex is configured to do here

The file `AGENTS.md` at the root of this repo tells Codex to act as a
Socratic tutor. It will generally ask you questions and give hints rather
than writing complete solutions. You can override this by insisting, but
the instructor can see that you did (the transcript records your prompt).

## What counts as academic honesty

| You do this... | ...and it's: |
|---|---|
| Ask Codex to explain a concept you just learned | fine |
| Ask Codex to review your code for bugs | fine |
| Ask Codex for a hint on where you're stuck | fine |
| Ask Codex to generate a function, then type it over verbatim | violation |
| Ask Codex to do the assignment, then edit lightly | violation |
| Use Codex outside this repo and not save the transcript | violation |
| Delete a transcript from `.codex-transcripts/` before submission | violation |

If you're uncertain whether a use is allowed, ask your instructor before
submitting — not after.

## Verifying what was captured

```bash
git log --oneline --all -- .codex-transcripts/
# Show any specific commit:
git show <commit-sha> -- .codex-transcripts/
```

## If Codex is down or you prefer not to use it

You are never required to use Codex. This policy only covers what happens
**if** you use it.
