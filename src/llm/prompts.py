from typing import List

from src.db.models import Article, Proposal


def build_proposal_prompt(
    articles: List[Article],
    approved_history: List[Proposal] = None,
    rejected_history: List[Proposal] = None,
    global_feedback: str = None,
    count: int = 3,
) -> str:
    """Builds a structured prompt for the LLM to generate post proposals from curated articles and history feedback."""
    count = max(1, count)
    item_word = "proposal" if count == 1 else "proposals"

    # 1. Base instructions, anti-slop rules, and format constraints
    prompt = (
        "You are an experienced software engineer and thoughtful tech curator with a grounded, authentic human voice.\n"
        f"Review the following curated articles and propose exactly {count} separate, distinct, highly engaging social post {item_word} (proposals).\n\n"
        "--- CRITICAL ANTI-AI-SLOP DIRECTIVES (STRICTLY ENFORCED) ---\n"
        "- NEVER use generic AI buzzwords or corporate marketing hype:\n"
        "  Banned words: 'delve', 'delving', 'revolutionize', 'revolutionizing', 'game-changer', 'game-changing', "
        "'testament', 'tapestry', 'landscape', 'pivotal', 'beacon', 'foster', 'harness', 'supercharge', 'unleash', "
        "'skyrocket', 'demystify', 'spearhead', 'realm', 'plethora', 'cutting-edge', 'groundbreaking', 'ever-evolving', "
        "'paradigm shift', 'deep dive'.\n"
        "- NEVER use cliché AI rhetorical openings or tropes:\n"
        "  * 'In today's fast-paced world / digital landscape...'\n"
        "  * 'Imagine a world where...' or 'Sounds like science fiction? Think again.'\n"
        "  * 'Here's the kicker:' or 'Let's unpack this:' or 'Buckle up:'\n"
        "  * 'Discover how...' or 'Witness the future of...'\n"
        "  * 'It's not just X, it's a testament to Y.'\n"
        "- Sound like a real person: Grounded, conversational, and intellectual — like an experienced engineer chatting with peers.\n"
        "- For titles: Write clear, punchy hooks focused on real engineering substance, trade-offs, or relatable observations (NO clickbait, NO corporate jargon).\n"
        "- For angles: Outline the practical core in 2-3 concise sentences: what problem was solved, what architectural compromise was made, or what lesson was learned.\n\n"
        "For each proposal, you MUST assign it to one of the raw articles by matching its 'url'.\n"
        "Each proposal must include:\n"
        "1. 'proposed_title': An authentic, compelling hook/title suited for technical readers on LinkedIn.\n"
        "2. 'proposed_angle': A 2-3 sentence concept outlining the key technical message, real-world trade-off, and grounded tone.\n"
        "3. 'url': The exact URL of the original article this proposal is based on.\n\n"
        f"CRITICAL: You must output ONLY a valid JSON object containing a 'proposals' array with exactly {count} distinct proposal object(s). Match this exact JSON schema format:\n"
        "{\n"
        '  "proposals": [\n'
        "    {\n"
        '      "proposed_title": "compelling title/hook for article 1",\n'
        '      "proposed_angle": "the 2-3 sentence description of the concept and tone for article 1",\n'
        '      "url": "the matching original article 1 url"\n'
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

    prompt += f"Generate exactly {count} unique {item_word} based on the articles above. Remember, return ONLY raw JSON array. DO NOT wrap in markdown code blocks."
    return prompt


def build_final_post_prompt(proposal: Proposal, style_examples: List[str] = None) -> str:
    """Builds a prompt for expanding an approved proposal title and angle into a full LinkedIn post."""
    prompt = (
        "You are an experienced software engineer and authentic technical writer.\n"
        "Your task is to write a single, natural, human LinkedIn post based on this approved title and concept:\n\n"
        f"Approved Title: {proposal.proposed_title}\n"
        f"Approved Angle: {proposal.proposed_angle}\n"
        f"Original Article URL: {proposal.url}\n\n"
        "--- CRITICAL ANTI-AI-SLOP RULES (STRICTLY FORBIDDEN) ---\n"
        "- NEVER use generic AI buzzwords or corporate filler:\n"
        "  Banned words: 'delve', 'delving', 'revolutionize', 'revolutionizing', 'game-changer', 'game-changing', "
        "'testament', 'tapestry', 'landscape', 'pivotal', 'beacon', 'foster', 'harness', 'supercharge', 'unleash', "
        "'skyrocket', 'demystify', 'spearhead', 'realm', 'plethora', 'cutting-edge', 'groundbreaking', 'ever-evolving', "
        "'paradigm shift', 'deep dive'.\n"
        "- NEVER use cliché AI rhetorical openings or tropes:\n"
        "  * 'In today's fast-paced world / digital landscape...'\n"
        "  * 'Imagine a world where...' or 'Sounds like science fiction? Think again.'\n"
        "  * 'Here's the kicker:' or 'Let's unpack this:' or 'Buckle up:'\n"
        "  * 'Discover how...' or 'Witness the future of...'\n"
        "  * 'It's not just X, it's a testament to Y.'\n"
        "- NO hyper-enthusiastic cheerleader tone or excessive exclamation points.\n"
        "--- STRICT LENGTH & BREVITY CONSTRAINTS (KEEP IT SHORT) ---\n"
        "- Total post length must be SHORT: strictly between 100 and 180 words maximum (about 3 to 4 short paragraphs total).\n"
        "- Do NOT write long essays, wordy manifestos, or multi-part breakdowns. Readers scan quickly.\n"
        "- Be punchy and concise: state the observation, explain the technical takeaway or trade-off in a few sentences, share the link, and stop.\n\n"
        "--- HUMAN VOICE & TONE GUIDELINES ---\n"
        "- Sound like a real human engineer: Honest, pragmatic, relaxed, and observant.\n"
        "- Hook the reader with a relatable observation, contrarian insight, or practical dilemma in the first 1-2 lines.\n"
        "- Structure with comfortable line breaks and short paragraphs (1-3 sentences each) for effortless reading on mobile screens.\n"
        "- Focus on real substance: architectural decisions, engineering trade-offs, operational costs, and practical lessons (what worked vs what broke).\n"
        "- Use natural language and contractions (it's, that's, don't, we've) for an authentic human cadence.\n"
        "- Smoothly introduce the original article as an interesting resource (e.g. 'Read the full breakdown: ' or 'Worth checking out: ' followed by " + proposal.url + ").\n"
        "- Include 3-5 clean, relevant technical hashtags at the very bottom (e.g. #softwareengineering #architecture).\n\n"
        "Return ONLY the markdown-formatted post text. Do not include introductory notes, explanations, or quotes."
    )

    if style_examples:
        prompt += (
            "\n\n--- REFERENCE WRITING SAMPLES (MIMIC THIS AUTHOR'S VOICE & CONCISE BREVITY EXACTLY) ---\n"
            "Deconstruct, analyze, and mimic this user's tone, voice, paragraph layouts, line-spacing, and messaging style EXACTLY. "
            "Notice how short and punchy these posts are (around 100-150 words). Do NOT exceed their length:\n\n"
        )
        for i, sample in enumerate(style_examples, 1):
            prompt += f'Writing Sample {i}:\n"""\n{sample}\n"""\n\n'

    return prompt


def build_regeneration_prompt(proposal: Proposal, feedback: str) -> str:
    """Builds a prompt for rewriting and refining an existing proposal based on custom user feedback critiques."""
    prompt = (
        "You are an expert technical editor with an authentic, human tone.\n"
        "You previously proposed this LinkedIn post draft concept:\n"
        f"  - Title: {proposal.proposed_title}\n"
        f"  - Concept/Angle: {proposal.proposed_angle}\n"
        f"  - Original Article Link: {proposal.url}\n\n"
        "The user has reviewed your draft and provided this specific feedback/critique:\n"
        f"  - '{feedback}'\n\n"
        "Your task is to rewrite and refine the proposal's proposed_title and proposed_angle to strictly satisfy their feedback.\n\n"
        "TONE & ANTI-SLOP RULES:\n"
        "- Keep it grounded, natural, and human. Zero AI buzzwords ('revolutionize', 'game-changer', 'delve', 'testament', 'ever-evolving', 'supercharge').\n"
        "- No marketing hype or clickbait. Focus on real technical value, engineering dilemmas, or architectural trade-offs.\n\n"
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
        "You are an elite developer, thoughtful tech writer, and expert copy editor.\n"
        "You previously generated this complete LinkedIn post copy:\n\n"
        f'"""\n{current_copy}\n"""\n\n'
        "The user has reviewed your draft and provided this specific refinement feedback/critique:\n"
        f"  - '{critique}'\n\n"
        "Your task is to rewrite, polish, and edit the post copy to strictly incorporate their feedback.\n\n"
        "CRITICAL ANTI-AI-SLOP & HUMAN VOICE RULES:\n"
        "- Strip out any AI buzzwords ('delve', 'revolutionize', 'game-changer', 'testament', 'tapestry', 'landscape', 'supercharge', 'unleash', 'beacon', 'cutting-edge').\n"
        "- Remove corporate clichés and overly excited cheerleader phrasing.\n"
        "- Keep emoji usage minimal (0-1 in the entire post) or completely absent if requested.\n"
        "- Preserve an authentic, grounded human tone: realistic engineering trade-offs, natural contractions, and comfortable short paragraphs.\n"
        "- STRICT BREVITY: Keep the total post short and punchy (strictly between 100 and 180 words maximum, 3 to 4 short paragraphs total). Do NOT make it a long essay.\n"
        "- Return ONLY the refined, polished markdown-formatted post text. Do not include introductory notes, explanations, or quotes."
    )
    if style_examples:
        prompt += (
            "\n\n--- REFERENCE WRITING SAMPLES (MIMIC THIS AUTHOR'S VOICE, CADENCE & BREVITY) ---\n"
            "Deconstruct, analyze, and mimic this user's tone, voice, paragraph layouts, line-spacing, and messaging style EXACTLY. "
            "Notice how short and punchy these posts are (around 100-150 words). Ensure the refined post matches this concise length:\n\n"
        )
        for i, ex in enumerate(style_examples, 1):
            prompt += f'Sample {i}:\n"""\n{ex}\n"""\n\n'
    return prompt

