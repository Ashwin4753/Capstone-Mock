from __future__ import annotations
import difflib
from typing import Any, Dict, List, Tuple
from .models import PatchOperation, PatchPlan

class SyncerAgent:
    """
    Controlled execution layer.

    Current safe auto-apply support:
    - exact low-risk span replacement only

    Everything else becomes a manual patch plan.
    """

    async def apply_changes(
        self,
        recommendations: List[Dict[str, Any]],
        governed_actions: List[Dict[str, Any]],
        repo_client: Any,
        require_approved: bool = True,
        approved_key: str = "approved",
    ) -> Dict[str, Any]:
        action_map = {str(a.get("change_id", "")): a for a in governed_actions}

        eligible: List[Dict[str, Any]] = []
        manual: List[Tuple[Dict[str, Any], str]] = []

        for rec in recommendations:
            change_id = str(rec.get("change_id", ""))
            action = action_map.get(change_id)

            if not action:
                manual.append((rec, "Missing governance action"))
                continue

            if not bool(action.get("allowed_to_apply", False)):
                manual.append((rec, f"Blocked by governance: {action.get('reason', '')}"))
                continue

            if require_approved and not bool(rec.get(approved_key, True)):
                manual.append((rec, "Approval flag not satisfied"))
                continue

            if str(rec.get("proposal_type", "")).upper() != "TOKEN_SUBSTITUTION":
                manual.append((rec, "Only TOKEN_SUBSTITUTION is auto-applied"))
                continue

            if rec.get("span_start") is None or rec.get("span_end") is None:
                manual.append((rec, "Missing span_start/span_end"))
                continue

            replacement_text = str(rec.get("replacement_text", "")).strip()
            if not replacement_text:
                manual.append((rec, "Missing replacement_text"))
                continue

            eligible.append(rec)

        by_file: Dict[str, List[Dict[str, Any]]] = {}
        for rec in eligible:
            by_file.setdefault(str(rec["file_path"]), []).append(rec)

        patch_plans: List[PatchPlan] = []
        applied_count = 0

        for file_path, file_recs in by_file.items():
            original_content = await self._safe_read_file(repo_client, file_path)
            updated_content, notes, applied_recs = self._apply_span_replacements(original_content, file_recs)
            changed = original_content != updated_content

            diff = self._make_diff(file_path, original_content, updated_content)
            operations: List[PatchOperation] = []

            for rec in applied_recs:
                operations.append(
                    PatchOperation(
                        operation_type="span_replace",
                        file_path=file_path,
                        span_start=rec.get("span_start"),
                        span_end=rec.get("span_end"),
                        replacement_text=rec.get("replacement_text"),
                        summary=str(rec.get("title", "Applied token substitution")),
                    )
                )

            if changed:
                await self._safe_write_file_if_available(repo_client, file_path, updated_content)
                applied_count += len(applied_recs)

            patch_plans.append(
                PatchPlan(
                    change_id="MULTI" if len(applied_recs) > 1 else str(applied_recs[0].get("change_id", "")) if applied_recs else "",
                    file_path=file_path,
                    strategy="AUTO_SPAN_REPLACE",
                    operations=operations,
                    auto_applied=changed,
                    summary=f"Applied {len(applied_recs)} safe change(s) to {file_path}" if changed else f"No auto changes applied to {file_path}",
                    diff=diff,
                    notes=notes,
                )
            )

        manual_plans: List[PatchPlan] = []
        for rec, reason in manual:
            manual_plans.append(
                PatchPlan(
                    change_id=str(rec.get("change_id", "")),
                    file_path=str(rec.get("file_path", "")),
                    strategy="MANUAL_PATCH",
                    operations=[
                        PatchOperation(
                            operation_type="manual_only",
                            file_path=str(rec.get("file_path", "")),
                            summary=str(rec.get("title", "Manual modernization review")),
                            metadata={"reason": reason, "proposal_type": rec.get("proposal_type")},
                        )
                    ],
                    auto_applied=False,
                    summary=reason,
                    notes=[reason],
                )
            )

        all_plans = patch_plans + manual_plans

        return {
            "applied_count": applied_count,
            "manual_count": len(manual_plans),
            "patch_plans": [p.to_dict() for p in all_plans],
            "diffs": [
                {"file_path": p.file_path, "diff": p.diff}
                for p in patch_plans
                if p.diff
            ],
        }

    def _apply_span_replacements(
        self,
        content: str,
        recommendations: List[Dict[str, Any]],
    ) -> Tuple[str, List[str], List[Dict[str, Any]]]:
        safe_recs = sorted(recommendations, key=lambda item: int(item["span_start"]), reverse=True)
        updated = content
        notes: List[str] = []
        applied: List[Dict[str, Any]] = []

        for rec in safe_recs:
            start = int(rec["span_start"])
            end = int(rec["span_end"])
            replacement = str(rec["replacement_text"])

            if start < 0 or end > len(updated) or start >= end:
                notes.append(f"Invalid span: {start}-{end} in {rec.get('file_path')}")
                continue

            original_slice = updated[start:end]
            expected_value = str(rec.get("current_state", "")).strip()

            if expected_value and expected_value not in original_slice:
                notes.append(
                    f"Span mismatch warning at {rec.get('file_path')}:{rec.get('line')}: "
                    f"expected '{expected_value}', slice='{original_slice}'. Applied anyway."
                )

            updated = updated[:start] + replacement + updated[end:]
            applied.append(rec)

        return updated, notes, applied

    @staticmethod
    def _make_diff(file_path: str, original: str, updated: str) -> str:
        if original == updated:
            return ""

        original_lines = original.splitlines(keepends=True)
        updated_lines = updated.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            updated_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        return "".join(diff)

    async def _safe_read_file(self, repo_client: Any, path: str) -> str:
        fn = getattr(repo_client, "read_file", None)
        if callable(fn):
            return await fn(path)

        fn = getattr(repo_client, "get_file_content", None)
        if callable(fn):
            return await fn(path)

        raise AttributeError("Repo client must expose read_file(.) or get_file_content(.)")

    async def _safe_write_file_if_available(self, repo_client: Any, path: str, content: str) -> None:
        fn = getattr(repo_client, "write_file", None)
        if callable(fn):
            await fn(path, content)
            return

        fn = getattr(repo_client, "update_file", None)
        if callable(fn):
            await fn(path, content)
            return