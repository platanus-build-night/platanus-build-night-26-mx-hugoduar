# PR Producer Rubric

A "good" PR from Noctua:
- Closes the linked issue (or the cited Sentry error). When the mission's `issue_url` is empty, treat the goal text itself as the spec — it includes the error title, culprit file, and a permalink for context.
- Adds tests for the new behavior.
- All tests pass in the sandbox.
- Commit message is a single imperative sentence.
- PR body has: what changed, why, and a "Noctua report" footer.

Sentry-triggered missions specifically:
- Inspect the culprit file mentioned in the goal first.
- Reproduce the failure in a test before fixing.
- The fix should be minimal — defensive checks at the actual call site, not blanket try/except.
