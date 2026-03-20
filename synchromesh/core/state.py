from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StateManager:
    """
    Runtime metrics and run history manager for the modernization platform.
    """

    run_history: List[Dict[str, Any]] = field(default_factory=list)
    latest_metrics: Dict[str, Any] = field(default_factory=dict)

    def compute_metrics(
        self,
        *,
        repository_candidates: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        governed_actions: List[Dict[str, Any]],
        patch_plans: List[Dict[str, Any]],
        fallback_events: List[Dict[str, Any]],
        warnings: List[Dict[str, Any]],
        errors: List[Dict[str, Any]],
        evaluation_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        findings_by_category = Counter(str(item.get("category", "unknown")) for item in findings)
        findings_by_subcategory = Counter(str(item.get("subcategory", "unknown")) for item in findings)
        recommendations_by_type = Counter(str(item.get("proposal_type", "unknown")) for item in recommendations)
        governed_by_risk = Counter(str(item.get("risk_level", "unknown")) for item in governed_actions)

        auto_eligible_count = sum(
            1 for item in governed_actions if bool(item.get("allowed_to_apply", False))
        )
        approval_required_count = sum(
            1 for item in governed_actions if bool(item.get("requires_approval", False))
        )
        governance_block_count = sum(
            1 for item in governed_actions if not bool(item.get("allowed_to_apply", False))
        )

        auto_patch_count = sum(
            1 for item in patch_plans if bool(item.get("auto_applied", False))
        )
        manual_patch_plan_count = sum(
            1 for item in patch_plans if str(item.get("strategy", "")).upper() == "MANUAL_PATCH"
        )

        total_findings = len(findings)
        total_recommendations = len(recommendations)

        modernization_progress_score = round(
            (auto_patch_count / total_recommendations) * 100, 2
        ) if total_recommendations else 0.0

        auto_remediation_readiness = round(
            (auto_eligible_count / total_recommendations) * 100, 2
        ) if total_recommendations else 0.0

        frontend_findings = findings_by_category.get("frontend", 0)
        backend_findings = findings_by_category.get("backend", 0)
        config_findings = findings_by_category.get("config", 0)

        metrics = {
            "generated_at": _utc_now_iso(),
            "repository_candidate_count": len(repository_candidates),
            "total_findings": total_findings,
            "total_recommendations": total_recommendations,
            "total_governed_actions": len(governed_actions),
            "auto_eligible_count": auto_eligible_count,
            "approval_required_count": approval_required_count,
            "governance_block_count": governance_block_count,
            "auto_patch_count": auto_patch_count,
            "manual_patch_plan_count": manual_patch_plan_count,
            "frontend_findings_count": frontend_findings,
            "backend_findings_count": backend_findings,
            "config_findings_count": config_findings,
            "fallback_scan_count": len(fallback_events),
            "warning_count": len(warnings),
            "error_count": len(errors),
            "modernization_progress_score": modernization_progress_score,
            "auto_remediation_readiness": auto_remediation_readiness,
            "findings_by_category": dict(findings_by_category),
            "findings_by_subcategory": dict(findings_by_subcategory),
            "recommendations_by_type": dict(recommendations_by_type),
            "governed_actions_by_risk": dict(governed_by_risk),
            "evaluation_summary": deepcopy(evaluation_report),
        }

        self.latest_metrics = metrics
        return metrics

    def record_run(
        self,
        *,
        run_id: str,
        repo_root: str,
        repo_access_mode: str,
        scan_mode: str,
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        record = {
            "recorded_at": _utc_now_iso(),
            "run_id": run_id,
            "repo_root": repo_root,
            "repo_access_mode": repo_access_mode,
            "scan_mode": scan_mode,
            "metrics": deepcopy(metrics),
        }
        self.run_history.append(record)
        self.latest_metrics = deepcopy(metrics)
        return record

    def export_history(self, output_path: str) -> str:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.run_history, f, indent=2, ensure_ascii=False)
        return output_path