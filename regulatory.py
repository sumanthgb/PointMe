"""
engine/regulatory.py — Deterministic Regulatory Rules Engine

This is NOT an LLM call. Every rule is explicit Python logic.
Every rule that fires is logged in result.reasoning for the audit trail.

Aparna: add your rules here. The skeleton handles:
  - Orphan drug designation
  - 505(b)(2) pathway (existing MOA precedent)
  - BLA pathway (biologics)
  - Fast track eligibility
  - Breakthrough therapy eligibility
  - Accelerated approval eligibility
  - Priority review eligibility
"""

from models import (
    RegulatoryPathwayResult, SpecialDesignation,
    OpenTargetsResult, ClinicalTrialsResult, FDADrugsResult, OrangeBookResult
)
from config import (
    ORPHAN_DISEASE_PREVALENCE_THRESHOLD,
    PATHWAY_TIMELINES, PATHWAY_COSTS
)


# ---------------------------------------------------------------------------
# Disease metadata helper
# ---------------------------------------------------------------------------
# In production, wire this to a disease prevalence database (e.g. OMIM, Orphanet).
# For the hackathon, this is a stub that Aparna should populate.

KNOWN_PREVALENCES: dict[str, int] = {
    "non-small cell lung cancer": 234_000,
    "nsclc": 234_000,
    "pancreatic cancer": 64_000,
    "glioblastoma": 13_000,
    "acute myeloid leukemia": 21_000,
    "chronic myeloid leukemia": 9_000,
    "cystic fibrosis": 35_000,
    "duchenne muscular dystrophy": 15_000,
    # Add more as needed
}

def get_disease_prevalence(disease: str) -> int | None:
    """Look up US prevalence for a disease name. Returns None if unknown."""
    return KNOWN_PREVALENCES.get(disease.lower().strip())


# ---------------------------------------------------------------------------
# Rule helpers
# ---------------------------------------------------------------------------

def _is_serious_condition(disease: str, trials: ClinicalTrialsResult) -> bool:
    """
    Heuristic for 'serious or life-threatening condition' (FDA criterion).
    Checks disease name keywords + clinical trial context.
    """
    serious_keywords = [
        "cancer", "carcinoma", "leukemia", "lymphoma", "sarcoma",
        "tumor", "glioblastoma", "melanoma", "myeloma",
        "alzheimer", "parkinson", "als", "hiv", "aids",
        "heart failure", "sepsis", "stroke", "fibrosis",
    ]
    disease_lower = disease.lower()
    return any(kw in disease_lower for kw in serious_keywords)


def _has_unmet_need(trials: ClinicalTrialsResult, fda: FDADrugsResult) -> bool:
    """
    Proxy for 'unmet medical need':
    - No or few approved drugs for this target
    - High trial failure rate suggests current options are inadequate
    """
    few_approvals = len(fda.approved_drugs) <= 2
    high_failure = trials.success_rate < 0.5 and len(trials.failed_trials) > 0
    return few_approvals or high_failure


def _has_preliminary_evidence(trials: ClinicalTrialsResult, ot: OpenTargetsResult) -> bool:
    """
    Proxy for 'preliminary clinical evidence of substantial improvement'.
    Used for Breakthrough Therapy designation check.
    """
    strong_genetics = ot.genetic_score > 0.7
    early_phase_success = any(
        t.status == "COMPLETED" for t in trials.completed_trials
    )
    return strong_genetics and early_phase_success


# ---------------------------------------------------------------------------
# Main rules engine
# ---------------------------------------------------------------------------

