# WISeR Skin Readiness API

FastAPI service for deterministic, source-linked WISeR skin-substitute
readiness screening.

## Run

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Open:

- Interactive API: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/health`
- Readiness: `http://127.0.0.1:8000/ready`

Set `WISER_API_KEY` to protect `/v1` and `/v2` endpoints. Send the value using
the `X-API-Key` request header.

## Pilot Endpoint

Use:

```text
POST /v2/readiness/evaluate
```

The `/v1` endpoints preserve the original prototype and are not intended for
qualified rule validation.

## Verify

```powershell
python -m unittest discover -s tests -v
```

After starting the service:

```powershell
.\smoke.ps1 -BaseUrl http://127.0.0.1:8000 -ApiKey <API_KEY>
```

## Safety

- Use synthetic or de-identified data only.
- Current rule packs remain `DRAFT`.
- Results do not determine coverage or replace qualified review.
- Every response includes request/evaluation audit identifiers.
