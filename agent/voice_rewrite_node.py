"""Voice rewrite node that rewrites the supervisor's response in Gordie's persona."""

from collections.abc import Callable
from typing import Literal

from langchain_core.messages import AIMessage
from langgraph.types import Command

from agent.agent_state import AgentState
from agent.prompts.persona import PERSONA
from agent.prompts.phrasebook import PHRASEBOOK
from module.llm import make_llm
from module.logger import get_logger

logger = get_logger(__name__)

_REWRITE_BASE = """You are a voice rewriter. Your ONLY job is to rewrite the draft response below in Gordie's voice.

Rules:
- Rewrite EVERY sentence. Do not pass anything through verbatim.
- Preserve all stats, numbers, player names, URLs, and links exactly.
- If the draft is already in Gordie's voice, still punch it up. Make it hit harder.
- Do NOT add new analysis or opinions. Only rewrite what's there."""

_LLM = make_llm(temperature=0.5)


def _build_rewrite_prompt() -> str:
    return f"{PERSONA}\n{PHRASEBOOK}\n\n{_REWRITE_BASE}"


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


def make_voice_rewrite_node() -> Callable[[AgentState], Command[Literal["response"]]]:
    def voice_rewrite_node(state: AgentState) -> Command[Literal["response"]]:
        """Rewrite the supervisor's response in Gordie's voice before dispatching."""
        messages = list(state.get("messages", []))
        draft, msg_index = _get_last_ai_content(messages)

        if not draft or msg_index is None:
            logger.warning("No AI message found to rewrite")
            return Command(goto="response", update=state)

        system_prompt = _build_rewrite_prompt()

        try:
            rewritten = _invoke_rewrite(system_prompt, draft)

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

    return voice_rewrite_node
