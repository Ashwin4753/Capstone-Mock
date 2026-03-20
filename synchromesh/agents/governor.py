from __future__ import annotations

from typing import Any, Dict, List

from .models import GovernedAction


class GovernorAgent:
    """
    Governance / risk policy layer.

    Keeps policy separate from recommendation logic.
    """

    PROTECTED_PATH_TOKENS = (
        "/migrations/",
        "/database/",
        "/infra/",
        "/terraform/",
        "/k8s/",
        "/helm/",
        "/auth/",
        "/security/",
    )

    def evaluate_recommendations(
        self,
        recommendations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        out: List[GovernedAction] = []

        for rec in recommendations:
            file_path = str(rec.get("file_path", "")).replace("\\", "/").lower()
            proposal_type = str(rec.get("proposal_type", "")).upper()
            risk_hint = str(rec.get("risk_hint", "MEDIUM")).upper()
            auto_applicable = bool(rec.get("auto_applicable", False))

            risk_level = risk_hint
            requires_approval = True
            allowed_to_apply = False
            reason = "Manual review required by default."
            policy_tags: List[str] = []

            if any(token in file_path for token in self.PROTECTED_PATH_TOKENS):
                risk_level = "HIGH"
                requires_approval = True
                allowed_to_apply = False
                reason = "Protected path: automatic modification is blocked."
                policy_tags.append("protected_path")
            elif proposal_type == "TOKEN_SUBSTITUTION" and auto_applicable and risk_hint == "LOW":
                risk_level = "LOW"
                requires_approval = False
                allowed_to_apply = True
                reason = "Exact low-risk token substitution is auto-eligible."
                policy_tags.append("safe_frontend_substitution")
            elif proposal_type in {"MOVE_TO_CONFIG", "USE_ENUM", "MANUAL_REFACTOR", "MANUAL_REVIEW"}:
                risk_level = max(risk_hint, "MEDIUM")
                requires_approval = True
                allowed_to_apply = False
                reason = "Structural or backend modernization requires approval."
                policy_tags.append("structural_change")
            else:
                risk_level = risk_hint
                requires_approval = True
                allowed_to_apply = False
                reason = "Change does not qualify for auto-apply under current policy."
                policy_tags.append("default_review")

            out.append(
                GovernedAction(
                    change_id=str(rec.get("change_id", "")),
                    finding_id=str(rec.get("finding_id", "")),
                    risk_level=risk_level,
                    requires_approval=requires_approval,
                    allowed_to_apply=allowed_to_apply,
                    reason=reason,
                    policy_tags=policy_tags,
                    metadata={"proposal_type": proposal_type},
                )
            )

        return [item.to_dict() for item in out]