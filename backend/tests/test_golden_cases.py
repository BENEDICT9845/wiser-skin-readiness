"""Golden case test runner.

Validated cases gate CI. Draft cases run as non-blocking smoke tests.
Withdrawn cases are skipped.
"""

import json
import unittest
from pathlib import Path

from app.evaluator_v2 import evaluate_case_v2
from app.schemas import CaseEvaluationRequest


GOLDEN_DIR = Path(__file__).parent / "golden_cases"


def discover_cases():
    if not GOLDEN_DIR.exists():
        return
    for pack_dir in sorted(GOLDEN_DIR.iterdir()):
        if not pack_dir.is_dir():
            continue
        for case_file in sorted(pack_dir.glob("*.json")):
            yield case_file


def _check_applicability(actual, expected) -> list:
    errs = []
    for key, expected_value in expected.items():
        actual_value = getattr(actual, key, None)
        if actual_value != expected_value:
            errs.append(
                f"applicability.{key}: expected {expected_value!r}, "
                f"got {actual_value!r}"
            )
    return errs


def _check_findings_must_include(actual_findings, must_include) -> list:
    errs = []
    actual_by_id = {f.rule_id: f for f in actual_findings}
    for expected in must_include:
        rule_id = expected["rule_id"]
        if rule_id not in actual_by_id:
            errs.append(f"missing required finding {rule_id!r}")
            continue
        actual = actual_by_id[rule_id]
        for attr in ("severity", "classification"):
            if attr in expected and getattr(actual, attr) != expected[attr]:
                errs.append(
                    f"finding {rule_id} {attr}: expected {expected[attr]!r}, "
                    f"got {getattr(actual, attr)!r}"
                )
    return errs


def _check_findings_must_not_include(actual_findings, must_not_include) -> list:
    actual_ids = {f.rule_id for f in actual_findings}
    return [
        f"unexpected finding {rule_id!r} present in response"
        for rule_id in must_not_include
        if rule_id in actual_ids
    ]


def _assert_matches(actual, expected: dict, policy: str) -> list:
    errs = []

    expected_applicability = expected.get("applicability")
    if expected_applicability:
        errs.extend(_check_applicability(actual.applicability, expected_applicability))

    if "readiness_status" in expected:
        if actual.readiness.status != expected["readiness_status"]:
            errs.append(
                f"readiness.status: expected {expected['readiness_status']!r}, "
                f"got {actual.readiness.status!r}"
            )

    if policy == "applicability_only":
        return errs

    errs.extend(
        _check_findings_must_include(
            actual.findings, expected.get("findings_must_include", [])
        )
    )
    errs.extend(
        _check_findings_must_not_include(
            actual.findings, expected.get("findings_must_not_include", [])
        )
    )
    return errs


class GoldenCaseTests(unittest.TestCase):
    def test_all_golden_cases(self):
        validated_failures = []
        draft_failures = []
        ran = 0

        for case_file in discover_cases():
            case_def = json.loads(case_file.read_text(encoding="utf-8"))
            status = case_def.get("review_status", "draft")
            if status == "withdrawn":
                continue

            request = CaseEvaluationRequest.model_validate(case_def["request"])
            actual = evaluate_case_v2(request)
            errors = _assert_matches(
                actual,
                case_def["expected"],
                policy=case_def.get(
                    "match_policy", "strict_top_level_subset_findings"
                ),
            )
            ran += 1
            if errors:
                tag = f"{case_def['golden_case_id']} ({case_file.name})"
                if status == "validated":
                    validated_failures.append((tag, errors))
                else:
                    draft_failures.append((tag, errors))

        self.assertGreater(ran, 0, "No golden cases discovered")
        if draft_failures:
            for tag, errs in draft_failures:
                print(f"\n[DRAFT GOLDEN CASE WARNINGS] {tag}")
                for error in errs:
                    print(f"  - {error}")

        if validated_failures:
            msg_lines = ["Validated golden case failures:"]
            for tag, errs in validated_failures:
                msg_lines.append(f"  {tag}")
                msg_lines.extend(f"    - {error}" for error in errs)
            self.fail("\n".join(msg_lines))


if __name__ == "__main__":
    unittest.main()
