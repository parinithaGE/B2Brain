"""Startup/environment validation."""

import os

from config import (
    FOLDER,
    MCP_EXE,
    OLLAMA_MODEL,
    OLLAMA_URL,
    OWNER,
    REPO,
)


def check_environment() -> None:
    """Validate required configuration before starting the pipeline."""
    token = os.getenv(
        "GITHUB_PERSONAL_ACCESS_TOKEN",
        "",
    ).strip()

    if not token:
        raise RuntimeError(
            "GITHUB_PERSONAL_ACCESS_TOKEN is not set. "
            "Set it in .env."
        )

    if not MCP_EXE:
        raise RuntimeError(
            "MCP_EXE is not configured."
        )

    if not os.path.exists(MCP_EXE):
        raise RuntimeError(
            f"GitHub MCP executable was not found: {MCP_EXE}"
        )

    if not OLLAMA_URL:
        raise RuntimeError(
            "OLLAMA_URL is not configured in .env."
        )

    if not OLLAMA_MODEL:
        raise RuntimeError(
            "OLLAMA_MODEL is not configured."
        )

    print("Environment check passed.")
    print(
        "Repository:",
        f"{OWNER}/{REPO}",
    )
    print(
        "Folder:",
        FOLDER,
    )
