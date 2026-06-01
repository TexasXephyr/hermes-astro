#!/usr/bin/env python3
"""
seed_corpus_openrouter.py — Wrapper to seed the atomic interpretation corpus
using OpenRouter instead of local Ollama.

Usage:
    cd ~/astro
    python3 scripts/seed_corpus_openrouter.py [--model MODEL]

Reads OPENROUTER_API_KEY from ~/.hermes/.env automatically.
Forces unbuffered output so progress is visible in real time.
"""

import os
import subprocess
import sys
from pathlib import Path


def _get_api_key() -> str:
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        raise FileNotFoundError(f"{env_path} not found")
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise KeyError("OPENROUTER_API_KEY not found in ~/.hermes/.env")


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "google/gemini-2.0-flash-001"
    api_key = _get_api_key()

    env = os.environ.copy()
    env["OLLAMA_BASE_URL"] = "https://openrouter.ai/api"
    env["OLLAMA_API_KEY"] = api_key
    env["PYTHONUNBUFFERED"] = "1"

    db_path = Path(__file__).resolve().parent.parent / "src" / "astro_api" / "astro.db"

    cmd = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve().parent / "seed_corpus.py"),
        "--model", model,
        "--db", str(db_path),
    ]

    print(f"Model:    {model}")
    print(f"Endpoint: https://openrouter.ai/api/v1/chat/completions")
    print(f"Database: {db_path}")
    print("")

    subprocess.run(cmd, env=env, check=True)


if __name__ == "__main__":
    main()
