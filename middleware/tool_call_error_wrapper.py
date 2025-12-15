import logging

from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage

logger = logging.getLogger(__name__)


@wrap_tool_call
def handle_tool_errors(request, handler):
    """Handle tool execution errors with custom messages."""
    try:
        return handler(request)
    except Exception as e:
        # Log the error for debugging purposes
        logger.error(f"Tool error: {e!s}")
        #
        # Return a custom error message to the model
        return ToolMessage(
            content=f"Tool error: Please check your input and try again. ({e!s})",
            tool_call_id=request.tool_call["id"],
        )
