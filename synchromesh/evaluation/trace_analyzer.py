from __future__ import annotations
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

class TraceAnalyzer:
    """
    Analyzes explainability and execution traces from a modernization run.
    """

    def summarize(self, trace_logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        stage_counts = Counter()
        event_counts = Counter()
        stage_event_counts: Dict[str, Counter] = defaultdict(Counter)

        for entry in trace_logs:
            stage = str(entry.get("stage", "unknown"))
            event = str(entry.get("event", "unknown"))
            stage_counts[stage] += 1
            event_counts[event] += 1
            stage_event_counts[stage][event] += 1

        return {
            "trace_count": len(trace_logs),
            "stages_seen": sorted(stage_counts.keys()),
            "stage_counts": dict(stage_counts),
            "event_counts": dict(event_counts),
            "stage_event_counts": {stage: dict(counter) for stage, counter in stage_event_counts.items()},
        }

    def summarize_findings(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_source_tool = Counter(str(item.get("source_tool", "unknown")) for item in findings)
        by_category = Counter(str(item.get("category", "unknown")) for item in findings)
        by_severity = Counter(str(item.get("severity", "unknown")) for item in findings)

        confidence_values: List[float] = []
        for item in findings:
            raw = item.get("confidence_score")
            if raw is None:
                continue
            try:
                confidence_values.append(float(raw))
            except Exception:
                continue

        return {
            "finding_count": len(findings),
            "by_source_tool": dict(by_source_tool),
            "by_category": dict(by_category),
            "by_severity": dict(by_severity),
            "average_confidence": round(sum(confidence_values) / len(confidence_values), 4) if confidence_values else None,
            "min_confidence": round(min(confidence_values), 4) if confidence_values else None,
            "max_confidence": round(max(confidence_values), 4) if confidence_values else None,
        }

    def summarize_recommendations(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_type = Counter(str(item.get("proposal_type", "unknown")) for item in recommendations)
        by_risk_hint = Counter(str(item.get("risk_hint", "unknown")) for item in recommendations)
        auto_applicable_count = sum(1 for item in recommendations if bool(item.get("auto_applicable", False)))

        return {
            "recommendation_count": len(recommendations),
            "by_type": dict(by_type),
            "by_risk_hint": dict(by_risk_hint),
            "auto_applicable_count": auto_applicable_count,
        }

    def summarize_governance(self, governed_actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_risk = Counter(str(item.get("risk_level", "unknown")) for item in governed_actions)
        approval_required_count = sum(1 for item in governed_actions if bool(item.get("requires_approval", False)))
        allowed_to_apply_count = sum(1 for item in governed_actions if bool(item.get("allowed_to_apply", False)))

        policy_tags = Counter()
        for item in governed_actions:
            for tag in item.get("policy_tags", []) or []:
                policy_tags[str(tag)] += 1

        return {
            "governed_action_count": len(governed_actions),
            "by_risk": dict(by_risk),
            "approval_required_count": approval_required_count,
            "allowed_to_apply_count": allowed_to_apply_count,
            "policy_tags": dict(policy_tags),
        }

    def summarize_execution(self, patch_plans: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_strategy = Counter(str(item.get("strategy", "unknown")) for item in patch_plans)
        auto_applied_count = sum(1 for item in patch_plans if bool(item.get("auto_applied", False)))

        operations_by_type = Counter()
        for plan in patch_plans:
            for op in plan.get("operations", []) or []:
                operations_by_type[str(op.get("operation_type", "unknown"))] += 1

        return {
            "patch_plan_count": len(patch_plans),
            "auto_applied_count": auto_applied_count,
            "by_strategy": dict(by_strategy),
            "operations_by_type": dict(operations_by_type),
        }

    def export_trace_csv(self, trace_logs: List[Dict[str, Any]], output_path: str) -> str:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "timestamp",
            "stage",
            "event",
            "payload_json",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for row in trace_logs:
                writer.writerow(
                    {
                        "timestamp": row.get("timestamp"),
                        "stage": row.get("stage"),
                        "event": row.get("event"),
                        "payload_json": json.dumps(row.get("payload", {}), ensure_ascii=False),
                    }
                )

        return output_path

    def export_findings_csv(self, findings: List[Dict[str, Any]], output_path: str) -> str:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "file_path",
            "category",
            "subcategory",
            "title",
            "severity",
            "line",
            "source_tool",
            "confidence_score",
            "symbol_name",
            "literal_value",
            "snippet",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for row in findings:
                writer.writerow(
                    {
                        "file_path": row.get("file_path"),
                        "category": row.get("category"),
                        "subcategory": row.get("subcategory"),
                        "title": row.get("title"),
                        "severity": row.get("severity"),
                        "line": row.get("line"),
                        "source_tool": row.get("source_tool"),
                        "confidence_score": row.get("confidence_score"),
                        "symbol_name": row.get("symbol_name"),
                        "literal_value": row.get("literal_value"),
                        "snippet": row.get("snippet"),
                    }
                )

        return output_path