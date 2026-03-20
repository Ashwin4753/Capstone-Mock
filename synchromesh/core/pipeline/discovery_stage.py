from __future__ import annotations
from typing import Any, Dict, List

class DiscoveryStage:
    """
    Stage 1: Repository discovery using ArchaeologistAgent.
    """

    def __init__(self, archaeologist_agent: Any):
        self.archaeologist = archaeologist_agent

    async def run(
        self,
        *,
        repo_client: Any,
        repo_root: str,
    ) -> Dict[str, Any]:
        candidates: List[Dict[str, Any]] = await self.archaeologist.scan_repository(
            github_mcp_client=repo_client,
            repo_root=repo_root,
        )
        summary = {
            "candidate_count": len(candidates),
        }
        return {
            "repository_candidates": candidates,
            "summary": summary,
        }