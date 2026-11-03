"""Launch the FlyOps local development application."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Start the local Streamlit server."""

    project_root = Path(__file__).resolve().parent

    environment = os.environ.copy()

    environment["PYTHONPATH"] = os.pathsep.join(
        [
            str(project_root),
            str(project_root / "src"),
            environment.get("PYTHONPATH", ""),
        ]
    )

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(project_root / "app" / "main.py"),
        "--server.address=127.0.0.1",
        "--server.port=8501",
        "--server.headless=true",
    ]

    process = subprocess.Popen(
        command,
        cwd=project_root,
        env=environment,
    )

    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    main()
