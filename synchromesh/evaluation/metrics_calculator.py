from __future__ import annotations
from collections import Counter, defaultdict
from typing import Any, Dict, List

class MetricsCalculator:
    """
    Computes modernization-first run metrics.

    This replaces the old parity-centric evaluation model.
    """

    def calculate(
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
    ) -> Dict[str, Any]:
        findings_by_category = Counter(str(item.get("category", "unknown")) for item in findings)
        findings_by_subcategory = Counter(str(item.get("subcategory", "unknown")) for item in findings)
        findings_by_severity = Counter(str(item.get("severity", "unknown")) for item in findings)

        recommendations_by_type = Counter(str(item.get("proposal_type", "unknown")) for item in recommendations)
        recommendations_by_risk_hint = Counter(str(item.get("risk_hint", "unknown")) for item in recommendations)

        governed_by_risk = Counter(str(item.get("risk_level", "unknown")) for item in governed_actions)
        governed_by_policy = Counter()
        for item in governed_actions:
            for tag in item.get("policy_tags", []) or []:
                governed_by_policy[str(tag)] += 1

        patches_by_strategy = Counter(str(item.get("strategy", "unknown")) for item in patch_plans)

        findings_by_file = Counter(str(item.get("file_path", "unknown")) for item in findings)
        recommendations_by_file = Counter(str(item.get("file_path", "unknown")) for item in recommendations)

        top_impacted_files = []
        file_union = set(findings_by_file) | set(recommendations_by_file)
        for file_path in file_union:
            top_impacted_files.append(
                {
                    "file_path": file_path,
                    "findings": findings_by_file.get(file_path, 0),
                    "recommendations": recommendations_by_file.get(file_path, 0),
                    "impact_score": findings_by_file.get(file_path, 0) + recommendations_by_file.get(file_path, 0),
                }
            )
        top_impacted_files.sort(key=lambda item: item["impact_score"], reverse=True)

        total_recommendations = len(recommendations)
        auto_eligible_count = sum(1 for item in governed_actions if bool(item.get("allowed_to_apply", False)))
        auto_applied_count = sum(1 for item in patch_plans if bool(item.get("auto_applied", False)))
        manual_patch_count = sum(
            1 for item in patch_plans if str(item.get("strategy", "")).upper() == "MANUAL_PATCH"
        )
        approval_required_count = sum(1 for item in governed_actions if bool(item.get("requires_approval", False)))
        governance_block_count = sum(1 for item in governed_actions if not bool(item.get("allowed_to_apply", False)))

        modernization_progress_score = round(
            (auto_applied_count / total_recommendations) * 100, 2
        ) if total_recommendations else 0.0

        auto_remediation_readiness = round(
            (auto_eligible_count / total_recommendations) * 100, 2
        ) if total_recommendations else 0.0

        frontend_findings_count = findings_by_category.get("frontend", 0)
        backend_findings_count = findings_by_category.get("backend", 0)
        config_findings_count = findings_by_category.get("config", 0)
        architecture_findings_count = findings_by_category.get("architecture", 0)

        return {
            "repository_candidate_count": len(repository_candidates),
            "total_findings": len(findings),
            "total_recommendations": len(recommendations),
            "total_governed_actions": len(governed_actions),
            "total_patch_plans": len(patch_plans),
            "frontend_findings_count": frontend_findings_count,
            "backend_findings_count": backend_findings_count,
            "config_findings_count": config_findings_count,
            "architecture_findings_count": architecture_findings_count,
            "approval_required_count": approval_required_count,
            "governance_block_count": governance_block_count,
            "auto_eligible_count": auto_eligible_count,
            "auto_applied_count": auto_applied_count,
            "manual_patch_count": manual_patch_count,
            "fallback_scan_count": len(fallback_events),
            "warning_count": len(warnings),
            "error_count": len(errors),
            "modernization_progress_score": modernization_progress_score,
            "auto_remediation_readiness": auto_remediation_readiness,
            "findings_by_category": dict(findings_by_category),
            "findings_by_subcategory": dict(findings_by_subcategory),
            "findings_by_severity": dict(findings_by_severity),
            "recommendations_by_type": dict(recommendations_by_type),
            "recommendations_by_risk_hint": dict(recommendations_by_risk_hint),
            "governed_actions_by_risk": dict(governed_by_risk),
            "governed_actions_by_policy": dict(governed_by_policy),
            "patches_by_strategy": dict(patches_by_strategy),
            "top_impacted_files": top_impacted_files[:20],
        }

    def calculate_frontend_submetrics(
        self,
        *,
        findings: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Optional frontend-specific metrics retained for the original design-sync story.
        """
        frontend_findings = [item for item in findings if str(item.get("category")) == "frontend"]
        token_recommendations = [
            item for item in recommendations if str(item.get("proposal_type", "")).upper() == "TOKEN_SUBSTITUTION"
        ]

        parity_proxy = round(
            (len(token_recommendations) / len(frontend_findings)) * 100, 2
        ) if frontend_findings else 0.0

        return {
            "frontend_findings_count": len(frontend_findings),
            "token_recommendation_count": len(token_recommendations),
            "frontend_parity_proxy": parity_proxy,
        }

    def build_dashboard_summary(
        self,
        *,
        metrics: Dict[str, Any],
        evaluation_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "headline_metrics": {
                "total_findings": metrics.get("total_findings", 0),
                "total_recommendations": metrics.get("total_recommendations", 0),
                "auto_applied_count": metrics.get("auto_applied_count", 0),
                "governance_block_count": metrics.get("governance_block_count", 0),
                "modernization_progress_score": metrics.get("modernization_progress_score", 0.0),
            },
            "category_breakdown": metrics.get("findings_by_category", {}),
            "proposal_breakdown": metrics.get("recommendations_by_type", {}),
            "risk_breakdown": metrics.get("governed_actions_by_risk", {}),
            "evaluation_summary": evaluation_report,
        }