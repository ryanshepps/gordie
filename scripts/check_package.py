import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    wheel = Path(sys.argv[1]).resolve()
    with TemporaryDirectory(prefix="gordie-wheel-") as directory:
        root = Path(directory)
        environment = root / "venv"
        subprocess.run(["uv", "venv", str(environment), "--python", sys.executable], check=True)
        python = environment / "bin/python"
        subprocess.run(["uv", "pip", "install", "--python", str(python), str(wheel)], check=True)
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.endswith(("_API_KEY", "_SECRET"))
            and key not in {"PYTHONPATH", "DATABASE_URL", "CREEM_PRODUCT_HOSTED_MONTHLY"}
        }
        env["GORDIE_DATA_DIR"] = str(root / "data")
        env["GORDIE_LOG_FILE"] = "stderr"
        subprocess.run(
            [str(python), "-I", "-c", _VERIFY_INSTALLATION],
            cwd=root,
            env=env,
            check=True,
            timeout=60,
        )
        for command in ("gordie", "gordie-message"):
            subprocess.run(
                [str(environment / "bin" / command), "--help"],
                cwd=root,
                env=env,
                check=True,
                timeout=30,
                stdout=subprocess.DEVNULL,
            )
    print("Wheel imports, resources, migrations, and CLI verified outside the checkout")


_VERIFY_INSTALLATION = """
import importlib
import os
import pkgutil
from pathlib import Path

import gordie

assert Path(gordie.__file__).resolve().is_relative_to((Path.cwd() / "venv").resolve())
for module in pkgutil.walk_packages(gordie.__path__, "gordie."):
    importlib.import_module(module.name)

from gordie.scripts import start_server
from gordie.scripts.setup import _DEFAULT_TEMPLATE_FILE
from gordie.tools.hockey.stats.duckdb_schema import DB_PATH
from gordie.tools.mlb.stats.mlb_schema import MLB_DB_PATH

assert "DATABASE_URL=" in _DEFAULT_TEMPLATE_FILE.read_text()
assert DB_PATH.parent == Path(os.environ["GORDIE_DATA_DIR"])
assert MLB_DB_PATH.parent == DB_PATH.parent
assert not DB_PATH.parent.exists()

def verify_migrations(config, revision):
    path = Path(config.get_main_option("script_location"))
    assert path.joinpath("env.py").is_file()
    assert path.joinpath("script.py.mako").is_file()
    assert list(path.joinpath("versions").glob("*.py"))
    assert revision == "head"

start_server.upgrade_database = verify_migrations
start_server.run_migrations()
"""


if __name__ == "__main__":
    main()
