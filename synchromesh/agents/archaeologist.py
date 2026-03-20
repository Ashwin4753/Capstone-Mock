from __future__ import annotations
import hashlib
from typing import Any, Dict, List, Optional
from .models import ScanFinding

class ArchaeologistAgent:
    """
    Repository discovery + capability-based candidate collection.

    Responsibilities:
    - discover relevant files in frontend/backend/config zones
    - call search tools when available through the unified repo client
    - return broad modernization candidates
    - avoid deep semantic interpretation (that belongs to Analyzer)
    """

    FRONTEND_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".css", ".scss")
    BACKEND_EXTENSIONS = (".py", ".java", ".kt", ".go", ".rb")
    CONFIG_EXTENSIONS = (".json", ".yaml", ".yml", ".env", ".toml", ".ini", ".properties")

    FRONTEND_HINTS = ("/src/", "/ui/", "/components/", "/pages/", "/styles/", "/frontend/")
    BACKEND_HINTS = ("/api/", "/server/", "/backend/", "/services/", "/controllers/", "/models/")
    CONFIG_HINTS = ("/config/", "/settings/", "/env/", "/resources/")

    def _make_finding_id(self, key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    async def scan_repository(
        self,
        repo_client: Any,
        repo_root: str = "",
    ) -> List[Dict[str, Any]]:
        files = await self._safe_list_files(repo_client, repo_root)
        findings: List[ScanFinding] = []

        for file_path in files:
            normalized = str(file_path).replace("\\", "/").lower()
            category = self._classify_path(normalized)
            if category is None:
                continue

            title = f"Modernization candidate in {category} layer"
            description = (
                "File identified as a candidate for modernization analysis based on path, "
                "extension, and repository heuristics."
            )

            findings.append(
                ScanFinding(
                    finding_id=self._make_finding_id(f"candidate|{file_path}|{category}"),
                    category=category,
                    subcategory="candidate_file",
                    file_path=file_path,
                    language=self._infer_language(file_path),
                    title=title,
                    description=description,
                    source_tool="repo_tree_scan",
                    confidence_score=0.75,
                    severity="LOW",
                    metadata={"repo_root": repo_root},
                )
            )

        # Enrich with repo search hotspots if available
        search_results = await self._safe_search_code(repo_client)
        for item in search_results:
            file_path = str(item.get("file_path", "")).strip()
            if not file_path:
                continue

            findings.append(
                ScanFinding(
                    finding_id=self._make_finding_id(
                        f"search_hotspot|{file_path}|{item.get('subcategory', 'search_hotspot')}|{item.get('line', '')}"
                    ),
                    category=str(item.get("category", self._classify_path(file_path.lower()) or "architecture")),
                    subcategory=str(item.get("subcategory", "search_hotspot")),
                    file_path=file_path,
                    language=self._infer_language(file_path),
                    title=str(item.get("title", "Potential modernization hotspot")),
                    description=str(item.get("description", "Repository search matched a modernization-related pattern.")),
                    line=item.get("line"),
                    snippet=str(item.get("snippet", "")),
                    source_tool="search_code",
                    confidence_score=float(item.get("confidence_score", 0.78)),
                    severity=str(item.get("severity", "LOW")).upper(),
                    metadata=item.get("metadata", {}) or {},
                )
            )

        return [f.to_dict() for f in self._deduplicate(findings)]

    def _classify_path(self, normalized_path: str) -> Optional[str]:
        if normalized_path.endswith(self.FRONTEND_EXTENSIONS) or any(h in normalized_path for h in self.FRONTEND_HINTS):
            return "frontend"

        if normalized_path.endswith(self.BACKEND_EXTENSIONS) or any(h in normalized_path for h in self.BACKEND_HINTS):
            return "backend"

        if normalized_path.endswith(self.CONFIG_EXTENSIONS) or any(h in normalized_path for h in self.CONFIG_HINTS):
            return "config"

        return None

    def _infer_language(self, file_path: str) -> str:
        raw = file_path.lower()
        if raw.endswith(".py"):
            return "python"
        if raw.endswith(".java"):
            return "java"
        if raw.endswith(".kt"):
            return "kotlin"
        if raw.endswith(".go"):
            return "go"
        if raw.endswith(".rb"):
            return "ruby"
        if raw.endswith((".js", ".jsx")):
            return "javascript"
        if raw.endswith((".ts", ".tsx")):
            return "typescript"
        if raw.endswith((".css", ".scss")):
            return "css"
        if raw.endswith((".yaml", ".yml", ".json", ".toml", ".ini", ".properties", ".env")):
            return "config"
        return "unknown"

    def _deduplicate(self, findings: List[ScanFinding]) -> List[ScanFinding]:
        seen = set()
        out: List[ScanFinding] = []

        for item in findings:
            key = (
                item.category,
                item.subcategory,
                item.file_path,
                item.line,
                item.title,
                item.snippet,
            )
            if key not in seen:
                seen.add(key)
                out.append(item)

        return out

    async def _safe_list_files(self, repo_client: Any, repo_root: str) -> List[str]:
        fn = getattr(repo_client, "list_files", None)
        if callable(fn):
            return await fn(repo_root)

        fn = getattr(repo_client, "get_file_tree", None)
        if callable(fn):
            return await fn(repo_root)

        raise AttributeError("Repo client must expose list_files(.) or get_file_tree(.)")

    async def _safe_search_code(self, repo_client: Any) -> List[Dict[str, Any]]:
        """
        Optional enrichment.
        If search_code does not exist, return [].
        """
        fn = getattr(repo_client, "search_code", None)
        if not callable(fn):
            return []

        queries = [
            {
                "pattern": "TODO|FIXME|console.log|print\\(",
                "subcategory": "legacy_debug_or_debt_marker",
                "title": "Legacy debug or debt marker",
                "description": "Potential technical debt marker discovered via repository search.",
                "severity": "LOW",
            },
            {
                "pattern": "http://|https://|_TIMEOUT|_URL|_STATUS",
                "subcategory": "hardcoded_constant_or_endpoint",
                "title": "Potential hardcoded backend constant",
                "description": "Potential hardcoded endpoint/status/timeout discovered via repository search.",
                "severity": "MEDIUM",
            },
        ]

        out: List[Dict[str, Any]] = []
        for q in queries:
            try:
                rows = await fn(q["pattern"])
            except Exception:
                continue

            for row in rows or []:
                out.append(
                    {
                        "file_path": row.get("file_path") or row.get("path") or "",
                        "line": row.get("line"),
                        "snippet": row.get("snippet", ""),
                        "category": self._classify_path(str(row.get("file_path") or row.get("path") or "").lower()) or "architecture",
                        "subcategory": q["subcategory"],
                        "title": q["title"],
                        "description": q["description"],
                        "severity": q["severity"],
                        "confidence_score": 0.8,
                        "metadata": {"match": row},
                    }
                )
        return out