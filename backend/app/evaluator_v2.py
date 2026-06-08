"""V2 evaluator: predicate engine, aggregation, source-linked findings."""

from __future__ import annotations

import re
import hashlib
import json
from datetime import date
from typing import Any, Dict, List, Optional

from .rule_packs.models import (
    RulePack,
    Rule,
    SourceEntry,
    load_v2_rule_pack,
    select_rule_pack_for_case,
)
from .schemas import (
    ApplicabilityResult,
    CaseEvaluationRequest,
    CaseEvaluationResponse,
    EvidenceState,
    Finding,
    ReadinessResult,
    RulePackSummary,
    SourceReference,
    to_evidence_state,
)


DISCLAIMER_V2 = (
    "Decision support only. This result does not determine Medicare coverage, "
    "replace an applicable CMS or MAC review, or submit prior authorization. "
    "Findings cite their source; rule pack version is recorded for audit."
)


def _disclaimer_for_pack(pack: RulePack) -> str:
    if pack.status in {"DRAFT", "PROTOTYPE"}:
        return (
            f"Research-only {pack.status.lower()} rule pack; findings have not "
            "completed external clinical/compliance validation. " + DISCLAIMER_V2
        )
    return DISCLAIMER_V2


_PREDICATE_UNKNOWN = "__UNKNOWN__"


def _resolve_field(case: CaseEvaluationRequest, path: str) -> Any:
    parts = path.split(".")
    current: Any = case
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
    if hasattr(current, "value") and isinstance(current, EvidenceState):
        return current.value
    if hasattr(current, "isoformat"):
        return current.isoformat()
    return current


def _evaluate_predicate(predicate: Dict[str, Any], case: CaseEvaluationRequest) -> Any:
    if not predicate:
        return True
    if "always" in predicate:
        return bool(predicate["always"])
    if "all" in predicate:
        result = True
        for sub in predicate["all"]:
            r = _evaluate_predicate(sub, case)
            if r is False:
                return False
            if r == _PREDICATE_UNKNOWN:
                result = _PREDICATE_UNKNOWN
        return result
    if "any" in predicate:
        result = False
        for sub in predicate["any"]:
            r = _evaluate_predicate(sub, case)
            if r is True:
                return True
            if r == _PREDICATE_UNKNOWN:
                result = _PREDICATE_UNKNOWN
        return result
    if "not" in predicate:
        r = _evaluate_predicate(predicate["not"], case)
        if r == _PREDICATE_UNKNOWN:
            return _PREDICATE_UNKNOWN
        return not r
    if "for_each" in predicate:
        items = _resolve_field(case, predicate["for_each"]) or []
        regex = predicate.get("matches")
        if regex is None:
            return True
        pattern = re.compile(regex)
        return all(isinstance(i, str) and pattern.match(i) for i in items)
    if "days_between_lte" in predicate:
        return _evaluate_days_between(predicate["days_between_lte"], case, "<=")
    if "days_between_gte" in predicate:
        return _evaluate_days_between(predicate["days_between_gte"], case, ">=")

    field_path = predicate.get("field")
    if field_path is None:
        return True
    value = _resolve_field(case, field_path)
    if "exists" in predicate:
        return value is not None
    if value is None:
        return _PREDICATE_UNKNOWN
    if "equals" in predicate:
        return value == predicate["equals"]
    if "not_equals" in predicate:
        return value != predicate["not_equals"]
    if "in" in predicate:
        return value in predicate["in"]
    if "not_in" in predicate:
        return value not in predicate["not_in"]
    if "matches" in predicate:
        return bool(re.match(predicate["matches"], str(value)))
    if "is_state" in predicate:
        return to_evidence_state(value).value == predicate["is_state"]
    if "gt" in predicate:
        return _compare(value, predicate["gt"], ">")
    if "gte" in predicate:
        return _compare(value, predicate["gte"], ">=")
    if "lt" in predicate:
        return _compare(value, predicate["lt"], "<")
    if "lte" in predicate:
        return _compare(value, predicate["lte"], "<=")
    return True


