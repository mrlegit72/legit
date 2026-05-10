"""Upload a finished video to YouTube via the Data API v3.

OAuth flow: first run opens a browser for consent, then caches the token in
`~/.cache/yt-factory/token.json`. Subsequent runs are headless.

You'll need a `client_secrets.json` from Google Cloud Console:
  Console → APIs & Services → Credentials → Create Credentials →
  OAuth client ID → Desktop app → Download JSON → save as
  `client_secrets.json` next to pipeline.py.

YouTube Data API v3 must be enabled in the same project.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

log = logging.getLogger("yt_factory.upload")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = Path.home() / ".cache" / "yt-factory" / "token.json"


@dataclass
class UploadResult:
    video_id: str
    url: str


class YouTubeUploader:
    def __init__(self, client_secrets_path: Path):
        if not client_secrets_path.exists():
            raise FileNotFoundError(
                f"Missing {client_secrets_path}. Download it from "
                "Google Cloud Console (Credentials → OAuth client ID → Desktop app)."
            )
        self._client_secrets_path = client_secrets_path
        self._service = None

    def _get_service(self):
        if self._service is not None:
            return self._service

        creds: Optional[Credentials] = None
        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self._client_secrets_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
            try:
                # Token contains an OAuth refresh token — owner-only.
                TOKEN_PATH.chmod(0o600)
            except OSError:
                pass  # best-effort on Windows
            log.info("Cached YouTube token at %s", TOKEN_PATH)

        self._service = build("youtube", "v3", credentials=creds)
        return self._service

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        category_id: str = "22",  # 22 = People & Blogs (broad default)
        privacy: str = "private",  # private until you verify, then flip to public
        thumbnail_path: Optional[Path] = None,
    ) -> UploadResult:
        service = self._get_service()

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:500],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }
        media = MediaFileUpload(
            str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4"
        )
        log.info("Uploading %s (%s)...", video_path.name, privacy)
        request = service.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                log.info("  %d%%", int(status.progress() * 100))

        video_id = response["id"]
        log.info("Uploaded video id=%s", video_id)

        if thumbnail_path and thumbnail_path.exists():
            log.info("Setting thumbnail %s", thumbnail_path.name)
            service.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/png"),
            ).execute()

        return UploadResult(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
        )
