"""
app.py — TargetIQ FastAPI Server

Run:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY='sk-ant-...'
    uvicorn app:app --reload --port 8000

Endpoints:
    GET  /health    — liveness check
    GET  /mock      — mock response for frontend dev (no pipeline call)
    POST /evaluate  — full pipeline: {"target": "KRAS G12C", "disease": "NSCLC"}
"""

import asyncio
import json
import pathlib
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import (
    OpenTargetsResult, ClinicalTrialsResult, PubMedResult,
    UniProtResult, FDADrugsResult, OrangeBookResult, TargetIQResponse,
)

# Flat imports — all files live in the same directory
from open_targets import fetch_open_targets
from clinical_trials import fetch_clinical_trials, supplement_with_drug_names
from pubmed import fetch_pubmed
from uniprot import fetch_uniprot
from fda_drugs import fetch_fda_drugs
from orange_book import fetch_orange_book
from regulatory import determine_regulatory_pathway
from cross_reference import cross_reference
from scoring import compute_scores_full
from cost_model import estimate_development_cost
from llm_synthesis import synthesize_with_llm

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TargetIQ API",
    description="AI-powered drug target evaluation platform",
    version="0.1.0",
)

# Allow all origins — needed for frontend to call this from any host
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool: 6 workers fire simultaneously
_executor = ThreadPoolExecutor(max_workers=6)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    target: str
    disease: str


class HealthResponse(BaseModel):
    status: str
    version: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run_in_thread(fn, *args):
    """Run a blocking function in the thread pool without blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, fn, *args)


async def _run_all_workers(target: str, disease: str):
    """Fire all 6 workers concurrently. Total wall time = slowest single worker."""
    results = await asyncio.gather(
        _run_in_thread(fetch_open_targets,    target, disease),
        _run_in_thread(fetch_clinical_trials, target, disease),
        _run_in_thread(fetch_pubmed,          target, disease),
        _run_in_thread(fetch_uniprot,         target, disease),
        _run_in_thread(fetch_fda_drugs,       target, disease),
        _run_in_thread(fetch_orange_book,     target, disease),
        return_exceptions=True,
    )

    def _safe(result, model_class):
        if isinstance(result, Exception):
            from models import WorkerMeta, WorkerStatus
            return model_class(
                meta=WorkerMeta(status=WorkerStatus.FAILED, error=str(result))
            )
        return result

    ot  = _safe(results[0], OpenTargetsResult)
    ct  = _safe(results[1], ClinicalTrialsResult)
    pm  = _safe(results[2], PubMedResult)
    up  = _safe(results[3], UniProtResult)
    fda = _safe(results[4], FDADrugsResult)
    ob  = _safe(results[5], OrangeBookResult)

    return ot, ct, pm, up, fda, ob


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

async def orchestrate(target: str, disease: str) -> dict:
    """Full TargetIQ pipeline."""

    # STEP 1: All 6 workers in parallel
    ot, ct, pm, up, fda, ob = await _run_all_workers(target, disease)

    # STEP 1b: Supplement ClinicalTrials with drug-name searches from Open Targets.
    # Gene-name searches miss trials filed under drug trade names (e.g. BACE1 → verubecestat).
    if ot.known_drugs:
        drug_names = [d.drug_name for d in ot.known_drugs]
        ct = await _run_in_thread(supplement_with_drug_names, ct, drug_names, disease)

    # STEP 2: Regulatory rules engine
    reg = determine_regulatory_pathway(
        target_data=ot,
        disease=disease,
        trials=ct,
        fda_data=fda,
        orange_book=ob,
    )

    # STEP 3: Cross-reference engine
    flags = cross_reference(ot, ct, pm, up, fda, ob)

    # STEP 4: Scoring
    scores = compute_scores_full(ot, ct, pm, up, fda, ob, reg, flags)

    # STEP 4b: Development cost & timeline estimate (Monte Carlo triangular, ~15ms)
    cost_estimate = None
    try:
        cost_estimate = estimate_development_cost(reg, ct, flags)
    except Exception:
        pass  # numpy unavailable or unexpected error — degrade gracefully

    # STEP 5: Assemble response
    response = TargetIQResponse(
        target=target,
        disease=disease,
        scores=scores,
        scientific_evidence={
            "genetic": {
                "score": ot.genetic_score,
                "associations": len(ot.genetic_associations),
                "top_associations": [a.model_dump() for a in ot.genetic_associations[:5]],
            },
            "clinical_trials": {
                "active": len(ct.active_trials),
                "completed": len(ct.completed_trials),
                "failed": len(ct.failed_trials),
                "success_rate": ct.success_rate,
                "phases": ct.phases,
            },
            "literature": {
                "total_papers": pm.total_papers,
                "relevance_score": pm.relevance_score,
                "key_papers": [p.model_dump() for p in pm.papers[:5]],
            },
            "expression": {
                "primary_tissues": [t.model_dump() for t in up.tissue_expression[:10]],
                "function_summary": up.function_summary,
                "subcellular_location": up.subcellular_location,
            },
            "tractability": {
                "score": ot.tractability_score,
                "molecule_type": ot.molecule_type,
                "known_drugs_in_pipeline": len(ot.known_drugs),
            },
        },
        regulatory_assessment=reg,
        flags=flags,
        cost_estimate=cost_estimate,
        data_sources={
            "open_targets":   {"status": ot.meta.status.value,  "query_time_ms": ot.meta.query_time_ms},
            "clinicaltrials": {"status": ct.meta.status.value,  "query_time_ms": ct.meta.query_time_ms},
            "pubmed":         {"status": pm.meta.status.value,  "query_time_ms": pm.meta.query_time_ms},
            "uniprot":        {"status": up.meta.status.value,  "query_time_ms": up.meta.query_time_ms},
            "fda_drugs":      {"status": fda.meta.status.value, "query_time_ms": fda.meta.query_time_ms},
            "orange_book":    {"status": ob.meta.status.value,  "query_time_ms": ob.meta.query_time_ms},
        }
    )

    # STEP 6: LLM synthesis
    try:
        response.llm_synthesis = await _run_in_thread(synthesize_with_llm, response)
    except Exception as e:
        response.llm_synthesis = f"LLM synthesis failed: {str(e)}"

    return response.model_dump()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/mock")
async def mock_response():
    """Returns mock JSON for frontend dev — no pipeline call."""
    mock_path = pathlib.Path(__file__).parent / "mock_response.json"
    if mock_path.exists():
        return json.loads(mock_path.read_text())
    raise HTTPException(status_code=404, detail="mock_response.json not found")


@app.post("/evaluate")
async def evaluate(req: EvaluateRequest):
    """
    Full pipeline evaluation.

    Example:
        POST /evaluate
        {"target": "KRAS G12C", "disease": "non-small cell lung cancer"}
    """
    if not req.target.strip() or not req.disease.strip():
        raise HTTPException(status_code=400, detail="target and disease are required")

    try:
        result = await orchestrate(req.target, req.disease)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))