# WISeR Skin Readiness API - Client Testing Guide

## Purpose

WISeR Skin Readiness is a shadow-mode decision-support API. It checks a
structured, de-identified skin-substitute case and returns:

- whether the case is within the encoded WISeR workflow
- whether important documentation and episode facts are confirmed
- source-linked findings explaining missing or concerning facts
- a recommended next action for the qualified reviewer

The current primary pilot scope is Texas Original Medicare DFU and neuropathic
DFU cases evaluated using the draft L35041 first-slice rule pack.

This API does not determine Medicare coverage, submit prior authorization, or
replace qualified clinical, coding, compliance, CMS, MAC, or Cohere review.

## Pilot Access

Base URL:

```text
https://wiser-skin-readiness-pilot.onrender.com
```

Opening the base URL redirects to the interactive Swagger API documentation.

Protected endpoints require the shared pilot value in this HTTP header:

```text
X-API-Key: <shared-pilot-key>
```

Use synthetic or de-identified information only. Do not submit patient names,
MRNs, beneficiary identifiers, dates of birth, addresses, or identifiable
clinical notes.

## Recommended Testing Workflow

1. Open the base URL.
2. Select `POST /v2/readiness/evaluate`.
3. Select **Try it out**.
4. Enter the pilot key in the `x-api-key` field.
5. Paste the known-ready sample from
   `backend/sample_requests/texas-dfu-ready-v2.json`.
6. Select **Execute**.
7. Confirm the result is `READY_FOR_QUALIFIED_REVIEW`.
8. Change one field at a time using the scenario catalog in
   `backend/sample_requests/texas-dfu-test-catalog.json`.
9. Record the `evaluation_id`, expected status, actual status, and feedback.

The scenario catalog is automatically tested against the evaluator on every
code change.

## API Endpoints

### Pilot Endpoints

| Method and path | Authentication | Purpose |
| --- | --- | --- |
| `POST /v2/readiness/evaluate` | Required | Evaluate one structured case |
| `POST /v2/readiness/evaluate-batch` | Required | Evaluate 1 to 500 cases |
| `GET /v2/rule-packs/{rule_pack_id}` | Required | Inspect a rule pack and its sources |
| `GET /health` | None | Confirm the API process is responding |
| `GET /ready` | None | Confirm required rule packs load successfully |
| `GET /docs` | None | Open interactive API documentation |
| `GET /openapi.json` | None | Download the OpenAPI contract |

### Legacy Prototype Endpoints

The `/v1` endpoints preserve an earlier prototype. Testers validating the
current source-linked product should use `/v2`.

## Single-Case Evaluation

Request:

```http
POST /v2/readiness/evaluate
Content-Type: application/json
X-API-Key: <shared-pilot-key>
```

PowerShell example:

