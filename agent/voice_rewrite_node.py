"""Voice rewrite node that rewrites the supervisor's response in Gordie's persona."""

from typing import Literal

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Command

from agent.agent_state import AgentState
from agent.prompts.channel_guidelines import get_channel_guidelines
from agent.prompts.persona import PERSONA
from agent.prompts.phrasebook import PHRASEBOOK
from module.logger import get_logger

logger = get_logger(__name__)

_REWRITE_INSTRUCTION = """You are a voice rewriter. Your ONLY job is to rewrite the draft response below in Gordie's voice.

Rules:
- Rewrite EVERY sentence. Do not pass anything through verbatim.
- Preserve all stats, numbers, player names, URLs, and links exactly.
- Preserve the overall structure and information — just change the voice.
- If the draft is already in Gordie's voice, still punch it up. Make it hit harder.
- Do NOT add new analysis or opinions. Only rewrite what's there."""

_LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)


def _build_rewrite_prompt(channel: str) -> str:
    channel_guidelines = get_channel_guidelines(channel)
    return f"{PERSONA}\n{PHRASEBOOK}\n{channel_guidelines}\n\n{_REWRITE_INSTRUCTION}"


def _get_last_ai_content(messages: list[object]) -> tuple[str | None, int | None]:
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        msg_type = getattr(msg, "type", None)
        if msg_type is None and isinstance(msg, dict):
            msg_type = msg.get("type")
        if msg_type == "ai":
            content = getattr(msg, "content", None) if not isinstance(msg, dict) else msg.get("content")
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
        result = _LLM.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Rewrite this draft:\n\n{draft}"},
        ])
        rewritten = str(result.content)

        messages[msg_index] = AIMessage(content=rewritten)
        state["messages"] = messages
        state["response"] = rewritten

        logger.info(f"Voice rewrite complete: {rewritten[:200]}...")
    except Exception as e:
        logger.error(f"Voice rewrite failed, using original: {e}")

    return Command(goto="response", update=state)
