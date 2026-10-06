"""Terminal-style source-grounded documentation pipeline."""

from config import (
    FOLDER,
    MAX_SEARCH_QUERIES,
    MAX_SOURCE_CHARS,
    OWNER,
    REPO,
    SEARCH_PASSES,
)

from app.analyzer import analyze_source
from app.ranker import rank_candidates
from app.skills import (
    load_answer_engine_prompt,
    load_question_analyzer_prompt,
)
from app.startup import check_environment
from app.utils.llm import OllamaClient
from app.utils.mcp import MCPClient


class B2BDocumentationAssistant:
    """Coordinate question analysis, MCP search, ranking, fetch, and answer."""

    def __init__(self) -> None:
        self.llm = OllamaClient()
        self.mcp = MCPClient()

    async def run(self, question: str) -> dict:
        """Run the complete documentation pipeline."""
        question = question.strip()

        if not question:
            return self._empty("Please enter a question.")

        print("=" * 72)
        print("GITHUB B2B DOCUMENTATION MCP ASSISTANT")
        print("=" * 72)
        print("Repository :", f"{OWNER}/{REPO}")
        print("Folder     :", FOLDER)
        print("RAG        :", "NOT USED")
        print("FETCHES    :", "EXACTLY ONE FINAL FILE")

        check_environment()

        ollama_ok, ollama_message = self.llm.health_check()

        if not ollama_ok:
            raise RuntimeError(
                "Ollama could not be reached. "
                f"{ollama_message}"
            )

        print("Ollama     :", ollama_message)

        # ---------------------------------------------------------------
        # STEP 1 — UNDERSTAND QUESTION
        # ---------------------------------------------------------------
        print()
        print("=" * 72)
        print("STEP 1 — UNDERSTAND QUESTION")
        print("=" * 72)

        understanding = self.llm.understand_question(
            question=question,
            system_prompt=load_question_analyzer_prompt(),
        )

        print(
            "Intent:",
            understanding.get("intent", ""),
        )

        print("Queries:")

        for query in understanding.get("queries", []):
            print("  -", query)

        # ---------------------------------------------------------------
        # STEP 2 + STEP 3 — MCP + SEARCH
        # ---------------------------------------------------------------
        async with self.mcp:

            candidates = await self._search_all_passes(
                question,
                understanding,
            )

            if not candidates:
                return self._empty(
                    "No verified source file was found after "
                    f"{SEARCH_PASSES} complete search passes. "
                    "No answer was generated.",
                    understanding=understanding,
                )

            # -----------------------------------------------------------
            # STEP 4 — RANK ALL DISCOVERED CANDIDATES
            # -----------------------------------------------------------
            print()
            print("=" * 72)
            print("STEP 4 — RANK ALL CANDIDATES")
            print("=" * 72)

            ranked = rank_candidates(
                candidates,
                question,
                understanding.get("concepts", []),
            )

            ranked = self._boost_specific_paths(
                ranked,
                question,
                understanding,
            )

            print()
            print("Final candidate ranking:")

            for index, candidate in enumerate(
                ranked[:20],
                start=1,
            ):
                print(
                    f"{index}.",
                    candidate.get("path", ""),
                    "score=",
                    candidate.get("score", 0),
                )

            if not ranked:
                return self._empty(
                    "Search results were found, but no valid documentation "
                    "file could be selected.",
                    candidates=candidates,
                    understanding=understanding,
                )

            # -----------------------------------------------------------
            # IMPORTANT:
            #
            # Do NOT stop when the first search result is found.
            #
            # _search_all_passes() has already completed every configured
            # search pass and collected every unique candidate returned
            # by those searches.
            #
            # Only now do we select ONE final source file.
            # -----------------------------------------------------------
            selected = ranked[0]

            selected_path = str(
                selected.get("path", "")
            ).strip()

            if not selected_path:
                return self._empty(
                    "The search returned a candidate without a valid "
                    "source path.",
                    candidates=ranked,
                    understanding=understanding,
                )

            print()
            print("SELECTED SOURCE FILE:")
            print(selected_path)

            # -----------------------------------------------------------
            # STEP 5 — FETCH EXACTLY ONE FINAL FILE
            # -----------------------------------------------------------
            print()
            print("=" * 72)
            print("STEP 5 — FETCH EXACTLY ONE FINAL FILE")
            print("=" * 72)

            source = await self.mcp.get_file_contents(
                selected_path
            )

        # MCP is closed only AFTER the selected complete source file
        # has been fetched successfully.

        if not source.strip():
            return self._empty(
                "The selected source file could not be fetched. "
                "No answer was generated.",
                selected=selected_path,
                candidates=ranked,
                understanding=understanding,
            )

        if len(source) > MAX_SOURCE_CHARS:
            print(
                "WARNING: Source exceeds MAX_SOURCE_CHARS.",
                "Truncating source before analysis.",
            )

            source = source[:MAX_SOURCE_CHARS]

        # ---------------------------------------------------------------
        # STEP 6 — ANALYZE SOURCE
        # ---------------------------------------------------------------
        print()
        print("=" * 72)
        print("STEP 6 — ANALYZE SOURCE")
        print("=" * 72)

        analysis = analyze_source(
            source,
            question,
        )

        print(
            "Characters:",
            analysis["characters"],
        )

        print(
            "Lines:",
            analysis["lines"],
        )

        print(
            "Sections:",
            len(analysis["sections"]),
        )

        # ---------------------------------------------------------------
        # STEP 7 — GENERATE CONCISE ANSWER
        # ---------------------------------------------------------------
        print()
        print("=" * 72)
        print("STEP 7 — GENERATE ANSWER")
        print("=" * 72)

        answer = self.llm.answer(
            question=question,
            source=source,
            system_prompt=load_answer_engine_prompt(),
        )

        print()
        print("FINAL ANSWER")
        print("-" * 72)
        print(answer)

        return {
            "answer": answer,
            "source": source,
            "selected_file": selected_path,
            "candidates": ranked,
            "analysis": analysis,
            "understanding": understanding,
            "error": "",
        }

    async def _search_all_passes(
        self,
        question: str,
        understanding: dict,
    ) -> list[dict]:
        """
        Search the documentation thoroughly before selecting a source.

        Every configured search pass uses a different set of queries.
        No early stopping is performed.

        The goal is:

            question
                ↓
            multiple search strategies
                ↓
            all search passes
                ↓
            all unique candidates
                ↓
            ranking
                ↓
            ONE final source fetch
        """

        query_groups = self._build_query_groups(
            question,
            understanding,
        )

        candidates = []

        print()
        print("=" * 72)
        print("STEP 3 — SEARCH")
        print("=" * 72)

        for pass_number in range(
            1,
            SEARCH_PASSES + 1,
        ):
            print()
            print(
                f"SEARCH PASS {pass_number}/{SEARCH_PASSES}"
            )

            # Use a different query group for each pass.
            # If SEARCH_PASSES is larger than the available groups,
            # reuse the broadest group rather than stopping early.
            group_index = min(
                pass_number - 1,
                len(query_groups) - 1,
            )

            queries = query_groups[group_index]

            print(
                "Queries in this pass:",
                len(queries),
            )

            for query in queries:
                print()
                print("[MCP search_code]")
                print("Query:", query)

                try:
                    found = await self.mcp.search_code(
                        query
                    )
                except Exception as exc:
                    print(
                        "GitHub search error:",
                        str(exc),
                    )
                    continue

                print(
                    "Results:",
                    len(found),
                )

                candidates.extend(found)

            # Deduplicate AFTER EACH COMPLETE PASS.
            candidates = self._dedupe(candidates)

            print(
                "Unique candidates after pass:",
                len(candidates),
            )

            if candidates:
                print("Candidates discovered so far:")

                for candidate in candidates[:20]:
                    print(
                        "  -",
                        candidate.get("path", ""),
                    )

        print()
        print(
            "SEARCH COMPLETE — no early stopping."
        )
        print(
            "Total unique candidates:",
            len(candidates),
        )

        return candidates

    @staticmethod
    def _build_query_groups(
        question: str,
        understanding: dict,
    ) -> list[list[str]]:
        """
        Build different search strategies.

        Pass 1:
            Exact/direct wording.

        Pass 2:
            Semantic/concept wording.

        Pass 3:
            Documentation terminology and targeted terms.

        This prevents the old behavior where all three passes
        repeated exactly the same queries.
        """

        question_clean = " ".join(
            question.split()
        ).strip()

        question_lower = question_clean.lower()

        intent = str(
            understanding.get(
                "intent",
                "",
            )
        ).strip()

        model_queries = [
            str(query).strip()
            for query in understanding.get(
                "queries",
                [],
            )
            if str(query).strip()
        ]

        concepts = [
            str(concept).strip()
            for concept in understanding.get(
                "concepts",
                [],
            )
            if str(concept).strip()
        ]

        # ---------------------------------------------------------------
        # PASS 1 — DIRECT SEARCH
        # ---------------------------------------------------------------
        direct = []

        if question_clean:
            direct.append(question_clean)

        if intent:
            direct.append(intent)

        direct.extend(model_queries)

        # ---------------------------------------------------------------
        # PASS 2 — CONCEPT / SEMANTIC SEARCH
        # ---------------------------------------------------------------
        semantic = []

        if concepts:
            semantic.append(
                " ".join(concepts[:8])
            )

        semantic.extend(
            [
                f"{question_clean} Dynamics 365 Commerce",
                f"{question_clean} Commerce B2B",
                f"{question_clean} documentation",
            ]
        )

        # Add important words separately so GitHub search has
        # opportunities to find a better file than the first exact match.
        if concepts:
            for concept in concepts[:5]:
                semantic.append(
                    f"Dynamics 365 Commerce {concept}"
                )

        # ---------------------------------------------------------------
        # PASS 3 — TARGETED DOCUMENTATION SEARCH
        # ---------------------------------------------------------------
        targeted = []

        if any(
            term in question_lower
            for term in (
                "quantity",
                "quantities",
                "larger quantity",
                "maximum quantity",
                "order quantity",
            )
        ):
            targeted.extend(
                [
                    "quantity limits",
                    "product quantity limits",
                    "order quantity limits",
                    "maximum order quantity",
                    "minimum order quantity",
                    "quantity settings",
                ]
            )

        if any(
            term in question_lower
            for term in (
                "restrict",
                "restriction",
                "limit",
                "limits",
                "maximum",
                "minimum",
                "prevent",
            )
        ):
            targeted.extend(
                [
                    "limits",
                    "maximum",
                    "minimum",
                    "restrictions",
                ]
            )

        if "b2b" in question_lower:
            targeted.extend(
                [
                    "B2B",
                    "B2B e-commerce",
                    "B2B customer",
                    "B2B Commerce",
                ]
            )

        # Generic documentation-oriented fallbacks.
        targeted.extend(
            [
                f"{question_clean} settings",
                f"{question_clean} configuration",
                f"{question_clean} feature",
            ]
        )

        groups = [
            B2BDocumentationAssistant._clean_queries(
                direct
            ),
            B2BDocumentationAssistant._clean_queries(
                semantic
            ),
            B2BDocumentationAssistant._clean_queries(
                targeted
            ),
        ]

        # Make sure every pass has at least one query.
        for index, group in enumerate(groups):
            if not group:
                groups[index] = [
                    question_clean
                ] if question_clean else []

        print()
        print("Search query groups:")

        for index, group in enumerate(
            groups,
            start=1,
        ):
            print()
            print(
                f"Pass {index}:"
            )

            for query in group:
                print(
                    "  -",
                    query,
                )

        return groups

    @staticmethod
    def _clean_queries(
        values: list[str],
    ) -> list[str]:
        """Normalize and deduplicate search queries."""

        output = []
        seen = set()

        for value in values:
            cleaned = " ".join(
                str(value).split()
            ).strip()

            if not cleaned:
                continue

            cleaned = cleaned[:180]

            key = cleaned.lower()

            if key in seen:
                continue

            seen.add(key)
            output.append(cleaned)

            if len(output) >= MAX_SEARCH_QUERIES:
                break

        return output

    @staticmethod
    def _boost_specific_paths(
        ranked: list[dict],
        question: str,
        understanding: dict,
    ) -> list[dict]:
        """
        Apply deterministic boosts for highly specific terminology.

        This happens ONLY after all configured search passes have
        completed.
        """

        context = " ".join(
            [
                question.lower(),
                str(
                    understanding.get(
                        "intent",
                        "",
                    )
                ).lower(),
                " ".join(
                    str(x).lower()
                    for x in understanding.get(
                        "queries",
                        [],
                    )
                ),
                " ".join(
                    str(x).lower()
                    for x in understanding.get(
                        "concepts",
                        [],
                    )
                ),
            ]
        )

        wants_quantity_limits = (
            "quantity" in context
            and (
                "limit" in context
                or "maximum" in context
                or "restrict" in context
                or "larger" in context
            )
        )

        wants_b2b = "b2b" in context

        for candidate in ranked:
            path = str(
                candidate.get(
                    "path",
                    "",
                )
            ).lower()

            score = float(
                candidate.get(
                    "score",
                    0,
                )
            )

            # Very specific documentation filename.
            if wants_quantity_limits:
                if "quantity-limits" in path:
                    score += 200

                if "quantity" in path:
                    score += 50

                if "limit" in path:
                    score += 50

            if wants_b2b:
                if "/b2b/" in path:
                    score += 30

                if "b2b" in path:
                    score += 20

            candidate["score"] = score

        ranked.sort(
            key=lambda item: float(
                item.get(
                    "score",
                    0,
                )
            ),
            reverse=True,
        )

        return ranked

    @staticmethod
    def _dedupe(
        records: list[dict],
    ) -> list[dict]:
        """Deduplicate search candidates by repository path."""

        output = []
        seen = set()

        for record in records:
            path = str(
                record.get(
                    "path",
                    "",
                )
            ).strip()

            if not path:
                continue

            # Only accept documentation files inside the configured
            # B2B folder.
            normalized_path = path.replace(
                "\\",
                "/",
            ).lower()

            expected_folder = FOLDER.replace(
                "\\",
                "/",
            ).lower().strip("/")

            if expected_folder not in normalized_path:
                continue

            if not normalized_path.endswith(
                ".md"
            ):
                continue

            if normalized_path in seen:
                continue

            seen.add(normalized_path)

            output.append(record)

        return output

    @staticmethod
    def _empty(
        message: str,
        selected: str = "",
        candidates: list[dict] | None = None,
        understanding: dict | None = None,
    ) -> dict:
        """Return a consistent failed-pipeline result."""

        return {
            "answer": message,
            "source": "",
            "selected_file": selected,
            "candidates": candidates or [],
            "analysis": {},
            "understanding": understanding or {},
            "error": "",
        }