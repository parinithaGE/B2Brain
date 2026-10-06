"""GitHub MCP client using the official local stdio server."""

import json
import os
import re
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config import (
    BRANCH,
    FOLDER,
    MCP_EXE,
    MCP_TOOLS,
    OWNER,
    REPO,
    MAX_SEARCH_RESULTS_PER_QUERY,
)


class MCPClient:
    """Connect to GitHub MCP and expose search/fetch operations."""

    def __init__(self) -> None:
        self.session: ClientSession | None = None
        self._stdio_context = None
        self._session_context = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        await self.close()

    async def connect(self):
        """Start the official GitHub MCP server in stdio mode."""

        self.validate()

        token = os.getenv(
            "GITHUB_PERSONAL_ACCESS_TOKEN",
            "",
        ).strip()

        print("Starting GitHub MCP server...")
        print("MCP executable:", MCP_EXE)
        print("Repository:", f"{OWNER}/{REPO}")
        print("Folder:", FOLDER)

        environment = os.environ.copy()
        environment["GITHUB_PERSONAL_ACCESS_TOKEN"] = token
        environment["GITHUB_TOOLSETS"] = "repos"

        server_parameters = StdioServerParameters(
            command=MCP_EXE,
            args=[
                "stdio",
                "--tools=search_code,get_file_contents",
            ],
            env=environment,
        )

        self._stdio_context = stdio_client(
            server_parameters
        )

        read_stream, write_stream = (
            await self._stdio_context.__aenter__()
        )

        self._session_context = ClientSession(
            read_stream,
            write_stream,
        )

        self.session = (
            await self._session_context.__aenter__()
        )

        await self.session.initialize()

        tools = await self.session.list_tools()

        available_tools = {
            tool.name
            for tool in tools.tools
        }

        print(
            "Available MCP tools:",
            sorted(available_tools),
        )

        required_tools = {
            "search_code",
            "get_file_contents",
        }

        missing = required_tools - available_tools

        if missing:
            raise RuntimeError(
                "Required GitHub MCP tools are missing: "
                f"{sorted(missing)}"
            )

        print("GitHub MCP connection established.")

        return self

    async def close(self) -> None:
        """Close the MCP session and stdio process."""

        session_context = self._session_context
        stdio_context = self._stdio_context

        self.session = None
        self._session_context = None
        self._stdio_context = None

        if session_context is not None:
            try:
                await session_context.__aexit__(
                    None,
                    None,
                    None,
                )
            except Exception as exc:
                print(
                    "MCP session close warning:",
                    exc,
                )

        if stdio_context is not None:
            try:
                await stdio_context.__aexit__(
                    None,
                    None,
                    None,
                )
            except Exception as exc:
                print(
                    "MCP stdio close warning:",
                    exc,
                )

    def validate(self) -> None:
        """Validate local MCP configuration."""

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
            raise FileNotFoundError(
                "GitHub MCP executable does not exist:\n"
                f"{MCP_EXE}"
            )

    def _require_session(self) -> None:
        """Ensure an active MCP session exists."""

        if self.session is None:
            raise RuntimeError(
                "MCP client is not connected."
            )

    async def list_tools(self):
        """List tools exposed by the server."""

        self._require_session()

        result = await self.session.list_tools()

        return result.tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ):
        """Call one MCP tool."""

        self._require_session()

        result = await self.session.call_tool(
            tool_name,
            arguments,
        )

        if getattr(
            result,
            "isError",
            False,
        ):
            raise RuntimeError(
                self._result_text(result)
            )

        return result

        @staticmethod
        def _result_text(result: Any) -> str:
           """Extract readable error text from an MCP result."""

           parts = []

           structured = getattr(
            result,
            "structuredContent",
            None,
        )

        if structured:
            try:
                parts.append(
                    json.dumps(
                        structured,
                        default=str,
                    )
                )
            except Exception:
                parts.append(
                    str(structured)
                )

        structured = getattr(
            result,
            "structured_content",
            None,
        )

        if structured:
            try:
                parts.append(
                    json.dumps(
                        structured,
                        default=str,
                    )
                )
            except Exception:
                parts.append(
                    str(structured)
                )

        content = getattr(
            result,
            "content",
            None,
        ) or []

        for item in content:

            text = getattr(
                item,
                "text",
                None,
            )

            if text:
                parts.append(
                    str(text)
                )
                continue

            resource = getattr(
                item,
                "resource",
                None,
            )

            if resource is not None:

                resource_text = getattr(
                    resource,
                    "text",
                    None,
                )

                if resource_text:
                    parts.append(
                        str(resource_text)
                    )

        return "\n".join(
            dict.fromkeys(
                part.strip()
                for part in parts
                if part and part.strip()
            )
        )

    # ==============================================================
    # SEARCH
    # ==============================================================

    async def search_code(
        self,
        query: str,
    ) -> list[dict]:
        """Search the configured B2B documentation folder."""

        query = " ".join(
            str(query).split()
        ).strip()

        if not query:
            return []

        full_query = (
            f"repo:{OWNER}/{REPO} "
            f"path:{FOLDER} "
            f"extension:md "
            f"{query}"
        )

        print()
        print(
            "[MCP search_code]"
        )
        print(
            "Query:",
            full_query,
        )

        try:
            result = await self.call_tool(
                "search_code",
                {
                    "query": full_query[:256],
                    "perPage": MAX_SEARCH_RESULTS_PER_QUERY,
                    "page": 1,
                },
            )

        except Exception as exc:
            print(
                "GitHub search error:",
                exc,
            )
            return []

        records = self._extract_search_results(
            result
        )

        print(
            "GitHub search returned",
            len(records),
            "candidate file(s).",
        )

        for record in records:
            print(
                "  ->",
                record.get("path", ""),
            )

        return records

    async def search_tool(
        self,
        query: str,
    ) -> list[dict]:
        """Compatibility alias."""

        return await self.search_code(query)

    # ==============================================================
    # FETCH
    # ==============================================================

    async def get_file_contents(
        self,
        path: str,
    ) -> str:
        """Fetch exactly one complete Markdown file."""

        path = (
            str(path)
            .strip()
            .lstrip("/")
        )

        if not path:
            return ""

        if not path.startswith(
            f"{FOLDER}/"
        ):
            raise ValueError(
                "Refusing to fetch a file outside "
                "the configured B2B folder:\n"
                f"{path}"
            )

        print()
        print("=" * 80)
        print("FETCHING:")
        print(path)
        print("=" * 80)

        try:
            result = await self.call_tool(
                "get_file_contents",
                {
                    "owner": OWNER,
                    "repo": REPO,
                    "path": path,
                    "ref": BRANCH,
                },
            )

        except Exception as exc:
            print(
                "GitHub fetch error:",
                exc,
            )
            return ""

        source = self._extract_file_content(
            result
        )

        print(
            "FILE CONTENT FETCHED:",
            len(source),
            "characters",
        )

        print(
            "FILE LINES FETCHED:",
            len(source.splitlines()),
        )

        return source

    async def fetch_tool(
        self,
        path: str,
    ) -> str:
        """Compatibility alias."""

        return await self.get_file_contents(path)

    # ==============================================================
    # SEARCH RESULT EXTRACTION
    # ==============================================================

    @classmethod
    def _extract_search_results(
        cls,
        result: Any,
    ) -> list[dict]:
        """
        Extract candidate files from every common MCP response form.

        GitHub MCP responses can expose data through:

        - structuredContent
        - structured_content
        - TextContent
        - EmbeddedResource
        - nested dictionaries
        - JSON strings
        - plain text
        """

        records: list[dict] = []

        # ----------------------------------------------------------
        # 1. Inspect structured content.
        # ----------------------------------------------------------

        for attribute in (
            "structuredContent",
            "structured_content",
        ):
            value = getattr(
                result,
                attribute,
                None,
            )

            if value is not None:
                cls._collect_search_paths(
                    value,
                    records,
                )

        # ----------------------------------------------------------
        # 2. Inspect MCP content items.
        # ----------------------------------------------------------

        content = getattr(
            result,
            "content",
            None,
        ) or []

        for item in content:

            # Direct TextContent.
            text = getattr(
                item,
                "text",
                None,
            )

            if text:
                cls._parse_search_text(
                    str(text),
                    records,
                )

            # EmbeddedResource.
            resource = getattr(
                item,
                "resource",
                None,
            )

            if resource is not None:

                resource_text = getattr(
                    resource,
                    "text",
                    None,
                )

                if resource_text:
                    cls._parse_search_text(
                        str(resource_text),
                        records,
                    )

        # ----------------------------------------------------------
        # 3. Recursively inspect the complete result object.
        # ----------------------------------------------------------

        cls._walk_for_search_data(
            result,
            records,
        )

        # ----------------------------------------------------------
        # 4. Last-resort raw text extraction.
        # ----------------------------------------------------------

        if not records:

            raw_text = cls._deep_text(
                result
            )

            cls._extract_paths_from_raw_text(
                raw_text,
                records,
            )

        records = cls._dedupe_records(
            records
        )

        return records

    @classmethod
    def _walk_for_search_data(
        cls,
        value: Any,
        records: list[dict],
        depth: int = 0,
    ) -> None:
        """Recursively inspect an arbitrary MCP response."""

        if value is None:
            return

        if depth > 20:
            return

        if isinstance(value, str):

            text = value.strip()

            if (
                text.startswith("{")
                or text.startswith("[")
            ):
                try:
                    parsed = json.loads(text)

                    cls._collect_search_paths(
                        parsed,
                        records,
                    )

                except Exception:
                    pass

            return

        if isinstance(value, dict):

            cls._collect_search_paths(
                value,
                records,
            )

            for child in value.values():
                cls._walk_for_search_data(
                    child,
                    records,
                    depth + 1,
                )

            return

        if isinstance(value, (list, tuple)):

            for child in value:
                cls._walk_for_search_data(
                    child,
                    records,
                    depth + 1,
                )

            return

        # MCP objects such as EmbeddedResource.
        for attribute in (
            "text",
            "content",
            "contents",
            "resource",
            "structuredContent",
            "structured_content",
        ):

            try:
                child = getattr(
                    value,
                    attribute,
                    None,
                )
            except Exception:
                child = None

            if child is not None:
                cls._walk_for_search_data(
                    child,
                    records,
                    depth + 1,
                )

    @classmethod
    def _parse_search_text(
        cls,
        text: str,
        records: list[dict],
    ) -> None:
        """Parse JSON and plain-text search output."""

        text = text.strip()

        if not text:
            return

        # Direct JSON.
        try:
            value = json.loads(text)

            cls._collect_search_paths(
                value,
                records,
            )

            if records:
                return

        except Exception:
            pass

        # JSON embedded inside surrounding text.
        for start_char in (
            "{",
            "[",
        ):

            start = text.find(
                start_char
            )

            if start < 0:
                continue

            possible_json = text[start:]

            try:
                value = json.loads(
                    possible_json
                )

                cls._collect_search_paths(
                    value,
                    records,
                )

                if records:
                    return

            except Exception:
                continue

        # Markdown paths appearing in plain text.
        cls._extract_paths_from_raw_text(
            text,
            records,
        )

    @classmethod
    def _collect_search_paths(
        cls,
        value: Any,
        records: list[dict],
    ) -> None:
        """Recursively find B2B Markdown paths."""

        if value is None:
            return

        if isinstance(value, dict):

            path = value.get(
                "path"
            )

            if (
                isinstance(path, str)
                and cls._is_valid_b2b_path(
                    path
                )
            ):

                record = {
                    "path": path,
                    "name": value.get(
                        "name",
                        path.rsplit(
                            "/",
                            1,
                        )[-1],
                    ),
                    "snippet": cls._snippet(
                        value
                    ),
                }

                records.append(
                    record
                )

            for child in value.values():
                cls._collect_search_paths(
                    child,
                    records,
                )

            return

        if isinstance(value, list):

            for child in value:
                cls._collect_search_paths(
                    child,
                    records,
                )

            return

        if isinstance(value, str):

            stripped = value.strip()

            if (
                stripped.startswith("{")
                or stripped.startswith("[")
            ):

                try:
                    parsed = json.loads(
                        stripped
                    )

                    cls._collect_search_paths(
                        parsed,
                        records,
                    )

                except Exception:
                    pass

    @staticmethod
    def _is_valid_b2b_path(
        path: str,
    ) -> bool:
        """Return True only for Markdown files in the B2B folder."""

        normalized = (
            path
            .replace("\\", "/")
            .lstrip("/")
        )

        return (
            normalized.startswith(
                f"{FOLDER}/"
            )
            and normalized.lower().endswith(
                (
                    ".md",
                    ".markdown",
                )
            )
        )

    @staticmethod
    def _extract_paths_from_raw_text(
        text: str,
        records: list[dict],
    ) -> None:
        """Find B2B Markdown paths in arbitrary text."""

        if not text:
            return

        pattern = re.compile(
            rf"{re.escape(FOLDER)}/"
            r"[A-Za-z0-9_./-]+"
            r"\.(?:md|markdown)",
            re.IGNORECASE,
        )

        for match in pattern.findall(
            text
        ):

            path = (
                match
                .replace("\\", "/")
                .strip(
                    ".,;:)\"'`"
                )
            )

            if path:
                records.append(
                    {
                        "path": path,
                        "name": path.rsplit(
                            "/",
                            1,
                        )[-1],
                    }
                )

    @staticmethod
    def _snippet(
        item: dict,
    ) -> str:
        """Extract useful search-result snippets."""

        parts = []

        matches = item.get(
            "text_matches",
            [],
        )

        if isinstance(
            matches,
            list,
        ):

            for match in matches:

                if isinstance(
                    match,
                    dict,
                ):

                    value = (
                        match.get(
                            "fragment"
                        )
                        or match.get(
                            "text"
                        )
                    )

                    if value:
                        parts.append(
                            str(value)
                        )

                elif isinstance(
                    match,
                    str,
                ):
                    parts.append(
                        match
                    )

        for key in (
            "fragment",
            "text",
            "content",
        ):

            value = item.get(
                key
            )

            if isinstance(
                value,
                str,
            ):
                parts.append(
                    value
                )

        return "\n".join(
            dict.fromkeys(
                parts
            )
        )

    # ==============================================================
    # FILE CONTENT EXTRACTION
    # ==============================================================

    @classmethod
    def _extract_file_content(
        cls,
        result: Any,
    ) -> str:
        """
        Extract the actual Markdown source.

        IMPORTANT:

        GitHub MCP can return:

        TextContent:
            successfully downloaded text file (SHA: ...)

        followed by:

        EmbeddedResource:
            resource.text = actual Markdown

        The SHA/status message must NEVER be used as source.
        """

        resource_parts: list[str] = []
        normal_parts: list[str] = []

        content = getattr(
            result,
            "content",
            None,
        ) or []

        for item in content:

            resource = getattr(
                item,
                "resource",
                None,
            )

            if resource is not None:

                resource_text = getattr(
                    resource,
                    "text",
                    None,
                )

                if resource_text:
                    resource_parts.append(
                        str(resource_text)
                    )

                continue

            text = getattr(
                item,
                "text",
                None,
            )

            if text:

                text = str(text).strip()

                if text.lower().startswith(
                    "successfully downloaded text file"
                ):
                    continue

                normal_parts.append(
                    text
                )

        # Prefer EmbeddedResource because it is the
        # actual downloaded file representation.
        if resource_parts:

            return "\n".join(
                resource_parts
            ).strip()

        if normal_parts:

            # Try JSON wrappers first.
            for part in normal_parts:

                extracted = cls._extract_source_from_json(
                    part
                )

                if extracted:
                    return extracted

            return "\n".join(
                normal_parts
            ).strip()

        # Final fallback.
        raw = cls._deep_text(
            result
        )

        return cls._extract_source_from_json(
            raw
        ) or raw.strip()

    @classmethod
    def _extract_source_from_json(
        cls,
        text: str,
    ) -> str:
        """Extract source content from JSON wrappers."""

        text = text.strip()

        if not text:
            return ""

        try:
            value = json.loads(
                text
            )
        except Exception:
            return ""

        candidates: list[str] = []

        cls._collect_source_strings(
            value,
            candidates,
        )

        # Remove MCP status messages.
        candidates = [
            item.strip()
            for item in candidates
            if item.strip()
            and not item.lower().startswith(
                "successfully downloaded text file"
            )
        ]

        if not candidates:
            return ""

        # Actual Markdown is normally the largest string.
        candidates.sort(
            key=len,
            reverse=True,
        )

        return candidates[0]

    @classmethod
    def _collect_source_strings(
        cls,
        value: Any,
        output: list[str],
        depth: int = 0,
    ) -> None:
        """Recursively collect possible source strings."""

        if value is None:
            return

        if depth > 20:
            return

        if isinstance(
            value,
            str,
        ):

            if value.strip():
                output.append(
                    value
                )

            return

        if isinstance(
            value,
            dict,
        ):

            for key in (
                "text",
                "content",
                "body",
                "source",
                "data",
                "output",
                "result",
            ):

                if key in value:
                    cls._collect_source_strings(
                        value[key],
                        output,
                        depth + 1,
                    )

            return

        if isinstance(
            value,
            (list, tuple),
        ):

            for child in value:
                cls._collect_source_strings(
                    child,
                    output,
                    depth + 1,
                )

    # ==============================================================
    # GENERIC TEXT EXTRACTION
    # ==============================================================

    @classmethod
    def _deep_text(
        cls,
        value: Any,
        depth: int = 0,
    ) -> str:
        """Extract textual data recursively."""

        if value is None:
            return ""

        if depth > 20:
            return ""

        if isinstance(
            value,
            str,
        ):
            return value

        if isinstance(
            value,
            dict,
        ):

            parts = []

            for child in value.values():

                text = cls._deep_text(
                    child,
                    depth + 1,
                )

                if text:
                    parts.append(
                        text
                    )

            return "\n".join(
                parts
            )

        if isinstance(
            value,
            (list, tuple),
        ):

            parts = []

            for child in value:

                text = cls._deep_text(
                    child,
                    depth + 1,
                )

                if text:
                    parts.append(
                        text
                    )

            return "\n".join(
                parts
            )

        for attribute in (
            "text",
            "content",
            "contents",
            "resource",
            "structuredContent",
            "structured_content",
        ):

            try:
                child = getattr(
                    value,
                    attribute,
                    None,
                )
            except Exception:
                child = None

            if child is not None:

                text = cls._deep_text(
                    child,
                    depth + 1,
                )

                if text:
                    return text

        return ""

    # ==============================================================
    # DEDUPLICATION
    # ==============================================================

    @staticmethod
    def _dedupe_records(
        records: list[dict],
    ) -> list[dict]:
        """Deduplicate candidate files by repository path."""

        output = []
        seen = set()

        for record in records:

            path = str(
                record.get(
                    "path",
                    "",
                )
            ).strip()

            path = (
                path
                .replace("\\", "/")
                .lstrip("/")
            )

            if not path:
                continue

            key = path.lower()

            if key in seen:
                continue

            seen.add(
                key
            )

            record = dict(
                record
            )

            record["path"] = path

            output.append(
                record
            )

        return output