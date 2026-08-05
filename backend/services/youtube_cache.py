"""Persist cached YouTube comment counts for match result cards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.database.models import YouTubeCommentCache
from backend.database.session import get_sessionmaker
from backend.models.schemas import MatchSummary
from backend.repositories import football_data as repo
from backend.services.sentiment import hour_bucket_from_comment
from backend.services.youtube import YouTubeCommentBatch, YouTubeError, fetch_match_comments


@dataclass(frozen=True)
class YouTubeCommentCacheResult:
    status: str
    raw_comment_count: int | None = None
    analysed_comment_count: int | None = None
    source_video_count: int | None = None
    best_video_url: str | None = None
    best_video_title: str | None = None
    error_message: str | None = None


async def fetch_and_cache_youtube_comment_count(match: MatchSummary) -> YouTubeCommentCacheResult:
    """Fetch YouTube comments for one match and cache the result-card summary."""

    try:
        batch = fetch_match_comments(match)
    except YouTubeError as exc:
        return await cache_youtube_comment_error(match, exc)
    return await cache_youtube_comment_batch(match, batch)


async def cache_youtube_comment_batch(
    match: MatchSummary,
    batch: YouTubeCommentBatch,
) -> YouTubeCommentCacheResult:
    """Persist comment counts from an already fetched YouTube comment batch."""

    raw_count = len(batch.comments)
    analysed_count = analysed_comment_count(match, batch)
    source_video_count = len({comment.permalink for comment in batch.comments}) or None
    result = YouTubeCommentCacheResult(
        status="complete" if raw_count else "no_comments",
        raw_comment_count=raw_count,
        analysed_comment_count=analysed_count,
        source_video_count=source_video_count,
        best_video_url=batch.url,
        best_video_title=batch.title,
    )
    await persist_youtube_comment_cache(match, result)
    return result


async def cache_youtube_comment_error(
    match: MatchSummary,
    error: YouTubeError,
) -> YouTubeCommentCacheResult:
    """Persist a checked-but-empty/unavailable YouTube result."""

    message = str(error)
    result = YouTubeCommentCacheResult(
        status=youtube_error_status(message),
        error_message=message,
    )
    await persist_youtube_comment_cache(match, result)
    return result


async def persist_youtube_comment_cache(
    match: MatchSummary,
    result: YouTubeCommentCacheResult,
) -> YouTubeCommentCache | None:
    """Store a cache result when the match belongs to the local API-Football DB."""

    try:
        provider_fixture_id = int(match.id)
    except (TypeError, ValueError):
        return None

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        fixture = await repo.fixture_by_provider_fixture_id(session, provider_fixture_id)
        if fixture is None:
            return None
        cache = await repo.upsert_youtube_comment_cache(
            session,
            fixture,
            status=result.status,
            raw_comment_count=result.raw_comment_count,
            analysed_comment_count=result.analysed_comment_count,
            source_video_count=result.source_video_count,
            best_video_url=result.best_video_url,
            best_video_title=result.best_video_title,
            error_message=result.error_message,
            raw_payload={
                "source": "youtube",
                "match_id": match.id,
            },
        )
        await session.commit()
        return cache


def analysed_comment_count(match: MatchSummary, batch: YouTubeCommentBatch) -> int:
    """Return comments inside the app's first-24-hours-after-full-time window."""

    if not match.date:
        return 0
    kickoff = datetime.fromisoformat(match.date.replace("Z", "+00:00")).astimezone(timezone.utc)
    full_time = kickoff + timedelta(minutes=105)
    return sum(
        1
        for comment in batch.comments
        if hour_bucket_from_comment(comment.created_utc, full_time) is not None
    )


def youtube_error_status(message: str) -> str:
    clean = message.lower()
    if "429" in clean or "quota" in clean or "rate limit" in clean or "rate-limit" in clean:
        return "rate_limited"
    if "no comments" in clean or "comments disabled" in clean:
        return "no_comments"
    if "no youtube videos" in clean:
        return "unavailable"
    if "not configured" in clean:
        return "failed"
    return "failed"
