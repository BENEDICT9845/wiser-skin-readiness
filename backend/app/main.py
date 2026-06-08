import logging
import os
import secrets
import time
from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from .evaluator import evaluate_case, get_rule_pack
from .evaluator_v2 import evaluate_case_v2
from .rule_packs.models import load_v2_rule_pack
from .schemas import (
    BatchEvaluationRequest,
    BatchEvaluationResponse,
    CaseEvaluationRequest,
    CaseEvaluationResponse,
)


app = FastAPI(
    title="WISeR Skin Readiness API",
    version="0.3.0",
    description=(
        "Explainable, provider-side decision support for WISeR skin-substitute "
        "readiness screening. Use de-identified data only. This API does not "
        "determine Medicare coverage or replace qualified review."
    ),
)


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    configured_key = os.getenv("WISER_API_KEY")
    if configured_key and (
        x_api_key is None or not secrets.compare_digest(x_api_key, configured_key)
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.middleware("http")
async def request_audit_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logging.getLogger("wiser.audit").info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id, request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    details = [
        {"location": err["loc"], "message": err["msg"], "type": err["type"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR",
                            "message": "Request validation failed",
                            "details": details}},
    )


@app.get("/", include_in_schema=False)
def pilot_entrypoint() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    packs = [
        "cms-wiser-skin-l36690-v0.1",
        "cms-wiser-skin-l35041-tx-dfu-v0.1",
    ]
    loaded = []
    failures = []
    for pid in packs:
        try:
            load_v2_rule_pack(pid)
            loaded.append(pid)
        except Exception as exc:
            failures.append({"rule_pack_id": pid, "error": type(exc).__name__})
    if failures:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "RULE_PACK_READINESS_FAILED",
                "loaded_rule_packs": loaded,
                "failures": failures,
            },
        )
    return {"status": "ready", "rule_packs": loaded}


# v1 endpoints (prototype)
@app.get("/v1/rule-packs/current", dependencies=[Depends(require_api_key)])
def current_rule_pack() -> dict:
    return get_rule_pack()


@app.get("/v1/rule-packs/{rule_pack_id}", dependencies=[Depends(require_api_key)])
def rule_pack(rule_pack_id: str) -> dict:
    try:
        return get_rule_pack(rule_pack_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Rule pack not found")


@app.post("/v1/readiness/evaluate", response_model=CaseEvaluationResponse,
          dependencies=[Depends(require_api_key)])
def evaluate(request: CaseEvaluationRequest) -> CaseEvaluationResponse:
    return evaluate_case(request)


@app.post("/v1/readiness/evaluate-batch", response_model=BatchEvaluationResponse,
          dependencies=[Depends(require_api_key)])
def evaluate_batch(request: BatchEvaluationRequest) -> BatchEvaluationResponse:
    results = [evaluate_case(c) for c in request.cases]
    return BatchEvaluationResponse(count=len(results), results=results)


# v2 endpoints (source-linked)
@app.get("/v2/rule-packs/{rule_pack_id}", dependencies=[Depends(require_api_key)])
def rule_pack_v2(rule_pack_id: str) -> dict:
    try:
        return load_v2_rule_pack(rule_pack_id).model_dump(mode="json")
    except KeyError:
        raise HTTPException(status_code=404, detail="Rule pack not found")


@app.post("/v2/readiness/evaluate", response_model=CaseEvaluationResponse,
          dependencies=[Depends(require_api_key)])
def evaluate_v2(request: CaseEvaluationRequest) -> CaseEvaluationResponse:
    return evaluate_case_v2(request)


@app.post("/v2/readiness/evaluate-batch", response_model=BatchEvaluationResponse,
          dependencies=[Depends(require_api_key)])
def evaluate_batch_v2(request: BatchEvaluationRequest) -> BatchEvaluationResponse:
    results = [evaluate_case_v2(c) for c in request.cases]
    return BatchEvaluationResponse(count=len(results), results=results)
