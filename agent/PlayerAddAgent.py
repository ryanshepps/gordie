"""Player add agent for trading, picking up and dropping players"""

import logging
import os

logger = logging.getLogger(__name__)


if not os.environ.get("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY environment variable not set")
    raise ValueError("OPENAI_API_KEY environment variable not set")

player_add_task = """

"""
