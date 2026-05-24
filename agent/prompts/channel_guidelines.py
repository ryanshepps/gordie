from data.models import Medium

CHANNEL_GUIDELINES = {
    Medium.SMS: """# CHANNEL: SMS (Text Message)
- Plain text only. No markdown, tables, lists, or headers.
- Casual and punchy like texting a friend. Use contractions.
- Lead with the answer, back it up with the one or two numbers that matter most.""",
    Medium.EMAIL: """# CHANNEL: Email
- Send one comprehensive response with full stats tables, detailed analysis, and formatting.
- Use markdown for structure (headers, bold, tables).
- If the user references a topic you have no context for, proactively use search_past_conversations to check other threads before saying you don't know.""",
    Medium.DISCORD: """# CHANNEL: Discord
- Use Discord-flavored markdown. No HTML.
- Keep answers scannable in a chat window: short paragraphs, bullets, and code blocks for stat tables.
- Lead with the answer, then include the most relevant supporting numbers.""",
}


def get_channel_guidelines(channel: Medium | str) -> str:
    medium = channel if isinstance(channel, Medium) else Medium(channel)
    return CHANNEL_GUIDELINES.get(medium, CHANNEL_GUIDELINES[Medium.EMAIL])
