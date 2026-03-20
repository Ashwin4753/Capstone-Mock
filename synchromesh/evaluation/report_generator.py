from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

class ReportGenerator:
    """
    Generates modernization-first run reports.
    """

    def generate_markdown_report(
        self,
        *,
        run_id: str,
        repo_root: str,
        repo_access_mode: str,
        scan_mode: str,
        available_capabilities: List[str],
        findings: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        governed_actions: List[Dict[str, Any]],
        patch_plans: List[Dict[str, Any]],
        evaluation_report: Dict[str, Any],
        metrics: Dict[str, Any],
        warnings: Optional[List[Dict[str, Any]]] = None,
        errors: Optional[List[Dict[str, Any]]] = None,
        fallback_events: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        warnings = warnings or []
        errors = errors or []
        fallback_events = fallback_events or []

        timestamp = datetime.now(timezone.utc).isoformat()

        lines: List[str] = []
        lines.append(f"# SynchroMesh Modernization Run Report")
        lines.append("")
        lines.append(f"- **Run ID:** `{run_id}`")
        lines.append(f"- **Generated At:** `{timestamp}`")
        lines.append(f"- **Repository Root:** `{repo_root}`")
        lines.append(f"- **Repository Access Mode:** `{repo_access_mode}`")
        lines.append(f"- **Scan Mode:** `{scan_mode}`")
        lines.append(f"- **Available Capabilities:** {', '.join(available_capabilities) if available_capabilities else 'None'}")
        lines.append("")

        lines.append("## Run Summary")
        lines.append("")
        lines.append(f"- **Total Findings:** {metrics.get('total_findings', 0)}")
        lines.append(f"- **Total Recommendations:** {metrics.get('total_recommendations', 0)}")
        lines.append(f"- **Total Governed Actions:** {metrics.get('total_governed_actions', 0)}")
        lines.append(f"- **Total Patch Plans:** {metrics.get('total_patch_plans', 0)}")
        lines.append(f"- **Auto Applied Changes:** {metrics.get('auto_applied_count', 0)}")
        lines.append(f"- **Manual Patch Plans:** {metrics.get('manual_patch_count', 0)}")
        lines.append(f"- **Governance Blocks:** {metrics.get('governance_block_count', 0)}")
        lines.append(f"- **Modernization Progress Score:** {metrics.get('modernization_progress_score', 0.0)}")
        lines.append(f"- **Auto Remediation Readiness:** {metrics.get('auto_remediation_readiness', 0.0)}")
        lines.append("")

        lines.append("## Findings Breakdown")
        lines.append("")
        lines.extend(self._dict_bullets(metrics.get("findings_by_category", {}), "Category"))
        lines.append("")
        lines.extend(self._dict_bullets(metrics.get("findings_by_subcategory", {}), "Subcategory"))
        lines.append("")
        lines.extend(self._dict_bullets(metrics.get("findings_by_severity", {}), "Severity"))
        lines.append("")

        lines.append("## Recommendation Breakdown")
        lines.append("")
        lines.extend(self._dict_bullets(metrics.get("recommendations_by_type", {}), "Proposal Type"))
        lines.append("")
        lines.extend(self._dict_bullets(metrics.get("recommendations_by_risk_hint", {}), "Risk Hint"))
        lines.append("")

        lines.append("## Governance Breakdown")
        lines.append("")
        lines.extend(self._dict_bullets(metrics.get("governed_actions_by_risk", {}), "Risk Level"))
        lines.append("")
        lines.extend(self._dict_bullets(metrics.get("governed_actions_by_policy", {}), "Policy Tag"))
        lines.append("")

        lines.append("## Execution Breakdown")
        lines.append("")
        lines.extend(self._dict_bullets(metrics.get("patches_by_strategy", {}), "Patch Strategy"))
        lines.append("")

        top_files = metrics.get("top_impacted_files", []) or []
        if top_files:
            lines.append("## Top Impacted Files")
            lines.append("")
            for item in top_files[:10]:
                lines.append(
                    f"- `{item.get('file_path', '')}` — findings={item.get('findings', 0)}, "
                    f"recommendations={item.get('recommendations', 0)}, "
                    f"impact_score={item.get('impact_score', 0)}"
                )
            lines.append("")

        if recommendations:
            lines.append("## Recommendation Samples")
            lines.append("")
            for rec in recommendations[:10]:
                lines.append(f"### {rec.get('title', 'Recommendation')}")
                lines.append(f"- **File:** `{rec.get('file_path', '')}`")
                lines.append(f"- **Proposal Type:** `{rec.get('proposal_type', '')}`")
                lines.append(f"- **Current State:** `{rec.get('current_state', '')}`")
                lines.append(f"- **Proposed State:** `{rec.get('proposed_state', '')}`")
                if rec.get("target_symbol"):
                    lines.append(f"- **Target Symbol:** `{rec.get('target_symbol', '')}`")
                lines.append(f"- **Risk Hint:** `{rec.get('risk_hint', '')}`")
                lines.append(f"- **Reasoning:** {rec.get('reasoning', '')}")
                lines.append("")

        if patch_plans:
            lines.append("## Patch Plan Samples")
            lines.append("")
            for plan in patch_plans[:10]:
                lines.append(f"### `{plan.get('file_path', '')}`")
                lines.append(f"- **Strategy:** `{plan.get('strategy', '')}`")
                lines.append(f"- **Auto Applied:** `{plan.get('auto_applied', False)}`")
                lines.append(f"- **Summary:** {plan.get('summary', '')}")
                notes = plan.get("notes", []) or []
                if notes:
                    lines.append(f"- **Notes:** {' | '.join(str(n) for n in notes)}")
                lines.append("")

        lines.append("## Evaluation Summary")
        lines.append("")
        for key, value in evaluation_report.items():
            lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

        if warnings:
            lines.append("## Warnings")
            lines.append("")
            for item in warnings[:20]:
                lines.append(f"- `{item.get('code', 'warning')}` — {item.get('message', '')}")
            lines.append("")

        if errors:
            lines.append("## Errors")
            lines.append("")
            for item in errors[:20]:
                lines.append(f"- `{item.get('code', 'error')}` — {item.get('message', '')}")
            lines.append("")

        if fallback_events:
            lines.append("## Fallback Events")
            lines.append("")
            for item in fallback_events[:20]:
                lines.append(f"- `{item.get('fallback_type', 'fallback')}` — {item.get('message', '')}")
            lines.append("")

        return "\n".join(lines)

    def write_markdown_report(self, markdown_text: str, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)
        return output_path

    def write_json_report(self, payload: Dict[str, Any], output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return output_path

    def generate_report_bundle(
        self,
        *,
        output_dir: str,
        run_id: str,
        repo_root: str,
        repo_access_mode: str,
        scan_mode: str,
        available_capabilities: List[str],
        findings: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        governed_actions: List[Dict[str, Any]],
        patch_plans: List[Dict[str, Any]],
        evaluation_report: Dict[str, Any],
        metrics: Dict[str, Any],
        warnings: Optional[List[Dict[str, Any]]] = None,
        errors: Optional[List[Dict[str, Any]]] = None,
        fallback_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, str]:
        os.makedirs(output_dir, exist_ok=True)

        markdown_text = self.generate_markdown_report(
            run_id=run_id,
            repo_root=repo_root,
            repo_access_mode=repo_access_mode,
            scan_mode=scan_mode,
            available_capabilities=available_capabilities,
            findings=findings,
            recommendations=recommendations,
            governed_actions=governed_actions,
            patch_plans=patch_plans,
            evaluation_report=evaluation_report,
            metrics=metrics,
            warnings=warnings,
            errors=errors,
            fallback_events=fallback_events,
        )

        markdown_path = os.path.join(output_dir, "modernization_report.md")
        summary_json_path = os.path.join(output_dir, "modernization_report.json")

        summary_payload = {
            "run_id": run_id,
            "repo_root": repo_root,
            "repo_access_mode": repo_access_mode,
            "scan_mode": scan_mode,
            "available_capabilities": available_capabilities,
            "metrics": metrics,
            "evaluation_report": evaluation_report,
            "warnings": warnings or [],
            "errors": errors or [],
            "fallback_events": fallback_events or [],
        }

        self.write_markdown_report(markdown_text, markdown_path)
        self.write_json_report(summary_payload, summary_json_path)

        return {
            "markdown_report": markdown_path,
            "json_report": summary_json_path,
        }

    def _dict_bullets(self, mapping: Dict[str, Any], label: str) -> List[str]:
        if not mapping:
            return [f"- No {label.lower()} data available."]
        lines: List[str] = []
        for key, value in sorted(mapping.items(), key=lambda item: str(item[0])):
            lines.append(f"- **{key}**: {value}")
        return lines