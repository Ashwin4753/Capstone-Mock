from __future__ import annotations
from typing import Any, Dict, List

class EvaluationStage:
    """
    Stage 6: Post-run evaluation using EvaluatorAgent.
    """

    def __init__(self, evaluator_agent: Any):
        self.evaluator = evaluator_agent

    async def run(
        self,
        *,
        run_id: str,
        repo_root: str,
        repo_access_mode: str,
        scan_mode: str,
        available_capabilities: List[str],
        repository_candidates: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        governed_actions: List[Dict[str, Any]],
        patch_result: Dict[str, Any],
        warnings: List[Dict[str, Any]],
        errors: List[Dict[str, Any]],
        fallback_events: List[Dict[str, Any]],
        trace_logs: List[Dict[str, Any]],
        report_output_dir: str | None = None,
        generate_reports: bool = False,
    ) -> Dict[str, Any]:
        evaluation_result: Dict[str, Any] = self.evaluator.evaluate(
            run_id=run_id,
            repo_root=repo_root,
            repo_access_mode=repo_access_mode,
            scan_mode=scan_mode,
            available_capabilities=available_capabilities,
            repository_candidates=repository_candidates,
            findings=findings,
            recommendations=recommendations,
            governed_actions=governed_actions,
            patch_result=patch_result,
            warnings=warnings,
            errors=errors,
            fallback_events=fallback_events,
            trace_logs=trace_logs,
            report_output_dir=report_output_dir,
            generate_reports=generate_reports,
        )

        summary = {
            "evaluation_generated": True,
            "applied_changes": evaluation_result.get("evaluation_report", {}).get("applied_changes", 0),
            "blocked_changes": evaluation_result.get("evaluation_report", {}).get("blocked_changes", 0),
            "manual_changes": evaluation_result.get("evaluation_report", {}).get("manual_changes", 0),
        }

        return {
            **evaluation_result,
            "summary": summary,
        }