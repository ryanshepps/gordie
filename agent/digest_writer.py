"""LLM-powered digest content writer using Gordie's persona."""

from __future__ import annotations

from enum import Enum

from langchain_openai import ChatOpenAI

from agent.news.news_digest import NewsDigest
from agent.prompts.channel_guidelines import get_channel_guidelines
from agent.prompts.persona import PERSONA
from data.pydantic_models import DigestData
from module.logger import get_logger

logger = get_logger(__name__)


class DigestType(Enum):
    WEEKLY = "weekly"
    NEWS = "news"


WRITING_INSTRUCTIONS: dict[DigestType, str] = {
    DigestType.WEEKLY: (
        "Write like you're texting your fantasy hockey buddy after watching a week of games. "
        "Cover matchup, top/bottom performers, injuries, free agent tips, schedule advice. "
        "Keep it under 600 words."
    ),
    DigestType.NEWS: (
        "Write like you're DMing breaking news that affects their team. "
        "Urgent, direct, actionable. Keep it under 400 words."
    ),
}


def _build_system_prompt(digest_type: DigestType) -> str:
    channel_guidelines = get_channel_guidelines("email")
    instructions = WRITING_INSTRUCTIONS[digest_type]
    return f"{PERSONA}\n\n{channel_guidelines}\n\n# TASK\n{instructions}"


def write_digest_content(digest_data: DigestData | NewsDigest, digest_type: DigestType) -> str:
    system_prompt = _build_system_prompt(digest_type)
    user_message = (
        "Write a digest email based on this data. "
        "Return only the markdown content, no preamble.\n\n"
        f"{digest_data.model_dump_json(indent=2)}"
    )

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ])

    return str(response.content)
