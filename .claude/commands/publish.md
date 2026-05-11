---
description: Move a draft from content-agent/drafts/ to content-agent/published/ and print it ready for copy-paste
argument-hint: [draft-filename] (optional — defaults to today's draft)
---

You are the publisher. Job: move an approved draft from `drafts/` to
`published/` and hand the user clean text to paste to X / LinkedIn / wherever.

## Step 1: Resolve which draft

If the user passed a filename argument, use that.

If no argument was passed, list files in `content-agent/drafts/`. If there is
exactly one, use it. If there are zero, tell the user: "No drafts to publish.
Run `/draft-today` first." If there are multiple, list them with numbers and
ask the user to pick.

## Step 2: Move and rename

- Source: `content-agent/drafts/<filename>`
- Destination: `content-agent/published/<filename>`
- Use `git mv` (via Bash) so history is preserved. Do not `cp + rm`.

## Step 3: Commit

Run `git add -A && git commit -m "publish: <slug from filename>"`. Use the slug
portion of the filename (everything after the date) as the commit subject. Keep
the commit subject under 70 chars.

Do NOT push. The user pushes manually when they want to (some pieces may stay
local).

## Step 4: Print the clean copy

Print the published text inside a fenced code block so the user can one-tap
copy on mobile. Above the block, print:

```
✅ Moved to published/<filename> and committed.

Copy below and paste to your platform. When pasted, run `/publish` again with
the platform name to log where it went (optional):
```

After the code block, print:

```
Optional: log the publish target by editing the file and adding a frontmatter
line like `platforms: [x, linkedin]` — or just leave it. Mood.
```

## What NOT to do

- Do not push to remote (user controls when things go public)
- Do not auto-post to X / LinkedIn / anywhere — copy-paste only, v1
- Do not edit the draft text during the move — publish what was approved
- Do not delete from `drafts/` without moving (use `git mv`, not `rm`)
