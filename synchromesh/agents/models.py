from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ScanFinding:
    finding_id: str
    category: str  # frontend | backend | config | dependency | architecture
    subcategory: str  # hardcoded_url | timeout_constant | inline_style | etc.
    file_path: str
    language: str
    title: str
    description: str
    symbol_name: Optional[str] = None
    literal_value: Optional[str] = None
    line: Optional[int] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    snippet: str = ""
    source_tool: str = ""
    confidence_score: float = 0.0
    severity: str = "LOW"  # LOW | MEDIUM | HIGH
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModernizationRecommendation:
    change_id: str
    finding_id: str
    proposal_type: str  # TOKEN_SUBSTITUTION | EXTRACT_CONSTANT | USE_ENUM | MOVE_TO_CONFIG | MANUAL_REFACTOR
    file_path: str
    title: str
    current_state: str
    proposed_state: str
    replacement_text: Optional[str] = None
    target_symbol: Optional[str] = None
    line: Optional[int] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    risk_hint: str = "MEDIUM"
    reasoning: str = ""
    auto_applicable: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GovernedAction:
    change_id: str
    finding_id: str
    risk_level: str  # LOW | MEDIUM | HIGH
    requires_approval: bool
    allowed_to_apply: bool
    reason: str
    policy_tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PatchOperation:
    operation_type: str  # span_replace | manual_only
    file_path: str
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    replacement_text: Optional[str] = None
    summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PatchPlan:
    change_id: str
    file_path: str
    strategy: str  # AUTO_SPAN_REPLACE | MANUAL_PATCH
    operations: List[PatchOperation]
    auto_applied: bool
    summary: str
    diff: str = ""
    notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationReport:
    total_findings: int
    total_recommendations: int
    total_governed_actions: int
    applied_changes: int
    blocked_changes: int
    manual_changes: int
    summary: str
    by_category: Dict[str, int] = field(default_factory=dict)
    by_risk: Dict[str, int] = field(default_factory=dict)
    by_proposal_type: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)