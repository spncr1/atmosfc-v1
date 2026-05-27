# VADER scoring + bucketing logic

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Dict, List, Tuple

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from backend.models.schemas import ReactionIntensityBucket, SentimentBucket, TopComment
from backend.services.youtube import YouTubeComment

BUCKET_SIZE = 5
MATCH_MINUTES = 90
REACTION_WINDOWS = [
    (0, 3),
    (3, 6),
    (6, 9),
    (9, 12),
    (12, 15),
    (15, 18),
    (18, 21),
    (21, 24),
]

VIBE_DESCRIPTORS = [
    {
        "label": "Thriller",
        "subtext": "End to end, impossible to call",
        "min_sentiment": 0.2, "max_sentiment": 1.0,
        "min_volume": 800,
        "requires_close_score": True,
        "requires_large_margin": False,
        "requires_high_volume": True,
        "requires_late_shift": False,
    },
    {
        "label": "Dominant",
        "subtext": "One team, no contest",
        "min_sentiment": 0.3, "max_sentiment": 1.0,
        "min_volume": 0,
        "requires_close_score": False,
        "requires_large_margin": True,
        "requires_high_volume": False,
        "requires_late_shift": False,
    },
    {
        "label": "Chaotic",
        "subtext": "Frantic, end to end",
        "min_sentiment": -0.1, "max_sentiment": 0.4,
        "min_volume": 1000,
        "requires_close_score": False,
        "requires_large_margin": False,
        "requires_high_volume": True,
        "requires_late_shift": False,
    },
    {
        "label": "Controversial",
        "subtext": "Fans still arguing about it",
        "min_sentiment": -0.3, "max_sentiment": 0.1,
        "min_volume": 500,
        "requires_close_score": True,
        "requires_large_margin": False,
        "requires_high_volume": False,
        "requires_late_shift": False,
    },
    {
        "label": "Heartbreak",
        "subtext": "So close, yet so far",
        "min_sentiment": -0.5, "max_sentiment": -0.1,
        "min_volume": 300,
        "requires_close_score": True,
        "requires_large_margin": False,
        "requires_high_volume": False,
        "requires_late_shift": True,
    },
    {
        "label": "Bottled it",
        "subtext": "Had it won, gave it away",
        "min_sentiment": -0.6, "max_sentiment": -0.2,
        "min_volume": 400,
        "requires_close_score": False,
        "requires_large_margin": False,
        "requires_high_volume": False,
        "requires_late_shift": True,
    },
    {
        "label": "Capitulation",
        "subtext": "Complete collapse",
        "min_sentiment": -0.6, "max_sentiment": -0.2,
        "min_volume": 0,
        "requires_close_score": False,
        "requires_large_margin": True,
        "requires_high_volume": False,
        "requires_late_shift": False,
    },
    {
        "label": "Quietly pleased",
        "subtext": "Solid, professional job",
        "min_sentiment": 0.2, "max_sentiment": 1.0,
        "min_volume": 0,
        "requires_close_score": False,
        "requires_large_margin": False,
        "requires_high_volume": False,
        "requires_late_shift": False,
    },
    {
        "label": "Forgettable",
        "subtext": "Nothing to write home about",
        "min_sentiment": -0.1, "max_sentiment": 0.2,
        "min_volume": 0,
        "requires_close_score": False,
        "requires_large_margin": False,
        "requires_high_volume": False,
        "requires_late_shift": False,
    },
]

ENERGY_DESCRIPTORS = [
    {"label": "Roaring", "subtext": "Top 3% of all matches", "min_comments": 2000},
    {"label": "Loud", "subtext": "Major reaction online", "min_comments": 1000},
    {"label": "Buzzing", "subtext": "Solid online reaction", "min_comments": 500},
    {"label": "Murmuring", "subtext": "Moderate online activity", "min_comments": 100},
    {"label": "Quiet", "subtext": "Low online activity", "min_comments": 0},
]


def analyse_comments(
    comments: List[YouTubeComment],
    kickoff_utc: datetime,
    score_margin: int,
) -> Tuple[
    List[SentimentBucket],
    List[ReactionIntensityBucket],
    Dict[str, Dict[str, int]],
    List[TopComment],
    int,
    Dict[str, int],
    Dict[str, str],
    Dict[str, str],
]:
    # Score YouTube comments and return buckets, half split, top comments, and summary labels.

    analyzer = SentimentIntensityAnalyzer()
    bucket_scores: Dict[int, List[float]] = defaultdict(list)
    window_scores: Dict[int, List[float]] = defaultdict(list)
    scored_comments: List[Tuple[YouTubeComment, int, float]] = []
    scored_hours: List[Tuple[YouTubeComment, int, float]] = []
    half_split = {
        "first": {"pos": 0, "neg": 0, "neu": 0},
        "second": {"pos": 0, "neg": 0, "neu": 0},
    }
    full_time = kickoff_utc.astimezone(timezone.utc) + timedelta(minutes=105)

    for comment in comments:
        minute = minute_from_comment(comment.created_utc, kickoff_utc)
        hour = hour_bucket_from_comment(comment.created_utc, full_time)
        if hour is None:
            continue
        sentiment = analyzer.polarity_scores(comment.text)["compound"]
        bucket_minute = bucket_for_minute(minute)
        bucket_scores[bucket_minute].append(sentiment)
        window_scores[hour].append(sentiment)
        scored_comments.append((comment, minute, sentiment))
        scored_hours.append((comment, hour, sentiment))
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
    reaction_intensity = reaction_intensity_buckets(window_scores)
    peak_minute = peak_bucket_minute(buckets)
    peak_window = peak_reaction_window(reaction_intensity)
    top_comments = top_liked_comments(scored_hours)
    overall = mean([score for _, _, score in scored_comments]) if scored_comments else 0.0
    first_half_avg = average_bucket_sentiment(window_scores, 0, 12)
    second_half_avg = average_bucket_sentiment(window_scores, 12, 24)

    return (
        buckets,
        reaction_intensity,
        half_split,
        top_comments,
        peak_minute,
        peak_window,
        vibe_label(overall, len(scored_comments), score_margin, first_half_avg, second_half_avg),
        energy_label(len(scored_comments)),
    )


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


