# FastAPI entry point

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.models.schemas import AnalyseRequest, AnalysisResponse, AnalyseMeta
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
async def get_recent_matches(limit: int = Query(default=18, ge=1, le=30)):
    # Return recent finished matches for the landing page.

    try:
        return {"matches": await football_api.recent_matches(limit=limit)}
    except FootballDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/matches/search")
async def get_search_matches(
    q: str = "",
    competition: str | None = None,
    season: int | None = Query(default=None, ge=2015, le=2025),
    limit: int = Query(default=24, ge=1, le=50),
):
    # Search matches by team, competition, and season.

    try:
        matches = await football_api.search_matches(query=q, competition=competition, season=season, limit=limit)
        return {"matches": matches}
    except FootballDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/analyse", response_model=AnalysisResponse)
async def analyse_match(payload: AnalyseRequest) -> AnalysisResponse:
    # Analyse YouTube sentiment for one Football-Data.org match.

    try:
        raw_match = await football_api.get_match(payload.match_id)
        match = football_api.parse_match(raw_match)
        events = football_api.parse_events(raw_match)
        thread = fetch_match_comments(match)
        kickoff = datetime.fromisoformat(match.date.replace("Z", "+00:00")).astimezone(timezone.utc)
        buckets, half_split, top_comments, peak_minute, overall_vibe, crowd_energy = analyse_comments(
            thread.comments,
            kickoff,
        )
        return AnalysisResponse(
            match=match,
            events=events,
            sentiment_buckets=buckets,
            top_comments=top_comments,
            half_split=half_split,
            meta=AnalyseMeta(
                total_comments=len(thread.comments),
                peak_minute=peak_minute,
                overall_vibe=overall_vibe,
                crowd_energy=crowd_energy,
                youtube_thread_url=thread.url,
            ),
        )
    except FootballDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except YouTubeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
