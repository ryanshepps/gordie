"""Sandboxed Python execution tool for statistical computation."""

import subprocess
import sys

from langchain.tools import tool

from module.logger import get_logger
from tools.compute.sandbox_runner import MAX_OUTPUT_CHARS, build_sandbox_script

logger = get_logger(__name__)

TIMEOUT_SECONDS = 30


@tool
def execute_python(code: str, data_json: str = "{}") -> str:
    """Execute Python code in a sandboxed subprocess with pre-loaded data.

    The code runs with these modules pre-imported:
    - numpy (as np), scipy.stats, pandas (as pd)
    - math, json, statistics, collections (Counter, defaultdict, OrderedDict)

    A `data` variable is pre-loaded from `data_json` (parsed as JSON dict/list).
    Use print() to produce output — the tool returns whatever is printed to stdout.

    Args:
        code: Python code to execute. Use print() for output.
        data_json: JSON string that will be available as the `data` variable.

    Returns:
        stdout output on success, stderr on error, or timeout message.
    """
    script = build_sandbox_script(code, data_json)

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )

        if result.returncode == 0:
            output = result.stdout
            if len(output) > MAX_OUTPUT_CHARS:
                output = (
                    output[:MAX_OUTPUT_CHARS] + f"\n... (truncated at {MAX_OUTPUT_CHARS} chars)"
                )
            return output if output else "(no output)"

        error = result.stderr
        if len(error) > MAX_OUTPUT_CHARS:
            error = error[:MAX_OUTPUT_CHARS] + f"\n... (truncated at {MAX_OUTPUT_CHARS} chars)"
        return f"Error:\n{error}"

    except subprocess.TimeoutExpired:
        return f"Execution timed out after {TIMEOUT_SECONDS} seconds."
    except Exception as e:
        logger.error(f"execute_python error: {e}")
        return f"Failed to execute code: {e}"
