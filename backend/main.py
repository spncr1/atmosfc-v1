# FastAPI entry point

from __future__ import annotations

from datetime import datetime, timezone
from math import ceil

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.models.schemas import AnalyseRequest, AnalysisResponse, AnalyseMeta, MatchSearchResponse
from backend.services import football_api
from backend.services.football_api import FootballDataError
from backend.services.youtube import YouTubeError, fetch_match_comments
from backend.services.sentiment import analyse_comments

app = FastAPI(title="Atmos API", version="0.1.0")
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    # Return a simple service health response.

    return {"status": "ok"}


@app.get("/matches/recent")
async def get_recent_matches(
    competition: str | None = None,
    limit: int = Query(default=18, ge=1, le=30),
):
    # Return recent finished matches for the landing page.

    try:
        return {"matches": await football_api.recent_matches(limit=limit, competition=competition)}
    except FootballDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/matches/search", response_model=MatchSearchResponse)
async def get_search_matches(
    q: str = "",
    competition: str | None = None,
    season: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=15, ge=1, le=30),
):
    # Search matches by team, competition, and season.

    try:
        season_year = int(season) if season else None
        matches = await football_api.search_matches(query=q, competition=competition, season=season_year)
        total = len(matches)
        total_pages = ceil(total / page_size) if total else 0
        current_page = min(page, total_pages) if total_pages else 1
        start = (current_page - 1) * page_size
        end = start + page_size
        return {
            "matches": matches[start:end],
            "pagination": {
                "page": current_page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_previous": current_page > 1,
                "has_next": total_pages > 0 and current_page < total_pages,
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Season must be a year such as 2025.") from exc
    except FootballDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/analyse", response_model=AnalysisResponse)
async def analyse_match(payload: AnalyseRequest) -> AnalysisResponse:
    # Analyse YouTube sentiment for one Football-Data.org match.

    try:
        raw_match = await football_api.get_match(payload.match_id)
        match = football_api.parse_match(raw_match)
        if match.status != "FINISHED":
            raise HTTPException(status_code=400, detail="Only finished matches can be analysed.")
        events = football_api.parse_events(raw_match)
        video_comments = fetch_match_comments(match)
        kickoff = datetime.fromisoformat(match.date.replace("Z", "+00:00")).astimezone(timezone.utc)
        score_margin = _score_margin(raw_match)
        source_video_count = len({comment.permalink for comment in video_comments.comments}) or 1
        buckets, reaction_intensity, half_split, top_comments, peak_minute, peak_window, overall_vibe, crowd_energy = analyse_comments(
            video_comments.comments,
            kickoff,
            score_margin,
        )
        return AnalysisResponse(
            match=match,
            events=events,
            sentiment_buckets=buckets,
            reaction_intensity=reaction_intensity,
            top_comments=top_comments,
            half_split=half_split,
            meta=AnalyseMeta(
                total_comments=sum(bucket.comment_count for bucket in reaction_intensity),
                peak_minute=peak_minute,
                peak_window=peak_window,
                source_video_count=source_video_count,
                overall_vibe=overall_vibe,
                crowd_energy=crowd_energy,
                youtube_video_url=video_comments.url,
            ),
        )
    except FootballDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except YouTubeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _score_margin(raw_match: dict) -> int:
    score = raw_match.get("score", {}).get("fullTime", {})
    home_score = score.get("home")
    away_score = score.get("away")
    if home_score is None or away_score is None:
        return 0
    return abs(int(home_score) - int(away_score))
