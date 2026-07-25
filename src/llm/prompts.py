from typing import List

from src.db.models import Article, Proposal


def build_proposal_prompt(
    articles: List[Article],
    approved_history: List[Proposal] = None,
    rejected_history: List[Proposal] = None,
    global_feedback: str = None,
) -> str:
    """Builds a structured prompt for the LLM to generate 3-5 distinct proposals from curated articles and history feedback."""

    # 1. Base instructions and format constraint
    prompt = (
        "You are an expert LinkedIn Content Strategist and tech curator.\n"
        "Review the following curated articles and propose exactly 3 to 5 separate, distinct, highly engaging social post concepts (proposals).\n\n"
        "For each proposal, you MUST assign it to one of the raw articles by matching its 'url'.\n"
        "Each proposal must include:\n"
        "1. 'proposed_title': A compelling, click-worthy hook/title suited for a technical LinkedIn audience.\n"
        "2. 'proposed_angle': A 2-3 sentence concept outlining the key message, tone, and angle of the post.\n"
        "3. 'url': The exact URL of the original article this proposal is based on.\n\n"
        "CRITICAL: You must output ONLY a valid JSON object containing a 'proposals' array with 3 to 5 separate distinct proposal objects. Match this exact JSON schema format:\n"
        "{\n"
        '  "proposals": [\n'
        "    {\n"
        '      "proposed_title": "compelling title/hook for article 1",\n'
        '      "proposed_angle": "the 2-3 sentence description of the concept and tone for article 1",\n'
        '      "url": "the matching original article 1 url"\n'
        "    },\n"
        "    {\n"
        '      "proposed_title": "compelling title/hook for article 2",\n'
        '      "proposed_angle": "the 2-3 sentence description of the concept and tone for article 2",\n'
        '      "url": "the matching original article 2 url"\n'
        "    },\n"
        "    {\n"
        '      "proposed_title": "compelling title/hook for article 3",\n'
        '      "proposed_angle": "the 2-3 sentence description of the concept and tone for article 3",\n'
        '      "url": "the matching original article 3 url"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Do not include any Markdown code block wrapping (such as ```json ... ```), preamble, or postamble text. Return ONLY raw JSON.\n\n"
    )

    # 1.5 Inject Global Preferences (Overall Guidance)
    if global_feedback:
        prompt += f"--- OVERALL USER PREFERENCES (Follow this high-level guidance for topic selection & copywriting) ---\n- {global_feedback}\n\n"

    # 2. Inject Approved & Posted History (Positive Constraints)
    if approved_history:
        prompt += "--- USER PREFERENCES (Approved & Published Concepts - DO MORE OF THIS STYLE & TOPIC) ---\n"
        prompt += "Note: Items labeled [PUBLISHED SUCCESS] represent posts the user successfully shared on LinkedIn and have the absolute highest priority. Items labeled [APPROVED DRAFT] are also positive references.\n\n"
        for i, item in enumerate(approved_history, 1):
            status_tag = "PUBLISHED SUCCESS" if item.status.lower() == "posted" else "APPROVED DRAFT"
            prompt += f"Example {i} [{status_tag}]:\n"
            prompt += f"  - Title: {item.proposed_title}\n"
            prompt += f"  - Concept/Angle: {item.proposed_angle}\n\n"

    # 3. Inject Rejected History (Negative Constraints)
    if rejected_history:
        prompt += "--- USER PREFERENCES (Rejected Concepts - AVOID THESE STYLES & TOPICS) ---\n"
        for i, item in enumerate(rejected_history, 1):
            prompt += f"Never Do {i}:\n"
            prompt += f"  - Title: {item.proposed_title}\n"
            prompt += f"  - Concept/Angle: {item.proposed_angle}\n\n"

    # 4. Inject Curated Articles
    prompt += "--- CURATED TECH ARTICLES TO PROPOSE ---\n"
    for i, article in enumerate(articles, 1):
        prompt += f"Article {i}:\n"
        prompt += f"  - Title: {article.title}\n"
        prompt += f"  - Source: {article.source}\n"
        prompt += f"  - URL: {article.url}\n"
        prompt += f"  - Summary: {article.summary}\n\n"

    prompt += "Generate 3 to 5 unique proposals based on the articles above. Remember, return ONLY raw JSON array. DO NOT wrap in markdown code blocks."
    return prompt


