"""LLM-powered digest content writer using Gordie's persona."""

from __future__ import annotations

from enum import Enum

from langchain_openai import ChatOpenAI

from agent.news.news_digest import NewsDigest
from agent.prompts.channel_guidelines import get_channel_guidelines
from agent.prompts.persona import PERSONA
from agent.prompts.phrasebook import PHRASEBOOK
from data.pydantic_models import DigestData
from module.logger import get_logger

logger = get_logger(__name__)


class DigestType(Enum):
    WEEKLY = "weekly"
    NEWS = "news"


WRITING_INSTRUCTIONS: dict[tuple[DigestType, str], str] = {
    (DigestType.WEEKLY, "email"): (
        "Write like you're texting your fantasy hockey buddy after watching a week of games. "
        "Cover matchup, top/bottom performers, injuries, free agent tips, schedule advice. "
        "Keep it under 600 words."
    ),
    (DigestType.WEEKLY, "sms"): (
        "Write like you're texting your fantasy hockey buddy after watching a week of games. "
        "Cover the most important highlights: matchup, top performers, key injuries. "
        "No markdown. Keep it under 200 words."
    ),
    (DigestType.NEWS, "email"): (
        "Write like you're DMing breaking news that affects their team. "
        "Urgent, direct, actionable. Keep it under 400 words.\n\n"
        "RULES:\n"
        "- Never say \"tonight\" for a player unless has_game_today is true\n"
        "- For IR players with already_on_ir_slot=true, do NOT suggest finding a replacement\n"
        "- For new injuries without a game today, mention when their next game is instead of \"tonight\"\n"
        "- Only recommend \"start X over Y\" when position_conflicts exist in the data\n"
        "- If bench_reminders exist, casually remind the user to move those players to active slots\n"
        "- If there are no position_conflicts and no bench_reminders, skip the lineup section entirely\n"
        "- Use the injury alert fields (has_game_today, is_new_injury, already_on_ir_slot) to guide tone\n"
        "- Do NOT end with questions, offers to help, or calls to action (e.g. \"Want me to check waivers?\"). Just deliver the news and sign off."
    ),
    (DigestType.NEWS, "sms"): (
        "Write like you're DMing breaking news that affects their team. "
        "Urgent, direct, actionable. No markdown. Keep it under 150 words.\n\n"
        "RULES:\n"
        "- Never say \"tonight\" for a player unless has_game_today is true\n"
        "- For IR players with already_on_ir_slot=true, do NOT suggest finding a replacement\n"
        "- For new injuries without a game today, mention when their next game is instead of \"tonight\"\n"
        "- Only recommend \"start X over Y\" when position_conflicts exist in the data\n"
        "- If bench_reminders exist, casually remind the user to move those players to active slots\n"
        "- If there are no position_conflicts and no bench_reminders, skip the lineup section entirely\n"
        "- Do NOT end with questions, offers to help, or calls to action (e.g. \"Want me to check waivers?\"). Just deliver the news and sign off."
    ),
}


def _build_system_prompt(digest_type: DigestType, channel: str = "email") -> str:
    channel_guidelines = get_channel_guidelines(channel)
    instructions = WRITING_INSTRUCTIONS[(digest_type, channel)]
    return f"{PERSONA}\n{PHRASEBOOK}\n\n{channel_guidelines}\n\n# TASK\n{instructions}"


def write_digest_content(
    digest_data: DigestData | NewsDigest,
    digest_type: DigestType,
    channel: str = "email",
) -> str:
    system_prompt = _build_system_prompt(digest_type, channel)
    user_message = (
        "Write a digest based on this data. "
        "Return only the markdown content, no preamble.\n\n"
        f"{digest_data.model_dump_json(indent=2)}"
    )

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ])

    return str(response.content)
