# VADER scoring + bucketing logic

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Tuple

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from backend.models.schemas import SentimentBucket, TopComment
from backend.services.youtube import YouTubeComment

BUCKET_SIZE = 5
MATCH_MINUTES = 90


def analyse_comments(
    comments: List[YouTubeComment],
    kickoff_utc: datetime,
) -> Tuple[List[SentimentBucket], Dict[str, Dict[str, int]], List[TopComment], int, str, str]:
    # Score YouTube comments and return buckets, half split, top comments, and summary labels.

    analyzer = SentimentIntensityAnalyzer()
    bucket_scores: Dict[int, List[float]] = defaultdict(list)
    scored_comments: List[Tuple[YouTubeComment, int, float]] = []
    half_split = {
        "first": {"pos": 0, "neg": 0, "neu": 0},
        "second": {"pos": 0, "neg": 0, "neu": 0},
    }

    for comment in comments:
        minute = minute_from_comment(comment.created_utc, kickoff_utc)
        sentiment = analyzer.polarity_scores(comment.text)["compound"]
        bucket_minute = bucket_for_minute(minute)
        bucket_scores[bucket_minute].append(sentiment)
        scored_comments.append((comment, minute, sentiment))
        half = "first" if minute <= 45 else "second"
        half_split[half][_sentiment_label(sentiment)] += 1

    buckets = [
        SentimentBucket(
            minute=minute,
            score=round(mean(bucket_scores[minute]), 3) if bucket_scores[minute] else 0.0,
            comment_count=len(bucket_scores[minute]),
        )
        for minute in range(0, MATCH_MINUTES + BUCKET_SIZE, BUCKET_SIZE)
    ]
    peak_minute = peak_bucket_minute(buckets)
    top_comments = top_peak_comments(scored_comments, peak_minute)
    overall = mean([score for _, _, score in scored_comments]) if scored_comments else 0.0

    return buckets, half_split, top_comments, peak_minute, vibe_label(overall), energy_label(len(comments))


def minute_from_comment(created_utc: float, kickoff_utc: datetime) -> int:
    # Estimate match minute from a comment timestamp and kickoff time.

    kickoff = kickoff_utc.astimezone(timezone.utc)
    created = datetime.fromtimestamp(created_utc, tz=timezone.utc)
    minute = int((created - kickoff).total_seconds() // 60)
    return max(0, min(MATCH_MINUTES, minute))


def bucket_for_minute(minute: int) -> int:
    # Return the five-minute bucket start for a match minute.

    capped = max(0, min(MATCH_MINUTES, minute))
    return min(MATCH_MINUTES, (capped // BUCKET_SIZE) * BUCKET_SIZE)


def peak_bucket_minute(buckets: List[SentimentBucket]) -> int:
    # Return the bucket minute with the strongest sentiment movement.

    if not buckets:
        return 0
    return max(buckets, key=lambda bucket: (abs(bucket.score), bucket.comment_count)).minute


def top_peak_comments(scored_comments: List[Tuple[YouTubeComment, int, float]], peak_minute: int) -> List[TopComment]:
    # Return the top three comments by upvotes around the peak bucket.

    lower = max(0, peak_minute - BUCKET_SIZE)
    upper = min(MATCH_MINUTES, peak_minute + BUCKET_SIZE)
    nearby = [item for item in scored_comments if lower <= item[1] <= upper]
    ranked = sorted(nearby, key=lambda item: (item[0].score, abs(item[2])), reverse=True)[:3]
    return [
        TopComment(
            text=_trim(comment.text),
            score=comment.score,
            minute=minute,
            sentiment=round(sentiment, 3),
        )
        for comment, minute, sentiment in ranked
    ]


def vibe_label(score: float) -> str:
    # Translate an overall compound sentiment score into a display label.

    if score >= 0.25:
        return "Buoyant"
    if score <= -0.25:
        return "Frustrated"
    if score >= 0.05:
        return "Hopeful"
    if score <= -0.05:
        return "Tense"
    return "Balanced"


def energy_label(total_comments: int) -> str:
    # Translate comment volume into a crowd energy label.

    if total_comments >= 1500:
        return "Roaring"
    if total_comments >= 500:
        return "Lively"
    if total_comments >= 100:
        return "Buzzing"
    return "Quiet"


def _sentiment_label(score: float) -> str:
    # Classify one compound sentiment score as positive, negative, or neutral.

    if score >= 0.05:
        return "pos"
    if score <= -0.05:
        return "neg"
    return "neu"


def _trim(text: str, limit: int = 260) -> str:
    # Trim long comments for compact frontend display.

    clean = " ".join(text.split())
    return clean if len(clean) <= limit else f"{clean[: limit - 1]}..."
