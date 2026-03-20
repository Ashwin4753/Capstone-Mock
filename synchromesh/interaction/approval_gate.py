from __future__ import annotations

import hashlib
from typing import Any, Dict, List

class ApprovalGate:
    """
    UI-facing approval normalizer for modernization actions.
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

    def build_approval_items(
        self,
        recommendations: List[Dict[str, Any]],
        governed_actions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        action_map = {str(a.get("change_id", "")): a for a in governed_actions}
        out: List[Dict[str, Any]] = []

        for rec in recommendations:
            change_id = str(rec.get("change_id", ""))
            action = action_map.get(change_id, {})

            file_path = str(rec.get("file_path", ""))
            approval_id = self._make_approval_id(
                file_path=file_path,
                proposal_type=str(rec.get("proposal_type", "")),
                proposed_state=str(rec.get("proposed_state", "")),
                target_symbol=str(rec.get("target_symbol", "")),
            )

            out.append(
                {
                    "approval_id": approval_id,
                    "change_id": change_id,
                    "finding_id": rec.get("finding_id"),
                    "file_path": file_path,
                    "title": rec.get("title", "Modernization recommendation"),
                    "proposal_type": rec.get("proposal_type", ""),
                    "current_state": rec.get("current_state", ""),
                    "proposed_state": rec.get("proposed_state", ""),
                    "target_symbol": rec.get("target_symbol", ""),
                    "reasoning": rec.get("reasoning", ""),
                    "risk_hint": rec.get("risk_hint", "MEDIUM"),
                    "risk_level": action.get("risk_level", rec.get("risk_hint", "MEDIUM")),
                    "requires_approval": bool(action.get("requires_approval", True)),
                    "allowed_to_apply": bool(action.get("allowed_to_apply", False)),
                    "policy_tags": action.get("policy_tags", []) or [],
                    "governance_reason": action.get("reason", ""),
                    "approved": False,
                    "rejected": False,
                    "manual_only": str(rec.get("proposal_type", "")).upper() in {
                        "MOVE_TO_CONFIG",
                        "USE_ENUM",
                        "MANUAL_REFACTOR",
                        "MANUAL_REVIEW",
                    },
                }
            )

        return out

    def apply_interactive_policy(
        self,
        approval_items: List[Dict[str, Any]],
        *,
        max_auto_apply_files: int = 5,
    ) -> List[Dict[str, Any]]:
        touched_files = {
            str(item.get("file_path", ""))
            for item in approval_items
            if bool(item.get("allowed_to_apply", False))
        }

        for item in approval_items:
            file_path = str(item.get("file_path", "")).replace("\\", "/").lower()

            if any(token in file_path for token in self.PROTECTED_PATH_TOKENS):
                item["allowed_to_apply"] = False
                item["requires_approval"] = True
                item["governance_reason"] = "Protected path: manual approval required."
                item.setdefault("policy_tags", []).append("protected_path")

            if len(touched_files) > max_auto_apply_files:
                item["allowed_to_apply"] = False
                item["requires_approval"] = True
                item["governance_reason"] = (
                    f"Auto-apply disabled because touched files exceed threshold "
                    f"({len(touched_files)} > {max_auto_apply_files})."
                )
                item.setdefault("policy_tags", []).append("max_auto_apply_threshold")

        return approval_items

    def apply_user_decisions(
        self,
        approval_items: List[Dict[str, Any]],
        decisions: Dict[str, bool],
    ) -> List[Dict[str, Any]]:
        for item in approval_items:
            approval_id = str(item.get("approval_id", ""))
            if approval_id in decisions:
                approved = bool(decisions[approval_id])
                item["approved"] = approved
                item["rejected"] = not approved
        return approval_items

    def extract_syncer_ready_recommendations(
        self,
        recommendations: List[Dict[str, Any]],
        approval_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        approval_map = {str(item.get("change_id", "")): item for item in approval_items}

        out: List[Dict[str, Any]] = []
        for rec in recommendations:
            item = approval_map.get(str(rec.get("change_id", "")), {})
            enriched = dict(rec)
            enriched["approved"] = bool(item.get("approved", False))
            enriched["rejected"] = bool(item.get("rejected", False))
            enriched["requires_approval"] = bool(item.get("requires_approval", True))
            enriched["allowed_to_apply"] = bool(item.get("allowed_to_apply", False))
            out.append(enriched)
        return out

    def summarize(self, approval_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "total_items": len(approval_items),
            "approval_required_count": sum(1 for i in approval_items if bool(i.get("requires_approval", False))),
            "auto_allowed_count": sum(1 for i in approval_items if bool(i.get("allowed_to_apply", False))),
            "approved_count": sum(1 for i in approval_items if bool(i.get("approved", False))),
            "rejected_count": sum(1 for i in approval_items if bool(i.get("rejected", False))),
            "manual_only_count": sum(1 for i in approval_items if bool(i.get("manual_only", False))),
        }

    def _make_approval_id(
        self,
        *,
        file_path: str,
        proposal_type: str,
        proposed_state: str,
        target_symbol: str,
    ) -> str:
        raw = f"{file_path}|{proposal_type}|{proposed_state}|{target_symbol}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]