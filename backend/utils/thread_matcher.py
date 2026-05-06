# Match object which turns into a Reddit thread search

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Iterable, Optional

from backend.models.schemas import MatchSummary


def build_search_query(match: MatchSummary) -> str:
    # Construct a Reddit search query for an r/soccer post-match thread.

    return f'Post Match Thread "{match.home}" "{match.away}" {match.competition}'


def score_submission_title(match: MatchSummary, title: str) -> float:
    # Score how likely a Reddit title belongs to the supplied match.

    clean_title = title.lower()
    required = ["post", "match", "thread"]
    thread_bonus = 0.25 if all(word in clean_title for word in required) else 0.0
    teams = f"{match.home} {match.away}".lower()
    ratio = SequenceMatcher(None, teams, clean_title).ratio()
    home_bonus = 0.25 if match.home.lower() in clean_title else 0.0
    away_bonus = 0.25 if match.away.lower() in clean_title else 0.0
    competition_bonus = 0.1 if match.competition.lower() in clean_title else 0.0
    return ratio + thread_bonus + home_bonus + away_bonus + competition_bonus


def best_submission(match: MatchSummary, submissions: Iterable[Any]) -> Optional[Any]:
    # Return the highest-confidence Reddit submission for a match.

    ranked = sorted(
        ((score_submission_title(match, getattr(submission, "title", "")), submission) for submission in submissions),
        key=lambda item: item[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] < 0.55:
        return None
    return ranked[0][1]
