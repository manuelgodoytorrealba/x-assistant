from pydantic import BaseModel
from typing import Optional


class PostCandidate(BaseModel):
    author: str
    handle: str
    text: str
    url: str
    minutes_since_posted: int
    likes: int
    replies: int
    reposts: int
    topic_hint: str
    author_priority: int  # 1-10


class ScoredPost(PostCandidate):
    topic_relevance: float
    early_engagement: float
    reply_potential: float
    score: float
    recommended_action: str
    priority: str