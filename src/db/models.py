from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    title: str
    url: str
    source: str
    summary: str  # Initial description, or text summary from the news source
    score: Optional[float] = None
    date: Optional[str] = None


@dataclass
class Proposal:
    id: Optional[int]
    url: str
    title: str
    source: str
    summary: str
    proposed_title: str
    proposed_angle: str
    status: str  # 'pending', 'approved', 'rejected', 'skipped'
    created_at: Optional[datetime] = None
    feedback: Optional[str] = None
    completed_copy: Optional[str] = None
