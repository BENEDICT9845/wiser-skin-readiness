# WISeR Skin Readiness

An API-first, explainable readiness checker for structured, de-identified
skin-substitute cases under the CMS WISeR model.

The current pilot focuses on Texas Original Medicare DFU and neuropathic DFU
cases evaluated against a draft, source-linked L35041 rule pack.

## Product Boundary

The API:

- checks WISeR routing and first-slice applicability
- evaluates documentation and episode-readiness facts
- returns source-linked findings, triggering facts, and next actions
- records the rule-pack version and audit identifiers

The API does not determine Medicare coverage, submit prior authorization,
replace a qualified reviewer, or accept PHI during the pilot.

## Repository

```text
backend/            FastAPI service, rule packs, tests, and Dockerfile
docs/               Deployment, operations, reviewer, and rule-scope guides
.github/workflows/  Automated backend verification
render.yaml         Render pilot deployment Blueprint
```

## Run Locally

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000`. The root redirects to the interactive API
documentation.

For authenticated pilot behavior:

```powershell
$env:WISER_API_KEY = "your-pilot-secret"
python -m uvicorn app.main:app --port 8000
```

## Verify

```powershell
cd backend
python -m unittest discover -s tests -v
```

Docker verification:

```powershell
docker build --target test -t wiser-backend-test ./backend
docker run --rm wiser-backend-test
```

## Pilot Documentation

- [Deployment guide](docs/DEPLOYMENT.md)
- [Client API and testing guide](docs/API_TESTING_GUIDE.md)
- [Qualified reviewer guide](docs/REVIEWER_GUIDE.md)
- [Pilot operations](docs/OPERATIONS.md)
- [Rule scope and sources](docs/RULE_SCOPE.md)

## Current Status

The Texas and Ohio rule packs remain `DRAFT`. Results are for de-identified
shadow-mode review only and require qualified clinical/compliance validation.
