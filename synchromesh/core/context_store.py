from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ContextStore:
    """
    Run-scoped context store for the modernization pipeline.

    This is the single source of truth for:
    - agent outputs
    - pipeline stage outputs
    - warnings/errors/fallbacks
    - runtime metadata
    - evaluation/report artifacts
    """

    run_id: str
    created_at: str = field(default_factory=_utc_now_iso)

    # Source metadata
    repo_root: str = ""
    repo_access_mode: str = "unknown"  # local | remote | hybrid | unknown
    scan_mode: str = "mcp_preferred"   # mcp_preferred | local_only | fallback_only
    mcp_tools_available: List[str] = field(default_factory=list)

    # Core pipeline data
    repository_candidates: List[Dict[str, Any]] = field(default_factory=list)
    scan_findings: List[Dict[str, Any]] = field(default_factory=list)
    analysis_findings: List[Dict[str, Any]] = field(default_factory=list)
    modernization_recommendations: List[Dict[str, Any]] = field(default_factory=list)
    governed_actions: List[Dict[str, Any]] = field(default_factory=list)
    patch_plans: List[Dict[str, Any]] = field(default_factory=list)
    applied_changes: List[Dict[str, Any]] = field(default_factory=list)
    diffs: List[Dict[str, Any]] = field(default_factory=list)
    evaluation_report: Dict[str, Any] = field(default_factory=dict)

    # Per-agent outputs
    agent_outputs: Dict[str, Any] = field(default_factory=dict)

    # Observability
    stage_status: Dict[str, str] = field(default_factory=dict)
    stage_timings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    fallback_events: List[Dict[str, Any]] = field(default_factory=list)
    trace_logs: List[Dict[str, Any]] = field(default_factory=list)

    # Outputs
    exported_paths: Dict[str, str] = field(default_factory=dict)
    report_path: Optional[str] = None

    def set_source_metadata(
        self,
        *,
        repo_root: str = "",
        repo_access_mode: str = "unknown",
        scan_mode: str = "mcp_preferred",
        mcp_tools_available: Optional[List[str]] = None,
    ) -> None:
        self.repo_root = repo_root
        self.repo_access_mode = repo_access_mode
        self.scan_mode = scan_mode
        self.mcp_tools_available = list(mcp_tools_available or [])
        self.add_trace(
            "context",
            "source_metadata_initialized",
            {
                "repo_root": repo_root,
                "repo_access_mode": repo_access_mode,
                "scan_mode": scan_mode,
                "mcp_tools_available": self.mcp_tools_available,
            },
        )

    def start_stage(self, stage_name: str) -> None:
        self.stage_status[stage_name] = "running"
        self.stage_timings.setdefault(stage_name, {})
        self.stage_timings[stage_name]["started_at"] = _utc_now_iso()
        self.timeline.append(
            {"timestamp": _utc_now_iso(), "event": "stage_started", "stage": stage_name}
        )

    def complete_stage(self, stage_name: str, summary: Optional[Dict[str, Any]] = None) -> None:
        self.stage_status[stage_name] = "completed"
        self.stage_timings.setdefault(stage_name, {})
        self.stage_timings[stage_name]["completed_at"] = _utc_now_iso()
        if summary:
            self.stage_timings[stage_name]["summary"] = deepcopy(summary)
        self.timeline.append(
            {
                "timestamp": _utc_now_iso(),
                "event": "stage_completed",
                "stage": stage_name,
                "summary": deepcopy(summary) if summary else {},
            }
        )

    def fail_stage(self, stage_name: str, reason: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.stage_status[stage_name] = "failed"
        self.stage_timings.setdefault(stage_name, {})
        self.stage_timings[stage_name]["failed_at"] = _utc_now_iso()
        self.stage_timings[stage_name]["failure_reason"] = reason
        self.add_error(
            code="stage_failure",
            message=reason,
            stage=stage_name,
            details=details or {},
        )
        self.timeline.append(
            {
                "timestamp": _utc_now_iso(),
                "event": "stage_failed",
                "stage": stage_name,
                "reason": reason,
                "details": deepcopy(details) if details else {},
            }
        )

    def set_agent_output(self, agent_name: str, output: Any) -> None:
        self.agent_outputs[agent_name] = deepcopy(output)

    def add_warning(self, code: str, message: str, stage: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        self.warnings.append(
            {
                "timestamp": _utc_now_iso(),
                "code": code,
                "message": message,
                "stage": stage,
                "details": deepcopy(details) if details else {},
            }
        )

    def add_error(self, code: str, message: str, stage: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        self.errors.append(
            {
                "timestamp": _utc_now_iso(),
                "code": code,
                "message": message,
                "stage": stage,
                "details": deepcopy(details) if details else {},
            }
        )

    def add_fallback(self, fallback_type: str, message: str, stage: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        self.fallback_events.append(
            {
                "timestamp": _utc_now_iso(),
                "fallback_type": fallback_type,
                "message": message,
                "stage": stage,
                "details": deepcopy(details) if details else {},
            }
        )

    def add_trace(self, stage: str, event: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self.trace_logs.append(
            {
                "timestamp": _utc_now_iso(),
                "stage": stage,
                "event": event,
                "payload": deepcopy(payload) if payload else {},
            }
        )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "repo_root": self.repo_root,
            "repo_access_mode": self.repo_access_mode,
            "scan_mode": self.scan_mode,
            "mcp_tools_available": deepcopy(self.mcp_tools_available),
            "repository_candidates": deepcopy(self.repository_candidates),
            "scan_findings": deepcopy(self.scan_findings),
            "analysis_findings": deepcopy(self.analysis_findings),
            "modernization_recommendations": deepcopy(self.modernization_recommendations),
            "governed_actions": deepcopy(self.governed_actions),
            "patch_plans": deepcopy(self.patch_plans),
            "applied_changes": deepcopy(self.applied_changes),
            "diffs": deepcopy(self.diffs),
            "evaluation_report": deepcopy(self.evaluation_report),
            "agent_outputs": deepcopy(self.agent_outputs),
            "stage_status": deepcopy(self.stage_status),
            "stage_timings": deepcopy(self.stage_timings),
            "timeline": deepcopy(self.timeline),
            "warnings": deepcopy(self.warnings),
            "errors": deepcopy(self.errors),
            "fallback_events": deepcopy(self.fallback_events),
            "trace_logs": deepcopy(self.trace_logs),
            "exported_paths": deepcopy(self.exported_paths),
            "report_path": self.report_path,
        }

    def export_outputs(self, output_dir: str) -> Dict[str, str]:
        os.makedirs(output_dir, exist_ok=True)

        artifacts = {
            "context_snapshot.json": self.snapshot(),
            "repository_candidates.json": self.repository_candidates,
            "scan_findings.json": self.scan_findings,
            "analysis_findings.json": self.analysis_findings,
            "modernization_recommendations.json": self.modernization_recommendations,
            "governed_actions.json": self.governed_actions,
            "patch_plans.json": self.patch_plans,
            "applied_changes.json": self.applied_changes,
            "diffs.json": self.diffs,
            "evaluation_report.json": self.evaluation_report,
            "warnings.json": self.warnings,
            "errors.json": self.errors,
            "fallback_events.json": self.fallback_events,
            "trace_logs.json": self.trace_logs,
            "agent_outputs.json": self.agent_outputs,
        }

        exported: Dict[str, str] = {}
        for filename, payload in artifacts.items():
            path = os.path.join(output_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            exported[filename] = path

        self.exported_paths = exported
        self.report_path = exported.get("evaluation_report.json")
        return exported