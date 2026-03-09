"""
config.py — All constants, thresholds, and scoring weights for TargetIQ.

Centralised here so Aparna can tune the rules engine without touching logic files.
"""

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

SCIENCE_WEIGHTS = {
    "genetic_evidence":  0.30,
    "literature_support": 0.20,
    "prior_clinical":    0.25,
    "tractability":      0.15,
    "safety_profile":    0.10,
}

REGULATORY_WEIGHTS = {
    "pathway_complexity":    0.25,
    "special_designations":  0.20,
    "competitive_landscape": 0.20,
    "precedent_strength":    0.20,
    "ip_freedom":            0.15,
}

# Weight of science vs regulatory in final combined score
SCIENCE_WEIGHT  = 0.50
REGULATORY_WEIGHT = 0.50

# Recommendation thresholds (combined score 0-100)
# CAUTION band was 40-64 — too wide. A score of 40 and 64 have very different outlooks.
# Tightened: GO ≥ 65 (unchanged), CAUTION ≥ 45, NO-GO < 45.
# With Phase III failure penalties now reaching -30+ pts, this ensures class-failed
# targets cannot stay in low-CAUTION when their combined score is correctly suppressed.
THRESHOLD_GO      = 65
THRESHOLD_CAUTION = 45
# Below THRESHOLD_CAUTION → NO-GO


# ---------------------------------------------------------------------------
# Cross-reference engine thresholds
# ---------------------------------------------------------------------------

# Tissue expression level (0-1) above which we flag safety risk
EXPRESSION_SAFETY_THRESHOLD = 0.6

# Organs to monitor for toxicity
SAFETY_ORGANS = ["liver", "heart", "kidney", "brain", "lung"]

# Genetic score above this + failed trials = high-severity contradiction flag
GENETIC_CONTRADICTION_THRESHOLD = 0.7

# Minimum failed trials to trigger contradiction check
MIN_FAILED_TRIALS_FOR_FLAG = 1


# ---------------------------------------------------------------------------
# Regulatory rules engine constants
# ---------------------------------------------------------------------------

# Orphan Drug Act threshold (US prevalence)
ORPHAN_DISEASE_PREVALENCE_THRESHOLD = 200_000

# Pathway complexity scores (lower = easier/faster)
PATHWAY_COMPLEXITY = {
    "505(b)(2)": 0.8,   # highest score = least complex
    "505(b)(1)": 0.5,
    "BLA":       0.3,
    "NDA":       0.5,
    "unknown":   0.2,
}

# Special designation bonus scores (additive)
DESIGNATION_SCORES = {
    "orphan_drug":           0.25,
    "fast_track":            0.20,
    "breakthrough_therapy":  0.30,
    "accelerated_approval":  0.25,
    "priority_review":       0.20,
    "RMAT":                  0.30,
}

# Timeline estimates by pathway (years)
PATHWAY_TIMELINES = {
    "505(b)(2)": "3-5 years",
    "505(b)(1)": "8-12 years",
    "BLA":       "10-15 years",
    "NDA":       "8-12 years",
}

# Cost estimates by pathway
PATHWAY_COSTS = {
    "505(b)(2)": "$100M-400M",
    "505(b)(1)": "$800M-2B",
    "BLA":       "$1B-3B",
    "NDA":       "$800M-2B",
}


# ---------------------------------------------------------------------------
# API settings
# ---------------------------------------------------------------------------

# Timeout per worker in seconds (Modal will enforce this)
WORKER_TIMEOUT_SECONDS = 30

# PubMed: max papers to fetch
PUBMED_MAX_RESULTS = 20

# ClinicalTrials: max studies to fetch per query
CLINICALTRIALS_MAX_RESULTS = 100

# Open Targets: max known drugs to return
OPENTARGETS_MAX_DRUGS = 20


# ---------------------------------------------------------------------------
# LLM settings
# ---------------------------------------------------------------------------

LLM_MODEL_PRIMARY = "claude-sonnet-4-20250514"
LLM_MODEL_FALLBACK = "gpt-4o"
LLM_MAX_TOKENS = 2000
