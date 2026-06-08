import unittest
import json
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from app.evaluator_v2 import evaluate_case_v2
from app.rule_packs.models import RulePack
from app.schemas import CaseEvaluationRequest, CoverageType, WoundType


def minimal_case(**overrides) -> CaseEvaluationRequest:
    values = {
        "case_reference": "V2-CASE",
        "state": "OH",
        "coverage_type": CoverageType.ORIGINAL_MEDICARE,
        "service_date": date(2026, 6, 1),
        "wound_type": WoundType.DFU,
        "procedure_codes": ["15271"],
        "product_codes": ["Q4101"],
        "diagnosis_codes": ["E11.621"],
    }
    values.update(overrides)
    return CaseEvaluationRequest(**values)


def texas_ready_case(**overrides) -> CaseEvaluationRequest:
    fixture = (
        Path(__file__).parent
        / "golden_cases"
        / "cms-wiser-skin-l35041-tx-dfu-v0.1"
        / "TX-DFU-01-ready.json"
    )
    values = json.loads(fixture.read_text(encoding="utf-8"))["request"]
    values.update(overrides)
    return CaseEvaluationRequest.model_validate(values)


class EvaluateCaseV2Tests(unittest.TestCase):
    def test_coverage_applicability_rule_is_reachable(self):
        result = evaluate_case_v2(
            minimal_case(coverage_type=CoverageType.MEDICARE_ADVANTAGE)
        )

        self.assertEqual(
            result.applicability.status, "OUTSIDE_WISER_COVERAGE_SCOPE"
        )
        self.assertEqual(
            result.readiness.status, "OUTSIDE_WISER_COVERAGE_SCOPE"
        )
        self.assertEqual(
            result.findings[0].rule_id, "WISER_APPLICABILITY_ORIGINAL_MEDICARE"
        )

    def test_railroad_medicare_is_explicitly_outside_wiser_scope(self):
        result = evaluate_case_v2(
            minimal_case(coverage_type=CoverageType.RAILROAD_MEDICARE)
        )

        self.assertEqual(result.applicability.status, "OUTSIDE_WISER_COVERAGE_SCOPE")
        self.assertEqual(result.readiness.status, "OUTSIDE_WISER_COVERAGE_SCOPE")

    def test_wound_scope_applicability_rule_is_reachable(self):
        result = evaluate_case_v2(minimal_case(wound_type=WoundType.PRESSURE))

        self.assertEqual(result.applicability.status, "OUTSIDE_L36690_WOUND_SCOPE")
        self.assertEqual(result.readiness.status, "OUTSIDE_L36690_WOUND_SCOPE")

    def test_unknown_official_evidence_is_review_not_confirmed(self):
        result = evaluate_case_v2(minimal_case())
        unknown_findings = [finding for finding in result.findings if finding.status == "UNKNOWN"]

        self.assertEqual(result.readiness.status, "NEEDS_DOCUMENTATION")
        self.assertLess(result.readiness.confirmed_checks, result.readiness.total_checks)
        self.assertTrue(unknown_findings)
        self.assertTrue(
            all(finding.severity == "REVIEW" for finding in unknown_findings)
        )
        self.assertIn(
            "wound_bed.wound_size_cm_sq",
            next(
                finding.triggering_facts
                for finding in unknown_findings
                if finding.rule_id == "L36690_WOUND_SIZE_MINIMUM"
            ),
        )

    def test_outside_pilot_state_has_specific_routing(self):
        result = evaluate_case_v2(minimal_case(state="CA"))

        self.assertEqual(result.applicability.status, "OUTSIDE_WISER_PILOT_REGION")
        self.assertEqual(result.readiness.status, "OUTSIDE_WISER_PILOT_REGION")

    def test_texas_pack_abstains_when_code_scope_is_unconfirmed(self):
        result = evaluate_case_v2(
            minimal_case(
                state="TX",
                review_stage="INITIAL_PRE_AUTH",
                site_of_service="OFFICE",
            )
        )

        self.assertEqual(result.applicability.status, "REQUIRES_HUMAN_REVIEW")
        self.assertEqual(result.readiness.status, "REQUIRES_HUMAN_REVIEW")
        self.assertEqual(result.rule_pack.id, "cms-wiser-skin-l35041-tx-dfu-v0.1")

    def test_texas_ready_fixture_selects_l35041_pack(self):
        fixture = (
            Path(__file__).parent
            / "golden_cases"
            / "cms-wiser-skin-l35041-tx-dfu-v0.1"
            / "TX-DFU-01-ready.json"
        )
        request = CaseEvaluationRequest.model_validate(
            json.loads(fixture.read_text(encoding="utf-8"))["request"]
        )

        result = evaluate_case_v2(request)

        self.assertEqual(result.applicability.status, "LIKELY_ACTIVE_WISER_WORKFLOW")
        self.assertEqual(result.readiness.status, "READY_FOR_QUALIFIED_REVIEW")
        self.assertEqual(result.rule_pack.id, "cms-wiser-skin-l35041-tx-dfu-v0.1")

    def test_wiser_service_window_starts_january_15(self):
        result = evaluate_case_v2(
            minimal_case(state="TX", service_date=date(2026, 1, 10))
        )

        self.assertEqual(result.applicability.status, "BEFORE_WISER_SERVICE_WINDOW")
        self.assertEqual(result.readiness.status, "BEFORE_WISER_SERVICE_WINDOW")

    def test_texas_application_limit_uses_episode_dates(self):
        fixture = (
            Path(__file__).parent
            / "golden_cases"
            / "cms-wiser-skin-l35041-tx-dfu-v0.1"
            / "TX-DFU-08-application-limit.json"
        )
        request = CaseEvaluationRequest.model_validate(
            json.loads(fixture.read_text(encoding="utf-8"))["request"]
        )

        result = evaluate_case_v2(request)

        self.assertEqual(result.readiness.status, "NEEDS_DOCUMENTATION")
        self.assertIn(
            "L35041_DFU_APPLICATION_AND_WINDOW_LIMIT",
            {finding.rule_id for finding in result.findings},
        )

    def test_texas_pack_abstains_without_review_stage(self):
        result = evaluate_case_v2(
            minimal_case(
                state="TX",
                site_of_service="OFFICE",
            )
        )

        self.assertEqual(result.applicability.status, "REQUIRES_HUMAN_REVIEW")
        self.assertEqual(result.findings[0].rule_id, "L35041_TX_REVIEW_STAGE_REQUIRED")

    def test_texas_pack_abstains_for_emergency_site(self):
        result = evaluate_case_v2(
            minimal_case(
                state="TX",
                review_stage="INITIAL_PRE_AUTH",
                site_of_service="EMERGENCY",
            )
        )

        self.assertEqual(result.applicability.status, "REQUIRES_HUMAN_REVIEW")
        self.assertEqual(result.findings[0].rule_id, "WISER_APPLICABILITY_SITE_OF_SERVICE")

    def test_texas_pack_abstains_for_unsupported_site(self):
        result = evaluate_case_v2(
            minimal_case(
                state="TX",
                review_stage="INITIAL_PRE_AUTH",
                site_of_service="UNRECOGNIZED_SITE",
            )
        )

        self.assertEqual(result.applicability.status, "REQUIRES_HUMAN_REVIEW")
        self.assertEqual(result.findings[0].rule_id, "WISER_APPLICABILITY_SITE_OF_SERVICE")

    def test_service_after_model_period_does_not_select_pack(self):
        result = evaluate_case_v2(
            minimal_case(state="TX", service_date=date(2032, 1, 1))
        )

        self.assertEqual(result.applicability.status, "OUTSIDE_WISER_MODEL_PERIOD")
        self.assertEqual(result.readiness.status, "OUTSIDE_WISER_MODEL_PERIOD")

    def test_reversed_ctp_episode_dates_do_not_pass_window_rule(self):
        request = texas_ready_case(
            episode_history={
                "ctp_episode_start_date": "2026-06-02",
                "applications_so_far_in_episode": 0,
                "concurrent_products_in_episode": False,
                "same_wound_as_prior_course": False,
            }
        )

        result = evaluate_case_v2(request)
        finding_ids = {finding.rule_id for finding in result.findings}

        self.assertEqual(result.readiness.status, "READY_WITH_REVIEW")
        self.assertIn("L35041_DFU_APPLICATION_AND_WINDOW_LIMIT", finding_ids)
        self.assertIn("CTP_EPISODE_DATE_ORDER", finding_ids)

    def test_unsuccessful_same_wound_course_inside_one_year_blocks(self):
        request = texas_ready_case(
            episode_history={
                "ctp_episode_start_date": "2026-06-01",
                "applications_so_far_in_episode": 0,
                "concurrent_products_in_episode": False,
                "same_wound_as_prior_course": True,
                "last_completed_ctp_course_end_date": "2025-12-01",
                "last_completed_ctp_course_outcome": "FAILED_NO_IMPROVEMENT",
            }
        )

        result = evaluate_case_v2(request)

        self.assertEqual(result.readiness.status, "NEEDS_DOCUMENTATION")
        self.assertIn(
            "L35041_DFU_ONE_YEAR_SAME_WOUND_RETREATMENT",
            {finding.rule_id for finding in result.findings},
        )

    def test_non_failed_prior_course_does_not_fire_one_year_failure_rule(self):
        request = texas_ready_case(
            episode_history={
                "ctp_episode_start_date": "2026-06-01",
                "applications_so_far_in_episode": 0,
                "concurrent_products_in_episode": False,
                "same_wound_as_prior_course": True,
                "last_completed_ctp_course_end_date": "2025-12-01",
                "last_completed_ctp_course_outcome": "DISCONTINUED_OTHER",
            }
        )

        result = evaluate_case_v2(request)

        self.assertNotIn(
            "L35041_DFU_ONE_YEAR_SAME_WOUND_RETREATMENT",
            {finding.rule_id for finding in result.findings},
        )

    def test_healed_same_wound_retreatment_blocks(self):
        request = texas_ready_case(
            episode_history={
                "ctp_episode_start_date": "2026-06-01",
                "applications_so_far_in_episode": 0,
                "concurrent_products_in_episode": False,
                "same_wound_as_prior_course": True,
                "last_completed_ctp_course_outcome": "HEALED",
                "prior_healed_size_reduction_pct": 80,
                "prior_healed_size_cm_sq": 0.4,
            }
        )

        result = evaluate_case_v2(request)

        self.assertEqual(result.readiness.status, "NEEDS_DOCUMENTATION")
        self.assertIn(
            "L35041_DFU_HEALED_WOUND_RETREATMENT",
            {finding.rule_id for finding in result.findings},
        )

    def test_negative_application_count_is_rejected(self):
        with self.assertRaises(ValidationError):
            texas_ready_case(
                episode_history={
                    "ctp_episode_start_date": "2026-06-01",
                    "applications_so_far_in_episode": -1,
                }
            )

    def test_rule_pack_rejects_blocking_workflow_signal(self):
        payload = {
            "id": "invalid-pack",
            "label": "Invalid",
            "version": "1",
            "status": "DRAFT",
            "effective_date_range": {"starts_on": "2026-01-01"},
            "scope": {},
            "sources": {
                "PILOT": {
                    "kind": "PILOT_WORKFLOW_SIGNAL",
                    "title": "Pilot signal",
                }
            },
            "evidence_rules": [
                {
                    "rule_id": "INVALID",
                    "kind": "evidence",
                    "classification": "WORKFLOW_SIGNAL",
                    "severity": "BLOCKING",
                    "message_template": "Invalid",
                    "rationale_template": "Invalid",
                    "source_id": "PILOT",
                }
            ],
        }

        with self.assertRaises(ValueError):
            RulePack.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
