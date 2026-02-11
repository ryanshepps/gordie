"""Repository class for web thread records."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from data.repository import Repository


class WebThreadRepository(Repository):
    """Repository for managing web thread URL mappings."""

    def __init__(self, session: Session | None = None):
        super().__init__("web_threads", session)

    def create_web_thread(self, thread_id: str) -> str:
        """Create a web thread with an unguessable UUID.

        Args:
            thread_id: The conversation thread_id to link to

        Returns:
            The generated UUID used in the web URL (/r/{id})
        """
        web_thread_id = str(uuid.uuid4())
        self.insert(id=web_thread_id, thread_id=thread_id)
        return web_thread_id

    def get_web_thread(self, web_thread_id: str) -> tuple[Any, ...] | None:
        """Get a web thread by its UUID.

        Args:
            web_thread_id: The UUID from the web URL

        Returns:
            Record tuple or None if not found
        """
        return self.get_by(id=web_thread_id)

    def get_web_thread_by_thread_id(self, thread_id: str) -> tuple[Any, ...] | None:
        """Get a web thread by the conversation thread_id.

        Args:
            thread_id: The conversation thread_id

        Returns:
            Record tuple or None if not found
        """
        return self.get_by(thread_id=thread_id)
