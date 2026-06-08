# WISeR Skin Readiness - Qualified Reviewer Pilot Guide

## What This Pilot Does

This shadow-mode API checks whether a structured, de-identified wound episode
contains the documentation and episode facts needed to send a case to a
qualified reviewer.

The first review target is:

```text
Texas + Original Medicare + DFU or neuropathic DFU
+ service date from 2026-01-15 through 2031-12-31
+ structured L35041 readiness review
```

The result includes:

- WISeR routing and applicability
- a readiness status and entered-evidence completeness score
- source-linked findings
- the facts that triggered each finding
- a recommended next action
- rule-pack version and evaluation audit identifiers

It does **not** determine coverage, replace clinical judgment, submit prior
authorization, or replace CMS, MAC, or Cohere review.

## Pilot Safety

Use synthetic or de-identified data only.

Do not submit:

- patient names
- MRNs or beneficiary identifiers
- dates of birth
- addresses or contact information
- identifiable clinical notes

All current rule packs and expected cases remain `DRAFT` pending qualified
review.

## How To Test

For the complete endpoint and input-field reference, see
`API_TESTING_GUIDE.md`.

1. Open the shared deployment URL. It redirects to `/docs`.
2. Open `POST /v2/readiness/evaluate`.
3. Select **Try it out**.
4. Enter the shared pilot key in the `x-api-key` field.
5. Paste a case JSON body.
6. Select **Execute**.
7. Record the `evaluation_id`, expected result, actual result, and feedback.

## Status Meanings

| Status | Meaning |
| --- | --- |
| `READY_FOR_QUALIFIED_REVIEW` | Encoded checks passed; send to the qualified reviewer |
| `READY_WITH_REVIEW` | Review-level documentation or uncertainty remains |
| `NEEDS_DOCUMENTATION` | A blocking encoded documentation or episode condition was triggered |
| `REQUIRES_HUMAN_REVIEW` | The first-slice engine intentionally abstained |
| `OUTSIDE_WISER_COVERAGE_SCOPE` | Coverage type is outside WISeR |
| `BEFORE_WISER_SERVICE_WINDOW` | Service predates 2026-01-15 |
| `OUTSIDE_WISER_MODEL_PERIOD` | Service is after 2031-12-31 |

No status is a Medicare coverage decision or denial.

## Known-Ready Starting Case

Paste this case first. Expected result: `READY_FOR_QUALIFIED_REVIEW`.

```json
{
  "case_reference": "REVIEWER-READY-01",
  "state": "TX",
  "coverage_type": "ORIGINAL_MEDICARE",
  "service_date": "2026-06-01",
  "wound_type": "DFU",
  "review_stage": "INITIAL_PRE_AUTH",
  "site_of_service": "OFFICE",
  "procedure_codes": ["15271"],
  "product_codes": ["Q4101"],
  "diagnosis_codes": ["E11.621"],
  "wound_bed": {
    "wound_size_cm_sq": 2.4,
    "wound_thickness": "FULL",
    "tendon_muscle_joint_bone_or_sinus_tract": false,
    "bed_clean_and_granular": true,
    "necrotic_debris_or_exudate_present": false
  },
  "vascular_evidence": {
    "abi_value": 0.85
  },
  "infection_evidence": {
    "active_infection": false,
    "osteomyelitis_present": false
  },
  "contraindications": {
    "uncontrolled_diabetes": false,
    "active_charcot_arthropathy": false,
    "vasculitis": false,
    "ctp_component_hypersensitivity": false,
    "continued_exposure_to_causative_factors": false
  },
  "standard_care": {
    "care_duration_days": 35,
    "care_failed_or_unresponsive": true,
    "adherence_documented": true,
    "offloading_documented": true,
    "diabetes_diagnosis_documented": true,
    "diabetes_management_documented": true
  },
  "episode_history": {
    "episode_start_date": "2026-04-20",
    "ctp_episode_start_date": "2026-06-01",
    "applications_so_far_in_episode": 0,
    "concurrent_products_in_episode": false,
    "same_wound_as_prior_course": false
  },
  "texas_episode_evidence": {
    "code_scope_confirmed": true,
    "baseline_measurement_documented": true,
    "four_week_measurement_documented": true,
    "pre_placement_measurement_documented": true,
    "response_documented_within_30_days": true,
    "comprehensive_treatment_plan_documented": true,
    "failed_interventions_documented": true,
    "updated_medication_history_documented": true,
    "pertinent_medical_problem_review_documented": true,
    "planned_procedure_documented": true,
    "selected_product_documented": true,
    "risks_complications_documented": true
  }
}
```

