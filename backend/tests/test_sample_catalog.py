import copy
import json
import unittest
from pathlib import Path

from app.evaluator_v2 import evaluate_case_v2
from app.schemas import CaseEvaluationRequest


SAMPLES_DIR = Path(__file__).parents[1] / "sample_requests"


def apply_changes(payload: dict, changes: dict) -> dict:
    updated = copy.deepcopy(payload)
    for path, value in changes.items():
        current = updated
        parts = path.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return updated


class SampleCatalogTests(unittest.TestCase):
    def test_documented_pilot_scenarios_match_evaluator(self):
        catalog = json.loads(
            (SAMPLES_DIR / "texas-dfu-test-catalog.json").read_text(encoding="utf-8")
        )
        base = json.loads(
            (SAMPLES_DIR / catalog["base_request_file"]).read_text(encoding="utf-8")
        )

        for scenario in catalog["scenarios"]:
            with self.subTest(scenario=scenario["id"]):
                payload = apply_changes(base, scenario["changes"])
                payload["case_reference"] = f"CATALOG-{scenario['id']}"
                request = CaseEvaluationRequest.model_validate(payload)
                result = evaluate_case_v2(request)

                self.assertEqual(result.readiness.status, scenario["expected_status"])
                expected_finding = scenario["expected_finding"]
                if expected_finding:
                    self.assertIn(
                        expected_finding,
                        {finding.rule_id for finding in result.findings},
                    )


if __name__ == "__main__":
    unittest.main()