def _evaluate_days_between(config: Dict[str, Any], case: CaseEvaluationRequest, op: str) -> Any:
    start_value = _resolve_field(case, config["start_field"])
    end_value = _resolve_field(case, config["end_field"])
    if start_value is None or end_value is None:
        return _PREDICATE_UNKNOWN
    try:
        start = date.fromisoformat(start_value) if isinstance(start_value, str) else start_value
        end = date.fromisoformat(end_value) if isinstance(end_value, str) else end_value
        elapsed = (end - start).days
        days = int(config["days"])
    except (ValueError, TypeError, KeyError, AttributeError):
        return _PREDICATE_UNKNOWN
    if elapsed < 0:
        return _PREDICATE_UNKNOWN
    return elapsed <= days if op == "<=" else elapsed >= days


def _compare(value: Any, target: Any, op: str) -> Any:
    try:
        if isinstance(value, str) and isinstance(target, str):
            v = date.fromisoformat(value)
            t = date.fromisoformat(target)
        else:
            v = float(value)
            t = float(target)
    except (ValueError, TypeError):
        return _PREDICATE_UNKNOWN
    if op == ">": return v > t
    if op == ">=": return v >= t
    if op == "<": return v < t
    if op == "<=": return v <= t
    return _PREDICATE_UNKNOWN


_TEMPLATE_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")


def _render_template(template: str, case: CaseEvaluationRequest) -> str:
    def repl(m):
        v = _resolve_field(case, m.group(1))
        return "not provided" if v is None else str(v)
    return _TEMPLATE_PATTERN.sub(repl, template)


def _source_reference(pack: RulePack, source_id: str, rule: Optional[Rule] = None) -> SourceReference:
    entry: SourceEntry = pack.sources[source_id]
    return SourceReference(
        id=source_id, kind=entry.kind, title=entry.title, url=entry.url,
        section=rule.source_section if rule else None,
        effective_date=entry.published_or_updated, version=entry.version, note=entry.note,
    )


def _collect_field_paths(predicate: Dict[str, Any]) -> List[str]:
    paths: List[str] = []
    if "field" in predicate:
        paths.append(predicate["field"])
    for key in ("all", "any"):
        for sub in predicate.get(key, []):
            paths.extend(_collect_field_paths(sub))
    if "not" in predicate:
        paths.extend(_collect_field_paths(predicate["not"]))
    for key in ("days_between_lte", "days_between_gte"):
        if key in predicate:
            paths.append(predicate[key]["start_field"])
            paths.append(predicate[key]["end_field"])
    return paths


def _triggering_facts(rule: Rule, case: CaseEvaluationRequest) -> Dict[str, Any]:
    facts: Dict[str, Any] = {}
    paths = set(_TEMPLATE_PATTERN.findall(rule.message_template))
    paths.update(_collect_field_paths(rule.condition))
    for path in paths:
        facts[path] = _resolve_field(case, path)
    return facts


def _rule_fires(rule: Rule, case: CaseEvaluationRequest) -> bool:
    if _evaluate_predicate(rule.scope, case) is not True:
        return False
    result = _evaluate_predicate(rule.condition, case)
    if result is True: return False
    if result is False: return True
    return rule.unknown_is_fail


def _build_finding(rule: Rule, pack: RulePack, case: CaseEvaluationRequest) -> Finding:
    return Finding(
        rule_id=rule.rule_id, severity=rule.severity, category=rule.kind.upper(),
        message=_render_template(rule.message_template, case),
        rationale=_render_template(rule.rationale_template, case),
        source=_source_reference(pack, rule.source_id, rule),
        rule_pack_id=pack.id, rule_pack_version=pack.version,
        classification=rule.classification, status="FIRED",
        triggering_facts=_triggering_facts(rule, case),
        claim_id=rule.claim_id, next_action=rule.next_action,
    )


def _build_unknown_finding(rule: Rule, pack: RulePack, case: CaseEvaluationRequest) -> Finding:
    return Finding(
        rule_id=rule.rule_id, severity="REVIEW", category=rule.kind.upper(),
        message=f"Unable to evaluate {rule.rule_id}: required evidence was not provided.",
        rationale=_render_template(rule.rationale_template, case),
        source=_source_reference(pack, rule.source_id, rule),
        rule_pack_id=pack.id, rule_pack_version=pack.version,
        classification=rule.classification, status="UNKNOWN",
        triggering_facts=_triggering_facts(rule, case),
        claim_id=rule.claim_id,
        next_action=rule.next_action or "Confirm the required evidence before review.",
    )


