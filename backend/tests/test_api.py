import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


SAMPLE_REQUEST = (
    Path(__file__).parents[1] / "sample_requests" / "evaluate-dfu.json"
)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertTrue(response.headers["X-Request-ID"].startswith("req_"))

    def test_root_redirects_to_interactive_docs(self):
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/docs")

    def test_ready_check_loads_production_target_packs(self):
        response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")

    def test_evaluate_sample_case(self):
        payload = json.loads(SAMPLE_REQUEST.read_text(encoding="utf-8"))
        response = self.client.post("/v1/readiness/evaluate", json=payload)
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["applicability"]["status"], "LIKELY_ACTIVE_WISER_WORKFLOW")
        self.assertIn(body["readiness"]["status"], {"NEEDS_DOCUMENTATION", "READY_FOR_INTERNAL_REVIEW"})

    def test_unknown_rule_pack_returns_404(self):
        response = self.client.get("/v1/rule-packs/not-found")
        self.assertEqual(response.status_code, 404)

    def test_api_key_is_required_when_configured(self):
        with patch.dict(os.environ, {"WISER_API_KEY": "pilot-secret"}):
            unauthorized = self.client.get("/v1/rule-packs/not-found")
            authorized = self.client.get(
                "/v1/rule-packs/not-found",
                headers={"X-API-Key": "pilot-secret"},
            )
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(authorized.status_code, 404)

    def test_validation_errors_use_structured_non_echoing_envelope(self):
        response = self.client.post("/v2/readiness/evaluate", json={"case_reference": "X"})
        body = response.json()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(body["error"]["code"], "VALIDATION_ERROR")

    def test_negative_clinical_values_are_rejected(self):
        response = self.client.post(
            "/v2/readiness/evaluate",
            json={
                "case_reference": "NEGATIVE-WOUND",
                "state": "TX",
                "coverage_type": "ORIGINAL_MEDICARE",
                "service_date": "2026-06-01",
                "wound_type": "DFU",
                "wound_bed": {"wound_size_cm_sq": -1},
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")


if __name__ == "__main__":
    unittest.main()
