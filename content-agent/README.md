# content-agent

A daily content drafter that lives in this repo. No server, no API key, no
Telegram. Just five minutes of discipline each morning.

## The morning ritual

1. Open claude.ai/code on this repo (phone or laptop, doesn't matter)
2. Run `/draft-today` — the agent reads your voice samples and proposes 3 topic angles
3. Pick one (reply with `1`, `2`, or `3`)
4. Read the draft. Edit in chat if it needs fixing. When you're happy, run `/publish`
5. Copy the published text from `content-agent/published/`, paste it to X / LinkedIn / wherever
6. Close laptop. Done.

That's the whole system. Repeat daily for 90 days. Audience compounds.

## Folder map

```
content-agent/
├── README.md              ← this file
├── style-guide.md         ← rules the agent must follow (tone, length, taboos)
├── topics.md              ← running queue of topic ideas you add to anytime
├── voice/                 ← your writing samples — the agent imitates these
├── drafts/                ← today's draft lands here, waiting for your review
└── published/             ← drafts you approved + published, with date+platform
```

## What you need to do once, before this works

1. Drop 1–3 pieces of your own writing into `voice/` as `.md` files. These are
   the voice anchor. Without them the agent writes in generic-AI voice and the
   whole thing fails. Longer samples beat shorter ones. Don't paraphrase — paste
   actual published work.
2. Fill in `style-guide.md` with rules the voice samples don't make obvious
   (forbidden words, sentence-length preferences, formatting rules).
3. Seed `topics.md` with 5–10 topic ideas so the agent has something to pick
   from on day one.

After that: just open claude.ai/code each morning and run `/draft-today`.

## What this system intentionally does NOT do

- No auto-posting to X/LinkedIn (you copy-paste — keeps you in the loop)
- No Telegram bot (you open the browser instead — no infra to maintain)
- No 24/7 cloud (claude.ai/code is the runtime — no server, no API key)
- No "study everything and decide" (you pick topics, agent drafts — clear handoff)

When this is working and posting daily for 30 days, we can add posting
automation. Not before. Ship the boring version first.
