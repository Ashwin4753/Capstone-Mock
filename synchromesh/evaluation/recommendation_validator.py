from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple

class RecommendationValidator:
    """
    Validates modernization recommendations against expected references.

    Supports broader validation than old token-only matching.
    """

    def validate(
        self,
        predicted: List[Dict[str, Any]],
        expected: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        predicted_keys = {self._normalize_record(item) for item in predicted}
        expected_keys = {self._normalize_record(item) for item in expected}

        true_positives = predicted_keys & expected_keys
        false_positives = predicted_keys - expected_keys
        false_negatives = expected_keys - predicted_keys

        precision = self._safe_divide(len(true_positives), len(true_positives) + len(false_positives))
        recall = self._safe_divide(len(true_positives), len(true_positives) + len(false_negatives))
        f1 = self._safe_divide(2 * precision * recall, precision + recall) if (precision + recall) else 0.0

        return {
            "predicted_count": len(predicted_keys),
            "expected_count": len(expected_keys),
            "true_positive_count": len(true_positives),
            "false_positive_count": len(false_positives),
            "false_negative_count": len(false_negatives),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "matched_items": [self._tuple_to_dict(item) for item in sorted(true_positives)],
            "false_positives": [self._tuple_to_dict(item) for item in sorted(false_positives)],
            "false_negatives": [self._tuple_to_dict(item) for item in sorted(false_negatives)],
        }

    def validate_by_type(
        self,
        predicted: List[Dict[str, Any]],
        expected: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        proposal_types = sorted(
            set(str(item.get("proposal_type", "unknown")) for item in predicted)
            | set(str(item.get("proposal_type", "unknown")) for item in expected)
        )

        breakdown: Dict[str, Any] = {}
        for proposal_type in proposal_types:
            pred_subset = [item for item in predicted if str(item.get("proposal_type", "unknown")) == proposal_type]
            exp_subset = [item for item in expected if str(item.get("proposal_type", "unknown")) == proposal_type]
            breakdown[proposal_type] = self.validate(pred_subset, exp_subset)

        return breakdown

    def _normalize_record(self, item: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
        """
        Normalization key:
        (file_path, proposal_type, proposed_state, target_symbol, subcategory)

        This supports token substitutions, config extraction, enum suggestions,
        and manual modernization review types.
        """
        file_path = str(item.get("file_path", "")).strip()
        proposal_type = str(item.get("proposal_type", "")).strip().upper()
        proposed_state = str(item.get("proposed_state", "")).strip()
        target_symbol = str(item.get("target_symbol", "")).strip()
        subcategory = str(item.get("subcategory", item.get("metadata", {}).get("subcategory", ""))).strip()

        return (
            file_path,
            proposal_type,
            proposed_state,
            target_symbol,
            subcategory,
        )

    def _tuple_to_dict(self, item: Tuple[str, str, str, str, str]) -> Dict[str, Any]:
        return {
            "file_path": item[0],
            "proposal_type": item[1],
            "proposed_state": item[2],
            "target_symbol": item[3],
            "subcategory": item[4],
        }

    @staticmethod
    def _safe_divide(a: float, b: float) -> float:
        return a / b if b else 0.0