def reaction_intensity_buckets(hour_scores: Dict[int, List[float]]) -> List[ReactionIntensityBucket]:
    # Return post-match hourly reaction intensity normalised to a 0-100 scale.

    max_bucket_count = max((len(hour_scores[start]) for start, _ in REACTION_WINDOWS), default=0) or 1
    buckets: List[ReactionIntensityBucket] = []
    for hour, _ in REACTION_WINDOWS:
        scores = hour_scores[hour]
        sentiment = mean(scores) if scores else 0.0
        normalised_volume = (len(scores) / max_bucket_count) * 100
        normalised_sentiment = ((sentiment + 1) / 2) * 100
        intensity = (normalised_volume * 0.6) + (normalised_sentiment * 0.4)
        buckets.append(ReactionIntensityBucket(
            hour_offset=hour,
            intensity=round(max(0, min(100, intensity)), 2),
            sentiment=round(sentiment, 3),
            comment_count=len(scores),
        ))
    return buckets


def peak_reaction_window(buckets: List[ReactionIntensityBucket]) -> Dict[str, int]:
    # Return the highest intensity post-match window.

    if not buckets:
        return {"hour_start": 0, "hour_end": 1}
    peak = max(buckets, key=lambda bucket: (bucket.intensity, bucket.comment_count))
    for start, end in REACTION_WINDOWS:
        if start == peak.hour_offset:
            return {"hour_start": start, "hour_end": end}
    return {"hour_start": peak.hour_offset, "hour_end": min(24, peak.hour_offset + 1)}


def hour_bucket_from_comment(created_utc: float, full_time_utc: datetime) -> int | None:
    # Estimate the whole-hour bucket after full time for a YouTube comment.

    created = datetime.fromtimestamp(created_utc, tz=timezone.utc)
    delta_hours = (created - full_time_utc).total_seconds() / 3600
    if delta_hours < 0 or delta_hours >= 24:
        return None
    for start, end in REACTION_WINDOWS:
        if start <= delta_hours < end:
            return start
    return None


def average_bucket_sentiment(hour_scores: Dict[int, List[float]], start: int, end: int) -> float:
    scores = [score for hour, values in hour_scores.items() if start <= hour < end for score in values]
    return mean(scores) if scores else 0.0


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
            source_url=comment.permalink,
            source_label=comment.source_label,
            source_title=comment.source_title,
        )
        for comment, minute, sentiment in ranked
    ]


def top_liked_comments(scored_comments: List[Tuple[YouTubeComment, int, float]]) -> List[TopComment]:
    # Prefer source diversity, then backfill by likes when only a few videos survived.

    ranked_all = sorted(scored_comments, key=lambda item: item[0].score, reverse=True)
    best_by_source: Dict[str, Tuple[YouTubeComment, int, float]] = {}
    for item in ranked_all:
        source_url = item[0].permalink
        if source_url not in best_by_source:
            best_by_source[source_url] = item

    selected = sorted(best_by_source.values(), key=lambda item: item[0].score, reverse=True)[:3]
    selected_ids = {id(item) for item in selected}
    for item in ranked_all:
        if len(selected) >= 3:
            break
        if id(item) in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(id(item))

    return [
        TopComment(
            text=_trim(comment.text),
            score=comment.score,
            minute=0,
            sentiment=round(sentiment, 3),
            source_url=comment.permalink,
            source_label=comment.source_label,
            source_title=comment.source_title,
        )
        for comment, _, sentiment in selected
    ]


def vibe_label(
    score: float,
    total_comments: int,
    score_margin: int,
    first_half_avg: float,
    second_half_avg: float,
) -> Dict[str, str]:
    # Translate sentiment, volume, and match context into a display descriptor.

    for descriptor in VIBE_DESCRIPTORS:
        if score < descriptor["min_sentiment"] or score > descriptor["max_sentiment"]:
            continue
        if total_comments < descriptor["min_volume"]:
            continue
        if descriptor["requires_close_score"] and score_margin > 1:
            continue
        if descriptor["requires_large_margin"] and score_margin < 3:
            continue
        if descriptor["requires_high_volume"] and total_comments < 800:
            continue
        if descriptor["requires_late_shift"] and abs(second_half_avg - first_half_avg) <= 0.2:
            continue
        return {"label": descriptor["label"], "subtext": descriptor["subtext"]}
    fallback = VIBE_DESCRIPTORS[-1]
    return {"label": fallback["label"], "subtext": fallback["subtext"]}


def energy_label(total_comments: int) -> Dict[str, str]:
    # Translate comment volume into a crowd energy descriptor.

    for descriptor in ENERGY_DESCRIPTORS:
        if total_comments >= descriptor["min_comments"]:
            return {"label": descriptor["label"], "subtext": descriptor["subtext"]}
    fallback = ENERGY_DESCRIPTORS[-1]
    return {"label": fallback["label"], "subtext": fallback["subtext"]}


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
