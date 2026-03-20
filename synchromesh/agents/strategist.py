from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from .models import ModernizationRecommendation


class StrategistAgent:
    """
    Converts findings into modernization recommendations.

    Supports:
    - frontend token substitution
    - backend config extraction
    - enum recommendation
    - manual refactor suggestions
    """

    def _make_change_id(self, key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def generate_recommendations(
        self,
        findings: List[Dict[str, Any]],
        figma_tokens: Optional[Dict[str, Any]] = None,
        token_format: str = "var(--{token})",
    ) -> List[Dict[str, Any]]:
        figma_tokens = figma_tokens or {}
        value_to_token = self._build_value_to_token_map(figma_tokens)
        token_to_value = self._build_token_to_value_map(figma_tokens)

        recommendations: List[ModernizationRecommendation] = []

        for finding in findings:
            rec = self._recommend_for_finding(
                finding=finding,
                value_to_token=value_to_token,
                token_to_value=token_to_value,
                token_format=token_format,
            )
            recommendations.append(rec)

        return [r.to_dict() for r in recommendations]

    def _recommend_for_finding(
        self,
        finding: Dict[str, Any],
        value_to_token: Dict[str, str],
        token_to_value: Dict[str, str],
        token_format: str,
    ) -> ModernizationRecommendation:
        finding_id = str(finding.get("finding_id", ""))
        file_path = str(finding.get("file_path", ""))
        line = finding.get("line")
        span_start = finding.get("span_start")
        span_end = finding.get("span_end")
        subcategory = str(finding.get("subcategory", "")).strip()
        literal_value = str(finding.get("literal_value", "")).strip()
        symbol_name = str(finding.get("symbol_name", "")).strip()
        snippet = str(finding.get("snippet", ""))

        proposal_type = "MANUAL_REFACTOR"
        title = "Manual modernization review"
        current_state = literal_value or symbol_name or snippet or "unknown"
        proposed_state = "manual_review_required"
        replacement_text = None
        target_symbol = None
        risk_hint = "HIGH"
        auto_applicable = False
        reasoning = "This finding requires manual modernization review."

        # Frontend token opportunities
        if subcategory in {"hardcoded_color", "style_ast_color_literal"} and literal_value:
            normalized = self._normalize_color(literal_value)
            exact_token = value_to_token.get(normalized or "")
            if exact_token:
                proposal_type = "TOKEN_SUBSTITUTION"
                title = "Replace hardcoded color with token"
                proposed_state = exact_token
                replacement_text = token_format.format(token=exact_token)
                target_symbol = exact_token
                risk_hint = "LOW"
                auto_applicable = span_start is not None and span_end is not None
                reasoning = "Exact design-token value match found for hardcoded color."
            else:
                approx_token, approx_score = self._approximate_color_match(normalized or "", token_to_value)
                if approx_token and approx_score is not None and approx_score >= 0.92:
                    proposal_type = "TOKEN_SUBSTITUTION"
                    title = "Replace hardcoded color with approximate token match"
                    proposed_state = approx_token
                    replacement_text = token_format.format(token=approx_token)
                    target_symbol = approx_token
                    risk_hint = "MEDIUM"
                    auto_applicable = False
                    reasoning = f"Close token color match found (similarity={approx_score:.2f}); approval required."
                else:
                    proposal_type = "MANUAL_REFACTOR"
                    title = "Tokenize hardcoded color"
                    proposed_state = "introduce_design_token"
                    risk_hint = "MEDIUM"
                    reasoning = "No exact token match found; token mapping should be reviewed manually."

        elif subcategory in {"inline_style", "style_ast_inline_object"}:
            proposal_type = "MANUAL_REFACTOR"
            title = "Refactor inline style into shared styling system"
            proposed_state = "extract_to_design_system_or_component_style"
            risk_hint = "HIGH"
            auto_applicable = False
            reasoning = "Inline style blocks usually require structural refactoring and should not be auto-applied."

        # Backend modernization
        elif subcategory in {"hardcoded_url", "url_constant", "config_endpoint"}:
            proposal_type = "MOVE_TO_CONFIG"
            title = "Move URL to environment/config"
            proposed_state = "centralized_config_or_env_reference"
            risk_hint = "HIGH"
            auto_applicable = False
            reasoning = "Hardcoded URLs should be externalized into centralized configuration."

        elif subcategory in {"timeout_constant", "timeout_literal_or_symbol"}:
            proposal_type = "MOVE_TO_CONFIG"
            title = "Centralize timeout configuration"
            proposed_state = "shared_timeout_config"
            risk_hint = "MEDIUM"
            auto_applicable = False
            reasoning = "Timeout values should be centralized to improve consistency and operational control."

        elif subcategory in {"status_constant", "status_literal_or_symbol"}:
            proposal_type = "USE_ENUM"
            title = "Normalize statuses through enum or shared constant model"
            proposed_state = "enum_backed_status_model"
            risk_hint = "MEDIUM"
            auto_applicable = False
            reasoning = "Status values are better managed through enums or centralized status models."

        elif subcategory == "python_enum":
            proposal_type = "MANUAL_REVIEW"
            title = "Review enum usage and status normalization"
            proposed_state = "validate_enum_adoption_across_call_sites"
            risk_hint = "LOW"
            auto_applicable = False
            reasoning = "Enum already exists; review whether call sites consistently use it."

        elif subcategory == "broad_exception":
            proposal_type = "MANUAL_REFACTOR"
            title = "Replace broad exception handling with targeted exceptions"
            proposed_state = "specific_exception_types"
            risk_hint = "HIGH"
            auto_applicable = False
            reasoning = "Broad exception handling can hide failures and should be reviewed manually."

        elif subcategory in {"todo_marker", "fixme_marker"}:
            proposal_type = "MANUAL_REVIEW"
            title = "Review technical debt marker"
            proposed_state = "review_and_resolve_debt"
            risk_hint = "LOW" if subcategory == "todo_marker" else "MEDIUM"
            auto_applicable = False
            reasoning = "Debt markers are signals for review, not direct autonomous edits."

        change_id = self._make_change_id(
            f"{finding_id}|{file_path}|{line}|{proposal_type}|{proposed_state}|{replacement_text or ''}"
        )

        return ModernizationRecommendation(
            change_id=change_id,
            finding_id=finding_id,
            proposal_type=proposal_type,
            file_path=file_path,
            title=title,
            current_state=current_state,
            proposed_state=proposed_state,
            replacement_text=replacement_text,
            target_symbol=target_symbol,
            line=line,
            span_start=span_start,
            span_end=span_end,
            risk_hint=risk_hint,
            reasoning=reasoning,
            auto_applicable=auto_applicable,
            metadata={
                "subcategory": subcategory,
                "symbol_name": symbol_name,
                "snippet": snippet,
            },
        )

    def _build_token_to_value_map(self, figma_tokens: Dict[str, Any]) -> Dict[str, str]:
        flat: Dict[str, str] = {}

        def walk(prefix: str, obj: Any) -> None:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    walk(f"{prefix}{key}." if prefix else f"{key}.", value)
            else:
                token_name = prefix[:-1] if prefix.endswith(".") else prefix
                flat[token_name] = str(obj)

        if any(isinstance(v, dict) for v in figma_tokens.values()):
            walk("", figma_tokens)
        else:
            for key, value in figma_tokens.items():
                flat[str(key)] = str(value)

        return flat

    def _build_value_to_token_map(self, figma_tokens: Dict[str, Any]) -> Dict[str, str]:
        token_to_value = self._build_token_to_value_map(figma_tokens)
        value_to_token: Dict[str, str] = {}

        for token, value in token_to_value.items():
            normalized = self._normalize_color(value)
            if normalized and normalized not in value_to_token:
                value_to_token[normalized] = token

        return value_to_token

    @staticmethod
    def _normalize_color(value: str) -> Optional[str]:
        raw = value.strip().lower()
        if raw.startswith("#") and len(raw) in (4, 7):
            if len(raw) == 4:
                r, g, b = raw[1], raw[2], raw[3]
                return f"#{r}{r}{g}{g}{b}{b}"
            return raw
        return None

    def _approximate_color_match(
        self,
        normalized_value: str,
        token_to_value: Dict[str, str],
    ) -> Tuple[Optional[str], Optional[float]]:
        target_rgb = self._hex_to_rgb(normalized_value)
        if target_rgb is None:
            return None, None

        best_token: Optional[str] = None
        best_similarity = 0.0

        for token, raw_value in token_to_value.items():
            normalized_token_value = self._normalize_color(raw_value)
            if not normalized_token_value:
                continue

            token_rgb = self._hex_to_rgb(normalized_token_value)
            if not token_rgb:
                continue

            similarity = self._rgb_similarity(target_rgb, token_rgb)
            if similarity > best_similarity:
                best_similarity = similarity
                best_token = token

        if best_token is not None:
            return best_token, best_similarity

        return None, None

    @staticmethod
    def _hex_to_rgb(hex_value: str) -> Optional[Tuple[int, int, int]]:
        raw = hex_value.strip().lower()
        if not (raw.startswith("#") and len(raw) == 7):
            return None
        try:
            return (int(raw[1:3], 16), int(raw[3:5], 16), int(raw[5:7], 16))
        except Exception:
            return None

    @staticmethod
    def _rgb_similarity(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
        import math

        dr = a[0] - b[0]
        dg = a[1] - b[1]
        db = a[2] - b[2]

        distance = math.sqrt(dr * dr + dg * dg + db * db)
        max_distance = math.sqrt(255 * 255 * 3)
        return 1.0 - (distance / max_distance)