from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core enums
# ---------------------------------------------------------------------------


class CoverageType(str, Enum):
    ORIGINAL_MEDICARE = "ORIGINAL_MEDICARE"
    RAILROAD_MEDICARE = "RAILROAD_MEDICARE"
    MEDICARE_ADVANTAGE = "MEDICARE_ADVANTAGE"
    OTHER = "OTHER"


class WoundType(str, Enum):
    DFU = "DFU"
    NEUROPATHIC = "NEUROPATHIC"
    VSU = "VSU"
    VLU = "VLU"
    TRAUMA = "TRAUMA"
    PRESSURE = "PRESSURE"
    OTHER = "OTHER"


class EvidenceState(str, Enum):
    CONFIRMED = "CONFIRMED"
    UNCONFIRMED = "UNCONFIRMED"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"
    STALE = "STALE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReviewStage(str, Enum):
    INITIAL_PRE_AUTH = "INITIAL_PRE_AUTH"
    SUBSEQUENT_APPLICATION = "SUBSEQUENT_APPLICATION"
    CLAIM_PREPAYMENT_REVIEW = "CLAIM_PREPAYMENT_REVIEW"


def to_evidence_state(value: Any) -> EvidenceState:
    if value is None:
        return EvidenceState.UNKNOWN
    if isinstance(value, EvidenceState):
        return value
    if isinstance(value, str):
        try:
            return EvidenceState(value)
        except ValueError:
            return EvidenceState.UNKNOWN
    if value is True:
        return EvidenceState.CONFIRMED
    if value is False:
        return EvidenceState.UNCONFIRMED
    return EvidenceState.UNKNOWN


class DocumentationSignals(BaseModel):
    baseline_measurement_present: Optional[bool] = None
    serial_measurements_present: Optional[bool] = None
    photos_present: Optional[bool] = None
    standard_care_failure_present: Optional[bool] = None
    vascular_assessment_present: Optional[bool] = None
    infection_assessment_present: Optional[bool] = None
    infection_treatment_history_present: Optional[bool] = None
    prior_treatments_present: Optional[bool] = None
    product_rationale_present: Optional[bool] = None
    care_plan_present: Optional[bool] = None
    offloading_present: Optional[bool] = None
    compression_present: Optional[bool] = None


WoundThickness = Literal["PARTIAL", "FULL", "UNKNOWN"]


class WoundBed(BaseModel):
    wound_size_cm_sq: Optional[float] = Field(default=None, ge=0)
    wound_thickness: Optional[WoundThickness] = None
    tendon_muscle_joint_bone_or_sinus_tract: Optional[bool] = None
    bed_clean_and_granular: Optional[bool] = None
    necrotic_debris_or_exudate_present: Optional[bool] = None


class VascularEvidence(BaseModel):
    abi_value: Optional[float] = Field(default=None, ge=0)
    toe_pressure_mmhg: Optional[float] = Field(default=None, ge=0)
    assessment_documented: Optional[bool] = None


class InfectionEvidence(BaseModel):
    active_infection: Optional[bool] = None
    assessment_documented: Optional[bool] = None
    treatment_history_documented: Optional[bool] = None
    osteomyelitis_present: Optional[bool] = None


class Contraindications(BaseModel):
    uncontrolled_diabetes: Optional[bool] = None
    active_charcot_arthropathy: Optional[bool] = None
    vasculitis: Optional[bool] = None
    ctp_component_hypersensitivity: Optional[bool] = None
    continued_exposure_to_causative_factors: Optional[bool] = None


CompressionMethod = Literal[
    "MULTILAYER_DRESSING",
    "STOCKINGS_20MMHG_OR_HIGHER",
    "PNEUMATIC",
    "OTHER",
    "UNKNOWN",
]


class StandardCareHistory(BaseModel):
    care_duration_days: Optional[int] = Field(default=None, ge=0)
    care_failed_or_unresponsive: Optional[bool] = None
    adherence_documented: Optional[bool] = None
    ulcer_duration_days: Optional[int] = Field(default=None, ge=0)
    unresponsive_care_duration_days: Optional[int] = Field(default=None, ge=0)
    offloading_documented: Optional[bool] = None
    diabetes_diagnosis_documented: Optional[bool] = None
    diabetes_management_documented: Optional[bool] = None
    compression_documented: Optional[bool] = None
    compression_method: Optional[CompressionMethod] = None


CtpCourseOutcome = Literal[
    "HEALED",
    "FAILED_NO_IMPROVEMENT",
    "FAILED_WORSENING",
    "DISCONTINUED_OTHER",
    "UNKNOWN",
]


class EpisodeHistory(BaseModel):
    episode_start_date: Optional[date] = None
    ctp_episode_start_date: Optional[date] = None
    applications_so_far_in_episode: Optional[int] = Field(default=None, ge=0)
    products_used_in_episode: Optional[List[str]] = None
    concurrent_products_in_episode: Optional[bool] = None
    last_completed_ctp_course_end_date: Optional[date] = None
    last_completed_ctp_course_outcome: Optional[CtpCourseOutcome] = None
    prior_healed_size_cm_sq: Optional[float] = Field(default=None, ge=0)
    prior_healed_size_reduction_pct: Optional[float] = Field(default=None, ge=0, le=100)
    same_wound_as_prior_course: Optional[bool] = None


SmokingStatus = Literal["NEVER", "FORMER", "CURRENT", "UNKNOWN"]


class TobaccoUse(BaseModel):
    smoking_status: Optional[SmokingStatus] = None
    cessation_for_at_least_4_weeks: Optional[bool] = None
    documented: Optional[bool] = None


class TexasEpisodeEvidence(BaseModel):
    code_scope_confirmed: Optional[bool] = None
    baseline_measurement_documented: Optional[bool] = None
    four_week_measurement_documented: Optional[bool] = None
    pre_placement_measurement_documented: Optional[bool] = None
    subsequent_placement_measurements_documented: Optional[bool] = None
    response_documented_within_30_days: Optional[bool] = None
    comprehensive_treatment_plan_documented: Optional[bool] = None
    failed_interventions_documented: Optional[bool] = None
    updated_medication_history_documented: Optional[bool] = None
    pertinent_medical_problem_review_documented: Optional[bool] = None
    planned_procedure_documented: Optional[bool] = None
    selected_product_documented: Optional[bool] = None
    risks_complications_documented: Optional[bool] = None
    smoking_counseling_documented: Optional[bool] = None
    pre_treatment_wound_description_documented: Optional[bool] = None
    post_treatment_wound_description_documented: Optional[bool] = None
    wastage_documented: Optional[bool] = None
    continuation_rationale_documented: Optional[bool] = None


class CaseEvaluationRequest(BaseModel):
    case_reference: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=2, max_length=2)
    coverage_type: CoverageType
    service_date: date
    wound_type: WoundType
    review_stage: Optional[ReviewStage] = None
    site_of_service: Optional[str] = None
    episode_reference: Optional[str] = None
    wound_reference: Optional[str] = None
    planned_application_date: Optional[date] = None
    procedure_codes: List[str] = Field(default_factory=list)
    product_codes: List[str] = Field(default_factory=list)
    diagnosis_codes: List[str] = Field(default_factory=list)
    documentation: DocumentationSignals = Field(default_factory=DocumentationSignals)
    wound_bed: Optional[WoundBed] = None
    vascular_evidence: Optional[VascularEvidence] = None
    infection_evidence: Optional[InfectionEvidence] = None
    contraindications: Optional[Contraindications] = None
    standard_care: Optional[StandardCareHistory] = None
    episode_history: Optional[EpisodeHistory] = None
    tobacco_use: Optional[TobaccoUse] = None
    texas_episode_evidence: Optional[TexasEpisodeEvidence] = None


class BatchEvaluationRequest(BaseModel):
    cases: List[CaseEvaluationRequest] = Field(min_length=1, max_length=500)


class SourceReference(BaseModel):
    id: str
    kind: str
    title: str
    url: Optional[str] = None
    section: Optional[str] = None
    effective_date: Optional[str] = None
    version: Optional[str] = None
    note: Optional[str] = None


class ApplicabilityResult(BaseModel):
    status: str
    message: str
    state: str
    jurisdiction: Optional[str] = None
    mac: Optional[str] = None
    participant: Optional[str] = None
    source: SourceReference


class Finding(BaseModel):
    rule_id: str
    severity: str
    category: str
    message: str
    rationale: str
    source: SourceReference
    rule_pack_id: Optional[str] = None
    rule_pack_version: Optional[str] = None
    classification: Optional[str] = None
    status: Optional[str] = None
    triggering_facts: Optional[Dict[str, Any]] = None
    claim_id: Optional[str] = None
    next_action: Optional[str] = None


class ReadinessResult(BaseModel):
    status: str
    score: int
    score_label: str
    confirmed_checks: int
    total_checks: int


class RulePackSummary(BaseModel):
    id: str
    label: str
    version: str
    status: str
    guide_updated: str


class CaseEvaluationResponse(BaseModel):
    evaluation_id: str = Field(default_factory=lambda: f"eval_{uuid4().hex}")
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_fingerprint: Optional[str] = None
    case_reference: str
    applicability: ApplicabilityResult
    readiness: ReadinessResult
    findings: List[Finding]
    next_action: str
    rule_pack: RulePackSummary
    disclaimer: str


class BatchEvaluationResponse(BaseModel):
    count: int
    results: List[CaseEvaluationResponse]
