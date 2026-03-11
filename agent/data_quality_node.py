"""Data quality node that validates the supervisor's response for statistical rigor.

When issues are found, this node routes back to the supervisor with specific
feedback so it can redo its analysis with proper context. If no issues are
found (or the retry limit is reached), it passes through to voice_rewrite.
"""

from typing import Literal

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Command

from agent.agent_state import AgentState
from module.logger import get_logger

logger = get_logger(__name__)

_MAX_RETRIES = 1

_llm_instance: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return _llm_instance

_SYSTEM_PROMPT = """\
You are a data-quality reviewer for a fantasy hockey AI assistant.

You will receive the assistant's draft response. Check it against every rule below.
If ANY rule is violated, respond with a JSON object:

{"passed": false, "feedback": "<specific, actionable feedback for the assistant>"}

If ALL rules pass, respond with exactly:

{"passed": true}

## Rules

### Games Played Context
When the response compares players or makes roster recommendations (start/sit,
drop/add, trade) using season stats, it MUST acknowledge differences in games played
if the players have meaningfully different GP totals (roughly 10+ games apart).

Raw totals without GP context are misleading — a player returning from injury or a
recent call-up will have lower totals but may be producing at a higher per-game rate.

When this rule is violated, your feedback MUST include the specific players and
their games-played discrepancy. For example:
"Do not recommend dropping Player X based on raw totals alone. He has only played
32 games compared to Player Y's 58 — re-evaluate using per-game rates."
"""


def _get_last_ai_content(messages: list[object]) -> str | None:
    for msg in reversed(messages):
        msg_type = getattr(msg, "type", None)
        if msg_type is None and isinstance(msg, dict):
            msg_type = msg.get("type")
        if msg_type == "ai":
            content = (
                getattr(msg, "content", None)
                if not isinstance(msg, dict)
                else msg.get("content")
            )
            if content:
                return str(content)
    return None


def _parse_result(raw: str) -> tuple[bool, str | None]:
    import json

    try:
        parsed = json.loads(raw)
        return parsed.get("passed", True), parsed.get("feedback")
    except json.JSONDecodeError:
        lower = raw.lower()
        if '"passed": false' in lower or '"passed":false' in lower:
            start = lower.find('"feedback"')
            if start != -1:
                return False, raw[start + 12 :].strip().strip('"').strip("}")
        return True, None


def data_quality_node(
    state: AgentState,
) -> Command[Literal["supervisor", "voice_rewrite"]]:
    """Check the supervisor's response for data quality issues.

    If issues are found and retries remain, injects feedback and routes back
    to the supervisor. Otherwise passes through to voice_rewrite.
    """
    messages = list(state.get("messages", []))
    retries = state.get("data_quality_retries", 0)

    draft = _get_last_ai_content(messages)

    if not draft:
        logger.warning("No AI message found for data quality check")
        return Command(goto="voice_rewrite", update=state)

    if retries >= _MAX_RETRIES:
        logger.info("Data quality retry limit reached — passing through")
        return Command(goto="voice_rewrite", update=state)

    try:
        result = _get_llm().invoke([
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Draft response:\n\n{draft}"},
        ])
        passed, feedback = _parse_result(str(result.content))

        if passed or not feedback:
            logger.info("Data quality check passed")
            return Command(goto="voice_rewrite", update=state)

        logger.info(f"Data quality issue found, routing back to supervisor: {feedback}")
        feedback_msg = SystemMessage(
            content=(
                f"[DATA QUALITY REVIEWER] Your previous response has a data quality "
                f"issue. Please redo your analysis with this feedback:\n\n{feedback}"
            )
        )
        return Command(
            goto="supervisor",
            update={
                "messages": [*messages, feedback_msg],
                "data_quality_retries": retries + 1,
            },
        )
    except Exception as e:
        logger.error(f"Data quality check failed, passing through: {e}")
        return Command(goto="voice_rewrite", update=state)
