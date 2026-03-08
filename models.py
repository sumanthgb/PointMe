"""
models.py — Pydantic data models for TargetIQ pipeline.

Every worker returns one of these typed objects.
Every engine consumes and produces typed objects.
This is the contract between all components.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

class WorkerStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"   # got some data but not all fields
    FAILED  = "failed"    # total failure, use defaults


class WorkerMeta(BaseModel):
    status: WorkerStatus
    query_time_ms: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Worker 1 — Open Targets
# ---------------------------------------------------------------------------

class GeneticAssociation(BaseModel):
    study_id: str
    trait: str
    score: float
    source: str   # e.g. "GWAS", "rare_variant"

class KnownDrug(BaseModel):
    drug_name: str
    phase: float  # API can return fractional phases (e.g. 0.5 for Phase 1/2)
    status: str   # e.g. "Approved", "Phase 3", "Withdrawn"
    mechanism: str

class OpenTargetsResult(BaseModel):
    genetic_score: float = 0.0          # 0-1, aggregated association score
    genetic_associations: list[GeneticAssociation] = []
    known_drugs: list[KnownDrug] = []
    pathways: list[str] = []
    tractability_score: float = 0.0     # 0-1, how druggable is this target
    molecule_type: str = "small_molecule"  # "small_molecule" | "biologic" | "unknown"
    meta: WorkerMeta = WorkerMeta(status=WorkerStatus.FAILED)


# ---------------------------------------------------------------------------
# Worker 2 — ClinicalTrials.gov
# ---------------------------------------------------------------------------

class Trial(BaseModel):
    nct_id: str
    title: str
    phase: Optional[str] = None
    status: str
    why_stopped: Optional[str] = None   # GOLD — failure reasons
    enrollment: Optional[int] = None
    start_date: Optional[str] = None
    primary_outcome: Optional[str] = None

class ClinicalTrialsResult(BaseModel):
    active_trials: list[Trial] = []
    completed_trials: list[Trial] = []
    failed_trials: list[Trial] = []     # status: Terminated / Withdrawn
    phases: dict[str, int] = {}         # {"Phase 1": 3, "Phase 2": 5, ...}
    success_rate: float = 0.0           # completed / (completed + failed)
    meta: WorkerMeta = WorkerMeta(status=WorkerStatus.FAILED)


# ---------------------------------------------------------------------------
# Worker 3 — PubMed
# ---------------------------------------------------------------------------

class Paper(BaseModel):
    pmid: str
    title: str
    abstract: str
    year: int
    journal: Optional[str] = None
    citation_count: int = 0             # NOTE: PubMed doesn't provide this natively
                                        # We'll use Europe PMC or estimate from year

class PubMedResult(BaseModel):
    total_papers: int = 0
    papers: list[Paper] = []
    relevance_score: float = 0.0        # computed from recency + volume
    meta: WorkerMeta = WorkerMeta(status=WorkerStatus.FAILED)


# ---------------------------------------------------------------------------
# Worker 4 — UniProt
# ---------------------------------------------------------------------------

class TissueExpression(BaseModel):
    tissue: str
    level: str          # "High" | "Medium" | "Low" | "Not detected"
    level_numeric: float  # 0.0 to 1.0 normalized

class UniProtResult(BaseModel):
    uniprot_id: Optional[str] = None
    gene_name: str = ""
    function_summary: str = ""
    subcellular_location: list[str] = []
    tissue_expression: list[TissueExpression] = []
    disease_associations: list[str] = []
    meta: WorkerMeta = WorkerMeta(status=WorkerStatus.FAILED)


# ---------------------------------------------------------------------------
# Worker 5 — Drugs@FDA
# ---------------------------------------------------------------------------

class FDADrug(BaseModel):
    name: str
    approval_date: Optional[str] = None
    application_type: str               # "NDA", "BLA", "ANDA"
    application_number: Optional[str] = None
    pathway: str                        # "Standard", "Accelerated", "Priority", "Breakthrough"
    sponsor: Optional[str] = None
    mechanism_of_action: Optional[str] = None

class FDADrugsResult(BaseModel):
    approved_drugs: list[FDADrug] = []
    rejected_drugs: list[FDADrug] = []
    approved_drugs_same_moa: list[FDADrug] = []
    meta: WorkerMeta = WorkerMeta(status=WorkerStatus.FAILED)


# ---------------------------------------------------------------------------
# Worker 6 — FDA Orange Book
# ---------------------------------------------------------------------------

class ComparableDrug(BaseModel):
    name: str
    exclusivity_type: Optional[str] = None   # e.g. "NCE", "ODE", "PED"
    exclusivity_expiration: Optional[str] = None
    patent_number: Optional[str] = None
    patent_expiration: Optional[str] = None

class OrangeBookResult(BaseModel):
    comparable_drugs: list[ComparableDrug] = []
    ip_crowding_score: float = 0.0      # 0-1, higher = more crowded IP landscape
    meta: WorkerMeta = WorkerMeta(status=WorkerStatus.FAILED)


# ---------------------------------------------------------------------------
# Engine outputs
# ---------------------------------------------------------------------------

class SpecialDesignation(str, Enum):
    ORPHAN_DRUG       = "orphan_drug"
    FAST_TRACK        = "fast_track"
    BREAKTHROUGH      = "breakthrough_therapy"
    ACCELERATED       = "accelerated_approval"
    PRIORITY_REVIEW   = "priority_review"
    RMAT              = "RMAT"

class RegulatoryPathwayResult(BaseModel):
    recommended_pathway: Optional[str] = None   # "505(b)(1)", "505(b)(2)", "BLA", etc.
    special_designations: list[SpecialDesignation] = []
    estimated_timeline_years: Optional[str] = None
    estimated_cost_range: Optional[str] = None
    reasoning: list[str] = []                   # every rule that fired — audit trail


class FlagSeverity(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"

class FlagType(str, Enum):
    CONTRADICTION    = "contradiction"
    SAFETY_FLAG      = "safety_flag"
    CORROBORATED_RISK = "corroborated_risk"
    IP_RISK          = "ip_risk"
    DATA_GAP         = "data_gap"

class CrossReferenceFlag(BaseModel):
    type: FlagType
    severity: FlagSeverity
    message: str
    details: Optional[dict] = None


class Scores(BaseModel):
    science_score: float       # 0-100
    regulatory_score: float    # 0-100
    combined_score: float      # 0-100
    recommendation: str        # "GO" | "CAUTION" | "NO-GO"


# ---------------------------------------------------------------------------
# Final API response
# ---------------------------------------------------------------------------

class TargetIQResponse(BaseModel):
    target: str
    disease: str
    scores: Scores
    scientific_evidence: dict           # raw worker outputs, structured for frontend
    regulatory_assessment: RegulatoryPathwayResult
    flags: list[CrossReferenceFlag] = []
    llm_synthesis: Optional[str] = None
    data_sources: dict = {}             # per-worker query_time_ms and status
