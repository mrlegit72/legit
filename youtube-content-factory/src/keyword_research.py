"""Live YouTube keyword research via the Data API v3.

Uses an API key (not OAuth) — read-only. Two calls per query:
  1. search.list  → top N video IDs for the query (cost: 100 units)
  2. videos.list  → views/likes for those IDs        (cost: 1 unit)

Returns a structured KeywordReport that the SEO and script generators
fold into their prompt context, so titles and descriptions reflect what's
actually winning right now instead of what Claude saw at training time.

Set YOUTUBE_API_KEY in .env to enable. Without it, this module is skipped.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from googleapiclient.discovery import build
from pydantic import BaseModel, Field

log = logging.getLogger("yt_factory.keywords")


class TopVideo(BaseModel):
    video_id: str
    title: str
    channel_title: str
    published_at: str
    view_count: int = Field(default=0)
    like_count: int = Field(default=0)


class KeywordReport(BaseModel):
    query: str
    region_code: str
    top_videos: List[TopVideo]
    median_views: int
    high_view_threshold: int = Field(
        description="Views above this are 'breakout' for this niche."
    )

    def to_prompt_context(self) -> str:
        """Render as a readable block for the SEO/script Claude prompt."""
        lines = [
            f"LIVE YOUTUBE DATA for query: {self.query!r} ({self.region_code})",
            f"Median views (top 10): {self.median_views:,}",
            f"Breakout threshold: {self.high_view_threshold:,}+ views",
            "",
            "Top performing titles:",
        ]
        for v in self.top_videos[:10]:
            lines.append(
                f"  - [{v.view_count:>10,} views] {v.title}  ({v.channel_title})"
            )
        return "\n".join(lines)


class KeywordResearch:
    def __init__(self, api_key: str):
        self._service = build("youtube", "v3", developerKey=api_key)

    def research(
        self,
        query: str,
        region_code: str = "US",
        max_results: int = 15,
        published_after_iso: Optional[str] = None,
    ) -> KeywordReport:
        log.info("Researching keyword %r (region=%s)", query, region_code)
        search_kwargs = {
            "q": query,
            "part": "snippet",
            "type": "video",
            "regionCode": region_code,
            "maxResults": max_results,
            "order": "relevance",
        }
        if published_after_iso:
            search_kwargs["publishedAfter"] = published_after_iso

        search_resp = self._service.search().list(**search_kwargs).execute()
        items = search_resp.get("items", [])
        if not items:
            log.warning("No results for %r", query)
            return KeywordReport(
                query=query,
                region_code=region_code,
                top_videos=[],
                median_views=0,
                high_view_threshold=0,
            )

        ids = [it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId")]
        stats_resp = self._service.videos().list(
            id=",".join(ids), part="statistics,snippet"
        ).execute()

        videos: List[TopVideo] = []
        for v in stats_resp.get("items", []):
            stats = v.get("statistics", {})
            snippet = v.get("snippet", {})
            videos.append(TopVideo(
                video_id=v["id"],
                title=snippet.get("title", ""),
                channel_title=snippet.get("channelTitle", ""),
                published_at=snippet.get("publishedAt", ""),
                view_count=int(stats.get("viewCount", 0)),
                like_count=int(stats.get("likeCount", 0)),
            ))

        videos.sort(key=lambda v: v.view_count, reverse=True)
        view_counts = [v.view_count for v in videos] or [0]
        median = sorted(view_counts)[len(view_counts) // 2]
        # "Breakout" = top quartile of the sample.
        breakout = sorted(view_counts)[max(0, int(len(view_counts) * 0.75) - 1)]

        return KeywordReport(
            query=query,
            region_code=region_code,
            top_videos=videos,
            median_views=median,
            high_view_threshold=breakout,
        )