```powershell
$headers = @{ "X-API-Key" = "<shared-pilot-key>" }
$body = Get-Content .\backend\sample_requests\texas-dfu-ready-v2.json -Raw

Invoke-RestMethod `
  -Uri https://wiser-skin-readiness-pilot.onrender.com/v2/readiness/evaluate `
  -Method Post `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

## Batch Evaluation

Use the batch endpoint when an integration needs to evaluate multiple complete
case snapshots together.

```json
{
  "cases": [
    {
      "case_reference": "BATCH-001",
      "state": "TX",
      "coverage_type": "ORIGINAL_MEDICARE",
      "service_date": "2026-06-01",
      "wound_type": "DFU"
    }
  ]
}
```

The batch accepts 1 to 500 cases. If any case fails request-schema validation,
the request returns HTTP `422` before evaluation.

## Required Top-Level Inputs

| Field | Type | Accepted values or format | Meaning |
| --- | --- | --- | --- |
| `case_reference` | string | 1 to 120 characters | De-identified client reference |
| `state` | string | Two-letter US state | Service state used for routing |
| `coverage_type` | enum | `ORIGINAL_MEDICARE`, `RAILROAD_MEDICARE`, `MEDICARE_ADVANTAGE`, `OTHER` | Payer scope |
| `service_date` | date | `YYYY-MM-DD` | Planned or rendered service date |
| `wound_type` | enum | `DFU`, `NEUROPATHIC`, `VSU`, `VLU`, `TRAUMA`, `PRESSURE`, `OTHER` | Wound classification |

For the Texas first slice, expected in-scope values are:

```text
state = TX
coverage_type = ORIGINAL_MEDICARE
wound_type = DFU or NEUROPATHIC
service_date = 2026-01-15 through 2031-12-31
```

An accepted input field does not necessarily affect the current Texas rule
slice. Some fields are retained for backward compatibility or future
integration mapping. Testers should use the response `triggering_facts` to see
which submitted facts affected a finding.

## Routing and Case Inputs

| Field | Type | Accepted values or format | Meaning |
| --- | --- | --- | --- |
| `review_stage` | enum | `INITIAL_PRE_AUTH`, `SUBSEQUENT_APPLICATION`, `CLAIM_PREPAYMENT_REVIEW` | Controls stage-specific checks |
| `site_of_service` | string | First-slice supported: `OFFICE`, `HOME`, `HOSPITAL_OPD`, `ASC` | Site routing |
| `episode_reference` | string | De-identified | Client episode reference |
| `wound_reference` | string | De-identified | Client wound reference |
| `planned_application_date` | date | `YYYY-MM-DD` | Planned application date |
| `procedure_codes` | string array | Code strings | Procedure-code inputs |
| `product_codes` | string array | HCPCS-style code strings | Product-code inputs |
| `diagnosis_codes` | string array | Code strings | Diagnosis-code inputs |

The pilot does not independently confirm the complete licensed code
intersection. The Texas first slice abstains unless
`texas_episode_evidence.code_scope_confirmed` is `true`.

The optional top-level `documentation` object belongs to the legacy `/v1`
prototype. Current Texas rule validation uses the structured `/v2` evidence
objects described below.

## Wound-Bed Inputs

Object: `wound_bed`

| Field | Type | Meaning |
| --- | --- | --- |
| `wound_size_cm_sq` | non-negative number | Current wound area |
| `wound_thickness` | `PARTIAL`, `FULL`, or `UNKNOWN` | Documented wound thickness |
| `tendon_muscle_joint_bone_or_sinus_tract` | boolean | Whether deep structures or sinus tract are involved |
| `bed_clean_and_granular` | boolean | Whether wound bed is documented clean and granular |
| `necrotic_debris_or_exudate_present` | boolean | Whether necrotic debris or exudate is present |

## Vascular and Infection Inputs

Object: `vascular_evidence`

| Field | Type | Meaning |
| --- | --- | --- |
| `abi_value` | non-negative number | Documented ABI |
| `toe_pressure_mmhg` | non-negative number | Documented toe pressure |
| `assessment_documented` | boolean | Whether vascular assessment is documented |

Object: `infection_evidence`

| Field | Type | Meaning |
| --- | --- | --- |
| `active_infection` | boolean | Whether active infection is present |
| `osteomyelitis_present` | boolean | Whether underlying osteomyelitis is present |
| `assessment_documented` | boolean | Whether infection assessment is documented |
| `treatment_history_documented` | boolean | Whether infection treatment history is documented |

## Standard-Care Inputs

Object: `standard_care`

| Field | Type | Meaning |
| --- | --- | --- |
| `care_duration_days` | non-negative integer | Duration of documented conservative care |
| `care_failed_or_unresponsive` | boolean | Whether failure or non-response is documented |
| `adherence_documented` | boolean | Whether adherence is documented |
| `offloading_documented` | boolean | DFU offloading documentation |
| `diabetes_diagnosis_documented` | boolean | Diabetes diagnosis documentation |
| `diabetes_management_documented` | boolean | Diabetes management documentation |
| `ulcer_duration_days` | non-negative integer | Ulcer duration |
| `unresponsive_care_duration_days` | non-negative integer | Duration of unresponsive care |
| `compression_documented` | boolean | Compression documentation |
| `compression_method` | enum | `MULTILAYER_DRESSING`, `STOCKINGS_20MMHG_OR_HIGHER`, `PNEUMATIC`, `OTHER`, `UNKNOWN` |

## Contraindication Inputs

Object: `contraindications`

All fields are booleans:

- `uncontrolled_diabetes`
- `active_charcot_arthropathy`
- `vasculitis`
- `ctp_component_hypersensitivity`
- `continued_exposure_to_causative_factors`

## Episode-History Inputs

Object: `episode_history`

| Field | Type | Meaning |
| --- | --- | --- |
| `episode_start_date` | date | Broader wound episode start |
| `ctp_episode_start_date` | date | Start of current CTP treatment window |
| `applications_so_far_in_episode` | non-negative integer | Completed applications before the planned service |
| `products_used_in_episode` | string array | Products used in the episode |
| `concurrent_products_in_episode` | boolean | Whether simultaneous products are used |
| `same_wound_as_prior_course` | boolean | Whether history refers to the same wound |
| `last_completed_ctp_course_end_date` | date | Prior completed course end |
| `last_completed_ctp_course_outcome` | enum | `HEALED`, `FAILED_NO_IMPROVEMENT`, `FAILED_WORSENING`, `DISCONTINUED_OTHER`, `UNKNOWN` |
| `prior_healed_size_cm_sq` | non-negative number | Prior healed wound size |
| `prior_healed_size_reduction_pct` | number from 0 to 100 | Prior size-reduction percentage |

`applications_so_far_in_episode` means completed applications before the
planned service. A value of `9` permits evaluation of a planned tenth
application; `10` triggers the encoded application-limit finding.

## Texas Documentation Inputs

Object: `texas_episode_evidence`

These boolean fields represent whether the relevant evidence is confirmed:

| Group | Fields |
| --- | --- |
| Code scope | `code_scope_confirmed` |
| Measurements | `baseline_measurement_documented`, `four_week_measurement_documented`, `pre_placement_measurement_documented`, `subsequent_placement_measurements_documented`, `response_documented_within_30_days` |
| Pre-service packet | `comprehensive_treatment_plan_documented`, `failed_interventions_documented`, `updated_medication_history_documented`, `pertinent_medical_problem_review_documented`, `planned_procedure_documented`, `selected_product_documented`, `risks_complications_documented` |
| Stage-specific documentation | `pre_treatment_wound_description_documented`, `post_treatment_wound_description_documented`, `wastage_documented`, `continuation_rationale_documented` |
| Smoking | `smoking_counseling_documented` |

Omitted values are treated as unknown, not confirmed.

## Tobacco Inputs

Object: `tobacco_use`

| Field | Type | Meaning |
| --- | --- | --- |
| `smoking_status` | enum | `NEVER`, `FORMER`, `CURRENT`, `UNKNOWN` |
| `cessation_for_at_least_4_weeks` | boolean | Whether cessation duration is confirmed |
| `documented` | boolean | Whether tobacco history is documented |

## Understanding the Response

Important response fields:

| Field | Meaning |
| --- | --- |
| `evaluation_id` | Unique identifier to include in feedback |
| `evaluated_at` | UTC evaluation time |
| `request_fingerprint` | Stable SHA-256 fingerprint of the structured request |
| `applicability` | Routing, jurisdiction, MAC, participant, and applicability status |
| `readiness` | Top-level status and entered-evidence score |
| `findings` | Fired rules, source links, triggering facts, and next actions |
| `next_action` | Recommended overall next step |
| `rule_pack` | Exact rule-pack ID, version, and status |
| `disclaimer` | Product and decision-support boundary |

### Readiness Statuses

| Status | Meaning |
| --- | --- |
| `READY_FOR_QUALIFIED_REVIEW` | Encoded checks passed; send to qualified review |
| `READY_WITH_REVIEW` | Review-level uncertainty or missing evidence remains |
| `NEEDS_DOCUMENTATION` | A blocking encoded condition was triggered |
| `REQUIRES_HUMAN_REVIEW` | The first-slice engine intentionally abstained |
| `OUTSIDE_WISER_COVERAGE_SCOPE` | Coverage type is outside WISeR |
| `BEFORE_WISER_SERVICE_WINDOW` | Service predates 2026-01-15 |
| `OUTSIDE_WISER_MODEL_PERIOD` | Service is after 2031-12-31 |

### Finding Classifications

| Classification | Meaning |
| --- | --- |
| `OFFICIAL_RULE` | Encoded interpretation linked to an official source |
| `WORKFLOW_SIGNAL` | Operational signal, not an official coverage rule |
| `INTERNAL_VALIDATION` | Format, consistency, or product-boundary check |

### Finding Severities

| Severity | Meaning |
| --- | --- |
| `BLOCKING` | Drives `NEEDS_DOCUMENTATION` when triggered |
| `REVIEW` | Drives `READY_WITH_REVIEW` when no blocking finding exists |
| `INFORMATIONAL` | Provides validation or routing information |

## Verified Scenario Catalog

The supplied catalog contains 18 scenarios:

- complete ready case
- missing four-week measurement
- short standard care
- active infection
- low circulation
- incomplete pre-service packet
- application cap
- outside 12-week window
- simultaneous products
- unsuccessful prior course
- healed-wound retreatment
- subsequent application missing documentation
- code scope unconfirmed
- VLU outside first slice
- unsupported site
- Medicare Advantage
- before service window
- after model period

Files:

- `backend/sample_requests/texas-dfu-ready-v2.json`
- `backend/sample_requests/texas-dfu-test-catalog.json`

The catalog format:

```json
{
  "id": "ACTIVE_INFECTION",
  "changes": {
    "infection_evidence.active_infection": true
  },
  "expected_status": "NEEDS_DOCUMENTATION",
  "expected_finding": "L35041_DFU_INFECTION_AND_OSTEOMYELITIS"
}
```

Start with the ready request, apply the listed changes, and compare the actual
result with `expected_status` and `expected_finding`.

## Validation Errors

Malformed requests return HTTP `422`:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": []
  }
}
```

Examples include:

- missing required top-level fields
- invalid enum values
- negative wound size or application count
- invalid date format
- more than 500 batch cases

## Feedback To Provide

For each reviewed scenario, record:

```text
Reviewer role:
Evaluation ID:
Case reference:
Expected status:
Actual status:
Agree? Yes / No / Partially
Incorrect or missing finding:
Correct interpretation:
Suggested severity:
Suggested next action:
Supporting source:
Additional edge case:
Estimated workflow time saved or added:
```

The most valuable feedback is where the encoded status, severity, explanation,
or next action differs from real Texas wound-care review practice.
