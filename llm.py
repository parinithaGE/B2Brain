"""Synchronous Ollama HTTP client."""

import json
import re
from pathlib import Path
from typing import Optional

import requests

from config import (
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    OLLAMA_URL,
)


class OllamaClient:
    """Client for Ollama's /api/generate endpoint."""

    def __init__(
        self,
        base_url: str = OLLAMA_URL,
        model: str = OLLAMA_MODEL,
        timeout: int = OLLAMA_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _generate_url(self) -> str:
        """Return the normalized Ollama generate URL."""
        if self.base_url.endswith("/api/generate"):
            return self.base_url

        return self.base_url + "/api/generate"

    def health_check(self) -> tuple[bool, str]:
        """Check whether the configured Ollama host is reachable."""
        if not self.base_url:
            return (
                False,
                "OLLAMA_URL is empty.",
            )

        base = self.base_url

        if base.endswith("/api/generate"):
            base = base[:-len("/api/generate")]

        try:
            response = requests.get(
                base,
                timeout=15,
            )

            return (
                True,
                f"Ollama reachable ({response.status_code})",
            )

        except Exception as exc:
            return (
                False,
                str(exc),
            )

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
    ) -> str:
        """Generate one non-streaming response from Ollama."""
        if not self.base_url:
            raise RuntimeError(
                "OLLAMA_URL is not configured."
            )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
            },
        }

        if system:
            payload["system"] = system

        response = requests.post(
            self._generate_url(),
            json=payload,
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        return str(
            data.get(
                "response",
                "",
            )
        ).strip()

    def understand_question(
        self,
        question: str,
        system_prompt: str,
    ) -> dict:
        """Ask Ollama to produce structured search intent."""
        prompt = (
            "Understand this Microsoft Dynamics 365 Commerce "
            "documentation question for repository search.\n\n"
            f"QUESTION:\n{question}\n\n"
            "Return JSON only using the structure required by "
            "the system prompt."
        )

        raw = self.generate(
            prompt,
            system_prompt,
        )

        parsed = self._parse_json(raw)

        intent = str(
            parsed.get(
                "intent",
                question,
            )
        ).strip()

        concepts = parsed.get(
            "concepts",
            [],
        )

        queries = parsed.get(
            "queries",
            [],
        )

        if not isinstance(concepts, list):
            concepts = []

        if not isinstance(queries, list):
            queries = []

        return {
            "intent": intent,
            "concepts": [
                str(item).strip()
                for item in concepts
                if str(item).strip()
            ],
            "queries": [
                str(item).strip()
                for item in queries
                if str(item).strip()
            ],
        }

    def answer(
        self,
        question: str,
        source: str,
        system_prompt: str,
    ) -> str:
        """Generate the final grounded answer."""
        prompt = (
            "USER QUESTION:\n"
            f"{question}\n\n"
            "SOURCE CONTENT:\n"
            "---------------- BEGIN SOURCE ----------------\n"
            f"{source}\n"
            "----------------- END SOURCE -----------------\n\n"
            "Answer using ONLY the supplied source content."
        )

        return self.generate(
            prompt,
            system_prompt,
        )

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Parse JSON even if a model accidentally adds a code fence."""
        cleaned = raw.strip()

        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        )

        try:
            value = json.loads(cleaned)

            if isinstance(value, dict):
                return value

        except Exception:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start >= 0 and end > start:
            try:
                value = json.loads(
                    cleaned[start:end + 1]
                )

                if isinstance(value, dict):
                    return value

            except Exception:
                pass

        return {}
