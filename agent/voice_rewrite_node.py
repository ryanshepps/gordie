"""Voice rewrite node that rewrites the supervisor's response in Gordie's persona."""

from typing import Literal

from langchain_core.messages import AIMessage
from langgraph.types import Command

from agent.agent_state import AgentState
from agent.prompts.channel_guidelines import get_channel_guidelines
from agent.prompts.persona import PERSONA
from agent.prompts.phrasebook import PHRASEBOOK
from module.llm import make_llm
from module.logger import get_logger

logger = get_logger(__name__)

SMS_MAX_LENGTH = 800

_REWRITE_BASE = """You are a voice rewriter. Your ONLY job is to rewrite the draft response below in Gordie's voice.

Rules:
- Rewrite EVERY sentence. Do not pass anything through verbatim.
- Preserve all stats, numbers, player names, URLs, and links exactly.
- If the draft is already in Gordie's voice, still punch it up. Make it hit harder.
- Do NOT add new analysis or opinions. Only rewrite what's there."""

_SMS_RULES = """
- Aggressively condense. Cut all supporting detail that isn't essential.
- Lead with the recommendation, back it up with the one or two numbers that matter most.
- Never exceed 600 characters. Treat this as a hard limit."""

_EMAIL_RULES = """
- Preserve the overall structure and information — just change the voice."""

_CONDENSE_INSTRUCTION = (
    "Your previous rewrite was {length} characters. "
    "SMS messages MUST be under {limit} characters. "
    "Condense aggressively — keep only the core recommendation and 1-2 key stats. "
    "Cut everything else."
)

_LLM = make_llm(temperature=0.5)


def _build_rewrite_prompt(channel: str) -> str:
    channel_guidelines = get_channel_guidelines(channel)
    channel_rules = _SMS_RULES if channel == "sms" else _EMAIL_RULES
    return f"{PERSONA}\n{PHRASEBOOK}\n{channel_guidelines}\n\n{_REWRITE_BASE}{channel_rules}"


def _invoke_rewrite(system_prompt: str, draft: str) -> str:
    result = _LLM.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Rewrite this draft:\n\n{draft}"},
        ]
    )
    return str(result.content)


def _get_last_ai_content(messages: list[object]) -> tuple[str | None, int | None]:
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        msg_type = getattr(msg, "type", None)
        if msg_type is None and isinstance(msg, dict):
            msg_type = msg.get("type")
        if msg_type == "ai":
            content = (
                getattr(msg, "content", None) if not isinstance(msg, dict) else msg.get("content")
            )
            if content:
                return str(content), i
    return None, None


def voice_rewrite_node(state: AgentState) -> Command[Literal["response"]]:
    """Rewrite the supervisor's response in Gordie's voice before dispatching."""
    messages = list(state.get("messages", []))
    channel = state.get("channel", "email")

    draft, msg_index = _get_last_ai_content(messages)

    if not draft or msg_index is None:
        logger.warning("No AI message found to rewrite")
        return Command(goto="response", update=state)

    system_prompt = _build_rewrite_prompt(channel)

    try:
        rewritten = _invoke_rewrite(system_prompt, draft)

        if channel == "sms" and len(rewritten) > SMS_MAX_LENGTH:
            logger.info(
                f"SMS rewrite too long ({len(rewritten)} chars), retrying with condense instruction"
            )
            condense_prompt = (
                f"{system_prompt}\n\n"
                f"{_CONDENSE_INSTRUCTION.format(length=len(rewritten), limit=SMS_MAX_LENGTH)}"
            )
            rewritten = _invoke_rewrite(condense_prompt, rewritten)
            logger.info(f"SMS condense retry result: {len(rewritten)} chars")

        messages[msg_index] = AIMessage(content=rewritten)
        state_update: dict[str, object] = {
            "messages": messages,
            "response": rewritten,
        }

        logger.info(f"Voice rewrite complete ({len(rewritten)} chars): {rewritten[:200]}...")
    except Exception as e:
        logger.error(f"Voice rewrite failed, using original: {e}")
        state_update = {"messages": messages}

    return Command(goto="response", update={**state, **state_update})
