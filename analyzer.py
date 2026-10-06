"""Lightweight source analysis used for UI diagnostics."""


def analyze_source(
    source: str,
    question: str,
) -> dict:
    """Return basic source statistics without changing source content."""
    lines = source.splitlines()

    sections = []

    for line in lines:
        if line.lstrip().startswith("#"):
            sections.append(
                line.strip()
            )

    return {
        "characters": len(source),
        "lines": len(lines),
        "sections": sections,
        "question": question,
    }
