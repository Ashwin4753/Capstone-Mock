from __future__ import annotations
from typing import Any, Dict, List, Optional
from evaluation import MetricsCalculator, ReportGenerator, TraceAnalyzer
from .models import EvaluationReport

class EvaluatorAgent:
    """
    Evaluates modernization runs using the shared evaluation utilities.

    Responsibilities:
    - compute modernization-first metrics
    - summarize outcomes for orchestrator consumption
    - optionally generate report bundles
    - optionally summarize trace logs
    """

    def __init__(
        self,
        metrics_calculator: Optional[MetricsCalculator] = None,
        trace_analyzer: Optional[TraceAnalyzer] = None,
        report_generator: Optional[ReportGenerator] = None,
    ) -> None:
        self.metrics_calculator = metrics_calculator or MetricsCalculator()
        self.trace_analyzer = trace_analyzer or TraceAnalyzer()
        self.report_generator = report_generator or ReportGenerator()

    def evaluate(
        self,
        *,
        run_id: str = "",
        repo_root: str = "",
        repo_access_mode: str = "unknown",
        scan_mode: str = "unknown",
        available_capabilities: Optional[List[str]] = None,
        repository_candidates: Optional[List[Dict[str, Any]]] = None,
        findings: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        governed_actions: List[Dict[str, Any]],
        patch_result: Dict[str, Any],
        warnings: Optional[List[Dict[str, Any]]] = None,
        errors: Optional[List[Dict[str, Any]]] = None,
        fallback_events: Optional[List[Dict[str, Any]]] = None,
        trace_logs: Optional[List[Dict[str, Any]]] = None,
        report_output_dir: Optional[str] = None,
        generate_reports: bool = False,
    ) -> Dict[str, Any]:
        available_capabilities = available_capabilities or []
        repository_candidates = repository_candidates or []
        warnings = warnings or []
        errors = errors or []
        fallback_events = fallback_events or []
        trace_logs = trace_logs or []

        patch_plans = patch_result.get("patch_plans", []) or []

        metrics = self.metrics_calculator.calculate(
            repository_candidates=repository_candidates,
            findings=findings,
            recommendations=recommendations,
            governed_actions=governed_actions,
            patch_plans=patch_plans,
            fallback_events=fallback_events,
            warnings=warnings,
            errors=errors,
        )

        frontend_submetrics = self.metrics_calculator.calculate_frontend_submetrics(
            findings=findings,
            recommendations=recommendations,
        )

        trace_summary = self.trace_analyzer.summarize(trace_logs) if trace_logs else {
            "trace_count": 0,
            "stages_seen": [],
            "stage_counts": {},
            "event_counts": {},
            "stage_event_counts": {},
        }

        finding_trace_summary = self.trace_analyzer.summarize_findings(findings)
        recommendation_trace_summary = self.trace_analyzer.summarize_recommendations(recommendations)
        governance_trace_summary = self.trace_analyzer.summarize_governance(governed_actions)
        execution_trace_summary = self.trace_analyzer.summarize_execution(patch_plans)

        applied_changes = metrics.get("auto_applied_count", 0)
        blocked_changes = metrics.get("governance_block_count", 0)
        manual_changes = metrics.get("manual_patch_count", 0)

        report = EvaluationReport(
            total_findings=len(findings),
            total_recommendations=len(recommendations),
            total_governed_actions=len(governed_actions),
            applied_changes=applied_changes,
            blocked_changes=blocked_changes,
            manual_changes=manual_changes,
            summary=(
                f"Run completed with {len(findings)} findings, "
                f"{len(recommendations)} recommendations, "
                f"{applied_changes} auto-applied changes, "
                f"{manual_changes} manual patch plans, and "
                f"{blocked_changes} governance-blocked actions."
            ),
            by_category=metrics.get("findings_by_category", {}),
            by_risk=metrics.get("governed_actions_by_risk", {}),
            by_proposal_type=metrics.get("recommendations_by_type", {}),
        )

        result: Dict[str, Any] = {
            "evaluation_report": report.to_dict(),
            "metrics": metrics,
            "frontend_submetrics": frontend_submetrics,
            "trace_summary": trace_summary,
            "finding_trace_summary": finding_trace_summary,
            "recommendation_trace_summary": recommendation_trace_summary,
            "governance_trace_summary": governance_trace_summary,
            "execution_trace_summary": execution_trace_summary,
        }

        if generate_reports and report_output_dir:
            bundle = self.report_generator.generate_report_bundle(
                output_dir=report_output_dir,
                run_id=run_id,
                repo_root=repo_root,
                repo_access_mode=repo_access_mode,
                scan_mode=scan_mode,
                available_capabilities=available_capabilities,
                findings=findings,
                recommendations=recommendations,
                governed_actions=governed_actions,
                patch_plans=patch_plans,
                evaluation_report=report.to_dict(),
                metrics=metrics,
                warnings=warnings,
                errors=errors,
                fallback_events=fallback_events,
            )
            result["report_bundle"] = bundle

        return result