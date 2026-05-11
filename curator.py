"""
Zero-Cost Autonomous Curation Agent for X
=========================================

Workflow:
    Strategist  -> feedparser scans Google News RSS for trending/breaking stories
    Researcher  -> selects top-N most recent unseen articles
    Editor      -> LangChain + Claude turns each into a minimalist X post
    Database    -> SQLite stores posted titles for dedup
    Connector   -> tweepy publishes to X (Free Tier v2)

Run as a single script. All credentials come from environment variables
(loaded from .env locally, or from GitHub Actions secrets in CI).
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import feedparser
import tweepy
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("curator")

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
)
DB_PATH = Path(os.getenv("CURATOR_DB_PATH", "curator_state.sqlite3"))
MAX_POSTS_PER_RUN = int(os.getenv("CURATOR_MAX_POSTS", "3"))
X_CHAR_LIMIT = 280
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
DRY_RUN = os.getenv("CURATOR_DRY_RUN", "false").lower() in {"1", "true", "yes"}


# --------------------------------------------------------------------------- #
# Database (deduplication)
# --------------------------------------------------------------------------- #


def init_db(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posted (
            title_hash TEXT PRIMARY KEY,
            title      TEXT NOT NULL,
            posted_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    return conn


def _hash(title: str) -> str:
    return hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()


def already_posted(conn: sqlite3.Connection, title: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM posted WHERE title_hash = ?", (_hash(title),)
    )
    return cur.fetchone() is not None


def mark_posted(conn: sqlite3.Connection, title: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO posted (title_hash, title) VALUES (?, ?)",
        (_hash(title), title),
    )
    conn.commit()


# --------------------------------------------------------------------------- #
# Strategist + Researcher
# --------------------------------------------------------------------------- #


@dataclass
class Article:
    title: str
    summary: str
    link: str


def fetch_trending(limit: int = 10) -> list[Article]:
    log.info("Fetching Google News RSS")
    feed = feedparser.parse(GOOGLE_NEWS_RSS)
    if feed.bozo:
        log.warning("Feed parse warning: %s", feed.bozo_exception)
    articles: list[Article] = []
    for entry in feed.entries[:limit]:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        articles.append(
            Article(
                title=title,
                summary=(entry.get("summary") or "").strip(),
                link=(entry.get("link") or "").strip(),
            )
        )
    log.info("Pulled %d articles from feed", len(articles))
    return articles


def select_fresh(
    conn: sqlite3.Connection, articles: Iterable[Article], n: int
) -> list[Article]:
    fresh: list[Article] = []
    for art in articles:
        if already_posted(conn, art.title):
            continue
        fresh.append(art)
        if len(fresh) >= n:
            break
    log.info("Selected %d fresh articles", len(fresh))
    return fresh


# --------------------------------------------------------------------------- #
# Editor (Claude via LangChain)
# --------------------------------------------------------------------------- #

EDITOR_SYSTEM = (
    "You are a minimalist editor for an X (Twitter) account. "
    "You convert news into ultra-clean posts that read like a calm signal."
)

EDITOR_USER = """Turn the following news item into a single X post.

Hard rules:
- 3 sentences MAX. Short sentences are better.
- High white space: insert a blank line between sentences.
- 100% value. No filler, no opinion words like "amazing" or "huge".
- No hashtags. No emojis. No @mentions. No links.
- Under {char_limit} characters total, including the blank lines.
- Do not wrap the output in quotes or markdown. Output ONLY the post text.

News title: {title}
News summary: {summary}
"""


def build_editor():
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    prompt = ChatPromptTemplate.from_messages(
        [("system", EDITOR_SYSTEM), ("user", EDITOR_USER)]
    )
    model = ChatAnthropic(model=CLAUDE_MODEL, temperature=0.4, max_tokens=400)
    return prompt | model | StrOutputParser()


def compose_post(chain, article: Article) -> str:
    raw = chain.invoke(
        {
            "title": article.title,
            "summary": article.summary or article.title,
            "char_limit": X_CHAR_LIMIT,
        }
    ).strip()
    # Strip accidental wrapping quotes/backticks from the model.
    for ch in ('"', "'", "`"):
        if raw.startswith(ch) and raw.endswith(ch):
            raw = raw[1:-1].strip()
    if len(raw) > X_CHAR_LIMIT:
        raw = raw[: X_CHAR_LIMIT - 1].rstrip()
    return raw


# --------------------------------------------------------------------------- #
# Connector (X / Twitter)
# --------------------------------------------------------------------------- #


def build_x_client() -> tweepy.Client:
    required = [
        "X_API_KEY",
        "X_API_SECRET",
        "X_ACCESS_TOKEN",
        "X_ACCESS_TOKEN_SECRET",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing X credentials: {', '.join(missing)}")
    return tweepy.Client(
        consumer_key=os.getenv("X_API_KEY"),
        consumer_secret=os.getenv("X_API_SECRET"),
        access_token=os.getenv("X_ACCESS_TOKEN"),
        access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET"),
        bearer_token=os.getenv("X_BEARER_TOKEN"),  # optional
    )


def publish(client: tweepy.Client, text: str) -> str | None:
    if DRY_RUN:
        log.info("DRY_RUN -> would post:\n%s", text)
        return "dry-run"
    resp = client.create_tweet(text=text)
    tweet_id = resp.data.get("id") if resp and resp.data else None
    log.info("Posted tweet id=%s", tweet_id)
    return tweet_id


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def run() -> int:
    conn = init_db()
    articles = fetch_trending(limit=20)
    if not articles:
        log.warning("No articles returned from feed; exiting")
        return 0

    fresh = select_fresh(conn, articles, n=MAX_POSTS_PER_RUN)
    if not fresh:
        log.info("Nothing new to post")
        return 0

    editor = build_editor()
    client = None if DRY_RUN else build_x_client()

    posted = 0
    for art in fresh:
        try:
            text = compose_post(editor, art)
            log.info("Composed (%d chars) for: %s", len(text), art.title)
            publish(client, text)
            mark_posted(conn, art.title)
            posted += 1
            time.sleep(2)  # gentle pacing between posts
        except tweepy.TweepyException as exc:
            log.error("X API error for %r: %s", art.title, exc)
        except Exception as exc:  # noqa: BLE001
            log.exception("Failed on %r: %s", art.title, exc)

    log.info("Run complete. Posted %d / %d", posted, len(fresh))
    return 0


if __name__ == "__main__":
    sys.exit(run())
