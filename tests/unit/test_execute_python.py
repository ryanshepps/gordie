"""Tests for the sandboxed Python execution tool."""

import json

from tools.compute.execute_python import execute_python
from tools.compute.sandbox_runner import build_sandbox_script


class TestBuildSandboxScript:
    def test_embeds_code_and_data(self) -> None:
        script = build_sandbox_script("print(data['x'])", '{"x": 42}')
        assert "import numpy" in script
        assert "import pandas" in script
        assert "base64" in script

    def test_handles_special_characters_in_code(self) -> None:
        code = 'print("hello\\nworld")\nprint({"key": "value"})'
        script = build_sandbox_script(code, "{}")
        assert "base64" in script


class TestExecutePython:
    def test_basic_math(self) -> None:
        result = execute_python.invoke({"code": "print(2 + 2)"})
        assert "4" in result

    def test_data_access(self) -> None:
        code = "print(data['scores'])"
        data = json.dumps({"scores": [10, 20, 30]})
        result = execute_python.invoke({"code": code, "data_json": data})
        assert "10" in result
        assert "20" in result
        assert "30" in result

    def test_numpy(self) -> None:
        code = """
values = data['values']
arr = np.array(values)
print(f"mean={np.mean(arr):.2f}")
print(f"std={np.std(arr):.2f}")
"""
        data = json.dumps({"values": [10, 20, 30, 40, 50]})
        result = execute_python.invoke({"code": code, "data_json": data})
        assert "mean=30.00" in result
        assert "std=" in result

    def test_scipy_zscore(self) -> None:
        code = """
values = data['values']
zscores = scipy.stats.zscore(values)
print([round(z, 2) for z in zscores])
"""
        data = json.dumps({"values": [10, 20, 30, 40, 50]})
        result = execute_python.invoke({"code": code, "data_json": data})
        assert "-" in result
        assert "0.0" in result

    def test_pandas(self) -> None:
        code = """
df = pd.DataFrame(data['players'])
print(df[['name', 'points']].to_string(index=False))
"""
        data = json.dumps({
            "players": [
                {"name": "McDavid", "points": 52},
                {"name": "Draisaitl", "points": 45},
            ]
        })
        result = execute_python.invoke({"code": code, "data_json": data})
        assert "McDavid" in result
        assert "52" in result

    def test_error_returns_stderr(self) -> None:
        result = execute_python.invoke({"code": "raise ValueError('test error')"})
        assert "Error" in result
        assert "test error" in result

    def test_timeout(self) -> None:
        code = """
import time
time.sleep(60)
"""
        result = execute_python.invoke({"code": code, "data_json": "{}"})
        assert "timed out" in result

    def test_no_output_returns_message(self) -> None:
        result = execute_python.invoke({"code": "x = 42"})
        assert "(no output)" in result

    def test_default_data_json(self) -> None:
        result = execute_python.invoke({"code": "print(type(data).__name__)"})
        assert "dict" in result

    def test_collections_available(self) -> None:
        code = """
c = Counter(data['items'])
print(dict(c.most_common(2)))
"""
        data = json.dumps({"items": ["a", "b", "a", "c", "a", "b"]})
        result = execute_python.invoke({"code": code, "data_json": data})
        assert "a" in result

    def test_statistics_module(self) -> None:
        code = """
values = data['values']
print(f"median={statistics.median(values)}")
"""
        data = json.dumps({"values": [1, 3, 5, 7, 9]})
        result = execute_python.invoke({"code": code, "data_json": data})
        assert "median=5" in result
