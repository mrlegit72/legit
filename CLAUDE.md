# Claude session context

This repo is two things at once:

1. **mrlegit.online** — a static copywriter portfolio site (`index.html`,
   served via GitHub Pages, CNAME points to `mrlegit.online`).
2. **A daily content engine** — see `content-agent/`. The owner uses
   claude.ai/code each morning to draft one long-form piece in their voice.

## When a session starts here

If the user doesn't say what they're working on, default to assuming they're
running the morning content ritual. Greet briefly and suggest:

> Morning. Run `/draft-today` to see today's 3 topic options.

Available commands (defined in `.claude/commands/`):

- `/draft-today` — propose 3 angles, draft the one the user picks, save to
  `content-agent/drafts/YYYY-MM-DD-slug.md`
- `/publish [filename]` — move an approved draft to `content-agent/published/`,
  commit, and print clean copy-paste-ready text

## Hard rules

- **Never modify `topics.md` automatically.** The user owns the topic queue.
  Suggest edits in chat; don't apply them.
- **Never auto-post to X, LinkedIn, or any external platform.** The publish
  flow is copy-paste only in v1.
- **Never invent voice.** If `content-agent/voice/` has no real samples yet,
  refuse to draft and tell the user to add at least one.
- **Never push to remote.** The user pushes manually.
- **Respect the style guide** in `content-agent/style-guide.md` — every
  forbidden pattern there is a hard fail.

## The portfolio site

`index.html`, `CNAME`, and `.github/workflows/jekyll-docker.yml` are the
portfolio site. Don't touch these unless the user explicitly asks about the
portfolio. Changes there go live on `mrlegit.online`.

## Other branches you may see

The remote has several `claude/*` branches with half-built side projects
(OSINT trader, financial advisor, YouTube content factory, etc.). These are
parked. **Do not start work in those branches** unless the user explicitly
names one. The current focus is one thing: the daily content engine.
