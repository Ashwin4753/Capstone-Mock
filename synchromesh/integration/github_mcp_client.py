from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except Exception:  # pragma: no cover
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None


class GitHubMCPClient:
    """
    GitHub MCP-backed modernization backend.

    Exposes the same high-level operations as LocalRepoClient wherever possible.
    """

    def __init__(
        self,
        *,
        server_command: str = "npx",
        server_args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        self.server_command = server_command
        self.server_args = server_args or ["-y", "@modelcontextprotocol/server-github"]
        self.env = env or os.environ.copy()
        self.owner: Optional[str] = None
        self.repo: Optional[str] = None

    def access_mode(self) -> str:
        return "remote"

    def capabilities(self) -> Dict[str, bool]:
        return {
            "list_files": True,
            "read_file": True,
            "write_file": True,
            "search_code": True,
            "scan_style_ast": True,
            "scan_backend_constants": True,
            "scan_repo_patterns": True,
            "resolve_symbol_usage": True,
            "create_pull_request": True,
        }

    def is_available(self) -> bool:
        return (
            ClientSession is not None
            and StdioServerParameters is not None
            and stdio_client is not None
            and bool(self.env.get("GITHUB_TOKEN"))
        )

    async def set_repo(self, owner: str, repo: str) -> None:
        self.owner = owner
        self.repo = repo

    async def health_check(self) -> Dict[str, Any]:
        if not self.is_available():
            return {"ok": False, "reason": "GitHub MCP dependencies or GITHUB_TOKEN missing"}

        try:
            tools = await self.list_tools()
            return {"ok": True, "tool_count": len(tools), "tools": tools}
        except Exception as exc:
            return {"ok": False, "reason": str(exc)}

    async def list_tools(self) -> List[str]:
        async with self._session() as session:
            response = await session.list_tools()
            return [tool.name for tool in getattr(response, "tools", [])]

    async def list_files(self, repo_root: str = "") -> List[str]:
        self._require_repo()
        tool_names = await self.list_tools()

        if "get_tree" in tool_names:
            rows = await self._call_tool("get_tree", {"owner": self.owner, "repo": self.repo, "path": repo_root or ""})
            return self._extract_tree_paths(rows)

        if "search_code" in tool_names:
            gathered = set()
            for ext in ["py", "java", "js", "jsx", "ts", "tsx", "css", "scss", "json", "yaml", "yml"]:
                query = f"repo:{self.owner}/{self.repo} extension:{ext}"
                rows = await self.search_code(query, repo_root=repo_root)
                for row in rows:
                    path = row.get("file_path")
                    if path:
                        gathered.add(path)
            return sorted(gathered)

        raise RuntimeError("No MCP tool available for listing files")

    async def read_file(self, path: str) -> str:
        self._require_repo()
        tool_names = await self.list_tools()

        candidates = []
        if "get_file_contents" in tool_names:
            candidates.extend(
                [
                    ("get_file_contents", {"owner": self.owner, "repo": self.repo, "path": path}),
                    ("get_file_contents", {"repo": f"{self.owner}/{self.repo}", "path": path}),
                ]
            )
        if "read_file" in tool_names:
            candidates.extend(
                [
                    ("read_file", {"owner": self.owner, "repo": self.repo, "path": path}),
                    ("read_file", {"repo": f"{self.owner}/{self.repo}", "path": path}),
                ]
            )

        last_error: Optional[Exception] = None
        for tool_name, payload in candidates:
            try:
                raw = await self._call_tool(tool_name, payload)
                return self._extract_file_content(raw)
            except Exception as exc:
                last_error = exc

        if last_error:
            raise last_error
        raise RuntimeError("Unable to read file via GitHub MCP")

    async def write_file(self, path: str, content: str, message: str = "Update file via SynchroMesh") -> None:
        self._require_repo()
        tool_names = await self.list_tools()

        candidates = []
        if "create_or_update_file" in tool_names:
            candidates.extend(
                [
                    (
                        "create_or_update_file",
                        {
                            "owner": self.owner,
                            "repo": self.repo,
                            "path": path,
                            "content": content,
                            "message": message,
                        },
                    ),
                    (
                        "create_or_update_file",
                        {
                            "repo": f"{self.owner}/{self.repo}",
                            "path": path,
                            "content": content,
                            "message": message,
                        },
                    ),
                ]
            )
        if "update_file" in tool_names:
            candidates.extend(
                [
                    (
                        "update_file",
                        {
                            "owner": self.owner,
                            "repo": self.repo,
                            "path": path,
                            "content": content,
                            "message": message,
                        },
                    )
                ]
            )

        last_error: Optional[Exception] = None
        for tool_name, payload in candidates:
            try:
                await self._call_tool(tool_name, payload)
                return
            except Exception as exc:
                last_error = exc

        if last_error:
            raise last_error
        raise RuntimeError("Unable to write file via GitHub MCP")

    async def search_code(self, query: str, repo_root: str = "") -> List[Dict[str, Any]]:
        self._require_repo()
        tool_names = await self.list_tools()

        if "search_code" not in tool_names:
            raise RuntimeError("GitHub MCP search_code tool unavailable")

        full_query = query
        if f"repo:{self.owner}/{self.repo}" not in full_query:
            full_query = f"repo:{self.owner}/{self.repo} {full_query}".strip()

        raw = await self._call_tool("search_code", {"query": full_query})
        return self._normalize_search_results(raw, repo_root=repo_root)

    async def scan_style_ast(self, repo_root: str = "") -> List[Dict[str, Any]]:
        tool_names = await self.list_tools()

        if "scan_style_ast" in tool_names:
            try:
                raw = await self._call_tool("scan_style_ast", self._repo_payload(repo_root))
                return self._normalize_generic_findings(raw, default_category="frontend", default_source="scan_style_ast")
            except Exception:
                pass

        # graceful MCP fallback using search_code
        findings: List[Dict[str, Any]] = []
        for query, subcategory, title, description in [
            ("style={{", "style_ast_inline_object", "Inline style object", "Inline style object detected through MCP search."),
            ("#", "style_ast_color_literal", "Color literal", "Potential hardcoded color literal detected through MCP search."),
        ]:
            try:
                rows = await self.search_code(query, repo_root=repo_root)
            except Exception:
                continue

            for row in rows:
                findings.append(
                    {
                        "file_path": row.get("file_path", ""),
                        "category": "frontend",
                        "subcategory": subcategory,
                        "title": title,
                        "description": description,
                        "line": row.get("line"),
                        "snippet": row.get("snippet", ""),
                        "source_tool": "search_code",
                        "confidence_score": 0.72,
                        "severity": "MEDIUM",
                        "metadata": {"search_query": query},
                    }
                )
        return findings

    async def scan_backend_constants(self, repo_root: str = "") -> List[Dict[str, Any]]:
        tool_names = await self.list_tools()

        if "scan_backend_constants" in tool_names:
            try:
                raw = await self._call_tool("scan_backend_constants", self._repo_payload(repo_root))
                return self._normalize_generic_findings(raw, default_category="backend", default_source="scan_backend_constants")
            except Exception:
                pass

        findings: List[Dict[str, Any]] = []
        for query, subcategory, title, description, severity in [
            ("_TIMEOUT", "timeout_constant", "Timeout constant", "Timeout-related constant detected through MCP search.", "HIGH"),
            ("_URL", "url_constant", "URL constant", "URL-related constant detected through MCP search.", "HIGH"),
            ("_STATUS", "status_constant", "Status constant", "Status-related constant detected through MCP search.", "MEDIUM"),
            ("class Enum", "python_enum", "Enum class", "Enum-related declaration detected through MCP search.", "LOW"),
            ("public static final", "backend_constant", "Java constant", "Java constant declaration detected through MCP search.", "MEDIUM"),
        ]:
            try:
                rows = await self.search_code(query, repo_root=repo_root)
            except Exception:
                continue

            for row in rows:
                findings.append(
                    {
                        "file_path": row.get("file_path", ""),
                        "category": "backend",
                        "subcategory": subcategory,
                        "title": title,
                        "description": description,
                        "line": row.get("line"),
                        "snippet": row.get("snippet", ""),
                        "source_tool": "search_code",
                        "confidence_score": 0.75,
                        "severity": severity,
                        "metadata": {"search_query": query},
                    }
                )
        return findings

    async def scan_repo_patterns(self, repo_root: str = "") -> List[Dict[str, Any]]:
        tool_names = await self.list_tools()

        if "scan_repo_patterns" in tool_names:
            try:
                raw = await self._call_tool("scan_repo_patterns", self._repo_payload(repo_root))
                return self._normalize_generic_findings(raw, default_category="architecture", default_source="scan_repo_patterns")
            except Exception:
                pass

        findings: List[Dict[str, Any]] = []
        for query, subcategory, title, description, severity in [
            ("TODO", "todo_marker", "TODO marker", "TODO marker detected through MCP search.", "LOW"),
            ("FIXME", "fixme_marker", "FIXME marker", "FIXME marker detected through MCP search.", "MEDIUM"),
            ("console.log", "debug_statement", "Debug statement", "console.log detected through MCP search.", "LOW"),
            ("print(", "debug_statement", "Debug statement", "print statement detected through MCP search.", "LOW"),
            ("except Exception", "broad_exception", "Broad exception", "Broad exception handling detected through MCP search.", "MEDIUM"),
        ]:
            try:
                rows = await self.search_code(query, repo_root=repo_root)
            except Exception:
                continue

            for row in rows:
                findings.append(
                    {
                        "file_path": row.get("file_path", ""),
                        "category": self._category_from_path(row.get("file_path", "")),
                        "subcategory": subcategory,
                        "title": title,
                        "description": description,
                        "line": row.get("line"),
                        "snippet": row.get("snippet", ""),
                        "source_tool": "search_code",
                        "confidence_score": 0.74,
                        "severity": severity,
                        "metadata": {"search_query": query},
                    }
                )
        return findings

    async def resolve_symbol_usage(self, symbol: str, repo_root: str = "") -> List[Dict[str, Any]]:
        if not symbol.strip():
            return []

        rows = await self.search_code(symbol, repo_root=repo_root)
        return [
            {
                "file_path": row.get("file_path", ""),
                "line": row.get("line"),
                "snippet": row.get("snippet", ""),
                "symbol": symbol,
            }
            for row in rows
        ]

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> Dict[str, Any]:
        self._require_repo()
        tool_names = await self.list_tools()
        if "create_pull_request" not in tool_names:
            raise RuntimeError("GitHub MCP create_pull_request tool unavailable")

        raw = await self._call_tool(
            "create_pull_request",
            {
                "owner": self.owner,
                "repo": self.repo,
                "title": title,
                "body": body,
                "head": head,
                "base": base,
            },
        )
        return self._normalize_json(raw)

    def _repo_payload(self, repo_root: str = "") -> Dict[str, Any]:
        self._require_repo()
        return {
            "owner": self.owner,
            "repo": self.repo,
            "repo_root": repo_root,
            "path": repo_root,
        }

    def _extract_tree_paths(self, raw: Any) -> List[str]:
        data = self._normalize_json(raw)
        results: List[str] = []

        if isinstance(data, dict):
            for key in ("tree", "files", "items", "entries"):
                rows = data.get(key)
                if isinstance(rows, list):
                    for row in rows:
                        path = row.get("path") if isinstance(row, dict) else None
                        if path and not str(path).endswith("/"):
                            results.append(str(path))
        elif isinstance(data, list):
            for row in data:
                if isinstance(row, dict):
                    path = row.get("path")
                    if path and not str(path).endswith("/"):
                        results.append(str(path))
        return sorted(set(results))

    def _extract_file_content(self, raw: Any) -> str:
        data = self._normalize_json(raw)

        if isinstance(data, dict):
            for key in ("content", "text", "body"):
                value = data.get(key)
                if isinstance(value, str):
                    return value
        if isinstance(data, str):
            return data
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _normalize_search_results(self, raw: Any, repo_root: str = "") -> List[Dict[str, Any]]:
        data = self._normalize_json(raw)
        rows = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

        out: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            path = row.get("path") or row.get("file_path") or ""
            if repo_root and path and not str(path).startswith(repo_root):
                continue

            out.append(
                {
                    "file_path": str(path),
                    "line": row.get("line") or row.get("line_number"),
                    "snippet": row.get("snippet") or row.get("text") or "",
                }
            )
        return out

    def _normalize_generic_findings(
        self,
        raw: Any,
        *,
        default_category: str,
        default_source: str,
    ) -> List[Dict[str, Any]]:
        data = self._normalize_json(raw)
        rows = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

        findings: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            findings.append(
                {
                    "file_path": row.get("file_path") or row.get("path") or "",
                    "category": row.get("category", default_category),
                    "subcategory": row.get("subcategory", "mcp_finding"),
                    "title": row.get("title", "MCP finding"),
                    "description": row.get("description", "Finding returned from MCP scan."),
                    "line": row.get("line"),
                    "span_start": row.get("span_start"),
                    "span_end": row.get("span_end"),
                    "snippet": row.get("snippet", ""),
                    "value": row.get("value"),
                    "literal_value": row.get("value"),
                    "symbol_name": row.get("symbol_name"),
                    "source_tool": row.get("source_tool", default_source),
                    "confidence_score": row.get("confidence_score", 0.9),
                    "severity": row.get("severity", "MEDIUM"),
                    "metadata": row.get("metadata", {}),
                }
            )
        return findings

    def _normalize_json(self, raw: Any) -> Any:
        if hasattr(raw, "content"):
            pieces = []
            for item in getattr(raw, "content", []) or []:
                text = getattr(item, "text", None)
                if text:
                    pieces.append(text)
            if len(pieces) == 1:
                raw = pieces[0]
            elif pieces:
                raw = "\n".join(pieces)

        if isinstance(raw, (dict, list)):
            return raw

        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return {}
            try:
                return json.loads(text)
            except Exception:
                return {"raw": text}

        return {}

    def _category_from_path(self, path: str) -> str:
        lower = str(path).lower()
        if lower.endswith((".js", ".jsx", ".ts", ".tsx", ".css", ".scss")):
            return "frontend"
        if lower.endswith((".py", ".java")):
            return "backend"
        if lower.endswith((".json", ".yaml", ".yml", ".toml", ".ini", ".properties", ".env")):
            return "config"
        return "architecture"

    def _require_repo(self) -> None:
        if not self.owner or not self.repo:
            raise RuntimeError("Repository not set. Call set_repo(owner, repo) first.")

    async def _call_tool(self, tool_name: str, payload: Dict[str, Any]) -> Any:
        async with self._session() as session:
            return await session.call_tool(tool_name, payload)

    @asynccontextmanager
    async def _session(self):
        if not self.is_available():
            raise RuntimeError("GitHub MCP client unavailable")

        server_params = StdioServerParameters(
            command=self.server_command,
            args=self.server_args,
            env=self.env,
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session