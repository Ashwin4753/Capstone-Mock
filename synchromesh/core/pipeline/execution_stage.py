from __future__ import annotations
from typing import Any, Dict, List

class ExecutionStage:
    """
    Stage 5: Controlled execution using SyncerAgent.
    """

    def __init__(self, syncer_agent: Any):
        self.syncer = syncer_agent

    async def run(
        self,
        *,
        recommendations: List[Dict[str, Any]],
        governed_actions: List[Dict[str, Any]],
        repo_client: Any,
        require_approved: bool = True,
        approved_key: str = "approved",
    ) -> Dict[str, Any]:
        patch_result: Dict[str, Any] = await self.syncer.apply_changes(
            recommendations=recommendations,
            governed_actions=governed_actions,
            github_mcp_client=repo_client,
            require_approved=require_approved,
            approved_key=approved_key,
        )

        patch_plans = patch_result.get("patch_plans", []) or []
        diffs = patch_result.get("diffs", []) or []

        applied_changes: List[Dict[str, Any]] = [
            item for item in patch_plans if bool(item.get("auto_applied", False))
        ]

        summary = {
            "patch_plan_count": len(patch_plans),
            "applied_change_count": len(applied_changes),
            "diff_count": len(diffs),
            "manual_count": int(patch_result.get("manual_count", 0)),
        }

        return {
            "patch_plans": patch_plans,
            "applied_changes": applied_changes,
            "diffs": diffs,
            "raw_patch_result": patch_result,
            "summary": summary,
        }