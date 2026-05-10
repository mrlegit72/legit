"""Pull recent video performance from YouTube Analytics → feed back into SEO.

Flow:
  1. `pipeline analytics-pull` runs the YouTube Analytics API for the last
     N days, scoped to the authenticated channel, and writes
     `output/analytics/report.json` with per-video views / CTR / AVD.
  2. The next `script` and `seo` runs auto-load that file and inject a
     "what's working / what's not" block into the Claude system prompt,
     so generated titles and angles are conditioned on real performance.

The OAuth flow uses a separate scope from upload (`yt-analytics.readonly`)
and a separate token cache, so giving the pipeline analytics access doesn't
also let it upload, and vice versa.

Requires the YouTube Analytics API to be enabled in the same Google Cloud
project as your upload credentials.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

log = logging.getLogger("yt_factory.analytics")

ANALYTICS_SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]
TOKEN_PATH = Path.home() / ".cache" / "yt-factory" / "analytics-token.json"


@dataclass
class VideoStats:
    video_id: str
    title: str
    views: int
    avg_view_duration_sec: float
    impression_ctr: float  # 0.0 – 1.0


@dataclass
class AnalyticsReport:
    period_days: int
    fetched_at: str
    videos: List[VideoStats]

    def median(self, key: str) -> float:
        values = sorted(getattr(v, key) for v in self.videos)
        return values[len(values) // 2] if values else 0.0

    def to_prompt_context(self) -> str:
        if not self.videos:
            return "(no analytics data available yet)"
        med_views = self.median("views")
        med_ctr = self.median("impression_ctr")
        med_avd = self.median("avg_view_duration_sec")

        winners = [v for v in self.videos if v.views >= med_views and v.impression_ctr >= med_ctr]
        losers = [v for v in self.videos if v.views < med_views and v.impression_ctr < med_ctr]

        lines = [
            f"CHANNEL ANALYTICS (last {self.period_days} days)",
            f"Median: views={int(med_views):,}, CTR={med_ctr:.1%}, AVD={int(med_avd)}s",
            "",
            "WHAT WORKED (keep doing more of this):",
        ]
        for v in winners[:5]:
            lines.append(
                f"  - {v.title!r}  → {v.views:,} views, {v.impression_ctr:.1%} CTR, {int(v.avg_view_duration_sec)}s AVD"
            )
        lines.append("")
        lines.append("WHAT UNDERPERFORMED (avoid these patterns):")
        for v in losers[:5]:
            lines.append(
                f"  - {v.title!r}  → {v.views:,} views, {v.impression_ctr:.1%} CTR"
            )
        return "\n".join(lines)


def _get_creds(client_secrets_path: Path) -> Credentials:
    creds: Optional[Credentials] = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), ANALYTICS_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path), ANALYTICS_SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        try:
            TOKEN_PATH.chmod(0o600)
        except OSError:
            pass  # best-effort on Windows
        log.info("Cached analytics token at %s", TOKEN_PATH)
    return creds


def fetch_recent(
    client_secrets_path: Path,
    period_days: int = 28,
    max_videos: int = 25,
) -> AnalyticsReport:
    """Pull per-video stats for the authenticated channel."""
    creds = _get_creds(client_secrets_path)
    yt_data = build("youtube", "v3", credentials=creds)
    yt_analytics = build("youtubeAnalytics", "v2", credentials=creds)

    # 1. Find the user's uploads playlist.
    channel_resp = yt_data.channels().list(part="contentDetails", mine=True).execute()
    items = channel_resp.get("items", [])
    if not items:
        log.warning("No channel found for these credentials.")
        return AnalyticsReport(period_days=period_days, fetched_at=date.today().isoformat(), videos=[])
    uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # 2. Pull the latest N video IDs from that playlist.
    pl_resp = yt_data.playlistItems().list(
        part="snippet", playlistId=uploads_id, maxResults=min(max_videos, 50)
    ).execute()
    video_ids: List[str] = []
    titles_by_id: dict[str, str] = {}
    for it in pl_resp.get("items", []):
        vid = it["snippet"]["resourceId"]["videoId"]
        video_ids.append(vid)
        titles_by_id[vid] = it["snippet"]["title"]
    if not video_ids:
        return AnalyticsReport(period_days=period_days, fetched_at=date.today().isoformat(), videos=[])

    # 3. Hit Analytics API for views/CTR/AVD per video.
    end = date.today()
    start = end - timedelta(days=period_days)
    response = yt_analytics.reports().query(
        ids="channel==MINE",
        startDate=start.isoformat(),
        endDate=end.isoformat(),
        metrics="views,averageViewDuration,cardImpressionCtr,annotationClickThroughRate",
        dimensions="video",
        filters=f"video=={','.join(video_ids)}",
        maxResults=max_videos,
    ).execute()

    rows = response.get("rows") or []
    column_headers = response.get("columnHeaders", [])
    name_to_idx = {h["name"]: i for i, h in enumerate(column_headers)}

    # The Analytics API doesn't expose impression CTR uniformly across tiers.
    # Use cardImpressionCtr where available; fall back to 0 — the prompt
    # context calls it out either way.
    videos: List[VideoStats] = []
    for row in rows:
        vid = row[name_to_idx["video"]]
        videos.append(VideoStats(
            video_id=vid,
            title=titles_by_id.get(vid, vid),
            views=int(row[name_to_idx["views"]] or 0),
            avg_view_duration_sec=float(row[name_to_idx["averageViewDuration"]] or 0),
            impression_ctr=float(row[name_to_idx.get("cardImpressionCtr", -1)] or 0)
                if "cardImpressionCtr" in name_to_idx else 0.0,
        ))
    videos.sort(key=lambda v: v.views, reverse=True)

    return AnalyticsReport(
        period_days=period_days,
        fetched_at=date.today().isoformat(),
        videos=videos,
    )


def save(report: AnalyticsReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "period_days": report.period_days,
            "fetched_at": report.fetched_at,
            "videos": [v.__dict__ for v in report.videos],
        }, indent=2),
        encoding="utf-8",
    )


def load_or_none(path: Path) -> Optional[AnalyticsReport]:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return AnalyticsReport(
        period_days=data["period_days"],
        fetched_at=data["fetched_at"],
        videos=[VideoStats(**v) for v in data["videos"]],
    )
