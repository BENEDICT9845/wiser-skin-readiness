"""Pydantic models for rule pack v2."""

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


SourceKind = Literal[
    "OFFICIAL_CMS_GUIDANCE",
    "OFFICIAL_LCD",
    "OFFICIAL_LCD_ARTICLE",
    "OFFICIAL_NCD",
    "PILOT_WORKFLOW_SIGNAL",
    "INTERNAL_VALIDATION",
]


class SourceEntry(BaseModel):
    kind: SourceKind
    title: str
    url: Optional[str] = None
    version: Optional[str] = None
    published_or_updated: Optional[str] = None
    license_note: Optional[str] = None
    note: Optional[str] = None


class EffectiveDateRange(BaseModel):
    starts_on: date
    ends_on: Optional[date] = None


class RulePackScope(BaseModel):
    states: List[str] = Field(default_factory=list)
    macs: List[str] = Field(default_factory=list)
    coverage_types: List[str] = Field(default_factory=list)
    wound_types: List[str] = Field(default_factory=list)
    service_categories: List[str] = Field(default_factory=list)


RuleKind = Literal["applicability", "evidence", "validation"]
Classification = Literal["OFFICIAL_RULE", "WORKFLOW_SIGNAL", "INTERNAL_VALIDATION"]
Severity = Literal["BLOCKING", "REVIEW", "INFORMATIONAL"]


class Rule(BaseModel):
    rule_id: str
    kind: RuleKind
    classification: Classification
    severity: Severity
    scope: Dict[str, Any] = Field(default_factory=dict)
    condition: Dict[str, Any] = Field(default_factory=dict)
    if_fails_status: Optional[str] = None
    message_template: str
    rationale_template: str
    source_id: str
    source_section: Optional[str] = None
    claim_id: Optional[str] = None
    next_action: Optional[str] = None
    unknown_is_fail: bool = False


class ScoringWeights(BaseModel):
    applicability: int = 0
    evidence_official_rule: int = 10
    evidence_workflow_signal: int = 3
    validation: int = 1


class ScoringBlock(BaseModel):
    blocking_to_status: Dict[str, str] = Field(default_factory=dict)
    score_basis: str = "ENTERED_EVIDENCE_COMPLETENESS"
    weights: ScoringWeights = Field(default_factory=ScoringWeights)


ChangelogKind = Literal["ADDED", "MODIFIED", "REMOVED"]


class ChangelogEntry(BaseModel):
    rule_id: str
    kind: ChangelogKind
    version_introduced: str
    claim_id: Optional[str] = None
    note: Optional[str] = None


RulePackStatus = Literal["DRAFT", "REVIEWED", "PUBLISHED", "SUPERSEDED", "WITHDRAWN", "PROTOTYPE"]


class RulePack(BaseModel):
    id: str
    label: str
    version: str
    status: RulePackStatus
    guide_version: Optional[str] = None
    guide_updated: Optional[str] = None
    effective_date_range: EffectiveDateRange
    scope: RulePackScope
    sources: Dict[str, SourceEntry]
    field_state_policy: Dict[str, Literal["boolean", "evidence_state"]] = Field(default_factory=dict)
    applicability_rules: List[Rule] = Field(default_factory=list)
    evidence_rules: List[Rule] = Field(default_factory=list)
    validation_rules: List[Rule] = Field(default_factory=list)
    scoring: ScoringBlock = Field(default_factory=ScoringBlock)
    changelog: List[ChangelogEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rule_integrity(self) -> "RulePack":
        grouped = (
            ("applicability", self.applicability_rules),
            ("evidence", self.evidence_rules),
            ("validation", self.validation_rules),
        )
        seen = set()
        for expected_kind, rules in grouped:
            for r in rules:
                if r.rule_id in seen:
                    raise ValueError(f"Duplicate rule_id: {r.rule_id}")
                seen.add(r.rule_id)
                if r.kind != expected_kind:
                    raise ValueError(f"Rule {r.rule_id} belongs in {expected_kind}_rules")
                if r.source_id not in self.sources:
                    raise ValueError(f"Rule {r.rule_id} references unknown source {r.source_id}")
                if r.classification == "WORKFLOW_SIGNAL" and r.severity == "BLOCKING":
                    raise ValueError(f"Workflow signal {r.rule_id} cannot be BLOCKING")
                if r.classification == "INTERNAL_VALIDATION" and r.severity != "INFORMATIONAL":
                    raise ValueError(f"Internal validation {r.rule_id} must be INFORMATIONAL")
        return self


from functools import lru_cache
from pathlib import Path


PACKS_DIR = Path(__file__).parent


def _read_pack_text(path: Path) -> str:
    raw = path.read_bytes().rstrip(b"\x00").rstrip()
    return raw.decode("utf-8")


@lru_cache(maxsize=8)
def load_v2_rule_pack(rule_pack_id: str) -> RulePack:
    path = PACKS_DIR / f"{rule_pack_id}.json"
    if not path.exists():
        raise KeyError(rule_pack_id)
    return RulePack.model_validate_json(_read_pack_text(path))


def select_rule_pack_for_case(
    state: str, coverage_type: str, wound_type: str, service_date: date
) -> Optional[RulePack]:
    """Select a jurisdiction/date pack; its applicability rules gate the case."""
    state = state.upper()
    candidates: List[RulePack] = []
    for path in PACKS_DIR.glob("*.json"):
        try:
            pack = RulePack.model_validate_json(_read_pack_text(path))
        except Exception:
            continue
        if pack.status == "WITHDRAWN":
            continue
        if state not in [s.upper() for s in pack.scope.states]:
            continue
        starts = pack.effective_date_range.starts_on
        ends = pack.effective_date_range.ends_on
        if service_date < starts:
            continue
        if ends is not None and service_date > ends:
            continue
        candidates.append(pack)
    if not candidates:
        return None
    status_priority = {"PUBLISHED": 0, "REVIEWED": 1, "DRAFT": 2, "PROTOTYPE": 3}
    candidates.sort(
        key=lambda p: (
            status_priority.get(p.status, 99),
            -p.effective_date_range.starts_on.toordinal(),
        )
    )
    return candidates[0]