PARTICIPANT_BY_STATE = {
    "TX": ("Novitas", "JH", "Cohere Health"),
    "OK": ("Novitas", "JH", "Humata Health"),
    "NJ": ("Novitas", "JL", "Genzeon"),
    "OH": ("CGS", "J15", "Innovaccer"),
    "AZ": ("Noridian", "JF", "Zyter"),
    "WA": ("Noridian", "JF", "Virtix Health"),
}


def _request_fingerprint(case: CaseEvaluationRequest) -> str:
    payload = case.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _no_pack_routing(case: CaseEvaluationRequest) -> tuple:
    state = case.state.upper()
    if case.coverage_type.value != "ORIGINAL_MEDICARE":
        return ("OUTSIDE_WISER_COVERAGE_SCOPE", "OUTSIDE_WISER_COVERAGE_SCOPE",
                "WISeR applies to Original Medicare fee-for-service cases.",
                "Follow the payer-specific workflow for this coverage type.")
    if case.service_date < date(2026, 1, 15):
        return ("BEFORE_WISER_SERVICE_WINDOW", "BEFORE_WISER_SERVICE_WINDOW",
                "The service date is before WISeR services became subject to review.",
                "Use the standard Medicare workflow for this service date.")
    if case.service_date > date(2031, 12, 31):
        return ("OUTSIDE_WISER_MODEL_PERIOD", "OUTSIDE_WISER_MODEL_PERIOD",
                "The service date is after the published WISeR model period.",
                "Use the applicable Medicare and MAC workflow for this service date.")
    if state not in PARTICIPANT_BY_STATE:
        return ("OUTSIDE_WISER_PILOT_REGION", "OUTSIDE_WISER_PILOT_REGION",
                f"State '{state}' is outside the six-state WISeR pilot region.",
                "Use the standard Medicare workflow for this state.")
    if state in {"AZ", "WA"}:
        return ("JF_SKIN_WORKFLOW_CURRENTLY_INACTIVE", "JF_SKIN_WORKFLOW_CURRENTLY_INACTIVE",
                "The JF/Noridian skin-substitute WISeR workflow is currently inactive.",
                "Follow the applicable standard Medicare and MAC workflow.")
    return ("NO_APPLICABLE_RULE_PACK", "REQUIRES_HUMAN_REVIEW",
            "The case may be within WISeR scope, but no reviewed v2 rule pack covers this state and service date.",
            "Route to the client's qualified reviewer until a rule pack is available.")


def _build_applicability(pack: RulePack, rule: Rule, case: CaseEvaluationRequest) -> ApplicabilityResult:
    mac, jurisdiction, participant = PARTICIPANT_BY_STATE.get(case.state.upper(), (None, None, None))
    return ApplicabilityResult(
        status=rule.if_fails_status or "OUTSIDE_SCOPE",
        message=_render_template(rule.message_template, case),
        state=case.state.upper(), jurisdiction=jurisdiction, mac=mac, participant=participant,
        source=_source_reference(pack, rule.source_id, rule),
    )


def _build_applicability_success(pack: RulePack, case: CaseEvaluationRequest) -> ApplicabilityResult:
    mac, jurisdiction, participant = PARTICIPANT_BY_STATE.get(case.state.upper(), (None, None, None))
    return ApplicabilityResult(
        status="LIKELY_ACTIVE_WISER_WORKFLOW",
        message=f"Case is within active WISeR-skin scope for state {case.state.upper()} under {mac} {jurisdiction} ({participant}).",
        state=case.state.upper(), jurisdiction=jurisdiction, mac=mac, participant=participant,
        source=_source_reference(pack, list(pack.sources.keys())[0]),
    )


