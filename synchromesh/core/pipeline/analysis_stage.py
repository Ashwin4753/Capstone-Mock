from __future__ import annotations
from typing import Any, Dict, List

class AnalysisStage:
    """
    Stage 2: Semantic analysis using AnalyzerAgent.
    """

    def __init__(self, analyzer_agent: Any):
        self.analyzer = analyzer_agent

    async def run(
        self,
        *,
        repository_candidates: List[Dict[str, Any]],
        repo_client: Any,
        repo_root: str,
    ) -> Dict[str, Any]:
        findings: List[Dict[str, Any]] = await self.analyzer.analyze(
            repository_candidates=repository_candidates,
            github_mcp_client=repo_client,
            repo_root=repo_root,
        )

        source_tools = sorted({str(item.get("source_tool", "unknown")) for item in findings})
        summary = {
            "finding_count": len(findings),
            "source_tools": source_tools,
        }
        return {
            "analysis_findings": findings,
            "summary": summary,
        }