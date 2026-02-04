"""Shared email formatting utilities.

Provides consistent markdown-to-HTML conversion and email formatting
across all email-sending components (graph nodes and scheduled jobs).
"""

import html
from dataclasses import dataclass
from enum import Enum

import markdown2

MARKDOWN_EXTRAS = ["tables", "fenced-code-blocks", "strike", "cuddled-lists"]


class FooterType(Enum):
    """Type of footer to append to emails."""

    NONE = "none"
    BETA = "beta"
    UNSUBSCRIBE = "unsubscribe"


@dataclass
class EmailContent:
    """Formatted email content ready for sending."""

    text_body: str
    html_body: str


def markdown_to_html(content: str) -> str:
    """Convert markdown content to HTML using standard extras.

    Args:
        content: Markdown-formatted text

    Returns:
        HTML string with converted markdown
    """
    return markdown2.markdown(content, extras=MARKDOWN_EXTRAS)


def wrap_html_document(html_content: str) -> str:
    """Wrap HTML content in a full document structure.

    Args:
        html_content: HTML body content

    Returns:
        Complete HTML document with DOCTYPE, head, and body
    """
    body_style = (
        "font-family: Arial, sans-serif; line-height: 1.6; color: #333; "
        "max-width: 600px; margin: 0 auto; padding: 20px;"
    )

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="{body_style}">
{html_content}
</body>
</html>"""


def format_quoted_reply_html(original_message: str) -> str:
    """Format the original message as a quoted HTML block for email replies.

    Args:
        original_message: The original user message to quote

    Returns:
        HTML formatted blockquote
    """
    escaped = html.escape(original_message.strip())
    escaped = escaped.replace("\n", "<br>")

    blockquote_style = (
        "margin: 0; padding: 10px 15px; border-left: 3px solid #ccc; "
        "background-color: #f9f9f9; color: #555;"
    )
    return f"""
<div style="margin-top: 20px;">
    <p style="color: #666; font-size: 12px; margin-bottom: 10px;">You wrote:</p>
    <blockquote style="{blockquote_style}">
        {escaped}
    </blockquote>
</div>
"""


def get_beta_footer_html() -> str:
    """Get the beta disclaimer footer HTML.

    Returns:
        HTML footer with beta notice
    """
    return """
<div style="margin-top: 20px;">
    <p style="color: #888; font-size: 12px; font-style: italic; margin: 0;">
        Note: Gordie is still in beta. He will make mistakes.
    </p>
</div>
"""


def get_beta_footer_text() -> str:
    """Get the beta disclaimer footer as plain text.

    Returns:
        Plain text beta notice
    """
    return "\n\nNote: Gordie is still in beta. He will make mistakes.\n"


def get_unsubscribe_footer_html() -> str:
    """Get the unsubscribe footer HTML.

    Returns:
        HTML footer with unsubscribe instructions
    """
    footer_style = (
        "margin-top: 30px; padding-top: 20px; border-top: 1px solid #ccc; "
        "font-size: 12px; color: #666;"
    )

    return f"""
<div style="{footer_style}">
    <p>To stop receiving these weekly updates, just reply to this email
    and ask me to turn them off.</p>
</div>
"""


def get_unsubscribe_footer_text() -> str:
    """Get the unsubscribe footer as plain text.

    Returns:
        Plain text unsubscribe notice
    """
    return (
        "\n\nTo stop receiving these weekly updates, just reply to this email "
        "and ask me to turn them off.\n"
    )


def format_email(
    content: str,
    footer_type: FooterType = FooterType.NONE,
    quoted_reply: str | None = None,
    stats_html: str | None = None,
) -> EmailContent:
    """Format email content with markdown conversion and optional components.

    Args:
        content: Markdown-formatted email body content
        footer_type: Type of footer to append (NONE, BETA, or UNSUBSCRIBE)
        quoted_reply: Optional original message to include as quoted reply
        stats_html: Optional HTML stats table to include

    Returns:
        EmailContent with text_body and html_body ready for sending
    """
    # Build text body
    text_body = content
    if footer_type == FooterType.BETA:
        text_body = text_body + get_beta_footer_text()
    elif footer_type == FooterType.UNSUBSCRIBE:
        text_body = text_body + get_unsubscribe_footer_text()

    # Build HTML body
    html_body = markdown_to_html(content)

    if stats_html:
        html_body = html_body + stats_html

    if quoted_reply:
        html_body = html_body + format_quoted_reply_html(quoted_reply)

    if footer_type == FooterType.BETA:
        html_body = html_body + get_beta_footer_html()
    elif footer_type == FooterType.UNSUBSCRIBE:
        html_body = html_body + get_unsubscribe_footer_html()

    html_body = wrap_html_document(html_body)

    return EmailContent(text_body=text_body, html_body=html_body)
