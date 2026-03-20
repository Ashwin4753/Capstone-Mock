from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class LocalRepoClient:
    """
    First-class local repository backend.

    Supports:
    - file operations
    - repo-wide search
    - local modernization scans
    - symbol usage resolution
    """

    TEXT_EXTENSIONS = {
        ".py", ".java", ".js", ".jsx", ".ts", ".tsx",
        ".css", ".scss", ".json", ".yaml", ".yml",
        ".toml", ".ini", ".properties", ".md", ".env",
    }

    IGNORE_DIRS = {
        ".git", ".hg", ".svn",
        "node_modules", "dist", "build", ".next",
        ".venv", "venv", "__pycache__", ".pytest_cache",
        ".mypy_cache", ".idea", ".vscode", "coverage",
    }

    FRONTEND_EXTS = {".js", ".jsx", ".ts", ".tsx", ".css", ".scss"}
    BACKEND_EXTS = {".py", ".java"}
    CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".properties", ".env"}

    HEX_PATTERN = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
    INLINE_STYLE_PATTERN = re.compile(r"\bstyle\s*=\s*\{\{.*?\}\}", re.DOTALL)
    URL_PATTERN = re.compile(r"https?://[^\s'\"`)<]+", re.IGNORECASE)
    TODO_PATTERN = re.compile(r"\bTODO\b", re.IGNORECASE)
    FIXME_PATTERN = re.compile(r"\bFIXME\b", re.IGNORECASE)
    BROAD_EXCEPT_PATTERN = re.compile(r"except\s+Exception\s*:")
    PY_ENUM_CLASS_PATTERN = re.compile(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((?:str,\s*)?Enum\)\s*:")
    JAVA_CONSTANT_PATTERN = re.compile(
        r"public\s+static\s+final\s+[A-Za-z0-9_<>\[\]]+\s+([A-Z0-9_]+)\s*="
    )
    DEBUG_PATTERN = re.compile(r"\b(console\.log|print\s*\()", re.IGNORECASE)

    def __init__(self, repo_root: str) -> None:
        self.repo_root = str(Path(repo_root).resolve())

    def access_mode(self) -> str:
        return "local"

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
            "create_pull_request": False,
        }

    async def set_repo(self, *_args, **_kwargs) -> None:
        """
        Compatibility shim for clients that expect set_repo().
        """
        return None

    async def list_files(self, repo_root: str = "") -> List[str]:
        base = self._resolve_repo_root(repo_root)
        results: List[str] = []

        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            for name in files:
                path = Path(root) / name
                if path.suffix.lower() in self.TEXT_EXTENSIONS:
                    results.append(self._relative(path))
        return sorted(results)

    async def read_file(self, path: str) -> str:
        resolved = self._resolve_path(path)
        with open(resolved, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    async def write_file(self, path: str, content: str) -> None:
        resolved = self._resolve_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)

    async def search_code(self, query: str, repo_root: str = "") -> List[Dict[str, Any]]:
        """
        Local regex/text search across repo.
        """
        pattern = re.compile(query, re.IGNORECASE)
        results: List[Dict[str, Any]] = []

        for path in await self.list_files(repo_root):
            try:
                content = await self.read_file(path)
            except Exception:
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                if pattern.search(line):
                    results.append(
                        {
                            "file_path": path,
                            "line": line_no,
                            "snippet": line.strip(),
                        }
                    )
        return results

    async def scan_style_ast(self, repo_root: str = "") -> List[Dict[str, Any]]:
        """
        Local semantic-ish frontend scan.
        Uses structured parsing where practical and regex-backed extraction where needed.
        """
        findings: List[Dict[str, Any]] = []

        for path in await self.list_files(repo_root):
            suffix = Path(path).suffix.lower()
            if suffix not in self.FRONTEND_EXTS:
                continue

            try:
                content = await self.read_file(path)
            except Exception:
                continue

            if suffix in {".js", ".jsx", ".ts", ".tsx"}:
                findings.extend(self._scan_frontend_code(path, content))
            elif suffix in {".css", ".scss"}:
                findings.extend(self._scan_stylesheet(path, content))

        return findings

    async def scan_backend_constants(self, repo_root: str = "") -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        for path in await self.list_files(repo_root):
            suffix = Path(path).suffix.lower()
            if suffix not in self.BACKEND_EXTS:
                continue

            try:
                content = await self.read_file(path)
            except Exception:
                continue

            if suffix == ".py":
                findings.extend(self._scan_python_backend(path, content))
            elif suffix == ".java":
                findings.extend(self._scan_java_backend(path, content))

        return findings

    async def scan_repo_patterns(self, repo_root: str = "") -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        for path in await self.list_files(repo_root):
            try:
                content = await self.read_file(path)
            except Exception:
                continue

            category = self._categorize_path(path)

            for pattern, subcategory, title, description, severity in [
                (self.TODO_PATTERN, "todo_marker", "TODO marker", "Unresolved technical debt marker.", "LOW"),
                (self.FIXME_PATTERN, "fixme_marker", "FIXME marker", "Known issue or unresolved engineering debt.", "MEDIUM"),
                (self.DEBUG_PATTERN, "debug_statement", "Debug statement", "Debug/log statement detected in source.", "LOW"),
            ]:
                for match in pattern.finditer(content):
                    findings.append(
                        self._make_finding(
                            file_path=path,
                            category=category,
                            subcategory=subcategory,
                            title=title,
                            description=description,
                            severity=severity,
                            line=self._line_from_index(content, match.start()),
                            snippet=self._get_line_snippet(content, match.start()),
                            source_tool="local_repo_patterns",
                        )
                    )

            if Path(path).suffix.lower() == ".py":
                for match in self.BROAD_EXCEPT_PATTERN.finditer(content):
                    findings.append(
                        self._make_finding(
                            file_path=path,
                            category="backend",
                            subcategory="broad_exception",
                            title="Broad exception handling",
                            description="Broad exception handling detected in Python code.",
                            severity="MEDIUM",
                            line=self._line_from_index(content, match.start()),
                            snippet=self._get_line_snippet(content, match.start()),
                            source_tool="local_repo_patterns",
                        )
                    )

        return findings

    async def resolve_symbol_usage(self, symbol: str, repo_root: str = "") -> List[Dict[str, Any]]:
        if not symbol.strip():
            return []

        escaped = re.escape(symbol)
        pattern = re.compile(rf"\b{escaped}\b")
        results: List[Dict[str, Any]] = []

        for path in await self.list_files(repo_root):
            try:
                content = await self.read_file(path)
            except Exception:
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                if pattern.search(line):
                    results.append(
                        {
                            "file_path": path,
                            "line": line_no,
                            "snippet": line.strip(),
                            "symbol": symbol,
                        }
                    )
        return results

    def _scan_frontend_code(self, path: str, content: str) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        for match in self.INLINE_STYLE_PATTERN.finditer(content):
            findings.append(
                self._make_finding(
                    file_path=path,
                    category="frontend",
                    subcategory="style_ast_inline_object",
                    title="Inline style object",
                    description="Inline style object detected in frontend source.",
                    severity="MEDIUM",
                    line=self._line_from_index(content, match.start()),
                    span_start=match.start(),
                    span_end=match.end(),
                    snippet=self._get_line_snippet(content, match.start()),
                    source_tool="local_style_ast",
                    metadata={"node_type": "inline_style"},
                )
            )

        for match in self.HEX_PATTERN.finditer(content):
            findings.append(
                self._make_finding(
                    file_path=path,
                    category="frontend",
                    subcategory="style_ast_color_literal",
                    title="Color literal",
                    description="Hardcoded color literal detected in frontend source.",
                    severity="MEDIUM",
                    line=self._line_from_index(content, match.start()),
                    span_start=match.start(),
                    span_end=match.end(),
                    value=match.group(0),
                    snippet=self._get_line_snippet(content, match.start()),
                    source_tool="local_style_ast",
                    metadata={"node_type": "color_literal"},
                )
            )

        return findings

    def _scan_stylesheet(self, path: str, content: str) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        for match in self.HEX_PATTERN.finditer(content):
            findings.append(
                self._make_finding(
                    file_path=path,
                    category="frontend",
                    subcategory="style_ast_color_literal",
                    title="Stylesheet color literal",
                    description="Hardcoded color literal detected in stylesheet.",
                    severity="MEDIUM",
                    line=self._line_from_index(content, match.start()),
                    span_start=match.start(),
                    span_end=match.end(),
                    value=match.group(0),
                    snippet=self._get_line_snippet(content, match.start()),
                    source_tool="local_style_ast",
                    metadata={"node_type": "stylesheet_color"},
                )
            )
        return findings

    def _scan_python_backend(self, path: str, content: str) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        # AST pass for constants and enums
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    base_names = {self._ast_name(base) for base in node.bases}
                    if "Enum" in base_names or "strEnum" in base_names or "StrEnum" in base_names:
                        findings.append(
                            self._make_finding(
                                file_path=path,
                                category="backend",
                                subcategory="python_enum",
                                title="Python Enum",
                                description="Python Enum class detected.",
                                severity="LOW",
                                line=getattr(node, "lineno", None),
                                snippet=self._get_line_by_no(content, getattr(node, "lineno", 1)),
                                source_tool="local_backend_ast",
                                symbol_name=node.name,
                            )
                        )

                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            symbol = target.id
                            literal = self._literal_from_ast(node.value)
                            subcategory, severity, description = self._classify_backend_symbol(symbol)

                            findings.append(
                                self._make_finding(
                                    file_path=path,
                                    category="backend",
                                    subcategory=subcategory,
                                    title="Python constant",
                                    description=description,
                                    severity=severity,
                                    line=getattr(node, "lineno", None),
                                    snippet=self._get_line_by_no(content, getattr(node, "lineno", 1)),
                                    source_tool="local_backend_ast",
                                    symbol_name=symbol,
                                    value=literal,
                                )
                            )
        except Exception:
            pass

        for match in self.URL_PATTERN.finditer(content):
            findings.append(
                self._make_finding(
                    file_path=path,
                    category="backend",
                    subcategory="hardcoded_url",
                    title="Hardcoded URL",
                    description="Hardcoded URL detected in backend source.",
                    severity="HIGH",
                    line=self._line_from_index(content, match.start()),
                    span_start=match.start(),
                    span_end=match.end(),
                    value=match.group(0),
                    snippet=self._get_line_snippet(content, match.start()),
                    source_tool="local_backend_ast",
                )
            )

        return findings

    def _scan_java_backend(self, path: str, content: str) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        for match in self.JAVA_CONSTANT_PATTERN.finditer(content):
            symbol = match.group(1)
            subcategory, severity, description = self._classify_backend_symbol(symbol)
            findings.append(
                self._make_finding(
                    file_path=path,
                    category="backend",
                    subcategory=subcategory,
                    title="Java constant",
                    description=description,
                    severity=severity,
                    line=self._line_from_index(content, match.start()),
                    snippet=self._get_line_snippet(content, match.start()),
                    source_tool="local_backend_ast",
                    symbol_name=symbol,
                )
            )

        for match in self.URL_PATTERN.finditer(content):
            findings.append(
                self._make_finding(
                    file_path=path,
                    category="backend",
                    subcategory="hardcoded_url",
                    title="Hardcoded URL",
                    description="Hardcoded URL detected in Java source.",
                    severity="HIGH",
                    line=self._line_from_index(content, match.start()),
                    span_start=match.start(),
                    span_end=match.end(),
                    value=match.group(0),
                    snippet=self._get_line_snippet(content, match.start()),
                    source_tool="local_backend_ast",
                )
            )

        return findings

    def _classify_backend_symbol(self, symbol: str) -> Tuple[str, str, str]:
        if symbol.endswith("_TIMEOUT"):
            return "timeout_constant", "HIGH", "Timeout-related constant detected."
        if symbol.endswith("_URL"):
            return "url_constant", "HIGH", "URL-related constant detected."
        if symbol.endswith("_STATUS"):
            return "status_constant", "MEDIUM", "Status-related constant detected."
        return "backend_constant", "MEDIUM", "Backend constant detected."

    def _make_finding(
        self,
        *,
        file_path: str,
        category: str,
        subcategory: str,
        title: str,
        description: str,
        severity: str,
        line: Optional[int] = None,
        span_start: Optional[int] = None,
        span_end: Optional[int] = None,
        snippet: str = "",
        source_tool: str,
        value: Optional[str] = None,
        symbol_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "file_path": file_path,
            "category": category,
            "subcategory": subcategory,
            "title": title,
            "description": description,
            "severity": severity,
            "line": line,
            "span_start": span_start,
            "span_end": span_end,
            "snippet": snippet,
            "source_tool": source_tool,
            "value": value,
            "literal_value": value,
            "symbol_name": symbol_name,
            "confidence_score": 0.86,
            "metadata": metadata or {},
        }

    def _categorize_path(self, path: str) -> str:
        suffix = Path(path).suffix.lower()
        if suffix in self.FRONTEND_EXTS:
            return "frontend"
        if suffix in self.BACKEND_EXTS:
            return "backend"
        if suffix in self.CONFIG_EXTS:
            return "config"
        return "architecture"

    def _resolve_repo_root(self, repo_root: str = "") -> Path:
        if not repo_root:
            return Path(self.repo_root)
        resolved = (Path(self.repo_root) / repo_root).resolve()
        self._validate_within_root(resolved)
        return resolved

    def _resolve_path(self, path: str) -> Path:
        resolved = (Path(self.repo_root) / path).resolve()
        self._validate_within_root(resolved)
        return resolved

    def _validate_within_root(self, resolved: Path) -> None:
        root = Path(self.repo_root).resolve()
        if root not in resolved.parents and resolved != root:
            raise ValueError(f"Path escapes repository root: {resolved}")

    def _relative(self, path: Path) -> str:
        return str(path.resolve().relative_to(Path(self.repo_root).resolve())).replace("\\", "/")

    def _line_from_index(self, text: str, index: int) -> int:
        return text.count("\n", 0, index) + 1

    def _get_line_snippet(self, text: str, index: int, max_len: int = 220) -> str:
        start = text.rfind("\n", 0, index)
        end = text.find("\n", index)
        start = 0 if start == -1 else start + 1
        end = len(text) if end == -1 else end
        snippet = text[start:end].strip()
        return snippet if len(snippet) <= max_len else snippet[: max_len - 3] + "..."

    def _get_line_by_no(self, text: str, line_no: int) -> str:
        lines = text.splitlines()
        if 1 <= line_no <= len(lines):
            return lines[line_no - 1].strip()
        return ""

    def _ast_name(self, node: Any) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return type(node).__name__

    def _literal_from_ast(self, node: Any) -> Optional[str]:
        if isinstance(node, ast.Constant):
            return str(node.value)
        return None