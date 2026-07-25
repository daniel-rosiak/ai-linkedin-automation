from abc import ABC, abstractmethod
from typing import List

from src.db.models import Article, Proposal


class BaseProvider(ABC):
    @abstractmethod
    def generate_proposals(
        self,
        articles: List[Article],
        approved_history: List[Proposal] = None,
        rejected_history: List[Proposal] = None,
        global_feedback: str = None,
    ) -> List[Proposal]:
        """Generates 3-5 distinct post proposals from curated articles and history feedback."""
        pass

    @abstractmethod
    def generate_post_text(self, proposal: Proposal, style_examples: List[str] = None) -> str:
        """Expands an approved proposal's title and angle into the final full post Markdown text."""
        pass

    @abstractmethod
    def regenerate_proposal(self, proposal: Proposal, feedback: str) -> Proposal:
        """Rewrites and refines an existing proposal using specific custom text feedback."""
        pass

    @abstractmethod
    def refine_post_text(self, current_copy: str, critique: str, style_examples: List[str] = None) -> str:
        """Iteratively rewrites and edits final copywriting text using specific user feedback."""
        pass
