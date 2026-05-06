# Pydantic request/response models

from typing import Dict, List, Optional

from pydantic import BaseModel


class MatchSummary(BaseModel):
    # A football match returned to the frontend.

    id: str
    home: str
    away: str
    score: str
    competition: str
    competition_code: str
    date: str
    round: Optional[str] = None
    season: Optional[str] = None
    status: Optional[str] = None


class MatchEvent(BaseModel):
    # A timeline event displayed beside sentiment.

    minute: int
    type: str
    description: str


class SentimentBucket(BaseModel):
    # Average sentiment for a five-minute match interval.

    minute: int
    score: float
    comment_count: int


class TopComment(BaseModel):
    # A high-signal Reddit comment near a peak sentiment moment.

    text: str
    score: int
    minute: int
    sentiment: float


class AnalyseRequest(BaseModel):
    # Request payload for match analysis.

    match_id: str


class AnalyseMeta(BaseModel):
    # Summary metadata for a sentiment analysis response.

    total_comments: int
    peak_minute: int
    overall_vibe: str
    crowd_energy: str
    reddit_thread_url: Optional[str] = None


class AnalysisResponse(BaseModel):
    # Complete payload consumed by analysis.html.

    match: MatchSummary
    events: List[MatchEvent]
    sentiment_buckets: List[SentimentBucket]
    top_comments: List[TopComment]
    half_split: Dict[str, Dict[str, int]]
    meta: AnalyseMeta
