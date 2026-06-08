# Pilot Deployment Guide - Render

Purpose: deploy the current API for a small, de-identified qualified-review
pilot. This is not a production or PHI-enabled deployment.

## Before Deployment

- Keep the repository private unless you intentionally want it public.
- Do not put PHI, patient names, MRNs, dates of birth, or identifiable notes in
  the repository or pilot requests.
- Generate a long random pilot API key and share it only with invited
  reviewers.
- Treat the Texas and Ohio rule packs as `DRAFT`.

## 1. Push the Repository

The local repository currently has no Git remote. Create an empty private
GitHub repository, then run from the project root:

```powershell
git add .
git commit -m "Prepare WISeR shadow pilot"
git remote add origin https://github.com/<account>/<repository>.git
git push -u origin main
```

Review staged files before committing. Do not commit `.env` files or secrets.

## 2. Deploy the Render Blueprint

1. Sign in at https://dashboard.render.com.
2. Select **New**, then **Blueprint**.
3. Connect the GitHub repository.
4. Render detects the root `render.yaml`.
5. Enter a long random value when prompted for `WISER_API_KEY`.
6. Apply the Blueprint and wait for the service to become live.

Render builds the runtime Docker target, provides its `PORT` environment
variable, and checks `/ready`. The first URL will look similar to:

```text
https://wiser-skin-readiness-pilot.onrender.com
```

Opening the root URL redirects to the interactive API documentation.

## 3. Verify the Deployment

Replace `<BASE_URL>` and `<API_KEY>`:

```powershell
Invoke-RestMethod <BASE_URL>/health
Invoke-RestMethod <BASE_URL>/ready

$headers = @{ "X-API-Key" = "<API_KEY>" }
Invoke-RestMethod `
  -Uri <BASE_URL>/v2/rule-packs/cms-wiser-skin-l35041-tx-dfu-v0.1 `
  -Headers $headers
```

Expected:

- `/health` returns `{"status":"ok"}`
- `/ready` returns both rule-pack IDs
- the protected rule-pack request returns HTTP 200 with the API key
- the same protected request returns HTTP 401 without the API key

Run the full smoke suite locally against the deployed URL:

```powershell
cd backend
.\smoke.ps1 -BaseUrl <BASE_URL> -ApiKey <API_KEY>
```

## 4. Share With Reviewers

Send reviewers:

- the root deployment URL
- the pilot API key through a separate private channel
- `REVIEWER_GUIDE.md`

Ask reviewers to use `POST /v2/readiness/evaluate`. The `/v1` endpoints are the
legacy prototype and should not be used for rule validation.

## Operations

- Render free services can spin down while idle, so the first request may be
  slower.
- Rotate `WISER_API_KEY` immediately if it is shared accidentally.
- Review platform logs, but never ask reviewers to submit PHI.
- Redeploy only after tests pass.
- Preserve evaluation IDs and request fingerprints when discussing a result.

## Deployment Exit Gate

The deployment is ready to share only when:

- `/ready` returns 200
- the smoke suite passes
- the API key is enabled
- the reviewer guide is shared
- reviewers agree to use de-identified data only

## References

- Render Docker services: https://render.com/docs/docker
- Render Blueprints: https://render.com/docs/infrastructure-as-code
- Render Blueprint specification: https://render.com/docs/blueprint-spec
