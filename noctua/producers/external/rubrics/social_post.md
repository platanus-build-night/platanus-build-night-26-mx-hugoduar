You are drafting a social media post.

Inputs:
- `goal` (required): the topic / idea to post about. Can include voice/tone hints.
- `inputs.platforms` (optional): a list like ["LINKEDIN", "TWITTER"]. Default: all connected.

For each chosen, connected platform, emit one `kind: "tool"` step using the
platform's composio action (e.g. `composio:LINKEDIN.LINKEDIN_CREATE_POST`).
The `payload.args` must match the action's input schema. For text-only posts,
`{"text": "<the post body>"}` is enough.

If you want to vary the wording per platform (Twitter's 280-char limit, LinkedIn's
formal voice), emit an `kind: "edit"` step first that asks Claude to draft the
per-platform versions, then reference its result in the tool steps.

Plan length: 1–4 steps. Always end after the last tool step — no validation step
needed; the action returning successful is the validation.
