# Pilot Operations Runbook

Scope: de-identified shadow-mode pilot only.

## Required environment

```text
WISER_API_KEY=<long random pilot secret>
```

When `WISER_API_KEY` is configured, all `/v1` and `/v2` endpoints require the
`X-API-Key` header. `/health` and `/ready` remain unauthenticated for platform
health checks.

Never place PHI in environment variables, logs, case references, evidence
references, or request headers.

## Local run

```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Container run

```powershell
docker build -t wiser-skin-readiness ./backend
docker run --rm -p 8000:8000 -e WISER_API_KEY=<secret> wiser-skin-readiness
```

## Health checks

- `GET /health`: process is responding
- `GET /ready`: production-target rule packs load and validate

## Audit behavior

- Every HTTP response includes `X-Request-ID`.
- Every evaluation includes `evaluation_id`, UTC `evaluated_at`, and a SHA-256
  request fingerprint.
- Request bodies and triggering facts are not written to application logs by
  the provided middleware.
- Logs contain request ID, method, path, status, and duration only.

## Rule-pack release

1. Add or modify the source-register and claim-ledger entries.
2. Create a new immutable rule-pack version; never silently edit a published
   pack.
3. Add draft golden cases and ordinary regression tests.
4. Run `python -m unittest discover -s tests -v`.
5. Complete technical and qualified review.
6. Promote pack status only after review evidence exists.
7. Deploy and verify `/ready`.

## Rollback

1. Restore the prior application image or release.
2. Keep the problematic pack in history and mark it `WITHDRAWN` or
   `SUPERSEDED`; do not delete it.
3. Record the affected rule IDs, evaluations, and source interpretation.
4. Re-run golden cases and technical tests before redeploying.

## Pilot restrictions

- Texas L35041 and Ohio L36690 packs remain `DRAFT`.
- Do not present results as coverage decisions.
- Do not use the pilot endpoint for identified patient data.
- Route unknown, conflicting, unsupported, and out-of-scope cases to the
  client's qualified reviewer.
