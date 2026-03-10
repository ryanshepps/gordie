from agent.context_validator import ValidationResult
from agent.prompts.channel_guidelines import get_channel_guidelines
from agent.prompts.persona import PERSONA
from agent.prompts.phrasebook import PHRASEBOOK
from agent.prompts.rules import RULES


def assemble_system_prompt(
    validation_result: ValidationResult, channel: str, user_email: str
) -> str:
    channel_guidelines = get_channel_guidelines(channel)

    context_parts = ["# CONTEXT", f"User email: {user_email}", "", validation_result.system_message]
    if validation_result.league_id:
        context_parts.append(f"\nLeague ID: {validation_result.league_id}")
    if validation_result.team_id:
        context_parts.append(f"Team ID: {validation_result.team_id}")
    context_section = "\n".join(context_parts)

    return f"{PERSONA}\n{PHRASEBOOK}\n{RULES}\n{channel_guidelines}\n\n{context_section}"
