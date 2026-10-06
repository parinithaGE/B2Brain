"""Deterministic candidate ranking for documentation search."""

import re


STOP_WORDS = {
    "the",
    "a",
    "an",
    "to",
    "of",
    "for",
    "in",
    "on",
    "and",
    "or",
    "is",
    "are",
    "with",
    "how",
    "can",
    "do",
    "does",
    "i",
    "user",
    "users",
    "create",
    "use",
    "using",
    "what",
    "where",
    "when",
    "this",
    "that",
    "from",
    "into",
    "my",
}


def _tokens(text: str) -> set[str]:
    """Return useful normalized words."""
    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            text.lower(),
        )
        if len(token) >= 3
        and token not in STOP_WORDS
    }


def _path_tokens(path: str) -> set[str]:
    """Tokenize a repository path."""
    return _tokens(
        path.replace(
            "-",
            " ",
        ).replace(
            "_",
            " ",
        ).replace(
            "/",
            " ",
        )
    )


def _score(
    path: str,
    question: str,
    concepts: list[str],
) -> float:
    """Calculate a transparent deterministic relevance score."""
    question_tokens = _tokens(question)

    concept_tokens = set()

    for concept in concepts:
        concept_tokens.update(
            _tokens(str(concept))
        )

    path_tokens = _path_tokens(path)

    score = 0.0

    score += len(
        question_tokens & path_tokens
    ) * 12

    score += len(
        concept_tokens & path_tokens
    ) * 18

    question_lower = question.lower()
    path_lower = path.lower()

    # Strong topic matches.
    if (
        "quantity" in question_lower
        and "quantity" in path_lower
    ):
        score += 60

    if (
        "limit" in question_lower
        and "limit" in path_lower
    ):
        score += 45

    if (
        "restrict" in question_lower
        and (
            "limit" in path_lower
            or "restrict" in path_lower
        )
    ):
        score += 45

    if (
        "b2b" in question_lower
        and "b2b" in path_lower
    ):
        score += 20

    return score


def rank_candidates(
    candidates: list[dict],
    question: str,
    concepts: list[str] | None = None,
) -> list[dict]:
    """
    Rank candidates without fetching them.

    The ranking uses only the question, concepts, and search-result
    metadata. It does not use unverified file content.
    """
    concepts = concepts or []

    ranked = []

    for candidate in candidates:
        item = dict(candidate)

        path = str(
            item.get(
                "path",
                "",
            )
        ).strip()

        item["score"] = _score(
            path,
            question,
            concepts,
        )

        ranked.append(item)

    ranked.sort(
        key=lambda item: (
            float(
                item.get(
                    "score",
                    0,
                )
            ),
            str(
                item.get(
                    "path",
                    "",
                )
            ),
        ),
        reverse=True,
    )

    return ranked
