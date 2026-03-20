from __future__ import annotations
import hashlib
import re
from typing import Any, Dict, List, Optional
from .models import ScanFinding

class AnalyzerAgent:
    """
    Semantic analysis agent.

    Preferred order:
    1. style AST scan
    2. backend constants scan
    3. repo pattern scan
    4. fallback regex/content scan
    """

    _URL_PATTERN = re.compile(r"""https?://[^\s'")]+""", re.IGNORECASE)
    _TIMEOUT_PATTERN = re.compile(r"""\b[A-Z_]*TIMEOUT[A-Z_]*\b|\btimeout\b""")
    _STATUS_PATTERN = re.compile(r"""\b[A-Z_]*STATUS[A-Z_]*\b|\bstatus\b""")
    _ENUM_PY_PATTERN = re.compile(r"""class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((?:str,\s*)?Enum\)\s*:""")
    _JAVA_CONSTANT_PATTERN = re.compile(
        r"""public\s+static\s+final\s+[A-Za-z0-9_<>\[\]]+\s+([A-Z0-9_]+)\s*="""
    )
    _INLINE_STYLE_PATTERN = re.compile(r"""\bstyle\s*=\s*\{\{.*?\}\}""", re.DOTALL)
    _HEX_PATTERN = re.compile(r"""#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b""")
    _TODO_PATTERN = re.compile(r"""\bTODO\b""", re.IGNORECASE)
    _FIXME_PATTERN = re.compile(r"""\bFIXME\b""", re.IGNORECASE)
    _BROAD_EXCEPT_PATTERN = re.compile(r"""except\s+Exception\s*:""")

    def _make_finding_id(self, key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    async def analyze(
        self,
        repository_candidates: List[Dict[str, Any]],
        repo_client: Any,
        repo_root: str = "",
    ) -> List[Dict[str, Any]]:
        findings: List[ScanFinding] = []

        findings.extend(await self._scan_style_ast(repo_client, repo_root))
        findings.extend(await self._scan_backend_constants(repo_client, repo_root))
        findings.extend(await self._scan_repo_patterns(repo_client, repo_root))

        if not findings:
            findings.extend(await self._fallback_scan(repository_candidates, repo_client))

        return [f.to_dict() for f in self._deduplicate(findings)]

    async def _scan_style_ast(self, repo_client: Any, repo_root: str) -> List[ScanFinding]:
        fn = getattr(repo_client, "scan_style_ast", None)
        if not callable(fn):
            return []

        try:
            rows = await fn(repo_root=repo_root)
        except TypeError:
            rows = await fn(repo_root)
        except Exception:
            return []

        out: List[ScanFinding] = []
        for row in rows or []:
            file_path = str(row.get("file_path", "")).strip()
            if not file_path:
                continue

            out.append(
                ScanFinding(
                    finding_id=self._make_finding_id(
                        f"style_ast|{file_path}|{row.get('node_type','')}|{row.get('line','')}|{row.get('value','')}"
                    ),
                    category="frontend",
                    subcategory=str(row.get("subcategory", "style_ast_node")),
                    file_path=file_path,
                    language=self._infer_language(file_path),
                    title=str(row.get("title", "Frontend modernization finding")),
                    description=str(row.get("description", "Structured style-related AST node detected.")),
                    symbol_name=row.get("symbol_name"),
                    literal_value=str(row.get("value", "")) if row.get("value") is not None else None,
                    line=row.get("line"),
                    span_start=row.get("span_start"),
                    span_end=row.get("span_end"),
                    snippet=str(row.get("snippet", "")),
                    source_tool="scan_style_ast",
                    confidence_score=float(row.get("confidence_score", 0.9)),
                    severity=str(row.get("severity", "MEDIUM")).upper(),
                    metadata=row.get("metadata", {}) or {},
                )
            )
        return out

    async def _scan_backend_constants(self, repo_client: Any, repo_root: str) -> List[ScanFinding]:
        fn = getattr(repo_client, "scan_backend_constants", None)
        if not callable(fn):
            return []

        try:
            rows = await fn(repo_root=repo_root)
        except TypeError:
            rows = await fn(repo_root)
        except Exception:
            return []

        out: List[ScanFinding] = []
        for row in rows or []:
            file_path = str(row.get("file_path", "")).strip()
            if not file_path:
                continue

            out.append(
                ScanFinding(
                    finding_id=self._make_finding_id(
                        f"backend_scan|{file_path}|{row.get('subcategory','')}|{row.get('line','')}|{row.get('symbol_name','')}"
                    ),
                    category="backend",
                    subcategory=str(row.get("subcategory", "backend_constant")),
                    file_path=file_path,
                    language=self._infer_language(file_path),
                    title=str(row.get("title", "Backend modernization finding")),
                    description=str(row.get("description", "Structured backend modernization finding detected.")),
                    symbol_name=row.get("symbol_name"),
                    literal_value=str(row.get("value", "")) if row.get("value") is not None else None,
                    line=row.get("line"),
                    span_start=row.get("span_start"),
                    span_end=row.get("span_end"),
                    snippet=str(row.get("snippet", "")),
                    source_tool="scan_backend_constants",
                    confidence_score=float(row.get("confidence_score", 0.9)),
                    severity=str(row.get("severity", "MEDIUM")).upper(),
                    metadata=row.get("metadata", {}) or {},
                )
            )
        return out

    async def _scan_repo_patterns(self, repo_client: Any, repo_root: str) -> List[ScanFinding]:
        fn = getattr(repo_client, "scan_repo_patterns", None)
        if not callable(fn):
            return []

        try:
            rows = await fn(repo_root=repo_root)
        except TypeError:
            rows = await fn(repo_root)
        except Exception:
            return []

        out: List[ScanFinding] = []
        for row in rows or []:
            file_path = str(row.get("file_path", "")).strip()
            if not file_path:
                continue

            out.append(
                ScanFinding(
                    finding_id=self._make_finding_id(
                        f"repo_patterns|{file_path}|{row.get('subcategory','')}|{row.get('line','')}|{row.get('title','')}"
                    ),
                    category=str(row.get("category", self._classify_path(file_path) or "architecture")),
                    subcategory=str(row.get("subcategory", "repo_pattern")),
                    file_path=file_path,
                    language=self._infer_language(file_path),
                    title=str(row.get("title", "Repository modernization finding")),
                    description=str(row.get("description", "Repository pattern indicates modernization opportunity.")),
                    line=row.get("line"),
                    snippet=str(row.get("snippet", "")),
                    source_tool="scan_repo_patterns",
                    confidence_score=float(row.get("confidence_score", 0.82)),
                    severity=str(row.get("severity", "LOW")).upper(),
                    metadata=row.get("metadata", {}) or {},
                )
            )
        return out

    async def _fallback_scan(
        self,
        repository_candidates: List[Dict[str, Any]],
        repo_client: Any,
    ) -> List[ScanFinding]:
        out: List[ScanFinding] = []

        for candidate in repository_candidates:
            file_path = str(candidate.get("file_path", "")).strip()
            if not file_path:
                continue

            try:
                content = await self._safe_read_file(repo_client, file_path)
            except Exception:
                continue

            language = self._infer_language(file_path)
            category = self._classify_path(file_path) or "architecture"

            if category == "frontend":
                out.extend(self._fallback_frontend_scan(content, file_path, language))

            if category == "backend":
                out.extend(self._fallback_backend_scan(content, file_path, language))

            if category == "config":
                out.extend(self._fallback_config_scan(content, file_path, language))

        return out

    def _fallback_frontend_scan(self, content: str, file_path: str, language: str) -> List[ScanFinding]:
        out: List[ScanFinding] = []

        for match in self._INLINE_STYLE_PATTERN.finditer(content):
            out.append(
                self._finding(
                    category="frontend",
                    subcategory="inline_style",
                    file_path=file_path,
                    language=language,
                    title="Inline style usage",
                    description="Inline style block detected; this bypasses shared design system patterns.",
                    line=self._line_from_index(content, match.start()),
                    span_start=match.start(),
                    span_end=match.end(),
                    snippet=self._get_line_snippet(content, match.start()),
                    source_tool="regex_fallback",
                    confidence_score=0.88,
                    severity="MEDIUM",
                )
            )

        for match in self._HEX_PATTERN.finditer(content):
            out.append(
                self._finding(
                    category="frontend",
                    subcategory="hardcoded_color",
                    file_path=file_path,
                    language=language,
                    title="Hardcoded color value",
                    description="Hardcoded color value detected instead of tokenized styling.",
                    literal_value=match.group(0),
                    line=self._line_from_index(content, match.start()),
                    span_start=match.start(),
                    span_end=match.end(),
                    snippet=self._get_line_snippet(content, match.start()),
                    source_tool="regex_fallback",
                    confidence_score=0.84,
                    severity="MEDIUM",
                )
            )
        return out

    def _fallback_backend_scan(self, content: str, file_path: str, language: str) -> List[ScanFinding]:
        out: List[ScanFinding] = []

        for match in self._URL_PATTERN.finditer(content):
            out.append(
                self._finding(
                    category="backend",
                    subcategory="hardcoded_url",
                    file_path=file_path,
                    language=language,
                    title="Hardcoded URL",
                    description="Endpoint or external URL is hardcoded in backend code.",
                    literal_value=match.group(0),
                    line=self._line_from_index(content, match.start()),
                    span_start=match.start(),
                    span_end=match.end(),
                    snippet=self._get_line_snippet(content, match.start()),
                    source_tool="regex_fallback",
                    confidence_score=0.86,
                    severity="HIGH",
                )
            )

        for match in self._ENUM_PY_PATTERN.finditer(content):
            out.append(
                self._finding(
                    category="backend",
                    subcategory="python_enum",
                    file_path=file_path,
                    language=language,
                    title="Python Enum discovered",
                    description="Enum class detected; evaluate whether status/config literals should be normalized through it.",
                    symbol_name=match.group(1),
                    line=self._line_from_index(content, match.start()),
                    snippet=self._get_line_snippet(content, match.start()),
                    source_tool="regex_fallback",
                    confidence_score=0.8,
                    severity="LOW",
                )
            )

        for match in self._JAVA_CONSTANT_PATTERN.finditer(content):
            symbol = match.group(1)
            subcategory = "backend_constant"
            severity = "MEDIUM"
            description = "Java constant detected for modernization review."

            if symbol.endswith("_TIMEOUT"):
                subcategory = "timeout_constant"
                severity = "HIGH"
                description = "Timeout constant detected; consider centralization in shared config."
            elif symbol.endswith("_URL"):
                subcategory = "url_constant"
                severity = "HIGH"
                description = "URL constant detected; consider centralization in config/environment."
            elif symbol.endswith("_STATUS"):
                subcategory = "status_constant"
                severity = "MEDIUM"
                description = "Status constant detected; consider enum-backed normalization."

            out.append(
                self._finding(
                    category="backend",
                    subcategory=subcategory,
                    file_path=file_path,
                    language=language,
                    title="Java constant discovered",
                    description=description,
                    symbol_name=symbol,
                    line=self._line_from_index(content, match.start()),
                    snippet=self._get_line_snippet(content, match.start()),
                    source_tool="regex_fallback",
                    confidence_score=0.83,
                    severity=severity,
                )
            )

        for pattern, subcategory, title, description, severity in [
            (self._TIMEOUT_PATTERN, "timeout_literal_or_symbol", "Timeout-related symbol", "Timeout-related identifier detected in backend code.", "MEDIUM"),
            (self._STATUS_PATTERN, "status_literal_or_symbol", "Status-related symbol", "Status-related identifier detected in backend code.", "LOW"),
            (self._TODO_PATTERN, "todo_marker", "TODO marker", "TODO marker suggests unresolved modernization work.", "LOW"),
            (self._FIXME_PATTERN, "fixme_marker", "FIXME marker", "FIXME marker suggests known technical debt.", "MEDIUM"),
            (self._BROAD_EXCEPT_PATTERN, "broad_exception", "Broad exception handling", "Broad exception handling pattern detected.", "MEDIUM"),
        ]:
            for match in pattern.finditer(content):
                out.append(
                    self._finding(
                        category="backend",
                        subcategory=subcategory,
                        file_path=file_path,
                        language=language,
                        title=title,
                        description=description,
                        line=self._line_from_index(content, match.start()),
                        snippet=self._get_line_snippet(content, match.start()),
                        source_tool="regex_fallback",
                        confidence_score=0.78,
                        severity=severity,
                    )
                )
        return out

    def _fallback_config_scan(self, content: str, file_path: str, language: str) -> List[ScanFinding]:
        out: List[ScanFinding] = []
        for match in self._URL_PATTERN.finditer(content):
            out.append(
                self._finding(
                    category="config",
                    subcategory="config_endpoint",
                    file_path=file_path,
                    language=language,
                    title="Endpoint in config",
                    description="Endpoint value found in configuration; verify centralization and environment-specific handling.",
                    literal_value=match.group(0),
                    line=self._line_from_index(content, match.start()),
                    snippet=self._get_line_snippet(content, match.start()),
                    source_tool="regex_fallback",
                    confidence_score=0.75,
                    severity="LOW",
                )
            )
        return out

    def _finding(
        self,
        *,
        category: str,
        subcategory: str,
        file_path: str,
        language: str,
        title: str,
        description: str,
        symbol_name: Optional[str] = None,
        literal_value: Optional[str] = None,
        line: Optional[int] = None,
        span_start: Optional[int] = None,
        span_end: Optional[int] = None,
        snippet: str = "",
        source_tool: str,
        confidence_score: float,
        severity: str,
    ) -> ScanFinding:
        return ScanFinding(
            finding_id=self._make_finding_id(
                f"{category}|{subcategory}|{file_path}|{line}|{symbol_name or ''}|{literal_value or ''}|{snippet}"
            ),
            category=category,
            subcategory=subcategory,
            file_path=file_path,
            language=language,
            title=title,
            description=description,
            symbol_name=symbol_name,
            literal_value=literal_value,
            line=line,
            span_start=span_start,
            span_end=span_end,
            snippet=snippet,
            source_tool=source_tool,
            confidence_score=confidence_score,
            severity=severity,
        )

    def _deduplicate(self, findings: List[ScanFinding]) -> List[ScanFinding]:
        seen = set()
        deduped: List[ScanFinding] = []
        for item in findings:
            key = (
                item.category,
                item.subcategory,
                item.file_path,
                item.line,
                item.symbol_name,
                item.literal_value,
                item.snippet,
            )
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped

    def _infer_language(self, file_path: str) -> str:
        raw = file_path.lower()
        if raw.endswith(".py"):
            return "python"
        if raw.endswith(".java"):
            return "java"
        if raw.endswith((".ts", ".tsx")):
            return "typescript"
        if raw.endswith((".js", ".jsx")):
            return "javascript"
        if raw.endswith((".css", ".scss")):
            return "css"
        if raw.endswith((".json", ".yaml", ".yml", ".env", ".toml", ".ini", ".properties")):
            return "config"
        return "unknown"

    def _classify_path(self, file_path: str) -> Optional[str]:
        normalized = file_path.replace("\\", "/").lower()
        if normalized.endswith((".js", ".jsx", ".ts", ".tsx", ".css", ".scss")):
            return "frontend"
        if normalized.endswith((".py", ".java", ".kt", ".go", ".rb")):
            return "backend"
        if normalized.endswith((".json", ".yaml", ".yml", ".env", ".toml", ".ini", ".properties")):
            return "config"
        return None

    @staticmethod
    def _line_from_index(text: str, index: int) -> int:
        return text.count("\n", 0, index) + 1

    @staticmethod
    def _get_line_snippet(text: str, index: int, max_len: int = 220) -> str:
        line_start = text.rfind("\n", 0, index)
        line_end = text.find("\n", index)

        if line_start == -1:
            line_start = 0
        else:
            line_start += 1

        if line_end == -1:
            line_end = len(text)

        snippet = text[line_start:line_end].strip()
        if len(snippet) > max_len:
            snippet = snippet[: max_len - 3] + "..."
        return snippet

    async def _safe_read_file(self, repo_client: Any, path: str) -> str:
        fn = getattr(repo_client, "read_file", None)
        if callable(fn):
            return await fn(path)

        fn = getattr(repo_client, "get_file_content", None)
        if callable(fn):
            return await fn(path)

        raise AttributeError("Repo client must expose read_file(.) or get_file_content(.)")