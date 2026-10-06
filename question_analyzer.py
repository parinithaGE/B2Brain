"""Compatibility wrapper for question analysis."""

from app.skills import load_question_analyzer_prompt
from app.utils.llm import OllamaClient


def understand_question(
    question: str,
    llm: OllamaClient | None = None,
) -> dict:
    """Understand a question through the configured Ollama skill."""
    client = llm or OllamaClient()

    return client.understand_question(
        question=question,
        system_prompt=load_question_analyzer_prompt(),
    )
