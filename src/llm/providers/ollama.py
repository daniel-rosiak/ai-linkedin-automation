import json
import re
from typing import List

import ollama

from src.db.models import Article, Proposal
from src.llm.base import BaseProvider
from src.llm.prompts import (
    build_copy_refinement_prompt,
    build_final_post_prompt,
    build_proposal_prompt,
    build_regeneration_prompt,
)


class OllamaProvider(BaseProvider):
    def __init__(self, host: str, model: str):
        self.host = host
        self.model = model
        self.client = ollama.Client(host=host)

    def generate_proposals(
        self,
        articles: List[Article],
        approved_history: List[Proposal] = None,
        rejected_history: List[Proposal] = None,
        global_feedback: str = None,
    ) -> List[Proposal]:
        if not articles:
            return []

        prompt = build_proposal_prompt(articles, approved_history, rejected_history, global_feedback)

        # We enforce JSON mode via format="json" option in Ollama client chat
        response = self.client.chat(model=self.model, messages=[{"role": "user", "content": prompt}], format="json")

        text = response["message"]["content"].strip()
        # Clean potential markdown wrapping
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            text = re.sub(r"\n```$", "", text)
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Attempt parsing inner array if there's stray conversational wrapper text
            match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return []
            else:
                return []

        if isinstance(data, dict):
            if "proposals" in data and isinstance(data["proposals"], list):
                data = data["proposals"]
            else:
                data = [data]
        elif not isinstance(data, list):
            return []

        proposals = []
        url_to_article = {a.url: a for a in articles}

        for obj in data:
            proposed_title = obj.get("proposed_title", "")
            proposed_angle = obj.get("proposed_angle", "")
            url = obj.get("url", "")

            article = url_to_article.get(url)
            source = article.source if article else "unknown"
            summary = article.summary if article else ""
            title = article.title if article else ""

            proposals.append(
                Proposal(
                    id=None,
                    url=url,
                    title=title,
                    source=source,
                    summary=summary,
                    proposed_title=proposed_title,
                    proposed_angle=proposed_angle,
                    status="pending",
                )
            )

        return proposals

    def generate_post_text(self, proposal: Proposal, style_examples: List[str] = None) -> str:
        prompt = build_final_post_prompt(proposal, style_examples)
        response = self.client.chat(model=self.model, messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"].strip()

    def regenerate_proposal(self, proposal: Proposal, feedback: str) -> Proposal:
        prompt = build_regeneration_prompt(proposal, feedback)
        response = self.client.chat(model=self.model, messages=[{"role": "user", "content": prompt}], format="json")
        text = response["message"]["content"].strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            text = re.sub(r"\n```$", "", text)
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return proposal

        return Proposal(
            id=proposal.id,
            url=proposal.url,
            title=proposal.title,
            source=proposal.source,
            summary=proposal.summary,
            proposed_title=data.get("proposed_title", proposal.proposed_title),
            proposed_angle=data.get("proposed_angle", proposal.proposed_angle),
            status="pending",
            created_at=proposal.created_at,
            feedback=feedback,
        )

    def refine_post_text(self, current_copy: str, critique: str, style_examples: List[str] = None) -> str:
        prompt = build_copy_refinement_prompt(current_copy, critique, style_examples)
        response = self.client.chat(model=self.model, messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"].strip()