def _build_response(pack, case, applicability, readiness, findings, next_action):
    return CaseEvaluationResponse(
        request_fingerprint=_request_fingerprint(case),
        case_reference=case.case_reference,
        applicability=applicability, readiness=readiness, findings=findings,
        next_action=next_action,
        rule_pack=RulePackSummary(
            id=pack.id, label=pack.label, version=pack.version, status=pack.status,
            guide_updated=pack.guide_updated or "",
        ),
        disclaimer=_disclaimer_for_pack(pack),
    )


def _no_pack_response(case: CaseEvaluationRequest) -> CaseEvaluationResponse:
    mac, jurisdiction, participant = PARTICIPANT_BY_STATE.get(case.state.upper(), (None, None, None))
    status, readiness_status, message, next_action = _no_pack_routing(case)
    src = SourceReference(id=status, kind="INTERNAL_VALIDATION", title="No applicable reviewed rule pack for this case")
    applicability = ApplicabilityResult(
        status=status, message=message, state=case.state.upper(),
        jurisdiction=jurisdiction, mac=mac, participant=participant, source=src,
    )
    readiness = ReadinessResult(
        status=readiness_status, score=0, score_label="No applicable rule pack",
        confirmed_checks=0, total_checks=0,
    )
    return CaseEvaluationResponse(
        request_fingerprint=_request_fingerprint(case),
        case_reference=case.case_reference,
        applicability=applicability, readiness=readiness, findings=[],
        next_action=next_action,
        rule_pack=RulePackSummary(id="none", label="No applicable rule pack",
                                   version="0", status="NONE_AVAILABLE", guide_updated=""),
        disclaimer=DISCLAIMER_V2,
    )


def evaluate_case_v2(case: CaseEvaluationRequest) -> CaseEvaluationResponse:
    pack = select_rule_pack_for_case(
        state=case.state, coverage_type=case.coverage_type.value,
        wound_type=case.wound_type.value, service_date=case.service_date,
    )
    if pack is None:
        return _no_pack_response(case)

    for rule in pack.applicability_rules:
        if _rule_fires(rule, case):
            applicability = _build_applicability(pack, rule, case)
            readiness = ReadinessResult(
                status=rule.if_fails_status or "OUTSIDE_SCOPE", score=0,
                score_label="Applicability gate failed; evidence not evaluated",
                confirmed_checks=0, total_checks=0,
            )
            return _build_response(
                pack, case, applicability, readiness,
                [_build_finding(rule, pack, case)],
                rule.next_action or "Follow the standard Medicare workflow.",
            )

    applicability = _build_applicability_success(pack, case)
    evidence_findings: List[Finding] = []
    confirmed_checks = 0
    total_checks = 0
    blocking = False
    review = False

    for rule in pack.evidence_rules:
        if _evaluate_predicate(rule.scope, case) is not True:
            continue
        total_checks += 1
        result = _evaluate_predicate(rule.condition, case)
        if result is True:
            confirmed_checks += 1
        elif result == _PREDICATE_UNKNOWN and not rule.unknown_is_fail:
            evidence_findings.append(_build_unknown_finding(rule, pack, case))
            review = True
        else:
            evidence_findings.append(_build_finding(rule, pack, case))
            if rule.severity == "BLOCKING":
                blocking = True
            elif rule.severity == "REVIEW":
                review = True

    for rule in pack.validation_rules:
        if _evaluate_predicate(rule.scope, case) is not True:
            continue
        if _rule_fires(rule, case):
            evidence_findings.append(_build_finding(rule, pack, case))

    if blocking:
        status = "NEEDS_DOCUMENTATION"
    elif review:
        status = "READY_WITH_REVIEW"
    else:
        status = "READY_FOR_QUALIFIED_REVIEW"

    score = round((confirmed_checks / total_checks) * 100) if total_checks else 100
    readiness = ReadinessResult(
        status=status, score=score, score_label=pack.scoring.score_basis,
        confirmed_checks=confirmed_checks, total_checks=total_checks,
    )

    if status == "READY_FOR_QUALIFIED_REVIEW":
        next_action = "Send the case for internal qualified review."
    elif status == "READY_WITH_REVIEW":
        next_action = "Resolve flagged review items before submission."
    else:
        next_action = "Collect or confirm the flagged documentation before review."

    return _build_response(pack, case, applicability, readiness, evidence_findings, next_action)
