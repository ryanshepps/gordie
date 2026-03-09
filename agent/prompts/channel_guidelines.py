CHANNEL_GUIDELINES = {
    "sms": """# CHANNEL: SMS (Text Message)
- Plain text only. No markdown, tables, lists, or headers.
- Casual and punchy like texting a friend. Use contractions.
- Lead with the answer, back it up with the one or two numbers that matter most.""",
    "email": """# CHANNEL: Email
- Send one comprehensive response with full stats tables, detailed analysis, and formatting.
- Use markdown for structure (headers, bold, tables).
- If the user references a topic you have no context for, proactively use search_past_conversations to check other threads before saying you don't know.""",
}


def get_channel_guidelines(channel: str) -> str:
    return CHANNEL_GUIDELINES.get(channel, CHANNEL_GUIDELINES["email"])
