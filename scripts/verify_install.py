"""Install a built wheel into a new venv, run the real demo, then uninstall."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "zip-content-diff"
MODULE = "zip_content_diff"


def main() -> None:
    wheels = list((ROOT / "dist").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Build exactly one wheel before running this check.")
    with tempfile.TemporaryDirectory(prefix=NAME + "-install-") as directory:
        target = Path(directory)
        venv.EnvBuilder(with_pip=True).create(target / "venv")
        python = (
            target / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        )
        subprocess.run(
            [str(python), "-m", "pip", "install", str(wheels[0])], cwd=target, check=True
        )
        subprocess.run([str(python), "-m", MODULE, "--version"], cwd=target, check=True)
        subprocess.run([str(python), str(ROOT / "scripts/demo.py")], cwd=target, check=True)
        subprocess.run([str(python), "-m", "pip", "uninstall", "-y", NAME], cwd=target, check=True)
        subprocess.run(
            [
                str(python),
                "-c",
                "import importlib.util; assert importlib.util.find_spec('" + MODULE + "') is None",
            ],
            cwd=target,
            check=True,
        )
    print(json.dumps({"clean_install": "passed", "demo": "passed", "uninstall": "passed"}))


if __name__ == "__main__":
    main()
