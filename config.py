"""Project configuration loaded from .env."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_FILE)


OWNER = os.getenv(
    "GITHUB_OWNER",
    "MicrosoftDocs",
).strip()

REPO = os.getenv(
    "GITHUB_REPO",
    "dynamics-365-unified-operations-public",
).strip()

FOLDER = os.getenv(
    "GITHUB_FOLDER",
    "articles/commerce/b2b",
).strip("/")

BRANCH = os.getenv(
    "GITHUB_BRANCH",
    "main",
).strip()

MCP_EXE = os.getenv(
    "MCP_EXE",
    r"C:\Users\parin\go\bin\github-mcp-server.exe",
).strip()

MCP_TOOLS = [
    "search_code",
    "get_file_contents",
]

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "",
).strip().rstrip("/")

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3.1:8b",
).strip()

OLLAMA_TIMEOUT = int(
    os.getenv(
        "OLLAMA_TIMEOUT",
        "300",
    )
)

SEARCH_PASSES = int(
    os.getenv(
        "SEARCH_PASSES",
        "3",
    )
)

MAX_SEARCH_QUERIES = int(
    os.getenv(
        "MAX_SEARCH_QUERIES",
        "12",
    )
)

MAX_SEARCH_RESULTS_PER_QUERY = int(
    os.getenv(
        "MAX_SEARCH_RESULTS_PER_QUERY",
        "30",
    )
)

MAX_SOURCE_CHARS = int(
    os.getenv(
        "MAX_SOURCE_CHARS",
        "180000",
    )
)