`code_scope_confirmed=true` means the tester separately confirmed current code
scope. The API does not yet independently maintain the complete licensed code
intersection. The codes in this synthetic example are placeholders for testing
the engine and must not be interpreted as a current coverage determination.

## Recommended Scenario Review

Start from the known-ready case and make one change at a time.

| Scenario | Change | Expected behavior | Reviewer question |
| --- | --- | --- | --- |
| Missing measurement | Set `four_week_measurement_documented` to `false` | `READY_WITH_REVIEW` | Should this stop readiness instead? |
| Short standard care | Set `care_duration_days` to `21` | `NEEDS_DOCUMENTATION` | Is the message and severity correct? |
| Active infection | Set `active_infection` to `true` | `NEEDS_DOCUMENTATION` | Is this appropriately blocking? |
| Inadequate circulation | Set ABI to `0.50` and toe pressure to `20` | `NEEDS_DOCUMENTATION` | Are thresholds and wording correct? |
| Incomplete packet | Set `selected_product_documented` to `false` | `READY_WITH_REVIEW` | Which missing packet facts should block? |
| Application cap | Set applications to `10` | `NEEDS_DOCUMENTATION` | Does application-count interpretation match workflow? |
| Simultaneous products | Set `concurrent_products_in_episode` to `true` | `NEEDS_DOCUMENTATION` | Is this applied at the right episode level? |
| Failed prior course | Set same wound true, outcome `FAILED_NO_IMPROVEMENT`, and prior end date within one year | `NEEDS_DOCUMENTATION` | Is the retreatment interpretation correct? |
| Subsequent application | Change stage to `SUBSEQUENT_APPLICATION` without post-application facts | `READY_WITH_REVIEW` | Which procedure-note facts are required? |
| Unconfirmed code scope | Set `code_scope_confirmed` to `false` | `REQUIRES_HUMAN_REVIEW` | Is abstention the correct behavior? |
| Unsupported wound | Change wound type to `VLU` | `REQUIRES_HUMAN_REVIEW` | Is the product boundary clear? |
| Unsupported site | Change site to `INPATIENT` | `REQUIRES_HUMAN_REVIEW` | Is routing guidance correct? |

## What We Need Reviewers To Validate

For each scenario, please answer:

1. Is the expected top-level status correct?
2. Is each fired rule medically and operationally appropriate?
3. Is the severity correct: blocking, review, or informational?
4. Is the explanation understandable and source interpretation correct?
5. Is the recommended next action useful?
6. Is a required Texas DFU scenario missing?
7. Would this result reduce review effort in the real workflow?

## Feedback Template

```text
Reviewer role and organization:
Review date:
Evaluation ID:
Case reference:

Expected status:
Actual status:
Agree with status? Yes / No / Partially

Incorrect or missing finding:
Correct interpretation:
Suggested severity:
Suggested wording or next action:
Source or policy reference:

Would this save time in your workflow? Yes / No / Unsure
Estimated minutes saved or added:
Additional edge case to test:
Other comments:
```

## Known Limitations To Challenge

Reviewers are specifically invited to challenge:

- which missing evidence should block versus create a review warning
- measurement-timeline requirements
- exact episode and application-count interpretation
- failed-course and healed-wound retreatment behavior
- post-application and wastage requirements
- current code-scope handling
- edge cases involving stale, conflicting, or scattered documentation

The goal of this pilot is to identify disagreements before any production or
coverage-readiness claims are made.
