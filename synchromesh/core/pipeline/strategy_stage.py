from __future__ import annotations
from typing import Any, Dict, List, Optional

class StrategyStage:
    """
    Stage 3: Modernization recommendation generation using StrategistAgent.
    """

    def __init__(self, strategist_agent: Any):
        self.strategist = strategist_agent

    async def run(
        self,
        *,
        findings: List[Dict[str, Any]],
        figma_tokens: Optional[Dict[str, Any]] = None,
        token_format: str = "var(--{token})",
    ) -> Dict[str, Any]:
        recommendations: List[Dict[str, Any]] = self.strategist.generate_recommendations(
            findings=findings,
            figma_tokens=figma_tokens or {},
            token_format=token_format,
        )

        summary = {
            "recommendation_count": len(recommendations),
        }
        return {
            "modernization_recommendations": recommendations,
            "summary": summary,
        }