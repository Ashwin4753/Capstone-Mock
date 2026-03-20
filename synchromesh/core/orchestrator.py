from __future__ import annotations
import inspect
import uuid
from typing import Any, Dict, List, Optional

from agents import (
    ArchaeologistAgent,
    AnalyzerAgent,
    EvaluatorAgent,
    GovernorAgent,
    StrategistAgent,
    SyncerAgent,
)

from .context_store import ContextStore
from .pipeline import (
    AnalysisStage,
    DiscoveryStage,
    EvaluationStage,
    ExecutionStage,
    GovernanceStage,
    StrategyStage,
)
from .state import StateManager

class SynchroMeshOrchestrator:
    """
    Clean 6-agent modernization orchestrator.

    Pipeline:
    1. Discovery
    2. Analysis
    3. Strategy
    4. Governance
    5. Execution
    6. Evaluation

    Philosophy:
    - orchestrator depends on a unified repository backend
    - local and MCP-backed repo access are both first-class
    - the rest of the system works against capabilities, not storage location
    """

    def __init__(
        self,
        *,
        repo_client: Any,
        state_manager: Optional[StateManager] = None,
        archaeologist_agent: Optional[ArchaeologistAgent] = None,
        analyzer_agent: Optional[AnalyzerAgent] = None,
        strategist_agent: Optional[StrategistAgent] = None,
        governor_agent: Optional[GovernorAgent] = None,
        syncer_agent: Optional[SyncerAgent] = None,
        evaluator_agent: Optional[EvaluatorAgent] = None,
    ) -> None:
        self.repo_client = repo_client
        self.state_manager = state_manager or StateManager()

        self.archaeologist = archaeologist_agent or ArchaeologistAgent()
        self.analyzer = analyzer_agent or AnalyzerAgent()
        self.strategist = strategist_agent or StrategistAgent()
        self.governor = governor_agent or GovernorAgent()
        self.syncer = syncer_agent or SyncerAgent()
        self.evaluator = evaluator_agent or EvaluatorAgent()

        self.discovery_stage = DiscoveryStage(self.archaeologist)
        self.analysis_stage = AnalysisStage(self.analyzer)
        self.strategy_stage = StrategyStage(self.strategist)
        self.governance_stage = GovernanceStage(self.governor)
        self.execution_stage = ExecutionStage(self.syncer)
        self.evaluation_stage = EvaluationStage(self.evaluator)

    async def run(
        self,
        *,
        repo_root: str = "",
        figma_tokens: Optional[Dict[str, Any]] = None,
        token_format: str = "var(--{token})",
        export_output_dir: Optional[str] = None,
        require_approved: bool = False,
        approved_key: str = "approved",
    ) -> Dict[str, Any]:
        run_id = str(uuid.uuid4())
        context = ContextStore(run_id=run_id)

        context.set_source_metadata(
            repo_root=repo_root,
            repo_access_mode=self._infer_repo_access_mode(self.repo_client),
            scan_mode=self._infer_scan_mode(self.repo_client),
            mcp_tools_available=self._detect_available_capabilities(self.repo_client),
        )

        discovery_result = await self._run_stage(
            context=context,
            stage_name="discovery",
            runner=self.discovery_stage.run,
            repo_client=self.repo_client,
            repo_root=repo_root,
        )
        repository_candidates = discovery_result["repository_candidates"]
        context.repository_candidates = repository_candidates
        context.set_agent_output("archaeologist", discovery_result)

        analysis_result = await self._run_stage(
            context=context,
            stage_name="analysis",
            runner=self.analysis_stage.run,
            repository_candidates=repository_candidates,
            repo_client=self.repo_client,
            repo_root=repo_root,
        )
        analysis_findings = analysis_result["analysis_findings"]
        context.analysis_findings = analysis_findings
        context.scan_findings = analysis_findings
        context.set_agent_output("analyzer", analysis_result)
        self._record_analysis_fallbacks(context, analysis_findings)

        strategy_result = await self._run_stage(
            context=context,
            stage_name="strategy",
            runner=self.strategy_stage.run,
            findings=analysis_findings,
            figma_tokens=figma_tokens or {},
            token_format=token_format,
        )
        recommendations = strategy_result["modernization_recommendations"]
        context.modernization_recommendations = recommendations
        context.set_agent_output("strategist", strategy_result)

        governance_result = await self._run_stage(
            context=context,
            stage_name="governance",
            runner=self.governance_stage.run,
            recommendations=recommendations,
        )
        governed_actions = governance_result["governed_actions"]
        context.governed_actions = governed_actions
        context.set_agent_output("governor", governance_result)

        execution_result = await self._run_stage(
            context=context,
            stage_name="execution",
            runner=self.execution_stage.run,
            recommendations=recommendations,
            governed_actions=governed_actions,
            repo_client=self.repo_client,
            require_approved=require_approved,
            approved_key=approved_key,
        )
        context.patch_plans = execution_result["patch_plans"]
        context.applied_changes = execution_result["applied_changes"]
        context.diffs = execution_result["diffs"]
        context.set_agent_output("syncer", execution_result)

        evaluation_result = await self._run_stage(
            context=context,
            stage_name="evaluation",
            runner=self.evaluation_stage.run,
            run_id=context.run_id,
            repo_root=context.repo_root,
            repo_access_mode=context.repo_access_mode,
            scan_mode=context.scan_mode,
            available_capabilities=context.mcp_tools_available,
            repository_candidates=context.repository_candidates,
            findings=analysis_findings,
            recommendations=recommendations,
            governed_actions=governed_actions,
            patch_result=execution_result["raw_patch_result"],
            warnings=context.warnings,
            errors=context.errors,
            fallback_events=context.fallback_events,
            trace_logs=context.trace_logs,
            report_output_dir=export_output_dir,
            generate_reports=bool(export_output_dir),
            )
        context.evaluation_report = evaluation_result["evaluation_report"]
        context.set_agent_output("evaluator", evaluation_result)
         
        metrics = evaluation_result.get("metrics") or self.state_manager.compute_metrics(
            repository_candidates=context.repository_candidates,
            findings=context.analysis_findings,
            recommendations=context.modernization_recommendations,
            governed_actions=context.governed_actions,
            patch_plans=context.patch_plans,
            fallback_events=context.fallback_events,
            warnings=context.warnings,
            errors=context.errors,
            evaluation_report=context.evaluation_report,
            )
        context.add_trace("orchestrator", "metrics_computed", metrics)

        run_record = self.state_manager.record_run(
            run_id=context.run_id,
            repo_root=context.repo_root,
            repo_access_mode=context.repo_access_mode,
            scan_mode=context.scan_mode,
            metrics=metrics,
        )

        exported_paths: Dict[str, str] = {}
        if export_output_dir:
            exported_paths = context.export_outputs(export_output_dir)

        return {
            "run_id": context.run_id,
            "repo_root": context.repo_root,
            "repo_access_mode": context.repo_access_mode,
            "scan_mode": context.scan_mode,
            "available_capabilities": context.mcp_tools_available,
            "repository_candidates": context.repository_candidates,
            "analysis_findings": context.analysis_findings,
            "modernization_recommendations": context.modernization_recommendations,
            "governed_actions": context.governed_actions,
            "patch_plans": context.patch_plans,
            "applied_changes": context.applied_changes,
            "diffs": context.diffs,
            "evaluation_report": context.evaluation_report,
            "metrics": metrics,
            "run_record": run_record,
            "warnings": context.warnings,
            "errors": context.errors,
            "fallback_events": context.fallback_events,
            "trace_logs": context.trace_logs,
            "stage_status": context.stage_status,
            "stage_timings": context.stage_timings,
            "timeline": context.timeline,
            "agent_outputs": context.agent_outputs,
            "exported_paths": exported_paths,
        }

    async def _run_stage(
        self,
        *,
        context: ContextStore,
        stage_name: str,
        runner: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        context.start_stage(stage_name)
        context.add_trace(
            stage_name,
            "stage_input_prepared",
            {"input_keys": sorted(kwargs.keys())},
        )

        try:
            result = runner(**kwargs)
            if inspect.isawaitable(result):
                result = await result

            summary = result.get("summary", {}) if isinstance(result, dict) else {}
            context.complete_stage(stage_name, summary=summary)
            context.add_trace(
                stage_name,
                "stage_output_generated",
                {"summary": summary},
            )
            return result

        except Exception as exc:
            context.fail_stage(
                stage_name,
                str(exc),
                details={"exception_type": type(exc).__name__},
            )
            raise

    def _record_analysis_fallbacks(
        self,
        context: ContextStore,
        findings: List[Dict[str, Any]],
    ) -> None:
        fallback_sources = {
            "regex_fallback",
            "local_repo_patterns",
            "local_style_ast",
            "local_backend_ast",
        }

        fallback_used = any(
            str(item.get("source_tool", "")).strip() in fallback_sources
            for item in findings
        )

        if fallback_used:
            context.add_fallback(
                fallback_type="analysis_fallback_used",
                message="Analysis used local and/or regex fallback for at least one finding.",
                stage="analysis",
                details={"finding_count": len(findings)},
            )

    def _infer_repo_access_mode(self, client: Any) -> str:
        access_mode = getattr(client, "access_mode", None)
        if callable(access_mode):
            try:
                return str(access_mode())
            except Exception:
                pass

        capabilities = self._detect_available_capabilities(client)
        has_file_io = all(
            name in capabilities for name in ["list_files", "read_file", "write_file"]
        )
        has_analysis = any(
            name in capabilities
            for name in [
                "search_code",
                "scan_style_ast",
                "scan_backend_constants",
                "scan_repo_patterns",
                "resolve_symbol_usage",
            ]
        )

        if has_file_io and has_analysis:
            return "hybrid"
        if has_file_io:
            return "local"
        if has_analysis:
            return "remote"
        return "unknown"

    def _infer_scan_mode(self, client: Any) -> str:
        capabilities = set(self._detect_available_capabilities(client))

        has_local_or_file_ops = {"list_files", "read_file", "write_file"}.issubset(capabilities)
        has_enrichment = bool(
            capabilities.intersection(
                {
                    "search_code",
                    "scan_style_ast",
                    "scan_backend_constants",
                    "scan_repo_patterns",
                    "resolve_symbol_usage",
                }
            )
        )

        if has_local_or_file_ops and has_enrichment:
            return "hybrid_preferred"
        if has_local_or_file_ops:
            return "local_only"
        if has_enrichment:
            return "analysis_only"
        return "unknown"

    def _detect_available_capabilities(self, client: Any) -> List[str]:
        capabilities_method = getattr(client, "capabilities", None)
        if callable(capabilities_method):
            try:
                caps = capabilities_method()
                if isinstance(caps, dict):
                    return sorted([name for name, enabled in caps.items() if enabled])
            except Exception:
                pass

        candidates = [
            "list_files",
            "read_file",
            "write_file",
            "search_code",
            "scan_style_ast",
            "scan_backend_constants",
            "scan_repo_patterns",
            "resolve_symbol_usage",
            "create_pull_request",
        ]
        return sorted(
            [name for name in candidates if callable(getattr(client, name, None))]
        )