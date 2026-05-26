# Pydantic request/response models

from typing import Dict, List, Optional

from pydantic import BaseModel


class MatchSummary(BaseModel):
    # A football match returned to the frontend.

    id: str
    home: str
    away: str
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    home_short_name: Optional[str] = None
    away_short_name: Optional[str] = None
    home_crest: Optional[str] = None
    away_crest: Optional[str] = None
    score: str
    half_time_score: Optional[str] = None
    competition: str
    competition_code: str
    date: str
    venue: Optional[str] = None
    round: Optional[str] = None
    season: Optional[str] = None
    status: Optional[str] = None


class SearchPagination(BaseModel):
    # Pagination metadata for match search results.

    page: int
    page_size: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool


class MatchSearchResponse(BaseModel):
    # Paginated match search response consumed by results.html.

    matches: List[MatchSummary]
    pagination: SearchPagination


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


class ReactionIntensityBucket(BaseModel):
    # Post-match reaction intensity for one hour bucket.

    hour_offset: int
    intensity: float
    sentiment: float
    comment_count: int


class PeakWindow(BaseModel):
    # Highest post-match reaction window.

    hour_start: int
    hour_end: int


class TopComment(BaseModel):
    # A high-signal YouTube comment near a peak sentiment moment.

    text: str
    score: int
    minute: int
    sentiment: float
    source_url: Optional[str] = None


class AnalyseRequest(BaseModel):
    # Request payload for match analysis.

    match_id: str


class AnalyseMeta(BaseModel):
    # Summary metadata for a sentiment analysis response.

    total_comments: int
    peak_minute: int
    peak_window: PeakWindow
    source_video_count: int
    overall_vibe: Dict[str, str]
    crowd_energy: Dict[str, str]
    youtube_video_url: Optional[str] = None


class AnalysisResponse(BaseModel):
    # Complete payload consumed by analysis.html.

    match: MatchSummary
    events: List[MatchEvent]
    sentiment_buckets: List[SentimentBucket]
    reaction_intensity: List[ReactionIntensityBucket]
    top_comments: List[TopComment]
    half_split: Dict[str, Dict[str, int]]
    meta: AnalyseMeta
