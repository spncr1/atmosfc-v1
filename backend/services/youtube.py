# YouTube comment fetching for match sentiment analysis

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
import time

import httpx

from backend.config import get_settings
from backend.models.schemas import MatchSummary

BASE_URL = "https://www.googleapis.com/youtube/v3"
MAX_VIDEOS = 4
MAX_COMMENTS_PER_VIDEO = 100


class YouTubeError(RuntimeError):
    # Raised when YouTube cannot satisfy a request.
    pass


@dataclass
class YouTubeComment:
    # A YouTube comment normalised for sentiment analysis.

    text: str
    score: int          # likeCount on YouTube
    created_utc: float  # publishedAt as unix timestamp
    permalink: str
    source_label: str
    source_title: str


@dataclass
class YouTubeCommentBatch:
    # Aggregated comments pulled from multiple YouTube videos for one match.

    title: str          # title of the best matching video
    url: str            # URL of the best matching video
    created_utc: float  # publishedAt of the best video as unix timestamp
    comments: List[YouTubeComment]


def fetch_match_comments(match: MatchSummary) -> YouTubeCommentBatch:
    # Search YouTube for match highlight videos and return aggregated comments.

    settings = get_settings()
    if not settings.youtube_api_key:
        raise YouTubeError("YOUTUBE_API_KEY is not configured.")

    videos = _search_videos(match, settings.youtube_api_key)
    if not videos:
        raise YouTubeError(f"No YouTube videos found for {match.home} vs {match.away}.")

    all_comments: List[YouTubeComment] = []
    best_video = videos[0]

    for video in videos:
        try:
            comments = _fetch_comments(video, settings.youtube_api_key)
            all_comments.extend(comments)
        except YouTubeError:
            # Comments disabled or unavailable — try next video
            continue

    if not all_comments:
        raise YouTubeError("No comments available for this match across all found videos.")

    return YouTubeCommentBatch(
        title=best_video["title"],
        url=f"https://youtube.com/watch?v={best_video['id']}",
        created_utc=best_video["published_utc"],
        comments=all_comments,
    )


def _search_videos(match: MatchSummary, api_key: str) -> List[dict]:
    # Search YouTube for highlight videos matching the match.

    query = _build_query(match)
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": MAX_VIDEOS,
        "order": "relevance",
        "key": api_key,
    }

    # Add date window around match date to improve relevance
    if match.date:
        match_dt = datetime.fromisoformat(match.date.replace("Z", "+00:00"))
        published_after = match_dt.strftime("%Y-%m-%dT00:00:00Z")
        published_before_dt = match_dt.replace(
            hour=23, minute=59, second=59
        )
        # Give a 3-day window after match for highlights to be uploaded
        from datetime import timedelta
        published_before = (match_dt + timedelta(days=3)).strftime("%Y-%m-%dT23:59:59Z")
        params["publishedAfter"] = published_after
        params["publishedBefore"] = published_before

    with httpx.Client(timeout=15.0) as client:
        response = client.get(f"{BASE_URL}/search", params=params)

    if response.status_code != 200:
        raise YouTubeError(f"YouTube search failed: {response.status_code}")

    data = response.json()
    videos = []
    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id:
            continue
        published_at = snippet.get("publishedAt", "")
        try:
            published_utc = datetime.fromisoformat(
                published_at.replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            published_utc = 0.0

        videos.append({
            "id": video_id,
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "published_utc": published_utc,
        })

    return videos


def _fetch_comments(video: dict, api_key: str) -> List[YouTubeComment]:
    # Fetch top-level comments from one YouTube video.

    comments = []
    page_token: Optional[str] = None
    video_id = video["id"]

    for _ in range(3):  # max 3 pages = 300 comments per video
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": MAX_COMMENTS_PER_VIDEO,
            "order": "relevance",
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        with httpx.Client(timeout=15.0) as client:
            response = client.get(f"{BASE_URL}/commentThreads", params=params)

        if response.status_code == 403:
            # Comments disabled on this video
            raise YouTubeError("Comments disabled.")
        if response.status_code != 200:
            raise YouTubeError(f"Comment fetch failed: {response.status_code}")

        data = response.json()

        for item in data.get("items", []):
            top = item.get("snippet", {}).get("topLevelComment", {})
            snippet = top.get("snippet", {})
            text = snippet.get("textOriginal", "").strip()
            if not text:
                continue

            published_at = snippet.get("publishedAt", "")
            try:
                published_utc = datetime.fromisoformat(
                    published_at.replace("Z", "+00:00")
                ).timestamp()
            except ValueError:
                published_utc = 0.0

            comments.append(YouTubeComment(
                text=text,
                score=int(snippet.get("likeCount", 0)),
                created_utc=published_utc,
                permalink=f"https://youtube.com/watch?v={video_id}",
                source_label=video.get("channel", "") or "YouTube",
                source_title=video.get("title", ""),
            ))

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return comments


def _build_query(match: MatchSummary) -> str:
    # Build a YouTube search query for a match.

    home = match.home
    away = match.away
    competition = match.competition

    # Strip common suffixes that hurt search relevance
    for suffix in [" FC", " CF", " SC", " AC", " AFC", " RFC"]:
        home = home.replace(suffix, "")
        away = away.replace(suffix, "")

    return f"{home} {away} highlights {competition}"
