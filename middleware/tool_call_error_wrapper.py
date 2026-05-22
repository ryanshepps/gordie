import time

from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage

from module.logger import get_logger

logger = get_logger(__name__)

MAX_TOOL_OUTPUT_CHARS = 40_000


@wrap_tool_call
def handle_tool_errors(request, handler):
    """Handle tool execution errors with custom messages and metrics."""
    tool_name = request.tool_call.get("name", "unknown")
    start_time = time.time()

    try:
        result = handler(request)

        duration = time.time() - start_time

        result_content = getattr(result, "content", "")
        if isinstance(result_content, str) and len(result_content) > MAX_TOOL_OUTPUT_CHARS:
            original_len = len(result_content)
            truncated_content = (
                result_content[:MAX_TOOL_OUTPUT_CHARS]
                + f"\n\n[TRUNCATED: output was {original_len:,} chars, capped at {MAX_TOOL_OUTPUT_CHARS:,}. "
                + "Narrow your query to get complete results.]"
            )
            result = ToolMessage(
                content=truncated_content,
                tool_call_id=request.tool_call["id"],
            )
            logger.warning(
                f"Tool output truncated: {tool_name} ({original_len:,} -> {MAX_TOOL_OUTPUT_CHARS:,} chars)",
                extra={"tool_name": tool_name, "original_chars": original_len},
            )

        preview = (
            result_content[:500] if isinstance(result_content, str) else str(result_content)[:500]
        )

        logger.info(
            f"Tool executed successfully: {tool_name}",
            extra={
                "tool_name": tool_name,
                "duration_ms": duration * 1000,
                "status": "success",
                "result_preview": preview,
            },
        )

        return result

    except Exception as e:
        duration = time.time() - start_time
        error_type = type(e).__name__

        logger.error(
            f"Tool error: {tool_name} - {e!s}",
            extra={
                "tool_name": tool_name,
                "duration_ms": duration * 1000,
                "status": "error",
                "error_type": error_type,
            },
            exc_info=True,
        )

        return ToolMessage(
            content=f"Tool error: Please check your input and try again. ({e!s})",
            tool_call_id=request.tool_call["id"],
        )
