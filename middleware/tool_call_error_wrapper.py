import time

from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage

from module.logger import get_logger
from module.metrics import tool_calls_total, tool_errors_total, tool_execution_duration_seconds
from module.tracing import create_span, record_exception, set_span_ok

logger = get_logger(__name__)


@wrap_tool_call
def handle_tool_errors(request, handler):
    """Handle tool execution errors with custom messages and metrics."""
    tool_name = request.tool_call.get("name", "unknown")
    start_time = time.time()

    with create_span(
        f"tool.{tool_name}",
        {"tool_name": tool_name},
    ) as span:
        try:
            result = handler(request)

            duration = time.time() - start_time
            tool_calls_total.labels(tool_name=tool_name, status="success").inc()
            tool_execution_duration_seconds.labels(tool_name=tool_name).observe(duration)

            span.set_attribute("duration_ms", duration * 1000)
            span.set_attribute("status", "success")
            set_span_ok(span)

            logger.info(
                f"Tool executed successfully: {tool_name}",
                extra={"tool_name": tool_name, "duration_ms": duration * 1000, "status": "success"},
            )

            return result

        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__

            tool_calls_total.labels(tool_name=tool_name, status="error").inc()
            tool_errors_total.labels(tool_name=tool_name, error_type=error_type).inc()
            tool_execution_duration_seconds.labels(tool_name=tool_name).observe(duration)

            span.set_attribute("duration_ms", duration * 1000)
            span.set_attribute("status", "error")
            span.set_attribute("error_type", error_type)
            record_exception(span, e)

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
