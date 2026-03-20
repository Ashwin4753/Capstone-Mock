from __future__ import annotations

from typing import Any, Dict, List, Optional


class RepoAdapter:
    """
    Unified repository backend.

    Philosophy:
    - local repo is source of truth for file operations
    - MCP is preferred for enrichment when available
    - both expose the same high-level capability surface
    """

    def __init__(
        self,
        *,
        local_client: Optional[Any] = None,
        github_client: Optional[Any] = None,
        prefer_local_for_files: bool = True,
        prefer_mcp_for_analysis: bool = True,
    ) -> None:
        self.local = local_client
        self.github = github_client
        self.prefer_local_for_files = prefer_local_for_files
        self.prefer_mcp_for_analysis = prefer_mcp_for_analysis

    def access_mode(self) -> str:
        has_local = self.local is not None
        has_remote = self.github is not None

        if has_local and has_remote:
            return "hybrid"
        if has_local:
            return "local"
        if has_remote:
            return "remote"
        return "unknown"

    def capabilities(self) -> Dict[str, bool]:
        capability_names = [
            "list_files",
            "read_file",
            "write_file",
            "search_code",
            "scan_style_ast",
            "scan_backend_constants",
            "scan_repo_patterns",
            "resolve_symbol_usage",
            "create_pull_request",
        ]

        result: Dict[str, bool] = {}
        for name in capability_names:
            result[name] = bool(
                self._has_method(self.local, name) or self._has_method(self.github, name)
            )
        return result

    async def list_files(self, repo_root: str = "") -> List[str]:
        client = self._choose_file_client("list_files")
        return await client.list_files(repo_root)

    async def read_file(self, path: str) -> str:
        client = self._choose_file_client("read_file")
        return await client.read_file(path)

    async def write_file(self, path: str, content: str) -> None:
        client = self._choose_file_client("write_file")
        return await client.write_file(path, content)

    async def search_code(self, query: str, repo_root: str = "") -> List[Dict[str, Any]]:
        client = self._choose_analysis_client("search_code")
        return await client.search_code(query, repo_root=repo_root)

    async def scan_style_ast(self, repo_root: str = "") -> List[Dict[str, Any]]:
        client = self._choose_analysis_client("scan_style_ast")
        return await client.scan_style_ast(repo_root=repo_root)

    async def scan_backend_constants(self, repo_root: str = "") -> List[Dict[str, Any]]:
        client = self._choose_analysis_client("scan_backend_constants")
        return await client.scan_backend_constants(repo_root=repo_root)

    async def scan_repo_patterns(self, repo_root: str = "") -> List[Dict[str, Any]]:
        client = self._choose_analysis_client("scan_repo_patterns")
        return await client.scan_repo_patterns(repo_root=repo_root)

    async def resolve_symbol_usage(self, symbol: str, repo_root: str = "") -> List[Dict[str, Any]]:
        client = self._choose_analysis_client("resolve_symbol_usage")
        return await client.resolve_symbol_usage(symbol, repo_root=repo_root)

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> Dict[str, Any]:
        if not self._has_method(self.github, "create_pull_request"):
            raise RuntimeError("Pull request creation requires GitHub MCP backend")
        return await self.github.create_pull_request(title=title, body=body, head=head, base=base)

    def _choose_file_client(self, method_name: str) -> Any:
        if self.prefer_local_for_files and self._has_method(self.local, method_name):
            return self.local
        if self._has_method(self.github, method_name):
            return self.github
        if self._has_method(self.local, method_name):
            return self.local
        raise RuntimeError(f"No backend available for file operation: {method_name}")

    def _choose_analysis_client(self, method_name: str) -> Any:
        if self.prefer_mcp_for_analysis and self._has_method(self.github, method_name):
            return self.github
        if self._has_method(self.local, method_name):
            return self.local
        if self._has_method(self.github, method_name):
            return self.github
        raise RuntimeError(f"No backend available for analysis operation: {method_name}")

    def _has_method(self, client: Optional[Any], method_name: str) -> bool:
        return client is not None and callable(getattr(client, method_name, None))