def build_final_post_prompt(proposal: Proposal, style_examples: List[str] = None) -> str:
    """Builds a prompt for expanding an approved proposal title and angle into a full LinkedIn post."""
    prompt = (
        "You are an elite developer and expert technical copywriter for LinkedIn.\n"
        "Your task is to write a single highly engaging, professional LinkedIn post based on this approved title and concept:\n\n"
        f"Approved Title: {proposal.proposed_title}\n"
        f"Approved Angle: {proposal.proposed_angle}\n"
        f"Original Article URL: {proposal.url}\n\n"
        "Writing constraints:\n"
        "- Hook the reader in the first sentence.\n"
        "- Structure with clear paragraphs and line breaks for readability (avoid blocks of dense text).\n"
        "- Explain the technical importance, trade-offs, or insights clearly.\n"
        "- Keep the tone professional, intellectual, yet highly engaging and accessible.\n"
        "- Include 3-5 relevant hashtags at the very bottom (e.g. #softwareengineering, #artificialintelligence, etc.).\n"
        "- Smoothly mention the original link as a resource: " + proposal.url + "\n\n"
        "Return ONLY the markdown-formatted post text. Do not include introductory notes, explanations, or quotes."
    )

    if style_examples:
        prompt += "\n\n--- REFERENCE WRITING SAMPLES (Deconstruct, analyze, and mimic this user's tone, voice, paragraph layouts, line-spacing, and messaging style EXACTLY) ---\n"
        for i, sample in enumerate(style_examples, 1):
            prompt += f'Writing Sample {i}:\n"""\n{sample}\n"""\n\n'

    return prompt


def build_regeneration_prompt(proposal: Proposal, feedback: str) -> str:
    """Builds a prompt for rewriting and refining an existing proposal based on custom user feedback critiques."""
    prompt = (
        "You are an expert LinkedIn copywriter and tech content editor.\n"
        "You previously proposed this LinkedIn post draft concept:\n"
        f"  - Title: {proposal.proposed_title}\n"
        f"  - Concept/Angle: {proposal.proposed_angle}\n"
        f"  - Original Article Link: {proposal.url}\n\n"
        "The user has reviewed your draft and provided this specific feedback/critique:\n"
        f"  - '{feedback}'\n\n"
        "Your task is to rewrite and refine the proposal's proposed_title and proposed_angle to strictly satisfy their feedback.\n"
        "CRITICAL: You must output ONLY a valid JSON object matching this exact schema:\n"
        "{\n"
        '  "proposed_title": "new refined title",\n'
        '  "proposed_angle": "new refined 2-3 sentence description of the concept and tone"\n'
        "}\n"
        "Do not include any Markdown code block wrapping (such as ```json ... ```), preamble, or postamble text. Return ONLY raw JSON."
    )
    return prompt


def build_copy_refinement_prompt(current_copy: str, critique: str, style_examples: List[str] = None) -> str:
    """Builds a prompt for iteratively editing and refining the expanded copywriting based on user text critiques."""
    prompt = (
        "You are an elite LinkedIn content editor and expert technical copywriter.\n"
        "You previously generated this complete LinkedIn post copy:\n\n"
        f'"""\n{current_copy}\n"""\n\n'
        "The user has reviewed your draft and provided this specific refinement feedback/critique:\n"
        f"  - '{critique}'\n\n"
        "Your task is to rewrite, polish, and edit the post copy to strictly incorporate their feedback.\n"
        "Maintain the technical depth, engaging hooks, and professional tone.\n"
        "Return ONLY the refined, polished markdown-formatted post text. Do not include introductory notes, explanations, or quotes."
    )
    if style_examples:
        prompt += "\n\n--- REFERENCE WRITING SAMPLES (Deconstruct, analyze, and mimic this user's tone, voice, paragraph layouts, line-spacing, and messaging style EXACTLY) ---\n"
        for i, ex in enumerate(style_examples, 1):
            prompt += f'Sample {i}:\n"""\n{ex}\n"""\n\n'
    return prompt
