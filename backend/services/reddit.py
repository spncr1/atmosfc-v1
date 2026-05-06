# PRAW thread fetching + comment parsing

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import praw

from backend.config import get_settings
from backend.models.schemas import MatchSummary
from backend.utils.thread_matcher import best_submission, build_search_query


class RedditError(RuntimeError):
    # Raised when Reddit cannot satisfy a request.
    pass


@dataclass
class RedditComment:
    # A Reddit comment normalized for sentiment analysis.

    text: str
    score: int
    created_utc: float
    permalink: str


@dataclass
class RedditThread:
    # A matched Reddit thread and its flattened comments.

    title: str
    url: str
    created_utc: float
    comments: List[RedditComment]


def fetch_post_match_thread(match: MatchSummary, limit: int = 8) -> RedditThread:
    # Search r/soccer for a match thread and return its comments.

    reddit = _client()
    query = build_search_query(match)
    subreddit = reddit.subreddit("soccer")
    submissions = subreddit.search(query, sort="relevance", time_filter="all", limit=limit)
    submission = best_submission(match, submissions)
    if submission is None:
        raise RedditError("No matching r/soccer post-match thread found.")

    submission.comments.replace_more(limit=0)
    comments = [
        RedditComment(
            text=comment.body,
            score=int(getattr(comment, "score", 0)),
            created_utc=float(comment.created_utc),
            permalink=f"https://reddit.com{comment.permalink}",
        )
        for comment in submission.comments.list()
        if getattr(comment, "body", None) and comment.body not in {"[deleted]", "[removed]"}
    ]
    return RedditThread(
        title=submission.title,
        url=f"https://reddit.com{submission.permalink}",
        created_utc=float(submission.created_utc),
        comments=comments,
    )


def _client() -> praw.Reddit:
    # Create a read-only PRAW client from environment variables.

    settings = get_settings()
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        raise RedditError("Reddit credentials are not configured.")
    return praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )
