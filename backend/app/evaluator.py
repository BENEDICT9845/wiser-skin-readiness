import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .schemas import (
    ApplicabilityResult,
    CaseEvaluationRequest,
    CaseEvaluationResponse,
    Finding,
    ReadinessResult,
    RulePackSummary,
    SourceReference,
)


RULE_PACK_PATH = Path(__file__).parent / "rule_packs" / "cms-wiser-skin-v6.json"
HCPCS_PATTERN = re.compile(r"^[A-Z][0-9]{4}$")
DISCLAIMER = (
    "Decision support only. This result does not determine Medicare coverage, "
    "replace an applicable CMS or MAC review, or submit prior authorization."
)


@lru_cache(maxsize=1)
def load_rule_pack() -> Dict[str, Any]:
    return json.loads(RULE_PACK_PATH.read_text(encoding="utf-8"))


def get_rule_pack(rule_pack_id: str | None = None) -> Dict[str, Any]:
    rule_pack = load_rule_pack()
    if rule_pack_id and rule_pack["id"] != rule_pack_id:
        raise KeyError(rule_pack_id)
    return rule_pack


def _source(rule_pack: Dict[str, Any], source_id: str) -> SourceReference:
    source = rule_pack["sources"][source_id]
    return SourceReference(id=source_id, **source)


def _applicability(
    case: CaseEvaluationRequest, rule_pack: Dict[str, Any]
) -> ApplicabilityResult:
    state = case.state.upper()
    cms_source = _source(rule_pack, "CMS_WISER_OPERATIONAL_GUIDE_V6")

    if case.coverage_type.value != "ORIGINAL_MEDICARE":
        return ApplicabilityResult(
            status="OUTSIDE_WISER_COVERAGE_SCOPE",
            message=(
                "WISeR readiness screening is limited to Original Medicare "
                "fee-for-service cases. Follow the payer-specific workflow."
            ),
            state=state,
            source=cms_source,
        )

    if case.service_date < date.fromisoformat(rule_pack["effective_date"]):
        return ApplicabilityResult(
            status="BEFORE_WISER_SERVICE_WINDOW",
            message=(
                "The service date is before this rule pack's WISeR screening "
                f"window of {rule_pack['effective_date']}."
            ),
            state=state,
            source=cms_source,
        )

    state_rule = rule_pack["states"].get(state)
    if not state_rule:
        return ApplicabilityResult(
            status="OUTSIDE_WISER_PILOT_REGION",
            message=(
                "This state is outside the WISeR pilot region. Follow the "
                "applicable Medicare and MAC workflow."
            ),
            state=state,
            source=cms_source,
        )

    if state_rule["skin_status"] == "LCD_WITHDRAWN":
        return ApplicabilityResult(
            status="JF_SKIN_WORKFLOW_CURRENTLY_INACTIVE",
            message=(
                "CMS guide v6.0 states that skin substitutes are not currently "
                "subject to WISeR in JF/Noridian because the relevant LCD was withdrawn."
            ),
            state=state,
            jurisdiction=state_rule["jurisdiction"],
            mac=state_rule["mac"],
            participant=state_rule["participant"],
            source=cms_source,
        )

    return ApplicabilityResult(
        status="LIKELY_ACTIVE_WISER_WORKFLOW",
        message=(
            "This case is in an active WISeR pilot state for skin-substitute "
            "readiness screening. Confirm code-level and applicable MAC criteria "
            "before submission."
        ),
        state=state,
        jurisdiction=state_rule["jurisdiction"],
        mac=state_rule["mac"],
        participant=state_rule["participant"],
        source=cms_source,
    )


def _iter_applicable_checks(
    case: CaseEvaluationRequest, rule_pack: Dict[str, Any]
) -> Iterable[Dict[str, Any]]:
    for check in rule_pack["documentation_checks"]:
        if "ALL" in check["wound_types"] or case.wound_type.value in check["wound_types"]:
            yield check


def _documentation_findings(
    case: CaseEvaluationRequest, rule_pack: Dict[str, Any]
) -> tuple[List[Finding], int, int]:
    findings: List[Finding] = []
    confirmed_checks = 0
    total_checks = 0

    for check in _iter_applicable_checks(case, rule_pack):
        total_checks += 1
        value = getattr(case.documentation, check["field"])
        if value is True:
            confirmed_checks += 1
            continue

        findings.append(
            Finding(
                rule_id=check["id"],
                severity=check["severity"],
                category="DOCUMENTATION_SIGNAL",
                message=f"{check['label']} is not confirmed.",
                rationale=check["rationale"],
                source=_source(rule_pack, check["source_id"]),
            )
        )

    return findings, confirmed_checks, total_checks


def _code_findings(
    case: CaseEvaluationRequest, rule_pack: Dict[str, Any]
) -> List[Finding]:
    source = _source(rule_pack, "INTERNAL_FORMAT_CHECK")
    findings: List[Finding] = []
    groups = (
        ("APPLICATION_CODES_MISSING", "Application procedure code", case.procedure_codes),
        ("PRODUCT_CODES_MISSING", "Product HCPCS code", case.product_codes),
        ("DIAGNOSIS_CODES_MISSING", "Diagnosis ICD-10 code", case.diagnosis_codes),
    )

    for rule_id, label, values in groups:
        if not values:
            findings.append(
                Finding(
                    rule_id=rule_id,
                    severity="WARNING",
                    category="CODE_SIGNAL",
                    message=f"{label} is missing.",
                    rationale="A reviewer should confirm the case coding before submission.",
                    source=source,
                )
            )

    for product_code in case.product_codes:
        normalized = product_code.strip().upper()
        if not HCPCS_PATTERN.fullmatch(normalized):
            findings.append(
                Finding(
                    rule_id="PRODUCT_HCPCS_FORMAT_REVIEW",
                    severity="WARNING",
                    category="CODE_SIGNAL",
                    message=f"Product HCPCS code '{product_code}' should be reviewed.",
                    rationale="This prototype expects the common letter-plus-four-digits HCPCS format.",
                    source=source,
                )
            )

    return findings


def _readiness(
    applicability: ApplicabilityResult, confirmed_checks: int, total_checks: int
) -> ReadinessResult:
    score = round((confirmed_checks / total_checks) * 100) if total_checks else 0

    if applicability.status != "LIKELY_ACTIVE_WISER_WORKFLOW":
        status = "REVIEW_ROUTING"
    elif score >= 90:
        status = "READY_FOR_INTERNAL_REVIEW"
    elif score >= 60:
        status = "NEEDS_DOCUMENTATION"
    else:
        status = "INCOMPLETE"

    return ReadinessResult(
        status=status,
        score=score,
        score_label="Entered-field workflow readiness score",
        confirmed_checks=confirmed_checks,
        total_checks=total_checks,
    )


def evaluate_case(case: CaseEvaluationRequest) -> CaseEvaluationResponse:
    rule_pack = load_rule_pack()
    applicability = _applicability(case, rule_pack)
    documentation_findings, confirmed_checks, total_checks = _documentation_findings(
        case, rule_pack
    )
    findings = [*documentation_findings, *_code_findings(case, rule_pack)]
    readiness = _readiness(applicability, confirmed_checks, total_checks)

    if applicability.status != "LIKELY_ACTIVE_WISER_WORKFLOW":
        next_action = "Review routing and follow the applicable payer and MAC workflow."
    elif readiness.status == "READY_FOR_INTERNAL_REVIEW":
        next_action = "Send the case for internal review before the applicable submission workflow."
    else:
        next_action = "Collect or confirm the flagged evidence before internal review."

    return CaseEvaluationResponse(
        case_reference=case.case_reference,
        applicability=applicability,
        readiness=readiness,
        findings=findings,
        next_action=next_action,
        rule_pack=RulePackSummary(
            id=rule_pack["id"],
            label=rule_pack["label"],
            version=rule_pack["version"],
            status=rule_pack["status"],
            guide_updated=rule_pack["guide_updated"],
        ),
        disclaimer=DISCLAIMER,
    )

