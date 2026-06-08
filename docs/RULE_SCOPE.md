# Rule Scope and Sources

## Current Pilot Scope

The primary pilot slice evaluates:

```text
Texas
+ Original Medicare
+ DFU or neuropathic DFU
+ service date from 2026-01-15 through 2031-12-31
+ structured, de-identified episode snapshot
+ L35041 draft readiness checks
```

The API intentionally abstains when the case is outside the encoded first
slice or when current code scope is not confirmed.

## Result Boundary

Results indicate whether encoded documentation and episode facts appear ready
for a client's qualified review.

Results do not:

- determine coverage or payment
- replace CMS, MAC, participant, coding, clinical, or compliance review
- submit prior authorization
- independently verify every licensed code-list intersection

## Rule Packs

| Rule pack | Scope | Status |
| --- | --- | --- |
| `cms-wiser-skin-l35041-tx-dfu-v0.1` | Texas DFU first slice | `DRAFT` |
| `cms-wiser-skin-l36690-v0.1` | Ohio L36690 technical slice | `DRAFT` |

Each finding identifies its source, rule-pack version, classification,
triggering facts, and recommended next action.

## Primary Official Sources

- [CMS WISeR Provider and Supplier Operational Guide](https://www.cms.gov/priorities/innovation/files/wiser-provider-supplier-guide.pdf)
- [CMS WISeR Model](https://www.cms.gov/priorities/innovation/innovation-models/wiser)
- [CMS L35041](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=35041)
- [CMS A54117](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleId=54117)
- [CMS L36690](https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=36690)
- [CMS A56696](https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleId=56696)

## Validation Requirement

The rule packs must remain `DRAFT` until qualified clinical/compliance
reviewers approve the source interpretation and representative case outcomes.
