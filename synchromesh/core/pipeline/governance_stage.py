from __future__ import annotations
from typing import Any, Dict, List

class GovernanceStage:
    """
    Stage 4: Governance review using GovernorAgent.
    """

    def __init__(self, governor_agent: Any):
        self.governor = governor_agent

    async def run(
        self,
        *,
        recommendations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        governed_actions: List[Dict[str, Any]] = self.governor.evaluate_recommendations(
            recommendations=recommendations
        )

        summary = {
            "governed_action_count": len(governed_actions),
            "auto_allowed_count": sum(
                1 for item in governed_actions if bool(item.get("allowed_to_apply", False))
            ),
            "approval_required_count": sum(
                1 for item in governed_actions if bool(item.get("requires_approval", False))
            ),
        }
        return {
            "governed_actions": governed_actions,
            "summary": summary,
        }