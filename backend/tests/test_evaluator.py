import unittest
from datetime import date

from app.evaluator import evaluate_case
from app.schemas import CaseEvaluationRequest, CoverageType, DocumentationSignals, WoundType


def complete_dfu_documentation() -> DocumentationSignals:
    return DocumentationSignals(
        baseline_measurement_present=True,
        serial_measurements_present=True,
        photos_present=True,
        standard_care_failure_present=True,
        vascular_assessment_present=True,
        infection_assessment_present=True,
        infection_treatment_history_present=True,
        prior_treatments_present=True,
        product_rationale_present=True,
        care_plan_present=True,
        offloading_present=True,
    )


def tx_case(**overrides) -> CaseEvaluationRequest:
    values = {
        "case_reference": "CASE-TX-001",
        "state": "TX",
        "coverage_type": CoverageType.ORIGINAL_MEDICARE,
        "service_date": date(2026, 5, 12),
        "wound_type": WoundType.DFU,
        "procedure_codes": ["15271"],
        "product_codes": ["Q4101"],
        "diagnosis_codes": ["E11.621", "L97.522"],
        "documentation": complete_dfu_documentation(),
    }
    values.update(overrides)
    return CaseEvaluationRequest(**values)


class EvaluateCaseTests(unittest.TestCase):
    def test_complete_texas_case_is_ready_for_internal_review(self):
        result = evaluate_case(tx_case())

        self.assertEqual(
            result.applicability.status, "LIKELY_ACTIVE_WISER_WORKFLOW"
        )
        self.assertEqual(result.readiness.status, "READY_FOR_INTERNAL_REVIEW")
        self.assertEqual(result.readiness.score, 100)
        self.assertEqual(result.findings, [])

    def test_missing_dfu_signals_are_explainable_workflow_findings(self):
        documentation = complete_dfu_documentation()
        documentation.serial_measurements_present = False
        documentation.offloading_present = None

        result = evaluate_case(tx_case(documentation=documentation))
        finding_ids = {finding.rule_id for finding in result.findings}

        self.assertIn("SERIAL_MEASUREMENTS_PRESENT", finding_ids)
        self.assertIn("DFU_OFFLOADING_PRESENT", finding_ids)
        self.assertEqual(result.readiness.status, "NEEDS_DOCUMENTATION")
        self.assertTrue(
            all(
                finding.source.kind == "PILOT_WORKFLOW_SIGNAL"
                for finding in result.findings
            )
        )

    def test_arizona_skin_case_routes_to_inactive_jf_workflow(self):
        result = evaluate_case(tx_case(state="AZ"))

        self.assertEqual(
            result.applicability.status, "JF_SKIN_WORKFLOW_CURRENTLY_INACTIVE"
        )
        self.assertEqual(result.readiness.status, "REVIEW_ROUTING")

    def test_medicare_advantage_case_is_outside_wiser_scope(self):
        result = evaluate_case(
            tx_case(coverage_type=CoverageType.MEDICARE_ADVANTAGE)
        )

        self.assertEqual(
            result.applicability.status, "OUTSIDE_WISER_COVERAGE_SCOPE"
        )

    def test_missing_codes_create_internal_validation_warnings(self):
        result = evaluate_case(
            tx_case(procedure_codes=[], product_codes=[], diagnosis_codes=[])
        )
        finding_ids = {finding.rule_id for finding in result.findings}

        self.assertIn("APPLICATION_CODES_MISSING", finding_ids)
        self.assertIn("PRODUCT_CODES_MISSING", finding_ids)
        self.assertIn("DIAGNOSIS_CODES_MISSING", finding_ids)


if __name__ == "__main__":
    unittest.main()
