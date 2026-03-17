"""Build sandboxed Python scripts for subprocess execution."""

import base64

ALLOWED_MODULES = [
    "numpy",
    "scipy.stats",
    "pandas",
    "math",
    "json",
    "statistics",
    "collections",
]

MAX_OUTPUT_CHARS = 50_000


def build_sandbox_script(code: str, data_json: str) -> str:
    code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    data_b64 = base64.b64encode(data_json.encode("utf-8")).decode("ascii")

    return f"""
import sys
import json
import base64
import math
import statistics
from collections import Counter, defaultdict, OrderedDict

import numpy as np
import scipy.stats
import pandas as pd

_data_raw = base64.b64decode("{data_b64}").decode("utf-8")
data = json.loads(_data_raw)

_code = base64.b64decode("{code_b64}").decode("utf-8")
exec(_code)
"""