def determine_regulatory_pathway(
    target_data: OpenTargetsResult,
    disease: str,
    trials: ClinicalTrialsResult,
    fda_data: FDADrugsResult,
    orange_book: OrangeBookResult,
) -> RegulatoryPathwayResult:
    """
    Deterministic rules engine. Evaluates all rules in order.
    Every rule that fires appends to result.reasoning.

    Args:
        target_data:  Open Targets result (molecule type, tractability, etc.)
        disease:      Disease name string
        trials:       ClinicalTrials.gov result
        fda_data:     Drugs@FDA result
        orange_book:  FDA Orange Book result

    Returns:
        RegulatoryPathwayResult with pathway, designations, timeline, and reasoning.
    """
    result = RegulatoryPathwayResult()
    is_serious = _is_serious_condition(disease, trials)
    has_unmet  = _has_unmet_need(trials, fda_data)

    # -----------------------------------------------------------------------
    # RULE 1: Biologic → BLA pathway
    # -----------------------------------------------------------------------
    if target_data.molecule_type == "biologic":
        result.recommended_pathway = "BLA"
        result.reasoning.append(
            "Target molecule type is classified as biologic → BLA (Biologics License Application) pathway applies."
        )

    # -----------------------------------------------------------------------
    # RULE 2: Existing approved drug with same MOA → 505(b)(2) eligible
    # -----------------------------------------------------------------------
    elif fda_data.approved_drugs_same_moa:
        result.recommended_pathway = "505(b)(2)"
        drug_names = [d.name for d in fda_data.approved_drugs_same_moa[:3]]
        result.reasoning.append(
            f"Approved drugs with same/similar MOA exist ({', '.join(drug_names)}) "
            "→ 505(b)(2) pathway may allow reliance on existing safety data."
        )

    # -----------------------------------------------------------------------
    # RULE 3: No precedent + small molecule → standard 505(b)(1) NDA
    # -----------------------------------------------------------------------
    else:
        result.recommended_pathway = "505(b)(1)"
        result.reasoning.append(
            "No approved drugs with same MOA found and molecule is a small molecule "
            "→ standard 505(b)(1) NDA pathway."
        )

    # -----------------------------------------------------------------------
    # RULE 4: Orphan Drug Designation
    # -----------------------------------------------------------------------
    prevalence = get_disease_prevalence(disease)
    if prevalence is not None and prevalence < ORPHAN_DISEASE_PREVALENCE_THRESHOLD:
        result.special_designations.append(SpecialDesignation.ORPHAN_DRUG)
        result.reasoning.append(
            f"Disease US prevalence ({prevalence:,}) is below 200,000 threshold "
            "→ eligible for Orphan Drug designation (7-year market exclusivity, tax credits)."
        )
    elif prevalence is None:
        result.reasoning.append(
            f"Disease prevalence unknown — manual orphan drug eligibility check recommended."
        )

    # -----------------------------------------------------------------------
    # RULE 5: Fast Track Designation
    # Criteria: serious condition + unmet medical need
    # -----------------------------------------------------------------------
    if is_serious and has_unmet:
        result.special_designations.append(SpecialDesignation.FAST_TRACK)
        result.reasoning.append(
            "Disease is serious/life-threatening AND unmet medical need is indicated "
            "→ eligible for Fast Track designation (rolling review, more FDA interactions)."
        )

    # -----------------------------------------------------------------------
    # RULE 6: Breakthrough Therapy Designation
    # Criteria: serious condition + preliminary evidence of substantial improvement
    # -----------------------------------------------------------------------
    if is_serious and _has_preliminary_evidence(trials, target_data):
        result.special_designations.append(SpecialDesignation.BREAKTHROUGH)
        result.reasoning.append(
            "Serious condition + strong genetic evidence + prior Phase completion "
            "→ may be eligible for Breakthrough Therapy designation (intensive FDA guidance)."
        )

    # -----------------------------------------------------------------------
    # RULE 7: Accelerated Approval
    # Criteria: serious condition + unmet need + surrogate endpoint available
    # We proxy surrogate endpoint availability from trial design (phase 2 completed)
    # -----------------------------------------------------------------------
    has_phase2 = any(t.status == "COMPLETED" and "PHASE2" in (t.phase or "").upper()
                     for t in trials.completed_trials)
    if is_serious and has_unmet and has_phase2:
        result.special_designations.append(SpecialDesignation.ACCELERATED)
        result.reasoning.append(
            "Serious condition + unmet need + completed Phase 2 trials "
            "→ potential Accelerated Approval pathway on surrogate endpoint."
        )

    # -----------------------------------------------------------------------
    # RULE 8: Priority Review
    # Criteria: significant improvement over available therapy OR first treatment
    # -----------------------------------------------------------------------
    no_current_treatment = len(fda_data.approved_drugs) == 0
    if no_current_treatment and is_serious:
        result.special_designations.append(SpecialDesignation.PRIORITY_REVIEW)
        result.reasoning.append(
            "No approved treatments found for this target/disease + serious condition "
            "→ eligible for Priority Review (6-month vs standard 12-month review clock)."
        )

    # -----------------------------------------------------------------------
    # Attach timeline and cost based on final pathway
    # -----------------------------------------------------------------------
    pathway = result.recommended_pathway or "unknown"
    result.estimated_timeline_years = PATHWAY_TIMELINES.get(pathway, "Unknown")
    result.estimated_cost_range = PATHWAY_COSTS.get(pathway, "Unknown")

    # Add designation bonuses to reasoning
    if result.special_designations:
        desig_names = [d.value for d in result.special_designations]
        result.reasoning.append(
            f"Special designations ({', '.join(desig_names)}) may reduce timeline and cost estimates above."
        )

    return result
